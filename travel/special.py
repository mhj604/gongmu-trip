"""별표 5·6의2·8 및 가족·준비금·퇴직 등 특수 여비."""
from datetime import date
from decimal import Decimal
from .models import *
from .context import receipt_status, net
from .expenses import expense_date

PREPARATION=['비자발급비','예방접종비','여행자보험','풍토병예방약','법정감염병검사']

def calculate(ctx,row):
    kind=row.get('종류','기타 특례')
    d=expense_date(ctx,row)
    currency=row.get('통화','KRW')
    actual=dec(row.get('실제지출액')) if row.get('실제지출액') not in ('',None) else None
    amount=net(row,actual or ZERO)
    status=receipt_status(row,True)
    ref='제28·29조'
    formula='공식 근거와 협의·승인 문서에 따른 금액'
    notes=str(row.get('승인근거',''))
    if kind in PREPARATION:
        ref='제23조; 지침 Ⅴ.6'
        status=receipt_status(row)
        formula='준비금 법정 항목 실지출 - 할인·지원·기관부담'
        if ctx.trip.kind!='국외': status=EXCLUDED; amount=ZERO
        if kind=='법정감염병검사' and not row.get('출입국필수'): status=REVIEW
        if actual is None: status=REVIEW
    elif kind in ['국내 이전비','국외 이전비']:
        ref='제19·20조; 별표 5; 지침 Ⅵ'
        qty=dec(row.get('화물량'))
        first=dec(row.get('기본구간실비'))
        extra=dec(row.get('초과구간실비'))
        threshold=Decimal(5 if kind=='국내 이전비' else 15)
        maximum=Decimal('7.5' if kind=='국내 이전비' else '25')
        amount=net(row,first+(extra/2 if qty>threshold else ZERO))
        formula=f'기본구간({threshold}까지) 실비 {first} + 인정 초과구간({maximum}까지) 실비 {extra} × 50%'
        if qty<=0 or row.get('기본구간실비') in ('',None) or (qty>threshold and row.get('초과구간실비') in ('',None)):
            status=REVIEW
        if qty>maximum: notes+=f'; {maximum} 초과 비용은 초과구간실비 입력에서 제외해야 함'
        if not row.get('이전요건확인') or not row.get('발령일') or not row.get('이전일'): status=REVIEW
        if row.get('이전일'):
            notes+='; 청구기한: 이전 다음날 기산 6개월(제20조). 국내 발령 후 1년 내 이전 여부 확인.'
    elif kind in ['국내 가족여비','국외 가족여비']:
        overseas=kind=='국외 가족여비'
        ref='제21·22조; '+('별표 6의2' if overseas else '제21조제3·4항')
        age=int(dec(row.get('나이')))
        ratio=Decimal(2)/3 if age>=12 else Decimal(1)/3
        fare=dec(row.get('본인기준운임'))
        stay=dec(row.get('본인기준숙박비'))
        daily=dec(row.get('본인기준일비식비'))
        prep=dec(row.get('본인기준준비금'))
        case=int(dec(row.get('국외지급사유',1)))
        amount=fare+(prep+(stay+daily)*ratio if overseas else stay+daily*ratio)
        if overseas and case in (7,8): amount=fare
        formula=f'운임 {fare} + '+(f'준비금 {prep} + (숙박 {stay}+일비식비 {daily})×{ratio}' if overseas else f'숙박 {stay} + 일비식비 {daily}×{ratio}')
        if overseas and case in (7,8): formula='별표 6의2 제7·8호: 운임 전액만'
        child=row.get('관계')=='자녀'
        if child and (row.get('독립생계') or (age>=26 and not row.get('자녀예외확인'))):
            amount=ZERO; status=EXCLUDED
        elif not row.get('가족요건확인') or not row.get('본인기준산출근거') or (overseas and case not in range(1,9)):
            status=REVIEW
        amount=net(row,amount)
        notes+='; 동반·허가·연령 등 사유별 요건은 증빙에서 확인. 본인 기준은 해당 가족 여행구간 산출액.'
    elif kind=='상시출장 월액':
        ref='제29조제2항; 별표 8 제1~4호'
        days=dec(row.get('인정출장일수'))
        monthly=dec(row.get('기관확정월액'))
        amount=monthly*min(days,Decimal(15))/15
        formula=f'기관 확정 월정액 {monthly} × min(인정출장일 {days},15) ÷ 15'
        if not row.get('대상호') in ['1','2','3','4'] or not row.get('기관지급기준'): status=REVIEW
        notes+='; 관할 외 출장 및 본 업무 외 출장일은 인정일수에서 제외'
    elif kind=='상시출장 일액':
        ref='제29조제2항; 별표 8 제5~7호'
        amount=dec(row.get('기관확정일액'))*dec(row.get('인정출장일수'))
        formula=f'기관 확정 일액 {row.get("기관확정일액")} × 인정출장일 {row.get("인정출장일수")}'
        if not row.get('대상호') in ['5','6','7'] or not row.get('기관지급기준'): status=REVIEW
    elif kind=='국내 사망자 여비':
        ref='제26조제1항'
        amount=dec(row.get('전직상당구간여비'))*2
        formula=f'전임지·신임지 관련 해당구간 전직 상당 여비 {row.get("전직상당구간여비")} × 2'
        if not row.get('본인기준산출근거'): status=REVIEW
    elif kind in ['퇴직·휴직 여비','사무인계 여비','국외 사망자 수습','유족 귀국','기타 특례']:
        ref={'퇴직·휴직 여비':'제24조','사무인계 여비':'제25조','국외 사망자 수습':'제26조제2·3항','유족 귀국':'제26조제4항','기타 특례':'제29조제1항'}[kind]
        # 사유별 구간/자격·기한 판정은 수동 심사 대상으로 명시한다.
        status=REVIEW
        notes+='; 자동 지급요건 판정 미지원. 일반 출장 엔진에서 해당 구간을 산출하여 소관기관 검토 필요.'
    else:
        status=REVIEW
        notes+='; 지급 항목 및 공식 근거 확인 필요'
    ctx.line('기타 인정 여비',kind,d,actual,actual,amount,status,formula,ref,currency,amount,notes=notes,rate_id=row.get('환율ID',''))
