"""간편 합계와 Enter 편집 후 값 초기화 문제의 회귀 사례."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from streamlit.testing.v1 import AppTest
from travel.models import Trip, ZERO
from travel.quick import build_schedule, calculate_preview


def quick_trip(kind='국내'):
    return Trip(kind=kind, meta={'시작일시':'2026-11-10T09:00:00+09:00',
        '종료일시':'2026-11-13T18:00:00+09:00','지급등급':'제2호','간편입력':True,
        '간편출장범위':'근무지 외','간편지역':'서울','간편숙박비':'100000',
        '간편교통비':'50000','간편환율':'1400','기본국가':'미국','기본도시':'뉴욕'})


def test_quick_totals_need_no_identity_and_preserve_hotel_remainder():
    trip = quick_trip()
    build_schedule(trip)
    assert sum(Decimal(r['실제지출액']) for r in trip.lodgings) == 100000
    assert all('배분설명' in row for row in trip.lodgings)
    assert all(row['왕복거리(km)'] == '' for row in trip.days)
    result = calculate_preview(trip)
    assert result.estimated == 350000  # 4일 일비·식비 + 숙박 합계 + 교통 합계
    assert result.claim == ZERO


def test_manual_forecast_rate_never_becomes_confirmed_or_changes_input():
    trip = quick_trip('국외')
    build_schedule(trip)
    original = deepcopy(trip.to_dict())
    result = calculate_preview(trip)
    assert result.estimated > 150000
    assert result.claim == ZERO
    assert result.trip == original == trip.to_dict()
    assert any('예상 환율' in issue for issue in result.issues)


def test_enter_edits_survive_second_edit_and_unrelated_rerun():
    app = AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py', default_timeout=20)
    trip = quick_trip()
    build_schedule(trip)
    trip.meta['_상세입력'] = True
    trip.evidence = [{'일자':'2026-11-10','문서번호':'1001','자료명':'교통 영수증'}]
    app.session_state['trip'] = trip
    app.run()
    assert not app.exception
    attrs = ['days','lodgings','transports','evidence']
    columns = ['출장시간(h)','실제지출액','실제지출액','문서번호']
    values = [7.5, 70000., 12345., '1024']
    identities = [frame.proto.id for frame in app.dataframe[:4]]
    for attr, column, value in zip(attrs, columns, values):
        app.session_state[trip.id+'_'+attr+'_editor'] = {
            'edited_rows':{0:{column:value}}, 'added_rows':[], 'deleted_rows':[]}
        app.run()
        assert not app.exception
        assert getattr(app.session_state.trip,attr)[0][column] == str(value)
        assert [frame.proto.id for frame in app.dataframe[:4]] == identities
    # 두 번째 Enter로 기존 입력과 새 입력이 함께 전달되어도 기존 값은 유지된다.
    app.session_state[trip.id+'_days_editor'] = {
        'edited_rows':{0:{'출장시간(h)':7.5,'왕복거리(km)':40.}}, 'added_rows':[], 'deleted_rows':[]}
    app.run()
    app.run()
    assert app.session_state.trip.days[0]['출장시간(h)'] == '7.5'
    assert app.session_state.trip.days[0]['왕복거리(km)'] == '40.0'
    assert app.session_state.trip.lodgings[0]['실제지출액'] == '70000.0'
    assert app.session_state.trip.transports[0]['실제지출액'] == '12345.0'
    assert app.session_state.trip.evidence[0]['문서번호'] == '1024'
    assert [frame.proto.id for frame in app.dataframe[:4]] == identities
    # 행 추가·삭제와 0원·미입력을 구분해서 보존한다.
    app.session_state[trip.id+'_lodgings_editor'] = {
        'edited_rows':{0:{'실제지출액':0.},1:{'실제지출액':None}},
        'added_rows':[{'숙박일':'2026-11-12','실제지출액':1234.}], 'deleted_rows':[2]}
    app.run()
    rows = app.session_state.trip.lodgings
    assert rows[0]['실제지출액'] == '0.0'
    assert rows[1]['실제지출액'] == ''
    assert rows[2]['실제지출액'] == '1234.0'
    assert rows[2]['실제숙박'] is True
    assert app.dataframe[1].proto.id == identities[1]


def test_car_fare_and_fuel_use_their_own_fields_and_keep_totals():
    trip = quick_trip()
    trip.meta.update({'간편교통수단':'자가용','간편자가용방식':'대중교통 운임',
                      '간편대중교통운임':'14000','간편운임출처':'철도 운임표'})
    build_schedule(trip)
    result = calculate_preview(trip)
    assert sum((r.amount or ZERO for r in result.lines if r.category=='교통비'),ZERO) == 14000
    # 기존 왕복 교통비 50,000원에 연료비를 중복 합산하지 않는다.
    trip.meta.update({'간편자가용방식':'연료비','간편주행거리':'119.7',
                      '간편유종':'휘발유','간편유가':'1700','간편통행료':'5000','간편주차료':'3000'})
    build_schedule(trip)
    result = calculate_preview(trip)
    car = next(r for r in result.lines if r.category=='교통비')
    assert car.amount == 25000 and car.status != '계산 확정'
    assert '11.97' in car.formula
    trip.meta['간편동승자'] = True
    build_schedule(trip)
    car = next(r for r in calculate_preview(trip).lines if r.category=='교통비')
    assert car.amount == 0 and car.status == '지급 제외'


def test_car_missing_inputs_stay_unknown_and_local_fuel_is_not_added():
    trip = quick_trip()
    trip.meta.update({'간편교통수단':'자가용','간편자가용방식':'대중교통 운임'})
    build_schedule(trip)
    car = next(r for r in calculate_preview(trip).lines if r.category=='교통비')
    assert car.amount is None
    trip.meta.update({'간편자가용방식':'연료비','간편주행거리':'119.7'})
    build_schedule(trip)
    car = next(r for r in calculate_preview(trip).lines if r.category=='교통비')
    assert car.amount is None
    trip.meta.update({'간편출장범위':'근무지 내','간편거리':'10','간편시간':'4',
                      '간편유가':'1700','간편통행료':'5000'})
    build_schedule(trip)
    assert trip.transports == []
    assert calculate_preview(trip).estimated == 80000


def test_quick_car_inputs_reach_calculation_without_opening_detail_table():
    app = AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py', default_timeout=20).run()
    next(s for s in app.selectbox if s.label=='교통수단').select('자가용').run()
    assert not app.exception
    next(s for s in app.selectbox if s.label=='자가용 계산 방식').select('연료비').run()
    next(t for t in app.toggle if t.label=='연료 단가 직접 입력').set_value(True).run()
    for label, value in [('총 주행거리 · 왕복 합계 (km)',119.7),('연료 단가 (원/L)',1700.),
                         ('통행료 합계 (원)',5000.),('주차료 합계 (원)',3000.)]:
        next(n for n in app.number_input if n.label==label).set_value(value).run()
    assert not app.exception
    result = app.session_state.current_result
    assert next(r for r in result.lines if r.category=='교통비').amount == 25000
    app.toggle[0].set_value(True).run()
    assert not app.exception
    assert any(t.label=='자가용 입력란 표시' and t.value for t in app.toggle)
    assert next(r for r in app.session_state.current_result.lines if r.category=='교통비').amount == 25000
