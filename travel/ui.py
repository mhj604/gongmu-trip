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

def text_input(trip,label,area=False):
    f=st.text_area if area else st.text_input
    trip.meta[label]=f(label,value=str(trip.meta.get(label,'')),key=key(trip,label))

def check(trip,label):
    trip.meta[label]=st.checkbox(label,value=bool(trip.meta.get(label,False)),key=key(trip,label))

def choose(trip,label,options):
    previous=trip.meta.get(label,options[0])
    trip.meta[label]=st.selectbox(label,options,index=options.index(previous) if previous in options else 0,key=key(trip,label))

def editor(trip,attr,template,visible,help_text=''):
    if help_text:st.caption(help_text)
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
    advanced=st.checkbox('세부 입력 열 모두 보기',key=key(trip,attr+'_all'))
    data=st.data_editor(df,num_rows='dynamic',hide_index=True,width='stretch',column_config=configs,
        column_order=list(template) if advanced else visible,key=key(trip,attr+'_editor'))
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
    st.subheader('출장 기본정보')
    kind=st.segmented_control('출장 유형',['국내','국외','특수'],default=trip.kind,key=key(trip,'kind'))
    if kind:trip.kind=kind
    c1,c2=st.columns(2)
    with c1:
        for name in ['성명','소속기관','부서','직위직급']:text_input(trip,name)
        choose(trip,'지급등급',GROUPS)
    with c2:
        text_input(trip,'출장명');text_input(trip,'출장목적',True)
        check(trip,'공무원');check(trip,'출장승인')
    with st.expander('지급등급과 비공무원 기준'):
        st.caption('제1호 세부 구분은 법령 안내의 별표 1 원문을 기준으로 선택합니다.')
        text_input(trip,'별표1세부구분')
        if not trip.meta.get('공무원',True):
            choose(trip,'별표9기준',['공무원의 배우자','사립학교 교원','공공기관 임원','공공기관 직원','민간기업 임직원','그 밖의 사람'])
            text_input(trip,'비공무원등급근거')
            if st.button('별표 9의 명시된 등급 적용',key=key(trip,'apply_grade')):
                mapping={'공공기관 임원':'제1호라','공공기관 직원':'제2호'}
                if trip.meta.get('별표9기준') in mapping:
                    grade=mapping[trip.meta['별표9기준']]
                    trip.meta['지급등급']=grade
                    st.session_state.pop(key(trip,'지급등급'),None)
                    st.rerun()
                else:st.info('배우자·교원은 준용 대상의 등급을 선택하고, 그 밖의 사람은 기관 결정 등급을 입력하세요.')
    st.subheader('기간과 장소')
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
    st.caption(f'한국시간 기준 {max(0,(ed-sd).days+1)}일 · 달력상 최대 {max(0,(ed-sd).days)}박. 실제 숙박은 숙박 내역에서 수정합니다.')
    c1,c2=st.columns(2)
    with c1:
        for name in ['출발지','근무지','경유지']:text_input(trip,name)
    with c2:
        for name in ['출장지','현지시간대','현지 출발복귀일정']:text_input(trip,name)
    text_input(trip,'비고',True)
    with st.expander('지급 조정 및 공적 마일리지'):
        text_input(trip,'기지급액')
        text_input(trip,'공적마일리지 절약운임(원)')
        check(trip,'마일리지증빙확인')
        text_input(trip,'마일리지증빙자료')
    if st.button('출장자 기본값으로 저장',key=key(trip,'profile')):
        store.set_preference('출장자',{k:trip.meta.get(k,'') for k in ['성명','소속기관','부서','직위직급','지급등급','별표1세부구분']})
        st.success('출장자 기본값을 저장했습니다.')

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
    st.subheader('국외 출장 계산' if overseas else '국내 출장 계산')
    desired='국외' if overseas else '국내'
    if trip.kind!=desired:
        st.info(f'현재 출장 유형은 {trip.kind}입니다. 기본정보에서 {desired}를 선택하면 이 화면의 입력으로 계산됩니다.')
    c1,c2=st.columns(2)
    with c1:
        countries=sorted(load_rules()['countries'])+['싱가포르','직접 입력'] if overseas else ['대한민국']
        choose(trip,'기본국가',countries)
        if trip.meta.get('기본국가')=='직접 입력':text_input(trip,'미열거국가')
    with c2:text_input(trip,'기본도시')
    if not overseas:
        check(trip,'통합특별시 해당')
        if trip.meta.get('통합특별시 해당'):text_input(trip,'종전 근무지 시군')
    else:
        grade,reason=destination(trip.meta.get('미열거국가') if trip.meta.get('기본국가')=='직접 입력' else trip.meta.get('기본국가',''),trip.meta.get('기본도시',''))
        st.caption(f'지역 등급: {grade or "근거 확인 필요"} · {reason}')
        choose(trip,'숙박정산방식',['실비','할인정액'])
        if trip.meta.get('숙박정산방식')=='할인정액':
            check(trip,'할인정액승인');text_input(trip,'할인정액승인근거')
            st.caption('해당 출장 전체 숙박에 85% 할인정액을 적용합니다. 무료 숙박은 제외하며 실비와 혼합하지 않습니다.')
    if st.button('날짜별 일정·숙박 자동 생성',key=key(trip,'generate')):
        generate_schedule(trip)
    tabs=st.tabs(['일별 일정','숙박비','교통비','환율','증빙 목록'])
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
    with tabs[3]:
        st.info('환율은 자동으로 가정하지 않습니다. 금융기관 고시·환전영수증·카드 결제내역의 수치와 출처를 입력하세요. 100 JPY당 고시값은 100으로 나누어 1 JPY당 원화로 입력합니다.')
        editor(trip,'fx',FX,list(FX),'정액여비 USD는 출장자가 달러를 구매할 때의 현찰환율을 사용합니다. 환율 종류·기준일·출처·증빙확인이 모두 필요합니다. 개별 비용에 환율ID를 지정할 수 있습니다.')
    with tabs[4]:editor(trip,'evidence',EVIDENCE_ROW,list(EVIDENCE_ROW),'증빙 원본은 기기에 보관하고 파일 경로·문서번호를 기록합니다. 각 비용 행의 증빙확인 상태도 표시하세요.')

def special_page(trip):
    st.subheader('특수 여비')
    st.caption('정액 출장과 함께 입력하면 합산됩니다. 특수 여비만 계산할 때는 기본정보의 출장 유형을 특수로 선택하세요.')
    selected=st.selectbox('입력 항목 안내',special_options())
    instructions={
       '국내 이전비':'화물량은 톤입니다. 기본구간실비는 5톤까지, 초과구간실비는 5톤 초과 7.5톤까지의 분리된 견적·영수증 금액을 입력합니다.',
       '국외 이전비':'화물량은 ㎥입니다. 기본구간은 15㎥까지, 초과구간은 15㎥ 초과 25㎥까지로 분리합니다.',
       '국내 가족여비':'해당 가족의 이동구간에 대한 본인 등급 기준 운임·숙박비·일비식비와 가족의 연령·관계·동반 요건을 입력합니다.',
       '국외 가족여비':'국외지급사유는 별표 6의2 제1~8호입니다. 제7·8호는 운임만 지급합니다. 제3·4호의 국내 체류 중 여비는 국내 가족여비로 별도 산출합니다.',
       '상시출장 월액':'대상호 1~4, 기관확정월액·인정출장일수·기관지급기준을 입력합니다. 법령에는 기관별 확정 금액이 없습니다.',
       '상시출장 일액':'대상호 5~7, 기관확정일액·인정출장일수·기관지급기준을 입력합니다.',
       '국내 사망자 여비':'해당 구간의 전직 상당 여비 산출근거와 금액을 입력합니다. 유족 지급 승인과 증빙이 필요합니다.'}
    st.info(instructions.get(selected,'준비금은 실제 지출액·증빙을 입력합니다. 퇴직·휴직·국외 사망자·기타 특례는 사유별 지급요건의 자동 판정이 없어 근거 확인 필요로 남습니다.'))
    template={**SPECIAL,'종류':selected,'일자':str(trip.meta.get('시작일시',''))[:10]}
    if st.button('선택한 특수 여비 입력 행 추가'):
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
    st.subheader('정산 결과')
    if result.issues:st.info('미확정·누락 항목이 있습니다. 아래 금액은 확정된 항목만 합산합니다.')
    st.metric(status_label(result),money(result.claim))
    c1,c2,c3=st.columns(3)
    c1.metric('확정 인정액',money(result.recognized));c2.metric('미확정 산정액',money(result.pending));c3.metric('기지급액',money(result.advance))
    if result.refund:st.caption('반납예정액 '+money(result.refund))
    rows=[]
    for r in result.summary():rows.append({k:money(v) if k!='항목' else v for k,v in r.items()})
    st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
    for cat in CATEGORIES:
        items=[r for r in result.lines if r.category==cat]
        with st.expander(f'{cat} 계산식과 적용 근거 · {len(items)}건'):
            for r in items:
                st.markdown(f'**{r.date} {r.name}** · {money(r.amount)} · {r.status}')
                st.caption(r.formula+' / '+r.reference+' / '+r.rule_version)
                if r.notes:st.write(r.notes)
                for url in r.source.split('\n'):st.markdown(f'[공식 원문]({url})')
    with st.expander('미입력·증빙·승인 및 정산기한',expanded=bool(result.issues)):
        for issue in result.issues:st.write('• '+issue)
        st.dataframe(pd.DataFrame(deadlines(result)),hide_index=True)
    if downloads:
        xlsx,docx=documents(dumps(result.to_dict()))
        title=''.join(c for c in result.trip['meta'].get('출장명','출장') if c.isalnum() or c in '_-')[:35]
        stamp=result.generated_at[:10].replace('-','')
        name=f'{result.trip["kind"]}출장_출장비정산서_{stamp}_{title}_{result.trip["id"]}'
        c1,c2=st.columns(2)
        c1.download_button('Excel 정산서 다운로드',xlsx,name+'.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',width='stretch')
        c2.download_button('Word 정산서 다운로드',docx,name+'.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document',width='stretch')
        st.download_button('입력·결과·법령 스냅샷 JSON 백업',dumps(result.to_dict()),name+'.json','application/json')
        st.caption('출력 문서는 위 계산 결과의 원본 입력 전체, 계산식, 상태, 근거, 환율을 포함합니다.')

def saved_page(store):
    st.subheader('저장된 출장 내역')
    query=st.text_input('출장명 검색')
    rows=store.list(query)
    if not rows:st.info('저장된 출장 내역이 없습니다.');return
    st.dataframe(pd.DataFrame(rows,columns=['식별자','출장명','유형','저장일시']),hide_index=True)
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
    st.subheader('법령 및 지급 기준 안내')
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
    st.subheader('프로그램 설정')
    st.caption('기본 계산·저장·문서 생성은 인터넷 연결 없이 동작합니다. 첫 설치 때는 의존성 다운로드가 필요합니다.')
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

def run():
    st.set_page_config(page_title='바른여비 · 공무 출장 정산',page_icon='🧾',layout='wide')
    st.markdown('''<style>
      .stApp { background:#f7f9fc; color:#26374c; }
      [data-testid="stSidebar"] {background:#edf2f7;}
      h1,h2,h3 { color:#182f4d; letter-spacing:-.035em; }
      .block-container { padding-top:2.3rem; max-width:1480px; }
      [data-testid="stMetric"] { background:white; border:1px solid #e0e7ef; padding:1rem 1.2rem; border-radius:12px; }
      [data-testid="stMetricValue"] { color:#087f8c; }
      .stButton>button,.stDownloadButton>button { border-radius:8px; }
      div[data-testid="stDataFrame"] { background:white; border-radius:8px; }
      .eyebrow {color:#087f8c;font-size:12px;font-weight:700;letter-spacing:.13em;}
      @media(max-width:700px){.block-container{padding:1rem;}}
      </style>''',unsafe_allow_html=True)
    store=Store()
    if 'trip' not in st.session_state:st.session_state.trip=default_trip(store)
    trip=st.session_state.trip
    with st.sidebar:
        st.markdown('## 바른여비')
        st.caption('공무 출장비 통합 정산')
        page=st.radio('메뉴',PAGES,label_visibility='collapsed')
        st.divider()
        st.caption('법령 자료 기준 '+load_rules()['as_of'])
        if st.button('새 출장으로 초기화',width='stretch'):
            st.session_state.trip=default_trip(store)
            st.session_state.use_original_rules=False
            st.rerun()
        st.caption('모든 기록은 이 컴퓨터의 SQLite에 저장됩니다.')
        with st.expander('가상 예시 불러오기'):
            files=sorted((Path(__file__).resolve().parents[1]/'examples').glob('*.json'))
            if files:
                selected=st.selectbox('예시',files,format_func=lambda p:p.stem)
                if st.button('예시 입력 사용'):
                    loaded=Trip.from_dict(json.loads(selected.read_text(encoding='utf-8')))
                    loaded.id=uuid4().hex[:12]
                    st.session_state.trip=loaded
                    st.session_state.use_original_rules=False
                    st.rerun()
    st.markdown('<div class="eyebrow">OFFICIAL TRAVEL EXPENSES</div>',unsafe_allow_html=True)
    st.title('출장의 시작부터 정산까지')
    st.caption('국가공무원 여비 규정에 따른 국내·국외 출장 계산과 정산서')
    if page=='새 출장 등록':base_page(trip,store)
    elif page=='국내 출장 계산':calculation_page(trip,False)
    elif page=='국외 출장 계산':calculation_page(trip,True)
    elif page=='특수 여비 계산':special_page(trip)
    elif page=='저장된 출장 내역':saved_page(store);return
    elif page=='법령 및 지급 기준 안내':rules_page();return
    elif page=='프로그램 설정':settings_page(trip,store)
    try:
        result=calculate(trip,st.session_state.get('original_rules') if st.session_state.get('use_original_rules') else None)
        st.session_state.current_result=result
    except (ValueError,KeyError,TypeError,ArithmeticError) as e:
        st.error('입력값을 확인하세요. '+str(e));return
    if page=='계산 결과 및 정산서':
        show_result(result,True)
    else:
        st.divider()
        c1,c2,c3=st.columns(3)
        c1.metric(status_label(result),money(result.claim))
        c2.metric('일정 / 숙박 입력',f'{len(trip.days)}일 / {len(trip.lodgings)}박')
        c3.metric('확인할 항목',f'{len(result.issues)}건')
        st.caption('입력 변경 시 자동 재계산 · 상세 근거와 문서 다운로드는 계산 결과 및 정산서 메뉴에서 확인하세요.')
    if st.button('출장 내역 저장',type='primary',width='stretch'):
        store.save(trip,result)
        st.success('입력, 계산 결과, 환율과 적용 법령 자료집을 함께 저장했습니다.')
