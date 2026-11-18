from decimal import Decimal
from io import BytesIO
from pathlib import Path

from docx import Document
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest

from travel.batch import calculate_batch
from travel.batch_documents import export_batch_excel, export_batch_word
from travel.engine import calculate
from travel.excel import export_excel
from travel.models import Result, ZERO, dumps
from travel.quick import build_schedule, calculate_preview
from travel.shared_lodging import allocation
from travel.storage import Store
from travel.word import export_word
from test_calculation import trip


def shared_trip(total='236634'):
    t=trip(4,start='2026-10-12')
    t.meta.update({'간편입력':True,'기본도시':'거제시','간편출장범위':'근무지 외',
        '간편지역':'기타','간편숙박비':total,'간편교통수단':'철도','간편교통비':'10000',
        '공동숙박':True,'공동숙박인원':2,'공동숙박자':[{'성명':'김동행','지급등급':'제2호'}]})
    return t


def category(result, name):
    return sum((line.amount or ZERO for line in result.lines if line.category==name),ZERO)


def test_shared_room_only_adds_lodging_and_preserves_rounding_and_person_caps():
    t=shared_trip()
    build_schedule(t)
    r=calculate_preview(t)
    assert len(t.days)==4 and len(t.transports)==1 and len(t.lodgings)==6
    assert category(r,'숙박비')==236634
    assert [row['분담액'] for row in allocation(r)]==[118317,118317]
    assert [row['상한'] for row in allocation(r)]==[210000,210000]
    assert not any('숙박 중복' in issue for issue in r.issues)
    t.meta['공동숙박']=False
    build_schedule(t)
    single=calculate_preview(t)
    assert category(single,'숙박비')==210000
    for name in ('일비','식비','교통비'):
        assert category(single,name)==category(r,name)
    t.meta.update({'공동숙박':True,'간편숙박비':'236635'})
    build_schedule(t)
    odd=calculate_preview(t)
    assert [row['분담액'] for row in allocation(odd)]==[118317,118318]
    assert category(odd,'숙박비')==sum(Decimal(row['실제지출액']) for row in t.lodgings)==236635
    # 서로 다른 등급의 상한과 실제 분담은 각 사람에게만 적용한다.
    t.meta['공동숙박자'][0]['지급등급']='제1호라'
    t.meta['간편숙박비']='600000'
    build_schedule(t)
    for row in t.lodgings: row['증빙확인']=True
    mixed=calculate(t)
    assert [row['예상 인정액'] for row in allocation(mixed)]==[210000,300000]
    assert category(mixed,'숙박비')==510000
    # 상세 입력에서 본인 25만원/동행자 5만원: 동행자의 잔여 상한을 합쳐 쓰지 않는다.
    for row in t.lodgings:
        row['숙박지급등급']='제2호'
        row['실제지출액']='83333' if row['숙박정산대상ID']=='self' else '16666'
    assert category(calculate(t),'숙박비')==259998


def test_shared_allocation_survives_save_and_all_four_document_exports(tmp_path):
    t=shared_trip()
    build_schedule(t)
    for row in [*t.lodgings,*t.transports]: row['증빙확인']=True
    t.meta['_상세입력']=True
    result=calculate(t)
    assert result.claim==446634  # 본인 일비·식비 20만원, 교통 1만원, 2명 숙박 236,634원
    assert Result.from_dict(result.to_dict()).to_dict()==result.to_dict()
    batch=calculate_batch([t,trip(1,start='2026-10-20')])
    store=Store(tmp_path/'shared.db')
    store.save_batch(batch)
    restored=store.load_batch(batch.id)
    assert restored.to_dict()==batch.to_dict()
    assert allocation(restored.results[0])==allocation(result)
    for blob,name in [(export_excel(result),'10_공동숙박_분담'),
                      (export_batch_excel(batch),'05_공동숙박_분담')]:
        ws=load_workbook(BytesIO(blob),data_only=True)[name]
        assert ws['E5'].value==118317 and ws['E6'].value==118317
        assert ws['G5'].value+ws['G6'].value==236634
        assert '김동행' in ws['B6'].value and '숙박비만' in ws['A2'].value
    for blob in (export_word(result),export_batch_word(batch)):
        doc=Document(BytesIO(blob))
        text='\n'.join(p.text for p in doc.paragraphs)+'\n'+'\n'.join(c.text for table in doc.tables for row in table.rows for c in row.cells)
        assert '공동숙박 분담 내역' in text and '숙박비만' in text
        assert '236,634원' in text and '118,317원' in text and '김동행' in text
    assert '숙박정산대상ID' in dumps(result.to_dict())


def test_shared_toggle_and_detailed_input_keep_same_lodging_people():
    t=shared_trip()
    app=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=30)
    app.session_state['trip']=t
    app.run()
    assert not app.exception
    assert category(app.session_state.current_result,'숙박비')==236634
    shared=next(w for w in app.toggle if w.label=='공동 출장자 숙박비 함께 정산')
    shared.set_value(False).run()
    assert not app.exception
    assert category(app.session_state.current_result,'숙박비')==210000
    next(w for w in app.toggle if w.label=='공동 출장자 숙박비 함께 정산').set_value(True).run()
    next(w for w in app.toggle if w.label=='날짜별로 다르게 입력').set_value(True).run()
    assert not app.exception
    assert len(app.session_state.trip.lodgings)==6
    assert category(app.session_state.current_result,'숙박비')==236634
    assert len(allocation(app.session_state.current_result))==2
