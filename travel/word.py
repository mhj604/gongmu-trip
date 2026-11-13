"""한글 글꼴과 편집 가능한 표를 사용하는 행정 정산서."""
from io import BytesIO
from decimal import Decimal
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from .models import *
from .report import flatten,metadata,deadlines,status_label,period

NAVY='182F4D'; TEAL='087F8C'

def shade(cell,color):
    element=OxmlElement('w:shd');element.set(qn('w:fill'),color);cell._tc.get_or_add_tcPr().append(element)

def display(value):
    if value is None: return '미입력'
    if isinstance(value,Decimal): return money(value)
    return str(value)

def table(doc,headers,rows,widths):
    t=doc.add_table(rows=1,cols=len(headers))
    t.autofit=False
    for col,width in zip(t.columns,widths): col.width=Cm(width)
    for c,h,width in zip(t.rows[0].cells,headers,widths):
        c.width=Cm(width); c.text=h; shade(c,'EAF0F6')
        for run in c.paragraphs[0].runs: run.bold=True;run.font.color.rgb=RGBColor.from_string(NAVY)
    repeat=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(repeat)
    for values in list(rows) or [['해당 없음']+['']*(len(headers)-1)]:
        row=t.add_row()
        no_split=OxmlElement('w:cantSplit');row._tr.get_or_add_trPr().append(no_split)
        for c,value,width in zip(row.cells,values,widths):
            c.width=Cm(width);c.text=display(value)
            for p in c.paragraphs:
                p.paragraph_format.space_after=Pt(3)
                p.paragraph_format.space_before=Pt(3)
                if isinstance(value,(Decimal,int,float)): p.alignment=WD_ALIGN_PARAGRAPH.RIGHT
                for r in p.runs:r.font.size=Pt(9)
    doc.add_paragraph().paragraph_format.space_after=Pt(1)
    return t

def hyperlink(paragraph,text,url):
    part=paragraph.part
    relation=part.relate_to(url,'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',is_external=True)
    link=OxmlElement('w:hyperlink');link.set(qn('r:id'),relation)
    r=OxmlElement('w:r');pr=OxmlElement('w:rPr');color=OxmlElement('w:color');color.set(qn('w:val'),'1660A0');pr.append(color);r.append(pr)
    tx=OxmlElement('w:t');tx.text=text;r.append(tx);link.append(r);paragraph._p.append(link)

def export_word(result:Result)->bytes:
    doc=Document()
    section=doc.sections[0]
    section.page_width=Cm(21);section.page_height=Cm(29.7)
    section.top_margin=Cm(1.6);section.bottom_margin=Cm(1.6)
    section.left_margin=Cm(1.7);section.right_margin=Cm(1.7)
    for name in ['Normal','Title','Heading 1','Heading 2']:
        style=doc.styles[name]
        style.font.name='맑은 고딕'
        style.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'맑은 고딕')
        style.font.color.rgb=RGBColor.from_string(NAVY if name!='Normal' else '283747')
    doc.styles['Normal'].font.size=Pt(10)
    doc.styles['Normal'].paragraph_format.space_after=Pt(6)
    doc.styles['Title'].font.size=Pt(20)
    doc.styles['Heading 1'].font.size=Pt(13)
    doc.styles['Heading 1'].paragraph_format.space_before=Pt(12)
    section.header.paragraphs[0].text='공무 출장비 정산서  /  '+result.trip['meta'].get('출장명','')
    for run in section.header.paragraphs[0].runs: run.font.size=Pt(8)
    foot=section.footer.paragraphs[0];foot.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    foot.add_run('페이지 ')
    field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');foot._p.append(field)
    doc.add_paragraph(result.trip['kind']+' 출장비 정산서','Title')
    p=doc.add_paragraph(status_label(result)+'  ')
    r=p.add_run(money(result.claim));r.bold=True;r.font.size=Pt(19);r.font.color.rgb=RGBColor.from_string(TEAL)
    doc.add_paragraph(f'확정 인정액 {money(result.recognized)}  ·  기지급액 {money(result.advance)}  ·  반납예정액 {money(result.refund)}')
    if result.issues:doc.add_paragraph(f'미확정 항목 {len(result.issues)}건은 확정 청구액에서 제외했습니다. 금액을 산정할 수 없는 항목도 포함됩니다.')
    doc.add_heading('1 출장 개요',1)
    table(doc,['항목','입력 내용'],list(flatten(result.trip['meta'])),[4,13.6])
    doc.add_heading('2 출장 일정',1)
    table(doc,['일자','국가 및 도시','업무와 이동 일정'],
        [[r.get('일자',''),f'{r.get("국가", "")} {r.get("도시", "")}',f'{r.get("업무일정", "")} {r.get("이동일정", "")}'] for r in result.trip['days']],[2.8,4.5,10.3])
    doc.add_heading('3 출장비 정산 총괄',1)
    rows=[[r['항목'],r['기준금액'],r['인정금액'],r['미확정금액']] for r in result.summary()]
    rows+=[['확정 인정액 합계',None,result.recognized,result.pending],['기지급액',None,result.advance,None],[status_label(result),None,result.claim,None]]
    t=table(doc,['항목','기준금액','확정 인정액','미확정금액'],rows,[5.1,4.1,4.2,4.2])
    for cell in t.rows[-1].cells:
        shade(cell,'DCF0EF')
        for p in cell.paragraphs:
            for r in p.runs:r.bold=True
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
            p.add_run(r.formula+'\n'+r.reference)
            if r.currency!='KRW':p.add_run(f'\n통화 {r.currency} / 외화금액 {r.foreign_amount} / 환율 {r.rate}')
            if r.notes:p.add_run('\n'+r.notes)
    doc.add_heading('5 지급 조정 및 예외',1)
    doc.add_paragraph('할인·기관부담·지원액은 해당 항목에서 차감합니다. 기지급액은 확정 인정액에서 한 번만 차감합니다. 미승인 추가지급액은 청구액에 포함하지 않습니다.')
    for issue in result.issues:doc.add_paragraph(issue,style='Normal')
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
    for key in ['id','kind','days','lodgings','transports','specials','fx','evidence','settings']:
        table(doc,['입력 경로','입력값'],list(flatten({key:result.trip[key]})),[7,10.6])
    buff=BytesIO();doc.save(buff);return buff.getvalue()
