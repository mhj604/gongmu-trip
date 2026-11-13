from .models import *
from .rules import destination
from .domestic import daily

def rates_for(ctx,row,group=None):
    grade,reason=destination(str(row.get('국가','')),str(row.get('도시','')),
        str(row.get('최인접수도국가','')),str(row.get('거리근거','')),ctx.rules)
    group=group or ctx.trip.meta.get('지급등급','제2호')
    return (ctx.rules['overseas_rates'].get(group,{}).get(grade),reason)

def calculate_day(ctx,day):
    rates,reason=rates_for(ctx,day)
    if not rates:
        for category in ['일비','식비']:
            ctx.line(category,'국외 '+category,str(day['일자']),status=REVIEW,
                reference='제16조; 별표 4 비고 2·3',notes=reason)
        return
    daily(ctx,day,rates['일비'],rates['식비'],'USD')

def finalize_fixed_rounding(ctx):
    # 정액 항목 전체를 원화 환산 후 10원 미만 절사. 일별 절사 누적 오차를 분리한다.
    groups={}
    for row in ctx.result.lines:
        if row.currency=='USD' and row.foreign_amount is not None and row.rate is not None and row.name in ['날짜별 일비','날짜별 식비','숙박비 할인정액','공적마일리지 추가 일비']:
            groups.setdefault(row.status,[]).append(row)
    for status,rows in groups.items():
        exact=sum((r.foreign_amount*r.rate for r in rows),ZERO)
        delta=ten_won(exact)-sum((r.amount or ZERO for r in rows),ZERO)
        if delta:
            ctx.line('기타 인정 여비','국외 정액여비 원화 절사',rows[-1].date,amount=delta,status=status,
                formula=f'정액여비 환산 합계 {exact}원 → 십원 미만 절사; 일별 표시액 조정 {delta}원',
                reference='지침 Ⅱ.5.나.2)(4)',notes='정액용 원화환율의 소수점은 먼저 절사함.')
