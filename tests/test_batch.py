from datetime import date
from io import BytesIO
from pathlib import Path
from docx import Document
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest
from travel.batch import calculate_batch
from travel.batch_documents import export_batch_excel, export_batch_word
from travel.models import Trip
from travel.storage import Store
from test_calculation import trip


def test_batch_keeps_per_trip_advances_snapshots_and_roundtrips(tmp_path):
    first, second = trip(2), trip(2,start='2026-10-20')
    first.meta.update({'출장명':'서울 협의','기지급액':'150000'})
    second.meta['출장명'] = '부산 협의'
    batch = calculate_batch([first,second])
    assert batch.estimated == 200000
    assert batch.total('claim') == 100000  # 두 출장의 기지급액을 서로 상계하지 않는다.
    assert batch.total('refund') == 50000
    store = Store(tmp_path/'batch.db')
    store.save_batch(batch)
    restored = store.load_batch(batch.id)
    assert len(restored.results) == 2
    assert restored.to_dict() == batch.to_dict()
    assert len(store.list()) == 2 and len(store.list_batches()) == 1
    rebuilt = calculate_batch([Trip.from_dict(r.trip) for r in restored.results],
                              {r.trip['id']:r.rule_snapshot for r in restored.results})
    assert rebuilt.total('claim') == 100000
    book = load_workbook(BytesIO(export_batch_excel(batch)),data_only=True)
    assert book.worksheets[0]['E7'].value == 200000
    assert book.worksheets[0]['F7'].value == 100000
    assert book.worksheets[0]['H7'].value == 50000
    assert book.worksheets[0]['C5'].value.date() == date(2026,10,10)
    doc = Document(BytesIO(export_batch_word(batch)))
    text = '\n'.join(p.text for p in doc.paragraphs)+'\n'+'\n'.join(c.text for t in doc.tables for row in t.rows for c in row.cells)
    assert '200,000원' in text and '서울 협의' in text and '부산 협의' in text
    assert any('서울 협의' in p.text for p in doc.paragraphs)
    assert any('부산 협의' in p.text for p in doc.paragraphs)


def test_adding_and_switching_trips_keeps_amounts_and_detail_edits():
    app = AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=30).run()
    first = app.session_state.trip.id
    app.session_state[first+'_간편교통비'] = {'value':'1234123'}
    app.run()
    next(b for b in app.button if b.label=='출장 추가').click().run()
    assert not app.exception
    second = app.session_state.trip.id
    assert first != second and len(app.session_state.batch_trips) == 2
    app.session_state[second+'_간편교통비'] = {'value':'20000'}
    app.run()
    assert app.session_state.current_batch.estimated == 1354123
    next(s for s in app.selectbox if s.label=='입력할 출장').select(first).run()
    assert not app.exception
    assert app.session_state.trip.meta['간편교통비'] == '1234123'
    next(t for t in app.toggle if t.label=='날짜별로 다르게 입력').set_value(True).run()
    app.session_state[first+'_days_editor'] = {'edited_rows':{0:{'출장시간(h)':7.5}},'added_rows':[],'deleted_rows':[]}
    app.run()
    next(s for s in app.selectbox if s.label=='입력할 출장').select(second).run()
    next(s for s in app.selectbox if s.label=='입력할 출장').select(first).run()
    assert not app.exception
    assert app.session_state.trip.days[0]['출장시간(h)'] == '7.5'
    next(b for b in app.button if b.label=='출장 삭제').click().run()
    assert not app.exception
    assert len(app.session_state.current_batch.results) == 1
    assert any(b.label=='일괄 저장' for b in app.button)
