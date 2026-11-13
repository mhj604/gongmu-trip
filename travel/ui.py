"""Streamlit 입력 화면과 정산 결과."""
from datetime import datetime,date,time,timedelta
from decimal import Decimal
from html import escape
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo
import json
import pandas as pd
import streamlit as st
from .models import *
from .engine import calculate
from .rules import load_rules,select_law,destination
from .storage import Store
from .excel import export_excel
from .word import export_word
from .report import metadata,deadlines,status_label
from .ui_theme import apply_theme,brand,page_header,section_heading,empty_state,summary_html,result_overview,PAGE_INFO

PAGES=['새 출장 등록','국내 출장 계산','국외 출장 계산','특수 여비 계산','계산 결과 및 정산서',
       '저장된 출장 내역','법령 및 지급 기준 안내','프로그램 설정']
GROUPS=['제2호','제1호라','제1호다','제1호나','제1호가']
DAY={'일자':'','국가':'대한민국','도시':'','업무일정':'','이동일정':'','여비인정일':True,
     '공무용차량':False,'도착다음날기산일수':'0','식비지원액':'','숙식제공여부':False,'식비조정액':'',
     '식비조정근거':'','항공선박이동':False,'별도식비필요':False,'식비실제지출':'',
     '동일행정구역':False,'왕복거리(km)':'','거리출처':'','출장시간(h)':'',
     '근거리운임':'','근거리식비':'','전용차량배정':False,'운전원본연업무':False,
     '분리도서':False,'교량연결':False,'종전 출장지 시군':'','근무지 판정':'자동','판정승인근거':'',
     '식비초과신청':False,'증빙확인':False,'승인':False,'승인근거':'','날짜변경선근거':'',
     '최인접수도국가':'','거리근거':''}
LODGING={'숙박일':'','국가':'대한민국','도시':'','지역구분':'기타','실제숙박':True,
         '실제지출액':'','통화':'KRW','할인액':'','기관부담액':'','지원액':'',
         '무료숙박':False,'기관직접결제':False,'초과신청':False,'증빙확인':False,'승인':False,
         '승인근거':'','동행조정등급':'','주간숙박사유':'','환율ID':'','최인접수도국가':'','거리근거':''}
LODGING.update({'결제수단':'개인카드','카드청구원화액':'','1USD당현지통화':'','현지환율기준일':'','현지환율출처':'','현금사용사유':''})
TRANSPORT={'일자':'','교통수단':'철도','출발지':'','도착지':'','좌석등급':'일반실','실제지출액':'','통화':'KRW',
           '할인액':'','기관부담액':'','지원액':'','기관직접결제':False,'증빙확인':False,'승인':False,'승인근거':'',
           '대중교통운임':'','운임출처':'','부득이한사유':'','거리(km)':'','거리출처':'','유종':'휘발유','유가':'',
           '유가출처':'','통행료':'','주차료':'','동승자':False,'마일리지처리':'사용 없음','환율ID':''}
SPECIAL={'일자':'','종류':'비자발급비','실제지출액':'','통화':'KRW','할인액':'','기관부담액':'','지원액':'',
         '증빙확인':False,'승인':False,'승인근거':'','출입국필수':False,'화물량':'','기본구간실비':'','초과구간실비':'',
         '이전요건확인':False,'발령일':'','이전일':'','나이':'','관계':'배우자','독립생계':False,'자녀예외확인':False,
         '가족요건확인':False,'본인기준운임':'','본인기준숙박비':'','본인기준일비식비':'',
         '본인기준준비금':'','본인기준산출근거':'','국외지급사유':'1','대상호':'','기관지급기준':'',
         '인정출장일수':'','기관확정월액':'','기관확정일액':'','전직상당구간여비':'','환율ID':''}
FX={'환율ID':'','통화':'USD','1단위당 원화':'','기준일':'','출처':'','환율종류':'현찰 매입(출장자 구매)','증빙확인':False}
EVIDENCE_ROW={'일자':'','관련항목':'','자료명':'','문서번호':'','보관위치':'','확인완료':False,'비고':''}

def default_trip(store):
    today=datetime.now(ZoneInfo('Asia/Seoul')).date()
    profile=store.preference('출장자',{})
    return Trip(meta={**profile,'출장명':'','출장목적':'','시작일시':datetime.combine(today,time(9),ZoneInfo('Asia/Seoul')).isoformat(),
                     '종료일시':datetime.combine(today,time(18),ZoneInfo('Asia/Seoul')).isoformat(),
                     '지급등급':profile.get('지급등급','제2호'),'공무원':True,'출장승인':False,'기지급액':'0'})

def key(trip,name):return trip.id+'_'+name

def navigate(page):
    st.session_state.navigation=page

FIELD_LABELS={'출장명':'출장명','출장목적':'출장 목적','소속기관':'소속 기관','직위직급':'직위·직급',
              '지급등급':'지급 등급','기본도시':'방문 도시','기본국가':'방문 국가','출장승인':'출장 승인 완료',
              '현지시간대':'현지 시간대','현지 출발복귀일정':'현지 출발·복귀 일정','기지급액':'기지급액 (원)'}
PLACEHOLDERS={'출장명':'예: 부산 유관기관 업무 협의','출장목적':'출장의 목적을 간단히 적어 주세요.',
              '성명':'이름','소속기관':'소속 기관명','출발지':'예: 서울','출장지':'예: 부산',
              '기본도시':'도시명 입력','비고':'필요한 내용이 있다면 남겨 주세요.'}

def text_input(trip,label,area=False):
    f=st.text_area if area else st.text_input
    options={'height':90} if area else {}
    trip.meta[label]=f(FIELD_LABELS.get(label,label),value=str(trip.meta.get(label,'')),
        placeholder=PLACEHOLDERS.get(label,''),key=key(trip,label),**options)

def check(trip,label):
    trip.meta[label]=st.checkbox(FIELD_LABELS.get(label,label),value=bool(trip.meta.get(label,False)),key=key(trip,label))

def choose(trip,label,options):
    previous=trip.meta.get(label,options[0])
    trip.meta[label]=st.selectbox(FIELD_LABELS.get(label,label),options,index=options.index(previous) if previous in options else 0,key=key(trip,label))

def editor(trip,attr,template,visible,help_text=''):
    source=getattr(trip,attr)
    rows=[{**template,**r} for r in source]
    df=pd.DataFrame(rows,columns=list(dict.fromkeys([*template,*[k for r in source for k in r]])))
    for col,default in template.items():
        if isinstance(default,bool):df[col]=df[col].fillna(default).astype(bool)
        else:df[col]=df[col].fillna('').astype(str)
    configs={col:st.column_config.CheckboxColumn(col) if isinstance(default,bool) else st.column_config.TextColumn(col) for col,default in template.items()}
    options={
        '지역구분':['서울','광역시','기타'],'교통수단':['철도','버스','항공','선박','자가용','공무용차량','무료교통','택시','기타'],
        '좌석등급':['일반실','특실','1등급','2등급','이코노미','프리미엄이코노미','비즈니스','일등석'],
        '근무지 판정':['자동','근무지 내','근무지 외'],'유종':list(load_rules()['fuel_efficiency']),
        '종류':special_options(),'환율종류':['현찰 매입(출장자 구매)','카드 결제','수동 공식환율'],
        '동행조정등급':['',*GROUPS], '마일리지처리':['사용 없음','보너스항공권','좌석승급']}
    options['결제수단']=['개인카드','현금','국내원화예약']
    for col,vals in options.items():
        if col in configs:configs[col]=st.column_config.SelectboxColumn(col,options=vals)
    left,right=st.columns([2,1])
    with left:
        advanced=st.toggle('상세 항목',key=key(trip,attr+'_all'),help='감액·지원금·승인 등 모든 입력 항목을 표시합니다.')
    with right:
        if help_text:
            with st.popover('입력 안내',width='stretch'):st.write(help_text)
    data=st.data_editor(df,num_rows='dynamic',hide_index=True,width='stretch',column_config=configs,
        column_order=list(template) if advanced else visible,key=key(trip,attr+'_editor'),height=min(420,max(180,(len(rows)+2)*38+20)))
    # 빈 추가 행만 제거한다. 불리언·0원·미입력은 서로 구분하여 보존한다.
    clean=[]
    for record in data.to_dict('records'):
        r={k:(v if isinstance(v,bool) else '' if pd.isna(v) else str(v)) for k,v in record.items()}
        if any(str(r.get(k,'')).strip() for k in template if not isinstance(template[k],bool)):
            clean.append(r)
    setattr(trip,attr,clean)

def special_options():
    return ['비자발급비','예방접종비','여행자보험','풍토병예방약','법정감염병검사',
            '국내 이전비','국외 이전비','국내 가족여비','국외 가족여비','상시출장 월액','상시출장 일액',
            '국내 사망자 여비','퇴직·휴직 여비','사무인계 여비','국외 사망자 수습','유족 귀국','기타 특례']

def base_page(trip,store):
    with st.container(border=True,key='trip_overview'):
        section_heading(1,'어떤 출장인가요?')
        kind=st.segmented_control('출장 유형',['국내','국외','특수'],default=trip.kind,key=key(trip,'kind'),width='stretch')
        if kind:trip.kind=kind
        text_input(trip,'출장명')
        text_input(trip,'출장목적',True)
    with st.container(border=True,key='traveler_card'):
        section_heading(2,'출장자')
        c1,c2=st.columns([1,1.45])
        with c1:text_input(trip,'성명')
        with c2:text_input(trip,'소속기관')
        choose(trip,'지급등급',GROUPS)
        with st.expander('부서·직위 및 지급기준'):
            c1,c2=st.columns(2)
            with c1:text_input(trip,'부서')
            with c2:text_input(trip,'직위직급')
            check(trip,'공무원')
            text_input(trip,'별표1세부구분')
            if not trip.meta.get('공무원',True):
                choose(trip,'별표9기준',['공무원의 배우자','사립학교 교원','공공기관 임원','공공기관 직원','민간기업 임직원','그 밖의 사람'])
                text_input(trip,'비공무원등급근거')
                if st.button('별표 9 등급 적용',key=key(trip,'apply_grade')):
                    mapping={'공공기관 임원':'제1호라','공공기관 직원':'제2호'}
                    if trip.meta.get('별표9기준') in mapping:
                        trip.meta['지급등급']=mapping[trip.meta['별표9기준']]
                        st.session_state.pop(key(trip,'지급등급'),None)
                        st.rerun()
                    else:st.info('준용 대상 또는 기관에서 결정한 지급등급을 선택해 주세요.')
            if st.button('다음 출장에도 이 정보 사용',key=key(trip,'profile'),type='tertiary'):
                store.set_preference('출장자',{k:trip.meta.get(k,'') for k in ['성명','소속기관','부서','직위직급','지급등급','별표1세부구분']})
                st.toast('출장자 기본정보를 저장했어요.')
    with st.container(border=True,key='schedule_card'):
        section_heading(3,'일정과 이동')
        start=datetime.fromisoformat(trip.meta['시작일시']);end=datetime.fromisoformat(trip.meta['종료일시'])
        c1,c2=st.columns(2)
        with c1:
            sd=st.date_input('출발일',value=start.date(),key=key(trip,'sd'))
            stime=st.time_input('출발시간',value=start.time(),key=key(trip,'st'))
        with c2:
            ed=st.date_input('복귀일',value=end.date(),key=key(trip,'ed'))
            etime=st.time_input('복귀시간',value=end.time(),key=key(trip,'et'))
        trip.meta['시작일시']=datetime.combine(sd,stime,ZoneInfo('Asia/Seoul')).isoformat()
        trip.meta['종료일시']=datetime.combine(ed,etime,ZoneInfo('Asia/Seoul')).isoformat()
        st.markdown(f'<div class="duration"><span>{max(0,(ed-sd).days+1)}일 일정</span><span>최대 {max(0,(ed-sd).days)}박</span><span>한국시간 기준</span></div>',unsafe_allow_html=True)
        c1,c2=st.columns(2)
        with c1:text_input(trip,'출발지')
        with c2:text_input(trip,'출장지')
        with st.expander('근무지·경유지 및 세부 일정'):
            c1,c2=st.columns(2)
            with c1:text_input(trip,'근무지')
            with c2:text_input(trip,'경유지')
            if trip.kind=='국외':
                text_input(trip,'현지시간대');text_input(trip,'현지 출발복귀일정')
        check(trip,'출장승인')
    with st.expander('비고·기지급액 및 마일리지'):
        text_input(trip,'비고',True)
        text_input(trip,'기지급액')
        text_input(trip,'공적마일리지 절약운임(원)')
        check(trip,'마일리지증빙확인')
        text_input(trip,'마일리지증빙자료')

def generate_schedule(trip):
    start=datetime.fromisoformat(trip.meta['시작일시']);end=datetime.fromisoformat(trip.meta['종료일시'])
    if end<start:st.error('복귀일시는 출발일시 이후로 입력하세요.');return
    if (end-start).days>730:st.error('일정 자동 생성은 730일 이내로 지정하세요.');return
    trip.days=[{**DAY,'일자':str(start.date()+timedelta(days=i)),
                '국가':trip.meta.get('미열거국가','') if trip.meta.get('기본국가')=='직접 입력' else trip.meta.get('기본국가','대한민국' if trip.kind=='국내' else ''),
                '도시':trip.meta.get('기본도시',''),
                '출장시간(h)':str(Decimal(str((end-start).total_seconds()))/3600) if start.date()==end.date() else '',
                '도착다음날기산일수':str(i)} for i in range((end.date()-start.date()).days+1)]
    trip.lodgings=[{**LODGING,'숙박일':str(start.date()+timedelta(days=i)),
                    '국가':trip.meta.get('미열거국가','') if trip.meta.get('기본국가')=='직접 입력' else trip.meta.get('기본국가','대한민국' if trip.kind=='국내' else ''),
                    '도시':trip.meta.get('기본도시',''),'통화':'USD' if trip.kind=='국외' else 'KRW'}
                    for i in range((end.date()-start.date()).days)]
    # 새 editor 키를 사용하여 이전 표의 편집 패치와 자동 생성 데이터가 섞이지 않도록 한다.
    for attr in ['days','lodgings']:st.session_state.pop(key(trip,attr+'_editor'),None)
    st.success('일정과 숙박 행을 생성했습니다. 개인 일정·이동일·타지역 체재와 실제 숙박을 수정하세요.')

def calculation_page(trip,overseas):
    desired='국외' if overseas else '국내'
    if trip.kind!=desired:
        st.caption(f'현재 출장 유형은 {trip.kind}입니다. 출장 정보에서 유형을 {desired}로 변경해 주세요.')
    with st.container(border=True,key='destination_card'):
        section_heading(1,'방문 장소와 일정')
        if overseas:
            c1,c2=st.columns(2)
            with c1:
                countries=['']+sorted(load_rules()['countries'])+['싱가포르','직접 입력']
                choose(trip,'기본국가',countries)
                if trip.meta.get('기본국가')=='직접 입력':text_input(trip,'미열거국가')
            with c2:text_input(trip,'기본도시')
            if trip.meta.get('기본국가') and trip.meta.get('기본도시'):
                grade,reason=destination(trip.meta.get('미열거국가','') if trip.meta.get('기본국가')=='직접 입력' else trip.meta.get('기본국가',''),trip.meta.get('기본도시',''))
                st.caption(f'지역 등급 {grade or "확인 필요"} · {reason}')
            with st.expander('숙박 정산 방식'):
                choose(trip,'숙박정산방식',['실비','할인정액'])
                if trip.meta.get('숙박정산방식')=='할인정액':
                    check(trip,'할인정액승인');text_input(trip,'할인정액승인근거')
                    st.caption('무료 숙박을 제외한 전체 숙박에 85% 할인정액을 적용합니다.')
        else:
            trip.meta['기본국가']='대한민국'
            text_input(trip,'기본도시')
            with st.expander('통합특별시 행정구역 기준'):
                check(trip,'통합특별시 해당')
                if trip.meta.get('통합특별시 해당'):text_input(trip,'종전 근무지 시군')
        if st.button('일정·숙박 자동 생성' if not trip.days else '일정·숙박 다시 생성',key=key(trip,'generate'),
                     icon=':material/calendar_add_on:',type='primary' if not trip.days else 'secondary',width='stretch'):
            generate_schedule(trip)
        if trip.days:st.caption(f'일정 {len(trip.days)}일 · 숙박 {len(trip.lodgings)}박 입력됨. 다시 생성하면 기존 일정과 숙박 행이 바뀝니다.')
    tabs=st.tabs(['일정','숙박','교통','환율','증빙'] if overseas else ['일정','숙박','교통','증빙'])
    with tabs[0]:
        editor(trip,'days',DAY,
            ['일자','국가','도시','업무일정','이동일정','여비인정일','공무용차량','도착다음날기산일수','식비지원액'] if overseas else
            ['일자','도시','업무일정','동일행정구역','왕복거리(km)','거리출처','출장시간(h)','공무용차량','도착다음날기산일수'],
            '표 아래 + 행에서 일정 추가·삭제. 하루 여러 근무지 내 출장은 하나로 합산합니다. 세부 열에서 제공 식사 조정액·근거, 도서·행정구역 예외, 날짜변경선 근거를 입력합니다.')
        if overseas:
            st.caption('국가 간 이동일·출귀국일은 해당 일자의 지급기준 국가와 도시를 지정하세요. 날짜변경선으로 반복·추가되는 인정일에는 별도 근거를 기록하세요.')
    with tabs[1]:
        editor(trip,'lodgings',LODGING,['숙박일','국가','도시','실제지출액','통화','결제수단','카드청구원화액','1USD당현지통화','현지환율기준일','현지환율출처','증빙확인'] if overseas else ['숙박일','도시','지역구분','실제지출액','통화','무료숙박','증빙확인','초과신청','승인','승인근거'],
            '1박당 1행. 실제 숙박하지 않은 행은 삭제하거나 실제숙박을 해제하세요. 할인액은 할인 전 지출액을 입력했을 때만 기록합니다. 결제 순액을 입력했다면 할인액을 중복 차감하지 마세요.')
        if overseas:st.caption('현지 카드 숙박은 수수료 포함 카드청구 원화액과 신청 당시 1USD당 현지통화 환율을 입력합니다. 국내 원화 예약은 통화 KRW로 입력합니다. 현금은 세부 열의 사용 사유가 필요합니다.')
    with tabs[2]:
        editor(trip,'transports',TRANSPORT,['일자','교통수단','출발지','도착지','좌석등급','실제지출액','통화','기관직접결제','증빙확인'],
            '자가용 세부 열: 부득이한 사유·승인·거리·유가·출처·통행료·주차료. 일반 자가용은 법정 좌석의 대중교통 운임과 출처를 입력합니다.')
    if overseas:
        with tabs[3]:
            st.caption('금융기관 고시·환전영수증·카드 결제내역의 환율을 입력해 주세요.')
            editor(trip,'fx',FX,list(FX),'정액여비 USD는 출장자가 달러를 구매할 때의 현찰환율을 사용합니다. 기준일·출처·증빙확인이 필요합니다. 100 JPY당 고시값은 100으로 나누어 1 JPY당 원화로 입력합니다. 개별 비용에는 환율ID를 지정할 수 있습니다.')
    with tabs[-1]:editor(trip,'evidence',EVIDENCE_ROW,list(EVIDENCE_ROW),'증빙 원본의 보관 위치와 문서번호를 기록하세요. 각 비용 행의 증빙확인 상태도 표시합니다.')

def special_page(trip):
    st.caption('기존 출장에 합산하거나, 출장 유형을 특수로 선택해 별도로 계산할 수 있어요.')
    selected=st.selectbox('입력 항목 안내',special_options())
    instructions={
       '국내 이전비':'화물량은 톤입니다. 기본구간실비는 5톤까지, 초과구간실비는 5톤 초과 7.5톤까지의 분리된 견적·영수증 금액을 입력합니다.',
       '국외 이전비':'화물량은 ㎥입니다. 기본구간은 15㎥까지, 초과구간은 15㎥ 초과 25㎥까지로 분리합니다.',
       '국내 가족여비':'해당 가족의 이동구간에 대한 본인 등급 기준 운임·숙박비·일비식비와 가족의 연령·관계·동반 요건을 입력합니다.',
       '국외 가족여비':'국외지급사유는 별표 6의2 제1~8호입니다. 제7·8호는 운임만 지급합니다. 제3·4호의 국내 체류 중 여비는 국내 가족여비로 별도 산출합니다.',
       '상시출장 월액':'대상호 1~4, 기관확정월액·인정출장일수·기관지급기준을 입력합니다. 법령에는 기관별 확정 금액이 없습니다.',
       '상시출장 일액':'대상호 5~7, 기관확정일액·인정출장일수·기관지급기준을 입력합니다.',
       '국내 사망자 여비':'해당 구간의 전직 상당 여비 산출근거와 금액을 입력합니다. 유족 지급 승인과 증빙이 필요합니다.'}
    with st.expander('이 항목의 입력 방법'):
        st.write(instructions.get(selected,'준비금은 실제 지출액·증빙을 입력합니다. 퇴직·휴직·국외 사망자·기타 특례는 사유별 지급요건의 자동 판정이 없어 근거 확인 필요로 남습니다.'))
    template={**SPECIAL,'종류':selected,'일자':str(trip.meta.get('시작일시',''))[:10]}
    if st.button('항목 추가',icon=':material/add:',type='primary'):
        trip.specials.append(template.copy())
        st.session_state.pop(key(trip,'specials_editor'),None)
    core=['일자','종류','실제지출액','통화','증빙확인','승인','승인근거']
    fields={
      '국내 이전비':['화물량','기본구간실비','초과구간실비','이전요건확인','발령일','이전일'],
      '국외 이전비':['화물량','기본구간실비','초과구간실비','이전요건확인','발령일','이전일'],
      '국내 가족여비':['나이','관계','가족요건확인','본인기준운임','본인기준숙박비','본인기준일비식비','본인기준산출근거'],
      '국외 가족여비':['나이','관계','독립생계','자녀예외확인','가족요건확인','국외지급사유','본인기준운임','본인기준숙박비','본인기준일비식비','본인기준준비금','본인기준산출근거'],
      '상시출장 월액':['대상호','기관확정월액','인정출장일수','기관지급기준'],
      '상시출장 일액':['대상호','기관확정일액','인정출장일수','기관지급기준'],
      '국내 사망자 여비':['전직상당구간여비','본인기준산출근거'],
      '법정감염병검사':['출입국필수']}
    editor(trip,'specials',SPECIAL,list(dict.fromkeys(core+fields.get(selected,[]))))
    with st.expander('특수 여비의 환율과 증빙'):
        editor(trip,'fx',FX,list(FX))
        editor(trip,'evidence',EVIDENCE_ROW,list(EVIDENCE_ROW))

@st.cache_data(show_spinner=False)
def documents(serialized):
    result=Result.from_dict(json.loads(serialized))
    return export_excel(result),export_word(result)

def show_result(result,downloads=False):
    with st.container(border=True,key='result_panel'):
        result_overview(result)
        if downloads:
            xlsx,docx=documents(dumps(result.to_dict()))
            title=''.join(c for c in result.trip['meta'].get('출장명','출장') if c.isalnum() or c in '_-')[:35]
            stamp=result.generated_at[:10].replace('-','')
            name=f'{result.trip["kind"]}출장_출장비정산서_{stamp}_{title}_{result.trip["id"]}'
            c1,c2=st.columns(2)
            c1.download_button('Excel 다운로드',xlsx,name+'.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',width='stretch',type='primary',icon=':material/table_view:')
            c2.download_button('Word 다운로드',docx,name+'.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document',width='stretch',icon=':material/description:')
    with st.container(border=True,key='result_details'):
        totals,detail,checks=st.tabs(['항목별 내역','계산 근거',f'확인 사항 {len(result.issues)}'])
        with totals:
            rows=[{k:money(v) if k!='항목' else v for k,v in r.items()} for r in result.summary()]
            st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
            st.caption('모든 정산서에 입력 내역과 계산 근거가 함께 기록됩니다.')
        with detail:
            for cat in CATEGORIES:
                items=[r for r in result.lines if r.category==cat]
                with st.expander(f'{cat} · {len(items)}건'):
                    if not items:st.caption('입력된 내역이 없어요.')
                    for r in items:
                        st.markdown(f'**{r.date} {r.name}** · {money(r.amount)} · {r.status}')
                        st.caption(r.formula+' / '+r.reference+' / '+r.rule_version)
                        if r.notes:st.write(r.notes)
                        for url in r.source.split('\n'):st.markdown(f'[공식 원문]({url})')
        with checks:
            if result.issues:
                for issue in result.issues:st.write('• '+issue)
            else:st.caption('추가로 확인할 항목이 없어요.')
            st.dataframe(pd.DataFrame(deadlines(result)),hide_index=True,width='stretch')
        if downloads:
            with st.expander('전체 기록 백업'):
                st.caption('입력값·계산 결과·적용 법령을 한 파일로 보관합니다.')
                st.download_button('JSON 백업 다운로드',dumps(result.to_dict()),name+'.json','application/json')

def saved_page(store):
    query=st.text_input('출장명 검색',placeholder='찾고 싶은 출장명을 입력하세요.',label_visibility='collapsed')
    rows=store.list(query)
    if not rows:
        empty_state('아직 저장된 출장이 없어요.','출장 정보를 입력한 뒤 저장하면 이곳에서 다시 볼 수 있어요.')
        st.button('출장 정보 입력',on_click=navigate,args=('새 출장 등록',),type='primary')
        return
    st.dataframe(pd.DataFrame(rows,columns=['식별자','출장명','유형','저장일시'])[['출장명','유형','저장일시']],hide_index=True,width='stretch')
    chosen=st.selectbox('출장 선택',rows,format_func=lambda r:f'{r[1]} · {r[2]} · {r[3]}')[0]
    trip,result=store.load(chosen)
    c1,c2,c3=st.columns(3)
    if c1.button('입력 불러오기',width='stretch'):
        st.session_state.trip=trip;st.session_state.original_rules=result.rule_snapshot
        st.session_state.use_original_rules=True
        st.session_state.loaded_result=result
        st.rerun()
    if c2.button('복사하여 신규 생성',width='stretch'):
        st.session_state.trip=store.copy(chosen)
        st.session_state.use_original_rules=False
        st.rerun()
    if c3.button('이 출장 삭제',width='stretch'):
        store.delete(chosen);st.rerun()
    st.caption('아래는 저장 당시 결과입니다. 저장 당시 법령·환율을 그대로 사용하여 정산서를 재생성합니다.')
    show_result(result,True)

def rules_page():
    rules=load_rules()
    st.caption('자료 기준일 '+rules['as_of']+' / 규칙 버전 '+rules['version'])
    version=st.selectbox('법령 시행본',rules['law_versions'],format_func=lambda r:r['id']+' '+r['number'])
    st.markdown(f'[국가법령정보센터 원문]({version["url"]})')
    no=st.selectbox('별표',['1','2','3','4','5','6의2','8','9'])
    st.text_area('공식 별표 전문',version['annexes'][no],height=360)
    for g in rules['guidelines']:st.markdown(f'[{g["id"]} {g["number"]}]({g["url"]})')
    country=st.text_input('국가·도시 기준 검색')
    rows=[{'국가':c,**v} for c,v in rules['countries'].items()]+rules['cities']
    st.dataframe(pd.DataFrame([r for r in rows if country in str(r)]),hide_index=True,width='stretch')
    group=st.selectbox('국외 지급등급 조회',GROUPS)
    st.dataframe(pd.DataFrame(rules['overseas_rates'][group]).T, width='stretch')
    st.info('미열거 국가를 라등급으로 가정하지 않습니다. 별표 4 비고 3에 따라 예정지에서 가장 가까운 수도가 있는 국가와 거리 근거를 입력해야 합니다.')
    st.markdown('상세 적용 범위와 미지원 사유는 저장소의 **docs/법령과계산기준.md**, **docs/지원범위.md**에 기록되어 있습니다.')

def settings_page(trip,store):
    st.caption('계산과 문서 생성은 인터넷 연결 없이 사용할 수 있어요.')
    loaded=st.session_state.get('original_rules')
    st.session_state.use_original_rules=st.checkbox('불러온 출장의 저장 당시 법령 자료집 사용',value=st.session_state.get('use_original_rules',False),disabled=loaded is None)
    choice=st.radio('재계산 기준',['출장일 기준','지정일 기준 재계산'],index=0 if trip.settings.get('기준 선택')!='지정일 기준 재계산' else 1)
    trip.settings['기준 선택']=choice
    if choice=='지정일 기준 재계산':
        basis=st.date_input('비교용 법령 기준일',value=date.fromisoformat(load_rules()['as_of']))
        trip.settings['재계산 기준일']=str(basis)
        st.info('지정일 기준은 비교 계산입니다. 실제 청구에는 출장일 당시 시행 규정이 적용됩니다.')
    upload=st.file_uploader('JSON 백업에서 불러오기',type=['json'])
    if upload and st.button('백업 가져오기'):
        try:
            raw=json.loads(upload.getvalue())
            t=Trip.from_dict(raw.get('trip',raw));t.id=uuid4().hex[:12]
            st.session_state.trip=t
            if raw.get('rule_snapshot'):
                st.session_state.original_rules=raw['rule_snapshot'];st.session_state.use_original_rules=True
            st.rerun()
        except (ValueError,KeyError,TypeError):st.error('이 프로그램에서 내보낸 출장 백업 JSON을 선택하세요.')
    if store.path.exists():st.download_button('SQLite 전체 기록 백업',store.path.read_bytes(),'출장비기록.sqlite3','application/vnd.sqlite3')

def start_new(store):
    st.session_state.trip=default_trip(store)
    st.session_state.use_original_rules=False
    navigate('새 출장 등록')

def save_trip(store,trip,result):
    store.save(trip,result)
    st.toast('출장 내역을 저장했어요.')

def run():
    st.set_page_config(page_title='바른여비 · 공무 출장 정산',page_icon=':material/work_outline:',layout='wide')
    apply_theme()
    store=Store()
    if 'trip' not in st.session_state:st.session_state.trip=default_trip(store)
    trip=st.session_state.trip
    with st.sidebar:
        brand()
        st.button('새 출장',icon=':material/add:',type='primary',width='stretch',on_click=start_new,args=(store,))
        st.markdown('<div class="nav-label">출장 관리</div>',unsafe_allow_html=True)
        page=st.radio('메뉴',PAGES,label_visibility='collapsed',format_func=lambda p:PAGE_INFO[p][2],key='navigation')
        st.divider()
        with st.expander('예시로 시작하기'):
            files=sorted((Path(__file__).resolve().parents[1]/'examples').glob('*.json'))
            if files:
                selected=st.selectbox('예시',files,format_func=lambda p:p.stem)
                if st.button('예시 불러오기',width='stretch'):
                    loaded=Trip.from_dict(json.loads(selected.read_text(encoding='utf-8')))
                    loaded.id=uuid4().hex[:12]
                    st.session_state.trip=loaded
                    st.session_state.use_original_rules=False
                    st.rerun()
        st.markdown('<div class="sidebar-note">기록은 이 기기에 저장돼요.<br>지급 기준 '+escape(load_rules()['as_of'])+'</div>',unsafe_allow_html=True)
    page_header(page)
    if page=='저장된 출장 내역':
        with st.container(border=True,key='saved_panel'):saved_page(store)
        return
    if page=='법령 및 지급 기준 안내':
        with st.container(border=True,key='rules_panel'):rules_page()
        return
    if page=='프로그램 설정':
        with st.container(border=True,key='settings_panel'):settings_page(trip,store)
    if page in PAGES[:4]:
        with st.container(key='workspace_columns'):
            main,aside=st.columns([2.5,1],gap='large')
            with main:
                with st.container(key='content_column'):
                    if page=='새 출장 등록':base_page(trip,store)
                    elif page=='국내 출장 계산':calculation_page(trip,False)
                    elif page=='국외 출장 계산':calculation_page(trip,True)
                    else:
                        with st.container(border=True,key='special_panel'):special_page(trip)
                    next_page=('국외 출장 계산' if trip.kind=='국외' else '특수 여비 계산' if trip.kind=='특수' else '국내 출장 계산') if page=='새 출장 등록' else '계산 결과 및 정산서'
                    st.button('비용 입력으로 계속' if page=='새 출장 등록' else '정산서 보기',on_click=navigate,args=(next_page,),
                              width='stretch',type='primary',icon=':material/arrow_forward:')
    try:
        result=calculate(trip,st.session_state.get('original_rules') if st.session_state.get('use_original_rules') else None)
        st.session_state.current_result=result
    except (ValueError,KeyError,TypeError,ArithmeticError) as e:
        st.error('입력값을 확인하세요. '+str(e));return
    if page=='계산 결과 및 정산서':
        show_result(result,True)
        st.button('출장 저장',on_click=save_trip,args=(store,trip,result),icon=':material/bookmark_add:')
    elif page in PAGES[:4]:
        with aside:
            with st.container(key='summary_column'):
                with st.container(border=True,key='summary_panel'):
                    summary_html(result)
                    st.button('출장 저장',on_click=save_trip,args=(store,trip,result),width='stretch',icon=':material/bookmark_add:')
                st.markdown('<div class="footer-note">입력한 내용으로 자동 계산돼요.</div>',unsafe_allow_html=True)
    elif page=='프로그램 설정':
        st.button('설정과 출장 저장',on_click=save_trip,args=(store,trip,result),type='primary')
