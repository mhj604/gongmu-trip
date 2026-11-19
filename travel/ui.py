"""필수 입력과 결과를 한 화면에 모은 출장비 계산기."""
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from html import escape
from uuid import uuid4
from zoneinfo import ZoneInfo
import json
import pandas as pd
import streamlit as st
from .models import *
from .rules import load_rules
from .storage import Store
from .excel import export_excel
from .word import export_word
from .quick import build_schedule, calculate_preview
from .fuel_prices import FuelQuote, FuelPriceError, fetch_quote, product_for, apply_quote
from .money_input import amount_input
from .batch import BatchResult, calculate_batch
from .batch_documents import export_batch_excel, export_batch_word
from .ui_theme import apply_theme, scroll_to_inputs
from .shared_lodging import allocation, SCOPE_NOTE

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
LODGING.update({'숙박정산대상ID':'','숙박정산대상':'','숙박지급등급':''})
TRANSPORT={'일자':'','교통수단':'철도','출발지':'','도착지':'','좌석등급':'일반실','실제지출액':'','통화':'KRW',
           '할인액':'','기관부담액':'','지원액':'','기관직접결제':False,'증빙확인':False,'승인':False,'승인근거':'',
           '대중교통운임':'','운임출처':'','부득이한사유':'','거리(km)':'','거리출처':'','유종':'휘발유','유가':'',
           '유가출처':'','통행료':'','주차료':'','동승자':False,'마일리지처리':'사용 없음','환율ID':''}
TRANSPORT['자가용정산방식']=''
SPECIAL={'일자':'','종류':'비자발급비','실제지출액':'','통화':'KRW','할인액':'','기관부담액':'','지원액':'',
         '증빙확인':False,'승인':False,'승인근거':'','출입국필수':False,'화물량':'','기본구간실비':'','초과구간실비':'',
         '이전요건확인':False,'발령일':'','이전일':'','나이':'','관계':'배우자','독립생계':False,'자녀예외확인':False,
         '가족요건확인':False,'본인기준운임':'','본인기준숙박비':'','본인기준일비식비':'',
         '본인기준준비금':'','본인기준산출근거':'','국외지급사유':'1','대상호':'','기관지급기준':'',
         '인정출장일수':'','기관확정월액':'','기관확정일액':'','전직상당구간여비':'','환율ID':''}
FX={'환율ID':'','통화':'USD','1단위당 원화':'','기준일':'','출처':'','환율종류':'현찰 매입(출장자 구매)','증빙확인':False}
EVIDENCE_ROW={'일자':'','관련항목':'','자료명':'','문서번호':'','보관위치':'','확인완료':False,'비고':''}


def key(trip, name):
    return trip.id+'_'+name


def default_trip(store):
    today = datetime.now(ZoneInfo('Asia/Seoul')).date()
    profile = store.preference('출장자', {})
    return Trip(meta={**profile, '지급등급': profile.get('지급등급','제2호'),
                      '시작일시': f'{today}T09:00:00+09:00', '종료일시': f'{today}T18:00:00+09:00',
                      '공무원': True, '간편입력': True})


# 표의 원본은 편집 시작 때 한 번만 만든다. Enter 후 같은 원본에 편집 패치를 적용한다.
def editor(trip, attr, template, visible):
    baseline_key = key(trip, attr+'_baseline')
    # 실행 중 앱이 갱신되어 열이 추가된 경우에만 기존 입력으로 기준표를 갱신한다.
    if baseline_key in st.session_state and not set(template).issubset(st.session_state[baseline_key].columns):
        st.session_state.pop(baseline_key, None)
        st.session_state.pop(key(trip, attr+'_editor'), None)
    if baseline_key not in st.session_state:
        source = getattr(trip, attr)
        columns = list(dict.fromkeys([*template, *[k for row in source for k in row]]))
        frame = pd.DataFrame([{**template, **row} for row in source], columns=columns)
        numeric = {'실제지출액','할인액','기관부담액','지원액','왕복거리(km)','출장시간(h)',
                   '도착다음날기산일수','식비지원액','식비조정액','근거리운임','근거리식비',
                   '거리(km)','유가','통행료','주차료','대중교통운임','카드청구원화액',
                   '1USD당현지통화','1단위당 원화','식비실제지출','화물량'}
        for column in columns:
            default = template.get(column, '')
            if isinstance(default, bool):
                frame[column] = frame[column].fillna(default).astype(bool)
            elif column in numeric:
                try:
                    frame[column] = pd.to_numeric(frame[column].replace('', None), errors='raise').astype('float64')
                except (TypeError, ValueError):
                    frame[column] = frame[column].fillna('').astype(str)
            else:
                frame[column] = frame[column].fillna('').astype(str)
        st.session_state[baseline_key] = frame
    frame = st.session_state[baseline_key]
    configs = {}
    for column in frame:
        if pd.api.types.is_bool_dtype(frame[column]):
            configs[column] = st.column_config.CheckboxColumn(column, default=template.get(column, False))
        elif pd.api.types.is_numeric_dtype(frame[column]):
            configs[column] = st.column_config.NumberColumn(column, min_value=0, step=.01, format='localized')
        else:
            configs[column] = st.column_config.TextColumn(column, default=str(template.get(column, '')))
    selections = {'지역구분': ['서울','광역시','기타'], '교통수단': ['철도','버스','항공','선박','자가용','공무용차량','무료교통','택시','기타'],
                  '결제수단': ['개인카드','현금','국내원화예약'],
                  '자가용정산방식':['','대중교통 운임','연료비'], '유종':list(load_rules()['fuel_efficiency'])}
    selections['숙박지급등급'] = [''] + GROUPS
    for column, options in selections.items():
        if column in configs:
            configs[column] = st.column_config.SelectboxColumn(column, options=options, default=template.get(column, options[0]))
    data = st.data_editor(frame, num_rows='dynamic', hide_index=True, width='stretch',
                          column_config=configs, column_order=visible,
                          key=key(trip, attr+'_editor'), height=280)
    rows = []
    for record in data.to_dict('records'):
        row = {column: (template.get(column, '') if pd.isna(value) else value if isinstance(value, bool) else str(value))
               for column, value in record.items()}
        if any(str(row.get(column, '')).strip() for column in frame if not isinstance(template.get(column), bool)):
            rows.append(row)
    setattr(trip, attr, rows)


def clear_editors(trip):
    for attr in ['days','lodgings','transports','fx','evidence','specials']:
        for suffix in ['_baseline','_editor']:
            st.session_state.pop(key(trip, attr+suffix), None)


def text(trip, name, label=None):
    trip.meta[name] = st.text_input(label or name, value=str(trip.meta.get(name, '')), key=key(trip, name))


def select(trip, name, label, options, help=None):
    value = trip.meta.get(name, options[0])
    trip.meta[name] = st.selectbox(label, options, index=options.index(value) if value in options else 0, key=key(trip, name), help=help)
    return trip.meta[name]


def number(trip, name, label, default=0, help=None):
    value = trip.meta.get(name, default)
    if '원' in label:
        # 이전 버전의 숫자 위젯 상태는 새 금액 위젯의 상태와 형식이 다르다.
        state = st.session_state.get(key(trip,name))
        if state is not None and not isinstance(state,dict):
            st.session_state.pop(key(trip,name),None)
        try:
            answer = amount_input(label,value,key=key(trip,name),help=help)
        except ValueError:
            st.error(label+'에 0 이상의 숫자를 입력하세요.')
            trip.meta.setdefault('_금액입력오류',[]).append(label)
            answer = None
        trip.meta[name] = '' if answer is None else str(answer)
        return answer
    value = None if value in ('', None) else float(value)
    answer = st.number_input(label, min_value=0., value=value, step=1., format='%.15g', key=key(trip, name), help=help)
    trip.meta[name] = '' if answer is None else str(answer)
    return answer


def date_fields(trip):
    a, b = st.columns(2)
    start = datetime.fromisoformat(trip.meta['시작일시'])
    end = datetime.fromisoformat(trip.meta['종료일시'])
    with a:
        sd = st.date_input('출발일', start.date(), key=key(trip,'start'))
    with b:
        ed = st.date_input('복귀일', end.date(), key=key(trip,'end'))
    trip.meta['시작일시'] = datetime.combine(sd, start.timetz()).isoformat()
    trip.meta['종료일시'] = datetime.combine(ed, end.timetz()).isoformat()
    return (ed-sd).days


def quick_fields(trip, nights):
    if trip.kind == '국외':
        a, b = st.columns(2)
        with a:
            select(trip, '기본국가', '방문 국가', ['']+sorted(set(load_rules()['countries']) | {'싱가포르'}))
        with b:
            text(trip, '기본도시', '방문 도시')
        a, b = st.columns(2)
        with a:
            payment_group(trip)
        with b:
            number(trip, '간편환율', '환율 · 1 USD당 원화', None, '직접 입력한 환율로 예상 금액을 계산합니다.')
    else:
        a, b = st.columns(2)
        with a:
            select(trip, '간편출장범위', '출장 범위', ['근무지 외','근무지 내'],
                   help='다른 시·군이며 왕복 12km 이상이면 근무지 외, 같은 시·군이거나 왕복 12km 미만이면 근무지 내를 선택하세요.')
        with b:
            payment_group(trip)
    local = trip.kind == '국내' and trip.meta.get('간편출장범위') == '근무지 내'
    if local:
        a, b = st.columns(2)
        with a:
            number(trip, '간편시간', '하루 출장시간 (시간)', None)
        with b:
            number(trip, '간편거리', '왕복거리 (km)', None)
        if trip.meta.get('간편거리') not in ('',None) and dec(trip.meta['간편거리']) <= 2:
            a, b = st.columns(2)
            with a:
                number(trip, '간편교통비', '하루 실제 교통비 (원)')
            with b:
                number(trip, '간편근거리식비', '하루 실제 식비 (원)')
        return
    if nights > 0:
        a, b = st.columns(2)
        with a:
            number(trip, '간편숙박비', f'숙박비 합계 · {nights}박 (원)', help='출장 전체 합계. 무료 숙박은 0원입니다. 일부 날짜만 숙박하거나 지역이 다르면 상세 입력을 사용하세요.')
        with b:
            if trip.kind == '국내':
                select(trip, '간편지역', '숙박 지역', ['기타','서울','광역시'])
        if trip.kind == '국내':
            shared_lodging_fields(trip)
    a, b = st.columns(2)
    with a:
        mode = select(trip,'간편교통수단','교통수단',['철도','버스','항공','선박','자가용','없음'])
    with b:
        if mode not in ('자가용','없음'):
            number(trip, '간편교통비', '왕복 교통비 합계 (원)')
    if mode == '자가용':
        car_fields(trip)
    if trip.kind == '국외':
        st.caption('숙박·교통비는 원화 합계로 입력하세요.')


def shared_lodging_fields(trip):
    m = trip.meta
    m['공동숙박'] = st.toggle('공동 출장자 숙박비 함께 정산',value=m.get('공동숙박',False),key=key(trip,'shared_lodging'))
    if not m['공동숙박']:
        return
    a, b = st.columns(2)
    with a:
        m['공동숙박인원'] = st.number_input('숙박 인원 (본인 포함)',min_value=2,max_value=20,
                value=int(m.get('공동숙박인원',2)),step=1,key=key(trip,'shared_count'))
    with b:
        with st.popover('동행자 이름·등급',width='stretch'):
            saved = m.get('공동숙박자',[])
            people = []
            for i in range(m['공동숙박인원']-1):
                person = saved[i] if i < len(saved) else {}
                name = st.text_input(f'동행 {i+1} 성명 (선택)',value=person.get('성명',''),key=key(trip,f'shared_name_{i}'))
                grade = person.get('지급등급') or m.get('지급등급','제2호')
                group = st.selectbox(f'동행 {i+1} 지급 등급',GROUPS,index=GROUPS.index(grade) if grade in GROUPS else 0,key=key(trip,f'shared_grade_{i}'))
                agency = st.text_input(f'동행 {i+1} 소속기관 (선택)',value=person.get('소속기관',''),key=key(trip,f'shared_agency_{i}'))
                position = st.text_input(f'동행 {i+1} 직급·직위 (선택)',value=person.get('직위직급',''),key=key(trip,f'shared_position_{i}'))
                people.append({'성명':name,'지급등급':group,'소속기관':agency,'직위직급':position})
            m['공동숙박자'] = people
    st.caption('위 숙박비에는 객실 영수증 총액을 한 번만 입력하세요. 같은 기간·지역에 함께 숙박한 공무 출장자만 포함합니다. '+SCOPE_NOTE)


def payment_group(trip):
    select(trip,'지급등급','지급 등급',GROUPS,
           help='일반 공무원은 보통 제2호입니다. 본인 직위에 해당하는 등급은 공무원 여비 규정 별표 1과 소속기관 기준을 확인하세요.')


def car_fields(trip):
    a, b = st.columns(2)
    with a:
        method = select(trip,'간편자가용방식','자가용 계산 방식',['대중교통 운임','연료비'],
                        help='일반적인 자가용 출장은 같은 구간의 철도·버스 운임 기준입니다. 부득이한 자가용 사용으로 연료비를 정산하는 경우 연료비를 선택하세요.')
    with b:
        if method == '대중교통 운임':
            number(trip,'간편대중교통운임','같은 구간 철도·버스 왕복 운임 (원)',None)
        else:
            number(trip,'간편주행거리','총 주행거리 · 왕복 합계 (km)',None)
    if method == '연료비':
        a, b = st.columns(2)
        with a:
            fuel = select(trip,'간편유종','유종',list(load_rules()['fuel_efficiency']))
            if fuel in ('하이브리드','플러그인하이브리드(연료)'):
                select(trip,'간편가격유종','사용 연료',['보통휘발유','자동차용경유'])
        with b:
            unit = 'kWh' if fuel in ['전기','플러그인하이브리드(전기)'] else 'kg' if fuel == '수소' else 'L'
            fuel_price_field(trip,fuel,unit)
        with st.popover('통행료·주차료 (선택)',width='stretch'):
            number(trip,'간편통행료','통행료 합계 (원)')
            number(trip,'간편주차료','주차료 합계 (원)')


def car_evidence_fields(trip):
    trip.meta['간편동승자'] = st.checkbox('동승자 (자가용 운임 제외)',value=trip.meta.get('간편동승자',False),key=key(trip,'car_passenger'))
    if trip.meta.get('간편자가용방식','대중교통 운임') == '대중교통 운임':
        text(trip,'간편운임출처','철도·버스 운임 출처')
    else:
        text(trip,'간편자가용사유','부득이한 자가용 사용 사유')
        text(trip,'간편거리출처','거리 출처')
        if trip.meta.get('간편유가자동'):
            st.caption(trip.meta.get('간편유가출처') or '유가 조회가 완료되면 출처가 자동 기록됩니다.')
        else:
            text(trip,'간편유가출처','연료 단가 출처')
        trip.meta['간편자가용승인'] = st.checkbox('자가용 사용 승인 완료',value=trip.meta.get('간편자가용승인',False),key=key(trip,'car_approved'))
        text(trip,'간편자가용승인근거','자가용 승인 근거')
    trip.meta['간편자가용증빙'] = st.checkbox('자가용 이용·지출 증빙 확인',value=trip.meta.get('간편자가용증빙',False),key=key(trip,'car_evidence'))


@st.cache_data(ttl=900, max_entries=512, show_spinner=False)
def lookup_oil_price(day, product):
    try:
        return fetch_quote(day,product), ''
    except FuelPriceError as error:
        return None, str(error)


def fuel_price_field(trip, fuel, unit):
    m = trip.meta
    day = m['시작일시'][:10]
    product = product_for(fuel,m.get('간편가격유종','보통휘발유'))
    previous_auto = m.get('간편유가자동',False)
    if product:
        with st.popover('유가 설정',width='stretch'):
            direct = st.toggle('연료 단가 직접 입력', value=m.get('간편유가직접입력',False),key=key(trip,'fuel_manual'))
    else:
        direct = True
    if product:
        m['간편유가직접입력'] = direct
    m['간편유가자동'] = bool(product and not direct)
    context = [day,fuel,product]
    previous_context = m.get('_유가입력조건')
    m['_유가입력조건'] = context
    if not m['간편유가자동'] and previous_context and previous_context != context:
        apply_quote(m,day,product,None)
        st.session_state.pop(key(trip,'간편유가'),None)
        st.session_state.pop(key(trip,'간편유가출처'),None)
    if not m['간편유가자동']:
        if previous_auto:
            # 직접 수정한 단가에 자동 조회 출처를 붙이지 않는다.
            m['간편유가조회'] = {}
            m['간편유가출처'] = ''
            m['간편유가기준일'] = ''
            st.session_state.pop(key(trip,'간편유가출처'),None)
        number(trip,'간편유가',f'연료 단가 (원/{unit})',None)
        if not product:
            st.caption('해당 날짜의 전기·수소 단가를 입력하세요.')
        return
    stored = m.get('간편유가조회',{})
    if (st.session_state.get('original_rules') and stored.get('day')==day and
            stored.get('product')==product and stored.get('price')):
        quote, error = FuelQuote(**stored), ''
    else:
        quote, error = lookup_oil_price(day,product)
    apply_quote(m,day,product,quote)
    value = format(dec(quote.price).normalize(),',f') if quote else ''
    st.text_input(f'연료 단가 · 자동 (원/{unit})',value=value,disabled=True,
                  placeholder='해당 날짜 유가 조회 불가',key=key(trip,'fuel_auto_'+day+'_'+product+'_'+value))
    if quote:
        st.caption(f'{day} · [오피넷 전국 평균]({quote.source})')
    else:
        st.warning(error)
        if st.button('유가 다시 조회',key=key(trip,'fuel_retry')):
            lookup_oil_price.clear(day,product)
            st.rerun()


def detail_fields(trip):
    names = ['일정','숙박','교통','증빙'] + (['환율'] if trip.kind == '국외' else [])
    if trip.specials:
        names.append('추가 여비')
    tabs = st.tabs(names)
    with tabs[0]:
        editor(trip,'days',DAY,['일자','국가','도시','여비인정일','동일행정구역','왕복거리(km)','거리출처','출장시간(h)','공무용차량','식비지원액','도착다음날기산일수'])
    with tabs[1]:
        shared = any(r.get('숙박정산대상ID') for r in trip.lodgings)
        people_columns = ['숙박정산대상ID','숙박정산대상','숙박지급등급'] if shared else []
        editor(trip,'lodgings',LODGING,['숙박일',*people_columns,'국가','도시','지역구분','실제숙박','실제지출액','통화','결제수단','카드청구원화액','1USD당현지통화','현지환율기준일','현지환율출처','현금사용사유','무료숙박','증빙확인'])
        if shared:
            st.caption('실제지출액은 각 사람의 분담액입니다. 영수증 총액을 사람마다 반복 입력하지 마세요. 정산대상ID가 같은 행끼리 숙박 상한을 계산합니다. '+SCOPE_NOTE)
    with tabs[2]:
        car_columns = st.toggle('자가용 입력란 표시',value=any(r.get('교통수단')=='자가용' for r in trip.transports),key=key(trip,'car_columns'))
        visible = ['일자','교통수단','출발지','도착지','좌석등급','실제지출액','통화','기관직접결제','증빙확인']
        if car_columns:
            visible += ['자가용정산방식','대중교통운임','운임출처','거리(km)','거리출처','유종','유가','유가출처','통행료','주차료','부득이한사유','승인','승인근거','동승자']
        editor(trip,'transports',TRANSPORT,visible)
        if car_columns:
            st.caption('자가용은 대중교통 운임 또는 연료비 방식을 선택하세요. 거리·통행료·주차료는 해당 행 이동 구간의 합계입니다. 실제지출액을 연료비에 중복 합산하지 않습니다.')
    with tabs[3]:
        editor(trip,'evidence',EVIDENCE_ROW,list(EVIDENCE_ROW))
    if trip.kind == '국외':
        with tabs[4]:
            editor(trip,'fx',FX,list(FX))
    if trip.specials:
        with tabs[-1]:
            editor(trip,'specials',SPECIAL,list(SPECIAL))
    st.caption('행 아래 +로 추가할 수 있습니다. 입력 후 Enter를 누르면 금액이 바로 반영됩니다.')


def reset_batch(trips, results=None, identifier=None, title=''):
    for name in ('batch_pending_id','current_result','current_batch'):
        st.session_state.pop(name,None)
    for trip in trips:
        for name in list(st.session_state):
            if name.startswith(trip.id+'_'):
                del st.session_state[name]
    st.session_state.batch_trips = trips
    st.session_state.batch_id = identifier or uuid4().hex[:12]
    st.session_state.batch_title = title
    st.session_state.batch_group = bool(identifier)
    st.session_state.pop('batch_title_input',None)
    st.session_state.batch_rules = {r.trip['id']:r.rule_snapshot for r in results or []}
    st.session_state.trip = trips[0]
    st.session_state.batch_selected = trips[0].id
    st.session_state.original_rules = st.session_state.batch_rules.get(trips[0].id)


def load_trip(store, identifier):
    trip, result = store.load(identifier)
    reset_batch([trip],[result])
    st.rerun()


def load_batch(store, identifier):
    batch = store.load_batch(identifier)
    reset_batch([Trip.from_dict(r.trip) for r in batch.results],batch.results,batch.id,batch.title)
    st.rerun()


def active_trip(identifier):
    trip = next(t for t in st.session_state.batch_trips if t.id == identifier)
    # 위젯이 없는 동안 편집 패치가 정리되어도 마지막 입력으로 표를 복원한다.
    clear_editors(trip)
    st.session_state.trip = trip
    st.session_state.original_rules = st.session_state.batch_rules.get(trip.id)


def remove_trip_from_inputs(identifier):
    """입력 중인 출장만 제거하고, 마지막 출장이라면 빈 새 입력을 연다."""
    trips = st.session_state.batch_trips
    index = next((i for i,t in enumerate(trips) if t.id == identifier),None)
    if index is None:
        return
    removed = trips.pop(index)
    clear_editors(removed)
    st.session_state.batch_rules.pop(identifier,None)
    if not trips:
        st.session_state.batch_reset_requested = True
    elif st.session_state.trip.id == identifier:
        st.session_state.batch_pending_id = trips[min(index,len(trips)-1)].id


def edit_trip_from_result(identifier):
    st.session_state.batch_pending_id = identifier
    st.session_state.edit_scroll = uuid4().hex


def delete_trip_from_result(identifier):
    remove_trip_from_inputs(identifier)
    st.session_state.trip_notice = '선택한 출장을 삭제했습니다.'


def render_trip_controls(identifier):
    with st.container(key='trip-actions-'+identifier):
        edit, delete = st.columns(2,gap='small')
        edit.button('수정',key='edit-trip-'+identifier,type='tertiary',width='stretch',
                    on_click=edit_trip_from_result,args=(identifier,),help='이 출장의 입력란으로 이동합니다.')
        delete.button('삭제',key='delete-trip-'+identifier,type='tertiary',width='stretch',
                      on_click=delete_trip_from_result,args=(identifier,),help='이 출장을 현재 계산에서 삭제합니다. 저장 기록은 내 기록에서 관리합니다.')


def render_trip_card(trip, number, result=None):
    meta=trip.meta
    name=meta.get('출장명') or f'출장 {number}'
    period=meta.get('시작일시','')[:10]+' ~ '+meta.get('종료일시','')[:10]
    amount=money(result.estimated) if result is not None else '입력 확인 필요'
    with st.container(key='trip-card-'+trip.id):
        heading, tools=st.columns([4,1.2],vertical_alignment='center')
        with heading:
            st.markdown('<header class="trip-card-heading"><span class="trip-number">'+str(number)+'</span>'
                '<div class="trip-identity"><strong>'+escape(name)+'</strong><span>'+escape(period)+'</span></div>'
                '<div class="trip-total"><span>예상 출장비</span><strong>'+escape(amount)+'</strong></div></header>',unsafe_allow_html=True)
        with tools:
            render_trip_controls(trip.id)
        if result is not None:
            render_cost_breakdown(result)


def render_batch_result(store, batch):
    incomplete = batch.incomplete or any(missing_quick_inputs(Trip.from_dict(r.trip)) for r in batch.results)
    label = '전체 입력한 항목 합계' if incomplete else '전체 예상 출장비'
    st.markdown('<div class="result-heading"><span>'+label+'</span><span>출장 '+str(len(batch.results))+'건</span></div>'
                '<div class="result-amount">'+escape(money(batch.estimated))+'</div>',unsafe_allow_html=True)
    parts = ['<div><span>'+cat+'</span><strong>'+escape(money(batch.category(cat)))+'</strong></div>'
             for cat in ['일비','식비','숙박비','교통비']]
    st.markdown('<div class="result-breakdown">'+''.join(parts)+'</div>',unsafe_allow_html=True)
    st.caption('출장별 비용')
    for row, result in zip(batch.rows(), batch.results):
        render_trip_card(Trip.from_dict(result.trip),row['번호'],result)
    if incomplete:
        st.info('입력이 필요한 출장이 있습니다. 각 출장에서 빠진 항목을 확인하세요.')
    save, excel, word = st.columns(3)
    if save.button('일괄 저장',type='primary',width='stretch'):
        store.save_batch(batch)
        st.toast('출장 '+str(len(batch.results))+'건을 함께 저장했습니다.')
    payload = dumps(batch.to_dict())
    excel.download_button('전체 Excel',lambda:export_batch_excel(BatchResult.from_dict(json.loads(payload))),
                          '출장비_일괄정산.xlsx',width='stretch',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    word.download_button('전체 Word',lambda:export_batch_word(BatchResult.from_dict(json.loads(payload))),
                         '출장비_일괄정산.docx',width='stretch',mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    st.caption('출력: [인사혁신처 공식 신청서](https://www.mpm.go.kr/mpm/info/resultPay/payBoard/?cntId=695&mode=view)와 별첨 계산 내역')


def missing_quick_inputs(trip):
    """총액 산출에 필요한 빈 입력만 이름으로 안내한다."""
    m = trip.meta
    if m.get('_상세입력'):
        return []
    missing = []
    def require(name, label, positive=False):
        value = m.get(name)
        if value in ('', None) or (positive and dec(value) <= 0):
            missing.append(label)
    if trip.kind == '국외':
        require('기본국가','방문 국가')
        if m.get('기본국가') != '싱가포르':
            require('기본도시','방문 도시')
        require('간편환율','환율',True)
    local = trip.kind == '국내' and m.get('간편출장범위') == '근무지 내'
    if local:
        require('간편시간','출장시간')
        require('간편거리','왕복거리')
    elif m.get('간편교통수단') == '자가용':
        if m.get('간편자가용방식','대중교통 운임') == '연료비':
            require('간편주행거리','총 주행거리',True)
            require('간편유가','연료 단가',True)
        else:
            require('간편대중교통운임','철도·버스 왕복 운임')
    return missing


def cost_breakdown_html(result):
    breakdown = []
    for category in ['일비','식비','숙박비','교통비']:
        lines = [line for line in result.lines if line.category == category and line.status != EXCLUDED]
        amount = sum((line.amount or ZERO for line in lines),ZERO)
        value = '입력 필요' if any(line.amount is None for line in lines) else money(amount)
        breakdown.append('<div><span>'+category+'</span><strong>'+escape(value)+'</strong></div>')
    return ''.join(breakdown)


def render_cost_breakdown(result):
    st.markdown('<div class="result-breakdown">'+cost_breakdown_html(result)+'</div>',unsafe_allow_html=True)


def render_line_details(result):
    if result.lines:
        st.dataframe(pd.DataFrame([{'항목':r.category,'내역':r.name,'일자':r.date,'금액':money(r.amount),
            '상태':r.status,'계산식':r.formula} for r in result.lines]),hide_index=True,width='stretch')


def render_shared_lodging(result):
    shared = allocation(result)
    if not shared:
        return
    st.caption(SCOPE_NOTE)
    st.caption('숙박비 분담액 합계 '+money(sum((row['분담액'] for row in shared),ZERO)))
    st.dataframe(pd.DataFrame([{'정산 대상':r['정산 대상'],'지급 등급':r['지급 등급'],
        '숙박':str(r['숙박일'])+'박','분담액':money(r['분담액']),
        '상한':money(r['상한']) if isinstance(r['상한'],Decimal) else r['상한'],
        '예상 인정액':money(r['예상 인정액'])} for r in shared]),hide_index=True,width='stretch')


def render_result(trip, result, nights):
    missing = missing_quick_inputs(trip)
    incomplete = missing or any(line.amount is None and line.status != EXCLUDED for line in result.lines)
    label = '입력한 항목 합계' if incomplete else '예상 출장비'
    duration = '당일' if nights == 0 else f'{nights}박 {nights+1}일'
    heading, tools=st.columns([4,1.2],vertical_alignment='center')
    with heading:
        st.markdown('<div class="result-heading"><span>'+label+'</span><span>'+duration+'</span></div>'
                    '<div class="result-amount">'+escape(money(result.estimated))+'</div>',unsafe_allow_html=True)
    with tools:
        render_trip_controls(trip.id)
    local = trip.kind == '국내' and not trip.meta.get('_상세입력') and trip.meta.get('간편출장범위') == '근무지 내'
    if not local:
        render_cost_breakdown(result)
    if missing:
        st.info(' · '.join(missing)+' 입력이 필요합니다.')
    elif incomplete:
        st.info('미입력 항목은 상세 입력·정산에서 확인하세요.')
    if result.advance:
        st.caption('기지급액 차감 후 '+money(max(ZERO,result.estimated-result.advance)))
    if trip.specials:
        st.caption('추가 여비 포함 '+money(sum((line.amount or ZERO for line in result.lines if line.category=='기타 인정 여비' and line.status != EXCLUDED),ZERO)))


def render_single_actions(store, trip, result):
    save, excel, word = st.columns(3)
    if save.button('계산 저장',type='primary',width='stretch'):
        store.save(trip,result)
        st.toast('저장했습니다.')
    payload = dumps(result.to_dict())
    excel.download_button('Excel 다운로드',lambda:export_excel(Result.from_dict(json.loads(payload))),
        '출장비_계산서.xlsx',width='stretch',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    word.download_button('Word 다운로드',lambda:export_word(Result.from_dict(json.loads(payload))),
        '출장비_계산서.docx',width='stretch',mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    st.caption('출력: [인사혁신처 공식 신청서](https://www.mpm.go.kr/mpm/info/resultPay/payBoard/?cntId=695&mode=view)와 별첨 계산 내역')


def result_details(trip, result, batch=None):
    st.caption('예상액에는 승인·증빙 확인 전 금액도 포함됩니다. 확정 청구액 '+money(result.claim))
    render_line_details(result)
    for issue in result.issues:
        st.caption('• '+issue)
    if batch is not None and (len(batch.results)>1 or st.session_state.get('batch_group')):
        st.download_button('전체 입력 백업 (JSON)',dumps(batch.to_dict()),'출장비_일괄백업.json','application/json')
        st.caption('위쪽 전체 합계에서 일괄 저장·출력할 수 있습니다. 이 탭은 선택한 출장의 상세 계산입니다.')
        return
    st.download_button('입력 백업 (JSON)',dumps(result.to_dict()),'출장비_백업.json','application/json')
    st.caption('공무원 여비 규정 · 자료 기준일 '+load_rules()['as_of'])


def run():
    st.set_page_config(page_title='바른여비 · 출장비 계산기', page_icon=':material/work_outline:', layout='centered')
    apply_theme()
    store = Store()
    if st.session_state.pop('batch_reset_requested',False):
        reset_batch([default_trip(store)])
    if 'trip' not in st.session_state:
        st.session_state.trip = default_trip(store)
    trip = st.session_state.trip
    if 'batch_trips' not in st.session_state:
        st.session_state.batch_trips = [trip]
        st.session_state.batch_id = uuid4().hex[:12]
        st.session_state.batch_title = ''
        st.session_state.batch_rules = {trip.id:st.session_state.original_rules} if st.session_state.get('original_rules') else {}
    if st.session_state.get('batch_pending_id'):
        target = st.session_state.pop('batch_pending_id')
        if target != trip.id:
            active_trip(target)
        st.session_state.batch_selected = target
        trip = st.session_state.trip
    trips = st.session_state.batch_trips
    if len(trips)>1:
        st.session_state.batch_group = True
    batch_mode = len(trips)>1 or st.session_state.get('batch_group',False)
    title, actions = st.columns([3,1])
    with title:
        st.title('출장비 계산기')
    notice = st.session_state.pop('trip_notice',None)
    if notice:
        st.toast(notice)
    with actions:
        with st.popover('내 기록', width='stretch'):
            if st.button('새 계산', width='stretch'):
                reset_batch([default_trip(store)])
                st.rerun()
            records = [('batch',r[0],'묶음 · '+r[1]+' · '+str(r[2])+'건 · '+r[3][:10]) for r in store.list_batches()]
            records += [('trip',r[0],(r[1] or '제목 없는 출장')+' · '+r[3][:10]) for r in store.list()]
            if records:
                chosen = st.selectbox('저장된 계산', records, format_func=lambda row:row[2])
                edit_record, delete_record = st.columns(2)
                if edit_record.button('불러와 수정', width='stretch'):
                    (load_batch if chosen[0]=='batch' else load_trip)(store,chosen[1])
                if delete_record.button('기록 삭제',width='stretch',help='개별 출장을 삭제하면 저장된 묶음에서도 제외합니다. 묶음 기록만 삭제하면 개별 기록은 유지합니다.'):
                    if chosen[0]=='batch':
                        store.delete_batch(chosen[1])
                        message = '묶음 기록을 삭제했습니다. 개별 출장 기록은 유지됩니다.'
                    else:
                        store.delete(chosen[1])
                        remove_trip_from_inputs(chosen[1])
                        message = '출장 기록을 삭제했습니다.'
                    st.session_state.trip_notice = message
                    st.rerun()
            else:
                st.caption('저장된 계산이 없습니다.')
    nav, add = st.columns([3,1],vertical_alignment='bottom')
    with nav:
        labels = {t.id:f'{i}. '+(t.meta.get('출장명') or '출장 '+str(i))+' · '+t.meta.get('시작일시','')[:10] for i,t in enumerate(trips,1)}
        if st.session_state.get('batch_selected') not in labels:
            st.session_state.batch_selected = trip.id
        selected = st.selectbox('입력할 출장',[t.id for t in trips],
                                format_func=lambda identifier:labels[identifier],key='batch_selected')
    if selected != trip.id:
        active_trip(selected)
        st.rerun()
    with add:
        add_requested = st.button('출장 추가',icon=':material/add:',width='stretch')
    kinds = ['국내','국외'] + (['특수'] if trip.kind == '특수' else [])
    kind = st.segmented_control('출장 유형',kinds,default=trip.kind,key=key(trip,'kind'),label_visibility='collapsed')
    if kind:
        trip.kind = kind
    manual_default = not trip.meta.get('간편입력',False) and any(
        [trip.days,trip.lodgings,trip.transports,trip.fx,trip.evidence,trip.specials])
    previous = trip.meta.get('_상세입력', manual_default)
    with st.container(border=True, key='inputs'):
        trip.meta.pop('_금액입력오류',None)
        nights = date_fields(trip)
        if previous:
            payment_group(trip)
            detail_fields(trip)
        else:
            quick_fields(trip, nights)
    # 상세 설정을 처리한 결과를 위쪽 결과 영역에 채운다.
    result_area = st.container(border=True, key='result')
    with st.expander('상세 입력·정산'):
        conditions, identity, reports = st.tabs(['조건 조정','정산 정보','계산 내역'])
        with conditions:
            manual = st.toggle('날짜별로 다르게 입력',value=previous,key=key(trip,'manual'),
                               help='일부 날짜 숙박·다른 출장지·무료 식사·공무용 차량 사용일이 다르면 날짜별로 입력하세요. 해제하면 간편 입력 합계로 다시 계산합니다.')
            if manual != previous:
                trip.meta['_상세입력'] = manual
                clear_editors(trip)
                st.rerun()
            trip.meta['_상세입력'] = manual
            if not manual:
                trip.meta['간편공용차량'] = st.checkbox('공무용 차량 이용', value=trip.meta.get('간편공용차량',False),key=key(trip,'vehicle'))
            number(trip,'기지급액','이미 받은 금액 (원)')
            local = trip.kind == '국내' and trip.meta.get('간편출장범위') == '근무지 내'
            if not manual and trip.meta.get('간편교통수단') == '자가용' and not local:
                car_evidence_fields(trip)
            st.caption('간편 입력은 전체 기간을 여비 인정일로 계산합니다. 개인 일정·식사 제공·일부 날짜 숙박은 날짜별 입력에서 조정하세요.')
        with identity:
            a, b = st.columns(2)
            with a:
                text(trip,'성명');text(trip,'출장명');text(trip,'직위직급','직급·직위')
            with b:
                text(trip,'소속기관');text(trip,'출장목적')
            trip.meta['출장승인'] = st.checkbox('출장 승인 완료',value=trip.meta.get('출장승인',False),key=key(trip,'approved'))
        with reports:
            if batch_mode:
                st.session_state.batch_title = st.text_input('묶음 이름 (선택)',value=st.session_state.batch_title,key='batch_title_input',placeholder='예: 11월 출장 정산')
            report_area = st.container()
    if add_requested:
        added = default_trip(store)
        for name in ('성명','소속기관','지급등급'):
            if trip.meta.get(name):
                added.meta[name] = trip.meta[name]
        trips.append(added)
        st.session_state.batch_group = True
        st.session_state.batch_pending_id = added.id
        st.rerun()
    try:
        if not manual:
            build_schedule(trip)
        batch = calculate_batch(trips,st.session_state.batch_rules,identifier=st.session_state.batch_id,title=st.session_state.batch_title)
        result = next(r for r in batch.results if r.trip['id']==trip.id)
    except (ValueError, KeyError, TypeError, ArithmeticError) as error:
        with result_area:
            st.error('입력값을 확인하세요. '+str(error))
            for i,item in enumerate(trips,1):
                render_trip_card(item,i)
        if st.session_state.get('edit_scroll'):
            scroll_to_inputs(st.session_state.pop('edit_scroll'))
        return
    st.session_state.current_result = result
    st.session_state.current_batch = batch
    with result_area:
        if batch_mode:
            render_batch_result(store,batch)
        else:
            render_result(trip,result,nights)
            render_single_actions(store,trip,result)
            if allocation(result):
                with st.expander('숙박비 분담 내역'):
                    render_shared_lodging(result)
    with report_area:
        result_details(trip,result,batch)
    if st.session_state.get('edit_scroll'):
        scroll_to_inputs(st.session_state.pop('edit_scroll'))
