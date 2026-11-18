"""전체 요약과 출장별 원본·산식을 포함한 일괄 Excel·Word 출력."""
from io import BytesIO
from datetime import date
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from .models import CATEGORIES, money
from .report import flatten, deadlines
from .excel import sheet, safe_value, MONEY, NAVY, shared_lodging_sheet, FONT
from .word import new_document, append_result, table


def export_batch_excel(batch):
    wb = Workbook()
    wb.remove(wb.active)
    headers = ['번호','출장명','출발일','복귀일','예상 출장비','확정 청구액','기지급액','반납예정액','상태']
    rows = batch.rows()
    values = [[row[h] if h not in ('출발일','복귀일') else date.fromisoformat(row[h]) for h in headers] for row in rows]
    ws = sheet(wb,'01_전체_요약','출장비 일괄 정산서',headers,values,
               [7,24,15,15,19,19,19,19,23],(5,6,7,8))
    for row in ws.iter_rows(min_row=5,max_row=4+len(rows),min_col=3,max_col=4):
        for cell in row:
            cell.number_format = 'yyyy-mm-dd'
    total_row = ws.max_row+1
    ws.cell(total_row,2,'전체 합계')
    caches = {}
    for column in range(5,9):
        cell = ws.cell(total_row,column)
        letter = cell.column_letter
        cell.value = f'=SUM({letter}5:{letter}{total_row-1})'
        cell.number_format = MONEY
        caches[cell.coordinate] = sum((row[headers[column-1]] for row in rows))
    for cell in ws[total_row]:
        cell.fill = PatternFill('solid',fgColor=NAVY)
        cell.font = Font(name=FONT,size=11,bold=True,color='FFFFFF')
    ws.row_dimensions[total_row].height = 32
    for category in CATEGORIES:
        row_number = ws.max_row+1
        ws.cell(row_number,2,category+' 합계')
        ws.merge_cells(start_row=row_number,start_column=2,end_row=row_number,end_column=4)
        ws.merge_cells(start_row=row_number,start_column=5,end_row=row_number,end_column=6)
        cell = ws.cell(row_number,5)
        safe_value(cell,batch.category(category))
        cell.number_format = MONEY
        ws.row_dimensions[row_number].height=28
        for column in (2,5):
            value=ws.cell(row_number,column)
            value.font=Font(name=FONT,size=10,color=NAVY)
            value.fill=PatternFill('solid',fgColor='F4F7FA')
            value.alignment=Alignment(vertical='center',horizontal='right' if column==5 else 'left',indent=1)
    ws.print_area = f'A1:I{ws.max_row}'
    ws.cell(2,1,'출장별 정산 결과 합계 | 기지급액은 각 출장에서 차감 · 미산출 항목은 상태 열 확인')
    detail = []
    grounds = []
    raw = []
    review = []
    for i,result in enumerate(batch.results,1):
        name = rows[i-1]['출장명']
        for line in result.lines:
            detail.append([i,name,line.date,line.category,line.name,line.actual,line.amount,line.status])
            grounds.extend([f'{i}. {name} / {line.date} / {line.name}',label,value] for label,value in
                [('계산식',line.formula),('근거',line.reference),('출처',line.source),('법령 버전',line.rule_version),('비고',line.notes)])
        raw.extend([i,name,path,value] for path,value in flatten(result.trip))
        raw.append([i,name,'적용 법령자료 버전',result.rule_snapshot['version']])
        review.extend([i,name,'미확정 사유',issue] for issue in result.issues)
        review.extend([i,name,'정산기한 / '+r['항목'],r['기한']+' / '+r['근거']] for r in deadlines(result))
    sheet(wb,'02_항목별_내역','출장별 항목과 금액',
          ['번호','출장명','일자','항목','내역','실제 지출액','인정금액','상태'],
          detail,[6,23,14,12,28,19,19,22],(6,7))
    sheet(wb,'03_원본_입력','출장별 원본 입력',
          ['번호','출장명','입력 경로','입력값'],raw,[7,24,50,85])
    sheet(wb,'04_정산_확인','출장별 정산 사유와 기한',
          ['번호','출장명','구분','내용'],review,[7,24,42,95])
    shared_lodging_sheet(wb,batch.results,'05_공동숙박_분담')
    sheet(wb,'06_계산_근거','출장별 계산식과 적용 근거',
          ['출장·일자·항목','구분','내용'],grounds,[32,18,86])
    sheet(wb,'07_출장별_비용','출장별 비용 요약',
          ['출장','일비','식비','숙박비','교통비','기타 인정 여비','예상 출장비'],
          [[f'{r["번호"]}. {r["출장명"]}',*[r[c] for c in CATEGORIES],r['예상 출장비']] for r in rows],
          [30,19,19,19,19,20,22],(2,3,4,5,6,7))
    from .official_forms import append_excel_forms
    form_sheets=[]
    for i,result in enumerate(batch.results,1):form_sheets+=append_excel_forms(wb,result,f'{i}_')
    # 일괄 출력은 총괄 뒤에 출장별 공식 신청서를 모은다.
    for index,form in enumerate(form_sheets,1):wb.move_sheet(form,offset=index-wb.index(form))
    wb.active = 0
    buffer = BytesIO()
    wb.save(buffer)
    # Excel을 실행하지 않는 뷰어에도 전체 합계가 표시되도록 수식 캐시를 기록한다.
    output = BytesIO()
    namespace = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with ZipFile(BytesIO(buffer.getvalue())) as src, ZipFile(output,'w',ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == 'xl/worksheets/sheet1.xml':
                root = ET.fromstring(data)
                for coordinate, value in caches.items():
                    cell = root.find(f'.//s:c[@r="{coordinate}"]',namespace)
                    cached = cell.find('s:v',namespace)
                    if cached is None:
                        cached = ET.SubElement(cell,'{'+namespace['s']+'}v')
                    cached.text = str(value)
                data = ET.tostring(root,encoding='utf-8',xml_declaration=True)
            dst.writestr(item,data)
    return output.getvalue()


def export_batch_word(batch):
    doc = new_document('공무 출장비 일괄 정산서')
    doc.add_paragraph('출장비 일괄 정산서','Title')
    doc.add_paragraph(f'출장 {len(batch.results)}건의 예상 출장비 합계는 {money(batch.estimated)}입니다. '
                      '전체 요약 다음에 각 출장의 일정, 항목별 산식, 정산 상태와 원본 입력을 수록했습니다.')
    doc.add_paragraph('확정 청구액 합계 '+money(batch.total('claim'))+' · 기지급액 합계 '+money(batch.total('advance')))
    doc.add_paragraph('기지급액은 출장별로 차감한 후 합산합니다. 승인·증빙 확인 전 금액은 확정 청구액에 포함하지 않습니다.')
    if batch.incomplete:
        doc.add_paragraph('금액을 산출하지 못한 항목이 있습니다. 아래 합계는 산출 가능한 항목만 포함합니다.')
    table(doc,['출장','기간','예상 출장비','확정 청구액'],
          [[f'{row["번호"]}. {row["출장명"]}',row['출발일']+' ~ '+row['복귀일'],row['예상 출장비'],row['확정 청구액']] for row in batch.rows()],
          [4.2,5.2,4.1,4.1])
    table(doc,['항목','전체 예상액'],[[category,batch.category(category)] for category in CATEGORIES]+[['합계',batch.estimated]],[8.8,8.8])
    doc.add_paragraph('생성일시 '+batch.generated_at)
    for i,result in enumerate(batch.results,1):
        doc.add_page_break()
        name = result.trip['meta'].get('출장명') or f'출장 {i}'
        from .official_forms import append_word_forms
        if append_word_forms(doc,result):doc.add_page_break()
        append_result(doc,result,f'별첨 {i} {name} 계산 내역')
    output = BytesIO()
    doc.save(output)
    return output.getvalue()
