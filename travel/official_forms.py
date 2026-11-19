"""인사혁신처 제226호 별지 제3·7호의 항목과 병합 배치를 재현한다.

공식 신청서와 앱의 계산 보조자료는 별도 페이지/시트로 구분한다.
공동숙박은 본인·동행자별 신청서를 작성하고 동행자에게 운임을 추가하지 않는다.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from math import ceil
from unicodedata import east_asian_width
from .models import ZERO, CONFIRMED, EXCLUDED, money, dec
from .report import ReportNumber, report_number

SOURCE_URL='https://www.mpm.go.kr/mpm/info/resultPay/payBoard/?cntId=695&mode=view'
PDF_URL='https://www.mpm.go.kr/board/file/bbs_0000000000000035/695/FILE_000000100073530/7aa6b30cca5926d04'


@dataclass
class Block:
    rows: list
    widths: list
    merges: list = field(default_factory=list)
    height: int = 28


@dataclass
class Form:
    number: int
    title: str
    person: str
    blocks: list
    statement: str
    attachment: str
    notes: list = field(default_factory=list)


def block_heights(block,number):
    """긴 기관명·성명도 셀 밖으로 잘리지 않도록 실제 문구에 맞춰 높이를 늘린다."""
    heights=[block.height]*len(block.rows)
    regions={(r,c):(r1,c1) for r,c,r1,c1 in block.merges}
    covered={(rr,cc) for r,c,r1,c1 in block.merges for rr in range(r,r1+1) for cc in range(c,c1+1) if (rr,cc)!=(r,c)}
    font=9 if number==3 else 8
    for r,values in enumerate(block.rows):
        for c,value in enumerate(values):
            if (r,c) in covered:continue
            r1,c1=regions.get((r,c),(r,c))
            if isinstance(value,ReportNumber):
                text=report_number(value.value,0 if value.krw else 2)+('원' if value.krw else '')
            else:text=money(value) if isinstance(value,Decimal) else str(value)
            width=460*sum(block.widths[c:c1+1])/sum(block.widths)-7
            lines=sum(max(1,ceil(sum(2 if east_asian_width(ch) in ('W','F') else 1 for ch in line)*font*.55/max(width,10))) for line in text.split('\n'))
            required=lines*font*1.2+5
            current=sum(heights[r:r1+1])
            if required>current:heights[r1]+=ceil(required-current)
    return heights


def period(result):
    m=result.trip['meta']
    return str(m.get('시작일시',''))[:10]+' ~ '+str(m.get('종료일시',''))[:10]


def destination(result):
    places=[]
    for r in result.trip['days']:
        name=' '.join(filter(None,[r.get('국가') if result.trip['kind']=='국외' else '',r.get('도시')]))
        if name and name not in places:places.append(name)
    return ', '.join(places) or result.trip['meta'].get('기본도시','')


def total(lines, attr, confirmed=False):
    rows=[r for r in lines if r.status!=EXCLUDED and (not confirmed or r.status==CONFIRMED)]
    return sum((getattr(r,attr) or ZERO for r in rows),ZERO)


def domestic_forms(result):
    m=result.trip['meta']
    lodging=[r for r in result.lines if r.category=='숙박비']
    shared_ids=list(dict.fromkeys(r.lodging_person_id for r in lodging if r.lodging_person_id))
    identities=['self']+[identifier for identifier in shared_ids if identifier!='self'] if shared_ids else ['']
    forms=[]
    for identifier in identities:
        own=identifier in ('','self')
        lines=[r for r in lodging if (r.lodging_person_id or 'self')==(identifier or 'self')]
        if own:
            name=m.get('성명','');agency=m.get('소속기관','');grade=m.get('직위직급','')
        else:
            suffix=identifier.removeprefix('companion')
            index=int(suffix)-1 if identifier.startswith('companion') and suffix.isdigit() else -1
            people=m.get('공동숙박자',[])
            person=people[index] if 0<=index<len(people) else {}
            name=person.get('성명','');agency=person.get('소속기관','');grade=person.get('직위직급','')
            if not name and lines:
                label=lines[0].lodging_person_name
                name=label.split(' · ',1)[1] if ' · ' in label else label if not label.startswith('공동 출장자') else ''
        real=total(lines,'actual')
        cap='실비' if lines and all(r.lodging_person_group.startswith('제1호') for r in lines) else total(lines,'basis')
        if not identifier and m.get('지급등급','').startswith('제1호'):cap='실비'
        reasons='; '.join(dict.fromkeys(str(r.get('승인근거','')) for r in result.trip['lodgings']
            if r.get('초과신청') and (r.get('숙박정산대상ID') or 'self')==(identifier or 'self') and r.get('승인근거')))
        transports=[]
        if own:
            remaining=[x for x in result.lines if x.category=='교통비']
            for r in result.trip['transports']:
                # 별지 제3호 유의사항: 항공운임은 별지 제5호 대상이다.
                if r.get('교통수단')=='항공':continue
                match=next((x for x in remaining if x.date==r.get('일자') and x.name==r.get('교통수단')),None)
                if match:remaining.remove(match)
                mode=r.get('교통수단','')
                if mode=='자가용':mode+='\n'+r.get('유종','')
                transports.append([r.get('일자',''),mode,r.get('출발지') or m.get('출발지',''),r.get('도착지',''),r.get('좌석등급',''),
                                   match.amount if match and match.amount is not None else ''])
        while len(transports)<4:transports.append(['']*6)
        blocks=[
            Block([['소 속',agency,'직 급\n(직위)',grade,'성 명',name]],[1.1,1.9,1,1.5,1,1.5],height=32),
            Block([['출장(부임)\n일 정','일 시',period(result)],['','출장(부임)지',destination(result)]],
                  [1.1,1.1,5.8],[(0,0,1,0)],30),
            Block([['숙 박 비','상한액 또는\n지급받은 선금',cap,'실제 소요액',real,'초과지출 사유',reasons]],
                  [1,1,1,1,1,1,1],height=56),
            Block([['운 임','일 자','교통편','출발지','도착지','등 급','금 액']]+[['']+r for r in transports],
                  [1]*7,[(0,0,len(transports),0)],30)]
        forms.append(Form(3,'국내여비 정산 신청서',name,blocks,
            '「공무원 여비 규정」 제16조 제1항·제2항에 의하여 관계서류를 첨부하여 위와 같이 국내여비의 정산을 신청합니다.',
            '첨 부 : 신용카드 매출전표 등 1부',[
                '1. 정산하는 여비 항목 중 운임은 국내여행에 한함. 다만, 국내·외 항공운임은 별지 제5호 서식에 의함',
                '2. 「공무원 여비 규정」 제16조 제1항 단서에 따라 숙박비를 상향하는 경우 ‘초과지출 사유’ 작성']))
    return forms


def foreign_forms(result):
    m=result.trip['meta']
    hotel=[r for r in result.lines if r.category=='숙박비']
    verified=all(r.status in (CONFIRMED,EXCLUDED) for r in hotel)
    # 지급받은 정액여비/숙박 선금은 기지급 총액으로 항목별 내역을 추정하지 않는다.
    fx=next((r for r in result.trip['fx'] if r.get('통화')=='USD' and r.get('증빙확인')), {})
    rate=fx.get('1단위당 원화','')
    method=m.get('숙박정산방식','실비')
    selections=['','','','','','']
    selections[0]='○'
    selections[5 if method=='할인정액' else 3 if any(r.get('초과신청') for r in result.trip['lodgings']) else 2]='○'
    purpose=[['출장목적\n및\n정산방법',m.get('출장목적',''),'원화 환율\n(1USD : ₩)','식비','','숙박비','','',''],
        ['','','','정액지급','실비정산\n상한액의\n1/2추가정산','실비정산\n상한액 내','실비정산\n상한액의\n1/2추가정산','특례협의','할인정액'],
        ['', '', rate,*selections]]
    purpose[0][2]+=('\n'+report_number(rate)) if rate else ''
    purpose[2][2]=''
    itinerary=[['출장일정','출장기간','출장국가','통화명','환율\n(1USD당)','환율 출처','환율적용 일자']]
    for country in dict.fromkeys(r.get('국가','') for r in result.trip['days']):
        q=next((r for r in result.trip['fx'] if r.get('통화')!='USD' and r.get('증빙확인')), {})
        itinerary.append(['',period(result),country,q.get('통화',''),'',q.get('출처',''),q.get('기준일','')])
    if len(itinerary)==1:itinerary.append(['']*7)
    payments=[['※ 정액여비\n및 운임\n지급내역','성명','직 급\n(여비등급)','합계 금액','일비','식비','숙박비\n할인정액','운임'],
        ['',m.get('성명',''),m.get('지급등급',''),'USD','','','',''],
        ['','','','₩','','','',''],['','합 계','','USD','','','',''],['','','','₩','','','','']]
    settle=[['숙박비\n실비정산\n(총괄)','통화\n단위','실 비\n상한액(A)','결제금액(현지에서 결제한 금액)','','','','정산금액\n(E)'],
        ['','','','계(B)','정부구매카드','개인카드(C)','현금(D)',''],
        ['','USD','','','','','',''],['','₩',total(hotel,'basis') if method!='할인정액' else '',
            total(hotel,'actual') if any(r.actual is not None for r in hotel) and method!='할인정액' else '','','','',
            total(hotel,'amount',True) if verified and method!='할인정액' else '']]
    adjustment=[['숙박비\n실비정산\n(총괄)','통화\n단위','초과금액\n(F=B-E)','선금지급액\n(G)','산출액\n(H=(C+D)-F-G)','조정액\n(I)','조정사유','지급(반납)액\n(J=H+I)'],
                ['','₩','','','','','','']]
    expenses=[['숙박비\n결제내역','일자','숙박업소명','결제방법','현지통화(ㄱ)','달러환산액(ㄴ)','원화환산액(ㄷ)']]
    for row in result.trip['lodgings']:
        line=next((r for r in hotel if r.date==row.get('숙박일')),None)
        actual=row.get('실제지출액','')
        if actual not in ('',None):actual=ReportNumber(dec(actual),row.get('통화')=='KRW')
        expenses.append(['',row.get('숙박일',''),row.get('숙박업소명',''),row.get('결제수단',''),
            actual,actual if row.get('통화')=='USD' else '',
            line.actual if line and line.actual is not None else ''])
    if len(expenses)==1:expenses.append(['']*7)
    expenses.append(['','합 계','','','','',''])
    personal=[['숙박비\n개인별\n정산내역','성명','소속','여비등급','선지급액(a)','개인카드+현금(b)','초과금액(c)','지급액(b-a-c)'],
        ['',m.get('성명',''),m.get('소속기관',''),m.get('지급등급',''),'','','',''],['','합 계(₩)','','','','','','']]
    prep=['비자발급비','예방접종비','여행보험가입비','풍토병예방약구입비','감염병 진단검사비']
    blocks=[Block([['대 표 자','소 속',m.get('소속기관',''),'직 급',m.get('직위직급',''),'성 명',m.get('성명','')]],[1,1,1.5,1,1.5,1,1.5],height=20),
        Block(purpose,[1.2,2,1,1,1,1,1,1,1],[(0,0,2,0),(0,1,2,1),(0,2,2,2),(0,3,0,4),(0,5,0,8)],21),
        Block(itinerary,[1.2,1.1,1.7,1.4,1.1,1.1,1.6],[(0,0,len(itinerary)-1,0)],20),
        Block(payments,[1.2,.8,1.3,1.7,1.2,1.2,1.2,1.2],[(0,0,4,0),(1,1,2,1),(1,2,2,2),(3,1,4,2)],18),
        Block(settle,[1.2,.6,1.6,1.5,1.4,1.4,1.1,1.3],[(0,0,3,0),(0,1,1,1),(0,2,1,2),(0,3,0,6),(0,7,1,7)],18),
        Block(adjustment,[1.2,.6,1.1,1.1,1.7,1,1.2,1.3],[(0,0,1,0)],20),
        Block(expenses,[1.2,.9,2.1,1.7,1.3,1.3,1.3],[(0,0,len(expenses)-1,0)],18),
        Block(personal,[1.2,.9,1,1.2,1.6,2,1.3,1.3],[(0,0,2,0),(2,1,2,3)],18),
        Block([['준비금\n정 산',*prep,'지급액 합계'],['','','','','','','₩']],[1.2,1.3,1.3,1.6,1.9,1.8,1.3],[(0,0,1,0)],18)]
    return [Form(7,'국외여비(식비·숙박비·준비금) 정산 신청서',m.get('성명',''),blocks,
        '「공무원 여비 규정」 제8조의2, 제16조 제1항·제2항, 제23조에 따라, 증거자료를 첨부하여 국외여비 정산을 신청합니다.',
        '첨 부 : 증거자료, 식비 및 숙박비 1/2추가 정산 신청사유 등 1부')]


def forms_for(result):
    if result.trip['kind']=='국내':return domestic_forms(result)
    if result.trip['kind']=='국외':return foreign_forms(result)
    return []


def append_word_forms(doc,result):
    from docx.shared import Pt,RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT,WD_ROW_HEIGHT_RULE
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from .word import table, shade
    forms=forms_for(result)
    for i,form in enumerate(forms):
        if i:doc.add_page_break()
        p=doc.add_paragraph(f'■ 공무원보수 등의 업무지침 제9장 [별지 제{form.number}호 서식]','Caption')
        p.paragraph_format.space_after=Pt(12 if form.number==3 else 5)
        p=doc.add_paragraph(form.title,'Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:run.font.size=Pt(20 if form.number==3 else 17)
        p=doc.add_paragraph('※ 「e-사람 시스템」 등 전산시스템으로 신청 시 수기 작성 생략','Caption')
        p.paragraph_format.space_after=Pt(10 if form.number==3 else 4)
        for block in form.blocks:
            # 공통 표의 정확한 본문 너비를 사용하되 공식 서식의 무채색 선과 병합을 적용한다.
            t=table(doc,['']*len(block.widths),block.rows,block.widths)
            t._tbl.remove(t.rows[0]._tr)
            margins=t._tbl.tblPr.find(qn('w:tblCellMar'))
            for margin in margins:
                margin.set(qn('w:w'),'20' if margin.tag in (qn('w:top'),qn('w:bottom')) else '60')
            for r0,c0,r1,c1 in block.merges:t.cell(r0,c0).merge(t.cell(r1,c1))
            heights=block_heights(block,form.number)
            for index,row in enumerate(t.rows):
                row.height=Pt(heights[index])
                if form.number==7:
                    row.height_rule=WD_ROW_HEIGHT_RULE.EXACTLY if heights[index]<600 else WD_ROW_HEIGHT_RULE.AT_LEAST
                    if heights[index]>=600:
                        split=row._tr.trPr.find(qn('w:cantSplit'))
                        if split is not None:row._tr.trPr.remove(split)
                for cell in row.cells:
                    shade(cell,'FFFFFF');cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
                    for p in cell.paragraphs:
                        p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                        p.paragraph_format.space_before=Pt(0);p.paragraph_format.space_after=Pt(0)
                        p.paragraph_format.line_spacing=1.05
                        for run in p.runs:run.font.size=Pt(9 if form.number==3 else 7.5)
            for edge in t._tbl.tblPr.find(qn('w:tblBorders')):
                edge.set(qn('w:color'),'777777');edge.set(qn('w:sz'),'4')
                if edge.tag in (qn('w:left'),qn('w:right')):edge.set(qn('w:val'),'nil')
            # 국외 서식은 구역이 이어지므로 표 사이의 빈 문단을 줄인다.
            spacer=doc.paragraphs[-1]
            spacer.paragraph_format.space_after=Pt(3 if form.number==3 else 0)
            spacer.paragraph_format.line_spacing=Pt(2 if form.number==3 else 1)
        p=doc.add_paragraph(form.statement)
        p.paragraph_format.space_before=Pt(10 if form.number==3 else 4)
        for run in p.runs:run.font.size=Pt(10 if form.number==3 else 8)
        p=doc.add_paragraph(form.attachment)
        for run in p.runs:run.font.size=Pt(9 if form.number==3 else 8)
        for text in ['년       월       일','신 청 인   성 명   '+form.person+'       (서명 또는 인)']:
            p=doc.add_paragraph(text);p.alignment=WD_ALIGN_PARAGRAPH.RIGHT
            p.paragraph_format.space_after=Pt(12 if form.number==3 else 3)
        if form.number==3:
            doc.add_paragraph('소속기관장 귀하')
            t=table(doc,['유의사항'],[[note] for note in form.notes],[17.6])
            shade(t.rows[0].cells[0],'E8E8E8')
            for p in t.rows[0].cells[0].paragraphs:
                for run in p.runs:run.font.color.rgb=RGBColor(0,0,0)
        else:
            instructions=Path(__file__).parent/'data/forms/국외_별지7호_작성방법.txt'
            if instructions.exists():
                doc.add_page_break();doc.add_heading('작성방법',1)
                for line in instructions.read_text().splitlines():
                    if line.strip():
                        p=doc.add_paragraph(line.strip())
                        p.paragraph_format.space_after=Pt(3);p.paragraph_format.line_spacing=1.1
                        for run in p.runs:run.font.size=Pt(8.5)
    return len(forms)


def append_excel_forms(wb,result,prefix=''):
    from openpyxl.styles import Font,Alignment,Border,Side,PatternFill
    from openpyxl.worksheet.page import PageMargins
    from .excel import safe_value,FONT,MONEY
    sheets=[]
    for i,form in enumerate(forms_for(result),1):
        ws=wb.create_sheet(f'신청서_{prefix}{i}_별지{form.number}호'[:31])
        sheets.append(ws)
        ws.sheet_view.showGridLines=False;ws.sheet_view.zoomScale=95
        ws.sheet_properties.tabColor='555555'
        for col in range(1,85):ws.column_dimensions[ws.cell(1,col).column_letter].width=1.05
        def merged(row,c0,c1,value,height=26,size=10,align='center'):
            if c1>c0:ws.merge_cells(start_row=row,start_column=c0,end_row=row,end_column=c1)
            c=ws.cell(row,c0);safe_value(c,value)
            c.font=Font(name=FONT,size=size,color='000000')
            c.alignment=Alignment(horizontal=align,vertical='center',wrap_text=True)
            ws.row_dimensions[row].height=height
        merged(1,1,84,f'■ 공무원보수 등의 업무지침 제9장 [별지 제{form.number}호 서식]',22,9,'left')
        merged(2,1,84,form.title,42,20 if form.number==3 else 17)
        ws.cell(2,1).font=Font(name=FONT,size=20 if form.number==3 else 17,bold=True)
        merged(3,1,84,'※ 「e-사람 시스템」 등 전산시스템으로 신청 시 수기 작성 생략',25,8,'left')
        cursor=5
        for block in form.blocks:
            heights=block_heights(block,form.number)
            boundaries=[1]
            for index in range(1,len(block.widths)+1):boundaries.append(1+round(84*sum(block.widths[:index])/sum(block.widths)))
            merge_map={(r,c):(r1,c1) for r,c,r1,c1 in block.merges}
            covered={(rr,cc) for r,c,r1,c1 in block.merges for rr in range(r,r1+1) for cc in range(c,c1+1) if (rr,cc)!=(r,c)}
            for r,values in enumerate(block.rows):
                ws.row_dimensions[cursor+r].height=min(409,heights[r])
                for c,value in enumerate(values):
                    if (r,c) in covered:continue
                    r1,c1=merge_map.get((r,c),(r,c))
                    ws.merge_cells(start_row=cursor+r,start_column=boundaries[c],end_row=cursor+r1,end_column=boundaries[c1+1]-1)
                    cell=ws.cell(cursor+r,boundaries[c]);safe_value(cell,value)
                    if isinstance(value,Decimal):cell.number_format=MONEY
                    cell.font=Font(name=FONT,size=9 if form.number==3 else 8)
                    cell.alignment=Alignment(vertical='center',horizontal='center',wrap_text=True)
                    side=Side(style='thin',color='777777')
                    # 병합된 전체 영역의 외곽선을 Excel에 명시한다.
                    for rr in range(cursor+r,cursor+r1+1):
                        for cc in range(boundaries[c],boundaries[c1+1]):
                            ws.cell(rr,cc).border=Border(top=side if rr==cursor+r else None,bottom=side if rr==cursor+r1 else None,
                                left=side if cc==boundaries[c] and c>0 else None,right=side if cc==boundaries[c1+1]-1 and c1<len(values)-1 else None)
            cursor+=len(block.rows)+(1 if form.number==3 else 0)
            if form.number==3:ws.row_dimensions[cursor-1].height=8
        merged(cursor,1,84,form.statement,38 if form.number==3 else 30,9 if form.number==3 else 8,'left');cursor+=1
        merged(cursor,1,84,form.attachment,24,9,'left');cursor+=1
        merged(cursor,1,84,'년       월       일',28,10,'right');cursor+=1
        merged(cursor,1,84,'신 청 인   성 명   '+form.person+'       (서명 또는 인)',28,10,'right');cursor+=1
        if form.number==3:
            merged(cursor,1,84,'소속기관장 귀하',30,12,'left');cursor+=1
            merged(cursor,1,84,'유의사항',22,10);ws.cell(cursor,1).fill=PatternFill('solid',fgColor='E8E8E8');cursor+=1
            for note in form.notes:merged(cursor,1,84,note,28,8,'left');cursor+=1
        ws.print_area=f'A1:CF{cursor-1}'
        ws.page_setup.orientation='portrait';ws.page_setup.paperSize=ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth=1;ws.page_setup.fitToHeight=1
        ws.sheet_properties.pageSetUpPr.fitToPage=True
        ws.page_margins=PageMargins(left=.55,right=.55,top=.55,bottom=.55,header=.2,footer=.2)
        ws.oddFooter.left.text=f'인사혁신처예규 제226호 별지 제{form.number}호'
        ws.oddFooter.right.text='&P / &N'
        if form.number==7:
            instructions=Path(__file__).parent/'data/forms/국외_별지7호_작성방법.txt'
            if instructions.exists():
                from .excel import sheet
                back=sheet(wb,f'신청서_{prefix}{i}_작성방법'[:31],'국외여비 정산 신청서 작성방법',
                    ['구분','작성방법'],[['별지 제7호',line] for line in instructions.read_text().splitlines() if line.strip()],[18,76])
                back.sheet_properties.tabColor='555555';sheets.append(back)
    return sheets
