"""openpyxl 기반 9개 시트 행정 정산서."""
from io import BytesIO
from decimal import Decimal
from datetime import date, datetime
from math import ceil
from zipfile import ZipFile,ZIP_DEFLATED
from xml.etree import ElementTree as ET
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
from openpyxl.worksheet.page import PageMargins
from openpyxl.formatting.rule import CellIsRule
from .models import *
from .report import flatten,metadata,deadlines,status_label

NAVY='182F4D'
TEAL='087F8C'
PALE='EEF4F8'
INK='283747'
MONEY='#,##0"원";[Red](#,##0"원");0"원"'

def safe_value(cell,value):
    if value is None: cell.value='미입력'
    elif isinstance(value,Decimal): cell.value=int(value) if value==value.to_integral_value() else float(value)
    elif isinstance(value,(dict,list)): cell.value=dumps(value)
    else: cell.value=value
    if isinstance(cell.value,str): cell.data_type='s'

def sheet(wb,name,title,headers,rows,widths=None,currency_columns=()):
    ws=wb.create_sheet(name)
    n=len(headers)
    ws.sheet_view.showGridLines=False
    ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=n)
    ws.cell(1,1,title).font=Font(name='맑은 고딕',size=19,bold=True,color=NAVY)
    ws.row_dimensions[1].height=36
    ws.merge_cells(start_row=2,start_column=1,end_row=2,end_column=n)
    ws.cell(2,1,'출장비 정산 | 모든 금액은 동일한 계산 결과 기준 · 미확정 금액은 청구액에서 제외').font=Font(name='맑은 고딕',size=9,color='63758B')
    ws.row_dimensions[2].height=24
    for j,label in enumerate(headers,1):
        cell=ws.cell(4,j,label)
        cell.font=Font(name='맑은 고딕',size=10,bold=True,color='FFFFFF')
        cell.fill=PatternFill('solid',fgColor=NAVY)
        cell.alignment=Alignment(vertical='center',wrap_text=True)
    ws.row_dimensions[4].height=28
    rows=list(rows) or [['해당 없음']+['']*(n-1)]
    for i,row in enumerate(rows,5):
        max_lines=1
        for j,val in enumerate(row,1):
            cell=ws.cell(i,j)
            safe_value(cell,val)
            cell.font=Font(name='맑은 고딕',size=10,color=INK)
            cell.fill=PatternFill('solid',fgColor='F5F8FA' if i%2==0 else 'FFFFFF')
            cell.alignment=Alignment(vertical='top',wrap_text=True,horizontal='right' if isinstance(val,(int,float,Decimal)) else 'left')
            cell.border=Border(bottom=Side(style='hair',color='DCE5EC'))
            if j in currency_columns and isinstance(val,(Decimal,int,float)): cell.number_format=MONEY
            if headers[j-1] in ['환율','외화금액'] and isinstance(val,(Decimal,int,float)): cell.number_format='#,##0.0000'
            text=str(cell.value or '')
            width=(widths or [24]*n)[j-1]
            max_lines=max(max_lines,sum(max(1,ceil(len(t)*1.7/max(width,10))) for t in text.split('\n')))
            if text.startswith('https://'):
                cell.hyperlink=text.split('\n')[0]
                cell.font=Font(name='맑은 고딕',size=9,color='1660A0',underline='single')
        ws.row_dimensions[i].height=min(360,max(26,max_lines*15))
    for j,width in enumerate(widths or [24]*n,1):
        ws.column_dimensions[ws.cell(4,j).column_letter].width=width
    ws.freeze_panes='B5'
    ws.auto_filter.ref=f'A4:{ws.cell(ws.max_row,n).coordinate}'
    ws.print_title_rows='1:4'
    ws.print_area=f'A1:{ws.cell(ws.max_row,n).coordinate}'
    ws.page_setup.orientation='landscape' if n>4 else 'portrait'
    ws.page_setup.paperSize=ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth=1
    ws.page_setup.fitToHeight=0
    ws.sheet_properties.pageSetUpPr.fitToPage=True
    ws.page_margins=PageMargins(left=.25,right=.25,top=.45,bottom=.45,header=.15,footer=.15)
    ws.oddFooter.center.text='&P / &N'
    ws.oddHeader.right.text='공무 출장비 정산서'
    return ws

def export_excel(result:Result)->bytes:
    wb=Workbook(); wb.remove(wb.active)
    rows=[]
    for r in result.summary(): rows.append([r['항목'],r['기준금액'],r['실제 지출액'],r['인정금액'],r['미확정금액']])
    ws=sheet(wb,'01_출장비_요약',result.trip['kind']+' 출장비 정산서',
        ['항목','기준금액','실제 지출액','확정 인정액','미확정금액'],rows,[26,22,22,22,22],(2,3,4,5))
    total_row=ws.max_row+1
    ws.cell(total_row,1,'확정 인정액 합계')
    ws.cell(total_row,4,f'=SUM(D5:D{total_row-1})')
    ws.cell(total_row,4).number_format=MONEY
    # 최종액은 캐시 지원 여부에 관계없이 표시되는 숫자 값으로 기록한다.
    extras=[('기지급액',result.advance),(status_label(result),result.claim),('반납예정액',result.refund),
            ('출장명',result.trip['meta'].get('출장명','')),('출장자',result.trip['meta'].get('성명','')),
            ('생성일시',result.generated_at),('법령 자료 버전',result.rule_snapshot['version'])]
    for key,val in extras:
        i=ws.max_row+1
        safe_value(ws.cell(i,1),key); safe_value(ws.cell(i,4),val)
        ws.cell(i,4).number_format=MONEY if isinstance(val,Decimal) else 'General'
        ws.row_dimensions[i].height=28
        if key==status_label(result):
            for cell in ws[i]:
                cell.fill=PatternFill('solid',fgColor=TEAL)
                cell.font=Font(name='맑은 고딕',size=16,bold=True,color='FFFFFF')
            ws.row_dimensions[i].height=40
    ws.print_area=f'A1:E{ws.max_row}'
    sheet(wb,'02_출장_기본정보','모든 원본 입력', ['입력 경로','사용자 입력값'],flatten(result.trip),[46,76])
    input_table=lambda records: [(p,v) for i,r in enumerate(records,1) for p,v in flatten(r,str(i)+'번')]
    sheet(wb,'03_상세_일정','일별 일정과 업무 내역',['일정·입력항목','입력값'],input_table(result.trip['days']),[44,72])
    detail_headers=['일자','내역','기준금액','실제 지출액','인정금액','상태','통화','외화금액','환율']
    for name,title,cat in [('04_교통비_내역','교통비 상세 정산','교통비'),('05_숙박비_내역','숙박비 상세 정산','숙박비'),
                           ('06_일비_식비','날짜별 일비와 식비',None),('07_기타_경비','기타 인정 여비','기타 인정 여비')]:
        lines=[r for r in result.lines if (r.category==cat if cat else r.category in ['일비','식비'])]
        sheet(wb,name,title,detail_headers,[[r.date,r.name,r.basis,r.actual,r.amount,r.status,r.currency,r.foreign_amount,r.rate] for r in lines],
            [15,29,19,19,19,18,10,18,18],(3,4,5))
    sheet(wb,'08_계산_근거','적용 법령과 계산식',
        ['일자·항목','계산식','적용 근거','법령·규칙 버전','출처','비고'],
        [[r.date+' '+r.name,r.formula,r.reference,r.rule_version,r.source,r.notes] for r in result.lines],
        [28,56,36,36,52,68])
    review=[['계산 상태',s] for s in result.issues]
    review += [[f'정산기한 / {r["항목"]}',r['기한']+' / '+r['근거']] for r in deadlines(result)]
    review += [[p,v] for p,v in flatten(result.trip['evidence'],'증빙')]
    review += [[p,v] for p,v in flatten(result.trip['fx'],'환율')]
    sheet(wb,'09_정산_검토','증빙과 승인 및 정산기한',['구분','내용'],review,[42,88])
    wb.active=0
    buff=BytesIO();wb.save(buff)
    # 단순 합계 수식의 캐시를 함께 저장한다. 미계산 뷰어에서도 총액이 비지 않는다.
    buff.seek(0); output=BytesIO()
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with ZipFile(buff) as src,ZipFile(output,'w',ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data=src.read(item.filename)
            if item.filename=='xl/worksheets/sheet1.xml':
                root=ET.fromstring(data)
                cell=root.find(f'.//s:c[@r="D{total_row}"]',ns)
                value=cell.find('s:v',ns)
                if value is None: value=ET.SubElement(cell,'{'+ns['s']+'}v')
                value.text=str(result.recognized)
                data=ET.tostring(root,encoding='utf-8',xml_declaration=True)
            dst.writestr(item,data)
    return output.getvalue()
