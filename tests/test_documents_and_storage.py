from io import BytesIO
from zipfile import ZipFile
from decimal import Decimal
from openpyxl import load_workbook
from docx import Document
from travel.engine import calculate
from travel.excel import export_excel
from travel.word import export_word
from travel.models import dumps,Result
from travel.storage import Store
from test_calculation import trip

def test_documents_use_same_result_and_preserve_every_raw_value():
    t=trip(2)
    t.meta['비고']='입력 원문 보존 확인'
    t.lodgings=[{'숙박일':'2026-10-10','지역구분':'서울','실제지출액':'85000','증빙확인':True}]
    r=calculate(t)
    book=load_workbook(BytesIO(export_excel(r)),data_only=True)
    doc=Document(BytesIO(export_word(r)))
    assert len(book.sheetnames)==9
    assert book.worksheets[0]['D10'].value==185000
    assert book.worksheets[0]['D12'].value==185000
    all_word='\n'.join(p.text for p in doc.paragraphs)+'\n'+'\n'.join(c.text for ta in doc.tables for row in ta.rows for c in row.cells)
    assert '185,000원' in all_word
    assert '입력 원문 보존 확인' in all_word
    assert any('입력 원문 보존 확인'==row[1] for row in book.worksheets[1].iter_rows(values_only=True) if len(row)>1)
    assert len(doc.part.rels)>5

def test_raw_text_is_not_an_excel_formula():
    t=trip();t.meta['비고']='=HYPERLINK("https://example.com")'
    book=load_workbook(BytesIO(export_excel(calculate(t))),data_only=False)
    target=[c for row in book.worksheets[1] for c in row if c.value==t.meta['비고']][0]
    assert target.data_type=='s'

def test_storage_preserves_versions_and_decimal(tmp_path):
    s=Store(tmp_path/'trips.db');t=trip();r=calculate(t)
    s.save(t,r)
    loaded,stored=s.load(t.id)
    assert stored.claim==r.claim and stored.rule_snapshot==r.rule_snapshot
    assert calculate(loaded,stored.rule_snapshot).claim==r.claim
    copy=s.copy(t.id)
    assert copy.id!=t.id
    assert len(s.list('정책'))==1
    s.delete(t.id)
    assert s.list()==[]
