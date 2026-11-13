from datetime import date,timedelta
from decimal import Decimal
from copy import deepcopy
import pytest
from travel.models import Trip,CONFIRMED,APPROVAL,EVIDENCE,REVIEW
from travel.engine import calculate
from travel.rules import load_rules,select_law,destination

def trip(days=1,kind='국내',start='2026-10-10'):
    begin=date.fromisoformat(start)
    t=Trip(kind=kind,meta={'성명':'홍길동(예시)','소속기관':'예시기관','출장명':'정책 협의','출장목적':'사업 협의',
        '지급등급':'제2호','공무원':True,'출장승인':True,'시작일시':start+'T09:00:00+09:00',
        '종료일시':str(begin+timedelta(days=days-1))+'T18:00:00+09:00','기지급액':'0'})
    t.days=[{'일자':str(begin+timedelta(days=i)),'도시':'부산','국가':'대한민국','왕복거리(km)':'400',
       '거리출처':'도로공사','출장시간(h)':'8','도착다음날기산일수':str(i)} for i in range(days)]
    return t

def subtotal(result,cat):return sum((r.amount or Decimal(0) for r in result.lines if r.category==cat and r.status==CONFIRMED),Decimal(0))

@pytest.mark.parametrize('hours,vehicle,expected',[('3',False,10000),('4',False,20000),('4',True,10000),('3',True,0)])
def test_local_article18(hours,vehicle,expected):
    t=trip();t.days[0].update({'동일행정구역':True,'출장시간(h)':hours,'공무용차량':vehicle})
    assert calculate(t).claim==expected

@pytest.mark.parametrize('distance,expected',[('11.99',20000),('12',50000)])
def test_roundtrip_12km_boundary(distance,expected):
    t=trip();t.days[0]['왕복거리(km)']=distance
    assert calculate(t).claim==expected

def test_short_trip_2km_real_cost():
    t=trip();t.days[0].update({'왕복거리(km)':'2','출장시간(h)':'4','근거리운임':'3000','근거리식비':'15000','증빙확인':True})
    assert calculate(t).claim==11333  # 지침 Ⅲ.2.마: 운임 + 식비 1/3 상한

def test_domestic_perdiem_and_meal():
    assert calculate(trip(2)).claim==100000

def test_multi_region_lodging_pools_actual_costs():
    # 예규 제226호 Ⅳ.3 사례: 경주 67,000 + 부산 82,000, 상한 합계 150,000
    t=trip(3)
    t.lodgings=[{'숙박일':'2026-10-10','지역구분':'기타','실제지출액':'67000','증빙확인':True},
                {'숙박일':'2026-10-11','지역구분':'광역시','실제지출액':'82000','증빙확인':True}]
    assert subtotal(calculate(t),'숙박비')==149000

@pytest.mark.parametrize('region,expected',[('서울',100000),('광역시',80000),('기타',70000)])
def test_lodging_caps(region,expected):
    t=trip(2);t.lodgings=[{'숙박일':'2026-10-10','지역구분':region,'실제지출액':'150000','증빙확인':True}]
    assert subtotal(calculate(t),'숙박비')==expected

def test_unapproved_excess_keeps_base_separate():
    t=trip(2);t.lodgings=[{'숙박일':'2026-10-10','지역구분':'기타','실제지출액':'100000','증빙확인':True,'초과신청':True}]
    r=calculate(t)
    assert subtotal(r,'숙박비')==70000
    assert r.pending==21000
    t.lodgings[0].update({'승인':True,'승인근거':'기관장 승인 제1호'})
    assert subtotal(calculate(t),'숙박비')==91000

@pytest.mark.parametrize('n,expected',[(15,25000),(16,22500),(30,22500),(31,20000),(60,20000),(61,17500)])
def test_long_stay_arrival_next_day_boundary(n,expected):
    t=trip();t.days[0]['도착다음날기산일수']=str(n)
    assert subtotal(calculate(t),'일비')==expected

@pytest.mark.parametrize('vehicle,expected',[(False,330000),(True,165000)])
def test_official_mileage_example(vehicle,expected):
    # 예규 제226호 Ⅳ.5: 10일, 절약운임 16만원, 총 일비 33만원 / 차량시 16만5천원
    t=trip(10);t.meta.update({'공적마일리지 절약운임(원)':'160000','마일리지증빙확인':True})
    for d in t.days:d['공무용차량']=vehicle
    assert subtotal(calculate(t),'일비')==expected

def test_free_meal_does_not_invent_thirds():
    t=trip();t.days[0]['숙식제공여부']=True
    assert any(r.category=='식비' and r.status==REVIEW for r in calculate(t).lines)

@pytest.mark.parametrize('country,city,expected',[('일본','도쿄','가'),('일본','오사카','나'),('중국','베이징','나'),
 ('중국','상하이','다'),('미국','로스앤젤레스','가'),('캐나다','오타와','나'),('베트남','하노이','라')])
def test_country_city_exceptions(country,city,expected):
    assert destination(country,city)[0]==expected

def test_unlisted_country_requires_nearest_capital():
    assert destination('부탄','팀푸')[0] is None
    assert destination('부탄','팀푸','인도','예정지→뉴델리 거리 자료')[0]=='나'
    assert destination('중국','')[0] is None

def test_official_foreign_fixed_example():
    # 예규 Ⅱ.5.나.2)(4): 일본 1박2일 5급, 환율 1137.05, 334270원
    t=trip(2,'국외')
    for d in t.days:d.update({'국가':'일본','도시':'오사카'})
    t.meta.update({'숙박정산방식':'할인정액','할인정액승인':True,'할인정액승인근거':'예시 승인'})
    t.lodgings=[{'숙박일':'2026-10-10','국가':'일본','도시':'오사카','실제숙박':True}]
    t.fx=[{'통화':'USD','기준일':'2026-10-09','1단위당 원화':'1137.05','환율종류':'현찰 매입(출장자 구매)','출처':'지침 예시의 가정환율','증빙확인':True}]
    r=calculate(t)
    assert r.claim==334270

def test_missing_exchange_rate_not_zero_confirmed():
    t=trip(1,'국외');t.days[0].update({'국가':'일본','도시':'도쿄'})
    r=calculate(t)
    assert r.claim==0
    assert all(x.status==REVIEW and x.amount is None for x in r.lines)

def test_discounted_transport_receipt_and_direct_payment():
    t=trip();t.transports=[{'일자':'2026-10-10','교통수단':'철도','실제지출액':'60000','할인액':'10000','증빙확인':True}]
    assert subtotal(calculate(t),'교통비')==50000
    t.transports[0]['기관직접결제']=True
    assert subtotal(calculate(t),'교통비')==0

def test_private_vehicle_fuel_only_with_reason_and_approval():
    t=trip();t.transports=[{'일자':'2026-10-10','교통수단':'자가용','부득이한사유':'산간오지','거리(km)':'119.7',
        '유종':'휘발유','유가':'1700','유가출처':'지침 예시 가정','거리출처':'예시 거리','통행료':'5000','증빙확인':True,'승인':True,'승인근거':'자가용 사용 승인'}]
    assert subtotal(calculate(t),'교통비')==22000

def test_advance_only_deducted_once():
    t=trip();t.meta['기지급액']='80000';r=calculate(t)
    assert r.claim==0 and r.refund==30000

def test_legal_versions_are_distinct():
    assert select_law('2026-06-30')['number']=='대통령령 제36013호'
    assert select_law('2026-07-01')['number']=='대통령령 제36492호'
    assert select_law('2026-10-02')['number']=='대통령령 제36728호'
    assert select_law('2025-12-31') is None

def test_special_moving_and_monthly():
    t=trip(kind='특수')
    t.specials=[{'일자':'2026-10-10','종류':'국내 이전비','화물량':'6','기본구간실비':'1000000','초과구간실비':'200000',
      '이전요건확인':True,'발령일':'2026-09-01','이전일':'2026-10-10','증빙확인':True,'승인':True,'승인근거':'이전 인정'}]
    assert calculate(t).claim==1100000
    t.specials=[{'일자':'2026-10-10','종류':'상시출장 월액','대상호':'1','기관확정월액':'150000','인정출장일수':'10',
     '기관지급기준':'기관 확정 지급기준','증빙확인':True,'승인':True,'승인근거':'기관 지급결정'}]
    assert calculate(t).claim==100000

@pytest.mark.parametrize('yen,bill,expected',[(11000,153254,153250),(13300,185301,155760),(13300,150732,150730)])
def test_official_foreign_card_lodging_examples(yen,bill,expected):
    # 예규 제226호 Ⅱ.5.나.6) 개인신용카드 사례. 원화만 비교하면 안 된다.
    t=trip(2,'국외')
    for d in t.days:d.update({'국가':'일본','도시':'오사카'})
    t.fx=[{'통화':'USD','기준일':'2026-10-09','1단위당 원화':'1137.05','환율종류':'현찰 매입(출장자 구매)','출처':'지침 예시 가정','증빙확인':True}]
    t.lodgings=[{'숙박일':'2026-10-10','국가':'일본','도시':'오사카','통화':'JPY','실제지출액':str(yen),
        '결제수단':'개인카드','카드청구원화액':str(bill),'1USD당현지통화':'82.5764',
        '현지환율기준일':'2026-10-09','현지환율출처':'지침 예시 가정','증빙확인':True}]
    assert subtotal(calculate(t),'숙박비')==expected
