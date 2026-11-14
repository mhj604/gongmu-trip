from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs
from urllib.error import URLError
import pytest
from streamlit.testing.v1 import AppTest
from travel.fuel_prices import (FuelQuote, FuelPriceError, OIL_URL, LPG_URL,
                               parse_quote, fetch_quote, product_for, apply_quote)
from test_quick_ui import quick_trip

HTML = '''<table><thead><tr><th>구분</th><th>자동차용경유</th><th>보통휘발유</th></tr></thead>
<tbody><tr><td>2026년10월11일</td><td>1842.42</td><td>1856.84</td></tr>
<tr><td>2026년10월12일</td><td>1843.08</td><td>1856.81</td></tr>
<tr><td>전일대비</td><td>0.66</td><td>-0.03</td></tr></tbody></table>'''


def test_exact_requested_day_and_product_ignore_previous_day_and_change_row():
    assert parse_quote(HTML,'2026-10-12','보통휘발유') == '1856.81'
    assert parse_quote(HTML,'2026-10-12','자동차용경유') == '1843.08'
    with pytest.raises(FuelPriceError):
        parse_quote(HTML,'2026-10-10','보통휘발유')
    with pytest.raises(FuelPriceError):
        parse_quote(HTML,'2026-10-12','자동차부탄')
    lpg = '<tr><th>기간</th><th>자동차부탄 (원/ℓ)</th></tr><tr><td>26년10월12일</td><td>1,143.73</td></tr>'
    assert parse_quote(lpg,'2026-10-12','자동차부탄') == '1143.73'


def test_fetch_posts_one_day_and_only_accepts_exact_date(monkeypatch):
    calls = []
    def respond(request, timeout):
        calls.append((request,timeout))
        return BytesIO(HTML.encode())
    monkeypatch.setattr('travel.fuel_prices.urlopen',respond)
    quote = fetch_quote('2026-10-12','보통휘발유')
    request, timeout = calls[0]
    assert request.full_url == OIL_URL and timeout == 8
    params = parse_qs(request.data.decode())
    assert params['TERM'] == ['D']
    assert params['STA_Y'] == params['END_Y'] == ['2026']
    assert params['STA_M'] == params['END_M'] == ['10']
    assert params['STA_D'] == params['END_D'] == ['12']
    assert params['OIL_CD_B027'] == ['Y']
    assert quote.price == '1856.81' and quote.source == OIL_URL and quote.fetched_at
    with pytest.raises(FuelPriceError):
        fetch_quote('2026-10-10','보통휘발유')
    def offline(*args, **kwargs):
        raise URLError('offline')
    monkeypatch.setattr('travel.fuel_prices.urlopen',offline)
    with pytest.raises(FuelPriceError,match='연결하지 못했습니다'):
        fetch_quote('2026-10-12','보통휘발유')
    with pytest.raises(FuelPriceError,match='아직 발표되지 않았습니다'):
        fetch_quote('2099-01-01','보통휘발유')


def test_failed_or_mismatched_quote_clears_old_rate_and_source():
    meta = {'간편유가':'1855','간편유가출처':'old'}
    quote = FuelQuote('2026-10-12','보통휘발유','1856.81',OIL_URL,'2026-11-14')
    apply_quote(meta,'2026-10-12','보통휘발유',quote)
    assert meta['간편유가조회']['day'] == '2026-10-12'
    with pytest.raises(FuelPriceError):
        apply_quote(meta,'2026-10-13','보통휘발유',quote)
    assert meta['간편유가'] == '' and meta['간편유가출처'] == ''
    apply_quote(meta,'2026-10-12','보통휘발유',quote)
    apply_quote(meta,'2026-10-13','보통휘발유',None)
    assert meta['간편유가'] == '' and meta['간편유가조회'] == {}
    assert product_for('하이브리드') == '보통휘발유'
    assert product_for('하이브리드','자동차용경유') == '자동차용경유'
    assert product_for('LPG') == '자동차부탄'
    assert product_for('전기') is None


def test_changing_departure_date_updates_fuel_price_and_failure_removes_old_amount(monkeypatch):
    def lookup(day, product):
        values = {'2026-10-12':'1856.81','2026-10-11':'1856.84'}
        if day not in values:
            return None, '해당 날짜 통계 미발표'
        price = '1843.08' if product == '자동차용경유' else values[day]
        return FuelQuote(day,product,price,OIL_URL,'2026-11-14'), ''
    monkeypatch.setattr('travel.ui.lookup_oil_price',lookup)
    trip = quick_trip()
    trip.meta.update({'시작일시':'2026-10-12T09:00:00+09:00','종료일시':'2026-10-15T18:00:00+09:00',
        '간편교통수단':'자가용','간편자가용방식':'연료비','간편주행거리':'570',
        '간편유종':'하이브리드','간편유가':'1855','간편통행료':'24000'})
    app = AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=20)
    app.session_state['trip'] = trip
    app.run()
    assert not app.exception
    assert app.session_state.trip.meta['간편유가'] == '1856.81'
    car = next(r for r in app.session_state.current_result.lines if r.category=='교통비')
    assert car.amount == (Decimal('570')*Decimal('1856.81')/Decimal('15.37')+24000).quantize(Decimal(1),rounding='ROUND_DOWN')
    app.date_input[0].set_value(date(2026,10,11)).run()
    assert not app.exception
    assert app.session_state.trip.meta['간편유가'] == '1856.84'
    assert app.session_state.trip.transports[0]['유가기준일'] == '2026-10-11'
    next(s for s in app.selectbox if s.label=='사용 연료').select('자동차용경유').run()
    assert app.session_state.trip.meta['간편유가'] == '1843.08'
    app.date_input[0].set_value(date(2026,10,10)).run()
    assert not app.exception
    assert app.session_state.trip.meta['간편유가'] == ''
    assert next(r for r in app.session_state.current_result.lines if r.category=='교통비').amount is None
