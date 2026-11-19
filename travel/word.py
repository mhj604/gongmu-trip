"""한글 글꼴과 편집 가능한 표를 사용하는 행정 정산서."""
from io import BytesIO
from decimal import Decimal
from docx import Document
from docx.shared import Cm,Pt,RGBColor,Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from .models import *
from .report import formatted_flatten as flatten,metadata,deadlines,status_label,period,ReportNumber,report_number,report_text
from .shared_lodging import allocation, SCOPE_NOTE

NAVY='243B57'; TEAL='245EC7'; FONT='맑은 고딕'

def shade(cell,color):
    element=OxmlElement('w:shd');element.set(qn('w:fill'),color);cell._tc.get_or_add_tcPr().append(element)

def display(value):
    if value is None: return '미입력'
    if isinstance(value,ReportNumber):return report_number(value.value,0 if value.krw else 2)+('원' if value.krw else '')
    if isinstance(value,Decimal): return money(value)
    if isinstance(value,(int,float)) and not isinstance(value,bool):return report_number(value)
    return str(value)

def table(doc,headers,rows,widths):
    t=doc.add_table(rows=1,cols=len(headers))
    t.autofit=False
    t.alignment=WD_TABLE_ALIGNMENT.CENTER
    section=doc.sections[-1]
    content_width=int((section.page_width-section.left_margin-section.right_margin)/635)
    exact=[round(content_width*w/sum(widths)) for w in widths]
    exact[-1]+=content_width-sum(exact)
    pr=t._tbl.tblPr
    size=pr.find(qn('w:tblW'));size.set(qn('w:type'),'dxa');size.set(qn('w:w'),str(content_width))
    borders=OxmlElement('w:tblBorders')
    for side in ['top','left','bottom','right','insideH','insideV']:
        edge=OxmlElement('w:'+side)
        for key,value in [('val','single'),('sz','4'),('color','D9D9D9')]:edge.set(qn('w:'+key),value)
        borders.append(edge)
    pr.append(borders)
    margins=OxmlElement('w:tblCellMar')
    for side,value in [('top','90'),('bottom','90'),('start','110'),('end','110')]:
        item=OxmlElement('w:'+side);item.set(qn('w:w'),value);item.set(qn('w:type'),'dxa');margins.append(item)
    pr.append(margins)
    for col,width in zip(t.columns,exact): col.width=Twips(width)
    for c,h,width in zip(t.rows[0].cells,headers,exact):
        c.width=Twips(width); c.text=h; shade(c,NAVY)
        c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
        for p in c.paragraphs:
            p.paragraph_format.keep_with_next=True
            p.paragraph_format.space_after=Pt(3)
            for run in p.runs: run.bold=True;run.font.size=Pt(9);run.font.color.rgb=RGBColor(255,255,255)
    repeat=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(repeat)
    for i,values in enumerate(list(rows) or [['해당 없음']+['']*(len(headers)-1)]):
        row=t.add_row()
        if max(len(display(v)) for v in values)<900:
            no_split=OxmlElement('w:cantSplit');row._tr.get_or_add_trPr().append(no_split)
        for c,value,width in zip(row.cells,values,exact):
            c.width=Twips(width);c.text=display(value)
            c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if i%2:shade(c,'F4F7FA')
            for p in c.paragraphs:
                p.paragraph_format.space_after=Pt(1)
                p.paragraph_format.space_before=Pt(1)
                p.paragraph_format.line_spacing=1.15
                p.paragraph_format.keep_with_next=False
                if isinstance(value,(Decimal,int,float,ReportNumber)): p.alignment=WD_ALIGN_PARAGRAPH.RIGHT
                for r in p.runs:r.font.size=Pt(9)
    spacer=doc.add_paragraph();spacer.paragraph_format.space_after=Pt(2);spacer.paragraph_format.space_before=Pt(0)
    spacer.paragraph_format.line_spacing=Pt(3)
    return t

def hyperlink(paragraph,text,url):
    part=paragraph.part
    relation=part.relate_to(url,'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',is_external=True)
    link=OxmlElement('w:hyperlink');link.set(qn('r:id'),relation)
    r=OxmlElement('w:r');pr=OxmlElement('w:rPr');color=OxmlElement('w:color');color.set(qn('w:val'),'1660A0');pr.append(color);r.append(pr)
    tx=OxmlElement('w:t');tx.text=text;r.append(tx);link.append(r);paragraph._p.append(link)

def new_document(header='공무 출장비 정산서'):
    doc=Document()
    section=doc.sections[0]
    section.page_width=Cm(21);section.page_height=Cm(29.7)
    section.top_margin=Cm(1.6);section.bottom_margin=Cm(1.6)
    section.left_margin=Cm(1.7);section.right_margin=Cm(1.7)
    for name in ['Normal','Title','Heading 1','Heading 2','Caption']:
        style=doc.styles[name]
        style.font.name=FONT
        style.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),FONT)
        fonts=style.element.get_or_add_rPr().rFonts
        for key in ['asciiTheme','eastAsiaTheme','hAnsiTheme','cstheme']:
            fonts.attrib.pop(qn('w:'+key),None)
        paragraph=style.element.find(qn('w:pPr'))
        if paragraph is not None:
            border=paragraph.find(qn('w:pBdr'))
            if border is not None:paragraph.remove(border)
        style.font.color.rgb=RGBColor.from_string('283747' if name=='Normal' else '000000')
    doc.styles['Normal'].font.size=Pt(10)
    doc.styles['Normal'].paragraph_format.space_after=Pt(6)
    doc.styles['Normal'].paragraph_format.line_spacing=1.25
    doc.styles['Normal'].paragraph_format.widow_control=True
    doc.styles['Title'].font.size=Pt(22)
    doc.styles['Title'].font.bold=True
    doc.styles['Title'].font.underline=False
    doc.styles['Title'].paragraph_format.space_after=Pt(8)
    doc.styles['Heading 1'].font.size=Pt(13)
    doc.styles['Heading 1'].paragraph_format.space_before=Pt(12)
    for name in ['Heading 1','Heading 2']:
        doc.styles[name].paragraph_format.keep_with_next=True
        doc.styles[name].paragraph_format.space_after=Pt(6)
    doc.styles['Heading 2'].font.size=Pt(11)
    doc.styles['Caption'].font.size=Pt(9)
    doc.styles['Caption'].font.color.rgb=RGBColor.from_string('657184')
    section.header_distance=Cm(.7);section.footer_distance=Cm(.7)
    section.header.paragraphs[0].text=header
    for run in section.header.paragraphs[0].runs: run.font.size=Pt(8)
    foot=section.footer.paragraphs[0];foot.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    foot.add_run('페이지 ')
    field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');foot._p.append(field)
    return doc


def append_result(doc, result, title=None):
    doc.add_paragraph(title or result.trip['kind']+' 출장비 정산서','Title')
    m=result.trip['meta']
    doc.add_paragraph((m.get('출장명') or '출장 정산')+'  |  '+period(result),'Caption')
    doc.add_paragraph('예상 출장비 (미확정 포함)  '+money(result.estimated))
    p=doc.add_paragraph(status_label(result)+'  ')
    r=p.add_run(money(result.claim));r.bold=True;r.font.size=Pt(19);r.font.color.rgb=RGBColor.from_string(TEAL)
    doc.add_paragraph(f'확정 인정액 {money(result.recognized)}  ·  기지급액 {money(result.advance)}  ·  반납예정액 {money(result.refund)}')
    if result.issues:doc.add_paragraph(f'미확정 항목 {len(result.issues)}건은 확정 청구액에서 제외했습니다. 금액을 산정할 수 없는 항목도 포함됩니다.')
    doc.add_heading('1 출장 개요',1)
    overview=[('출장자',m.get('성명') or '미입력'),('소속기관',m.get('소속기관') or '미입력'),
              ('출장목적',m.get('출장목적') or '미입력'),('지급등급',m.get('지급등급') or '미입력')]
    table(doc,['항목','입력 내용'],overview,[3,14.6])
    doc.add_heading('2 출장비 정산 총괄',1)
    rows=[[r['항목'],r['기준금액'],r['인정금액'],r['미확정금액']] for r in result.summary()]
    rows+=[['확정 인정액 합계','—',result.recognized,result.pending],['기지급액','—',result.advance,'—'],[status_label(result),'—',result.claim,'—']]
    t=table(doc,['항목','기준금액','확정 인정액','미확정금액'],rows,[5.1,4.1,4.2,4.2])
    for cell in t.rows[-1].cells:
        shade(cell,'DCF0EF')
        for p in cell.paragraphs:
            for r in p.runs:r.bold=True
    shared=allocation(result)
    if shared:
        doc.add_heading('공동숙박 분담 내역',2)
        doc.add_paragraph(SCOPE_NOTE+' 숙박비 분담액 합계 '+money(sum((r['분담액'] for r in shared),ZERO))+'. 위 정산 총괄에 이미 포함된 금액입니다.')
        table(doc,['정산 대상·등급','숙박','분담액','상한','예상 인정액'],
            [[r['정산 대상']+'\n'+r['지급 등급'],str(r['숙박일'])+'박',r['분담액'],r['상한'],r['예상 인정액']] for r in shared],
            [5.2,1.3,3.7,3.7,3.7])
    doc.add_heading('3 출장 일정',1)
    table(doc,['일자','국가 및 도시','업무와 이동 일정'],
        [[r.get('일자',''),f'{r.get("국가", "")} {r.get("도시", "")}',f'{r.get("업무일정", "")} {r.get("이동일정", "")}'] for r in result.trip['days']],[2.8,4.5,10.3])
    doc.add_heading('4 항목별 상세 계산',1)
    for cat in CATEGORIES:
        items=[r for r in result.lines if r.category==cat]
        if not items: continue
        doc.add_heading(cat,2)
        table(doc,['일자 및 내역','실제 지출액','인정금액','상태'],
            [[r.date+'\n'+r.name,r.actual,r.amount,r.status] for r in items],[6.4,4,4,3.2])
        for r in items:
            p=doc.add_paragraph()
            p.add_run(r.date+' '+r.name+'  ').bold=True
            p.add_run(report_text(r.formula)+'\n'+r.reference)
            if r.currency!='KRW':p.add_run(f'\n통화 {r.currency} / 외화금액 {report_number(r.foreign_amount)} / 환율 {report_number(r.rate)}')
            if r.notes:p.add_run('\n'+report_text(r.notes))
    doc.add_heading('5 지급 조정 및 예외',1)
    doc.add_paragraph('할인·기관부담·지원액은 해당 항목에서 차감합니다. 기지급액은 확정 인정액에서 한 번만 차감합니다. 미승인 추가지급액은 청구액에 포함하지 않습니다.')
    for issue in result.issues:doc.add_paragraph(report_text(issue),style='Normal')
    doc.add_heading('6 증빙 및 정산 확인',1)
    table(doc,['구분','내용'],[(p,v) for p,v in flatten(result.trip['evidence'],'증빙')],[5,12.6])
    table(doc,['정산 항목','신청 기한 및 근거'],[[r['항목'],r['기한']+' / '+r['근거']] for r in deadlines(result)],[5,12.6])
    doc.add_heading('7 적용 법령 및 계산 근거',1)
    used=sorted({(r.rule_version,r.source) for r in result.lines})
    for version,source in used:
        p=doc.add_paragraph(version)
        for url in source.split('\n'):
            if url:hyperlink(p,' 공식 원문 ',url)
    doc.add_paragraph('생성일시 '+result.generated_at+' / 법령자료 버전 '+result.rule_snapshot['version'])
    doc.add_heading('부록 모든 원본 입력',1)
    doc.add_paragraph('기본정보와 별도로 각 일정의 세부 조건, 교통·숙박·특수 여비, 환율, 증빙 및 계산 설정을 보존합니다.')
    for key in ['id','kind','meta','days','lodgings','transports','specials','fx','evidence','settings']:
        table(doc,['입력 경로','입력값'],list(flatten({key:result.trip[key]})),[6,11.6])


def export_word(result:Result)->bytes:
    doc=new_document('공무 출장비 정산서  /  '+result.trip['meta'].get('출장명',''))
    from .official_forms import append_word_forms
    if append_word_forms(doc,result):doc.add_page_break()
    append_result(doc,result,'별첨 출장비 계산 내역')
    buff=BytesIO();doc.save(buff);return buff.getvalue()
