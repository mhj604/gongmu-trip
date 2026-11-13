"""국내 정액여비, 근무지 내 출장, 장기체재 계산."""
from datetime import date
from decimal import Decimal
from .models import *
from .context import receipt_status

def local_trip(ctx,day):
    m=ctx.trip.meta
    day_date=str(day.get('일자',''))
    same=bool(day.get('동일행정구역',m.get('동일행정구역',False)))
    if day.get('분리도서') and not day.get('교량연결'): same=False
    law=ctx.law(day_date)
    if law and law['id']>='2026-07-01' and m.get('통합특별시 해당'):
        if not m.get('종전 근무지 시군') or not day.get('종전 출장지 시군'):
            return None,'통합특별시는 종전 광주·전남 시군을 입력해야 합니다.'
        same=m['종전 근무지 시군']==day['종전 출장지 시군']
    distance=day.get('왕복거리(km)')
    # 간편 화면의 명시적인 구간 선택. 정확한 거리를 임의로 만들어 저장하지 않는다.
    if (distance in ('',None) and not same and
            day.get('거리구간확인')=='다른 시군·왕복 12km 이상' and
            not m.get('통합특별시 해당') and not day.get('분리도서') and
            day.get('근무지 판정','자동')=='자동'):
        return False,'사용자 구간 확인: 다른 시군·왕복 12km 이상; 제18조 및 지침 Ⅲ'
    if distance in ('',None) and not same: return None,'다른 시군 출장의 왕복거리 미입력'
    if distance not in ('',None) and not day.get('거리출처'): return None,'왕복거리 산출 출처 미입력'
    classified=same or (distance not in ('',None) and dec(distance)<12)
    override=day.get('근무지 판정','자동')
    if override in ('근무지 내','근무지 외'):
        if not day.get('판정승인근거'): return None,'기관장 판정 근거 미입력'
        classified=override=='근무지 내'
    return classified,'제18조 및 지침 Ⅲ'

def local(ctx,day):
    d=str(day['일자'])
    hours=dec(day.get('출장시간(h)'))
    if day.get('출장시간(h)') in ('',None):
        ctx.line('일비','근무지 내 출장',d,status=REVIEW,notes='출장시간 미입력',reference='제18조; 지침 Ⅲ')
        return
    limit=Decimal(20000 if hours>=4 else 10000)
    if day.get('전용차량배정') or (day.get('운전원본연업무') and hours<4):
        amount=ZERO
    else:
        amount=max(ZERO,limit-(10000 if day.get('공무용차량') or day.get('운전원본연업무') else 0))
    distance=day.get('왕복거리(km)')
    status=CONFIRMED
    formula=f'{hours}시간: {limit}원 - 차량 감액'
    notes='같은 날 여러 출장의 시간을 합산하여 입력. 1일 총 한도 20,000원.'
    if distance in ('',None):
        status=REVIEW
        notes+=' 왕복 2km 이내 판정을 위한 거리 미입력.'
    elif dec(distance)<=2:
        fare=dec(day.get('근거리운임'))
        meal=min(dec(day.get('근거리식비')),Decimal(25000)/3) if hours>=4 else ZERO
        amount=min(amount,fare+meal)
        status=receipt_status(day)
        formula=f'min(차량 감액 후 한도, 운임 {fare} + min(식비 {day.get("근거리식비",0)}, 25,000/3))'
    if not day.get('거리출처'): status=REVIEW; notes+=' 거리 출처 미입력.'
    ctx.line('일비','근무지 내 출장',d,limit,None,amount,status,formula,'제18조; 지침 Ⅲ.2',notes=notes)

def stay_factor(day):
    n=int(dec(day.get('도착다음날기산일수')))
    return Decimal('0.7') if n>60 else Decimal('0.8') if n>30 else Decimal('0.9') if n>15 else Decimal(1)

def daily(ctx,day,per_diem,meal,currency='KRW'):
    d=str(day['일자'])
    per_diem,meal=Decimal(per_diem),Decimal(meal)
    fixed=currency=='USD'
    status=CONFIRMED
    if day.get('숙식제공여부') and day.get('식비조정액') in ('',None):
        status=REVIEW
    if dec(day.get('식비조정액')) and not day.get('식비조정근거'): status=REVIEW
    meal_amount=max(ZERO,meal-dec(day.get('식비지원액'))-dec(day.get('식비조정액')))
    if day.get('항공선박이동') and not day.get('별도식비필요'):
        meal_amount=ZERO
    vehicle=Decimal('0.5') if day.get('공무용차량') else Decimal(1)
    factor=stay_factor(day)
    ctx.line('일비','날짜별 일비',d,per_diem,None,per_diem*vehicle*factor,CONFIRMED,
             f'{per_diem} × 차량 {vehicle} × 장기체재 {factor}','제16조제3항·제17조; 별표 '+('4' if fixed else '2'),
             currency,per_diem*vehicle*factor,fixed,notes='장기체재는 도착 다음 날부터 기산, 일시 타지역 출장일 제외. 출발일은 0 입력.')
    ctx.line('식비','날짜별 식비',d,meal,dec(day['식비실제지출']) if day.get('식비실제지출') not in ('',None) else None,
             meal_amount,status,f'max(0, {meal} - 지원 {day.get("식비지원액",0)} - 근거 있는 조정 {day.get("식비조정액",0)})',
             '제16조제5항·제28조; 별표 '+('4' if fixed else '2'),currency,meal_amount,fixed,
             notes='제공 식사는 임의 1/3 공제하지 않음. 조정액과 기관 근거를 직접 입력.')
    if fixed and day.get('식비초과신청'):
        actual=dec(day.get('식비실제지출'))
        extra=min(max(ZERO,actual-meal),meal/2)
        ctx.line('식비','국외 식비 추가지급',d,meal/2,actual,extra,receipt_status(day,True),
                 f'min(max(0,실지출 {actual} - 정액 {meal}), 정액×0.5)','제16조제1·2항; 지침 Ⅴ.4',currency,extra,False,
                 notes=str(day.get('승인근거','')))

def mileage_bonus(ctx,eligible_days):
    saving=dec(ctx.trip.meta.get('공적마일리지 절약운임(원)'))
    if not saving or not eligible_days: return
    base_rows=[r for r in ctx.result.lines if r.name=='날짜별 일비' and r.basis is not None]
    if len(base_rows)!=len(eligible_days):
        ctx.line('일비','공적마일리지 추가 일비',str(eligible_days[0]['일자']),status=REVIEW,reference='별표 2·4 비고 1의2; 지침 Ⅳ.5·Ⅴ.5',notes='일비 또는 환율 근거 확인 후 재계산')
        return
    # 추가 일비 총한도 적용 후 날짜별 차량·체재 감액을 배분한다.
    theoretical=sum((r.basis*Decimal('0.5') for r in base_rows),ZERO)
    allowed=min(theoretical,saving/2)
    for row,day in zip(base_rows,eligible_days):
        portion=allowed*(row.basis*Decimal('0.5'))/theoretical if theoretical else ZERO
        portion*=stay_factor(day)*(Decimal('0.5') if day.get('공무용차량') else 1)
        foreign=row.currency=='USD' and row.rate is not None
        value=portion/row.rate if foreign else portion
        ctx.line('일비','공적마일리지 추가 일비',str(day['일자']),None,None,value,
                 CONFIRMED if ctx.trip.meta.get('마일리지증빙확인') else EVIDENCE,
                 f'min(일비합계×50%, 절약운임 {saving}/2) 날짜별 안분 후 차량·체재 감액',
                 '별표 2·4 비고 1의2; 지침 Ⅳ.5·Ⅴ.5',
                 'USD' if foreign else 'KRW',value if foreign else None,foreign)
