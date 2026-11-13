"""실비 운임 및 출장 전체 숙박비 정산."""
from decimal import Decimal, ROUND_HALF_UP
from .models import *
from .context import receipt_status, net
from .overseas import rates_for

def expense_date(ctx,row):
    return str(row.get('일자') or row.get('숙박일') or str(ctx.trip.meta.get('시작일시',''))[:10])

def transport(ctx,row):
    day=expense_date(ctx,row)
    mode=row.get('교통수단','철도')
    currency=row.get('통화','KRW')
    actual=None if row.get('실제지출액') in ('',None) else dec(row['실제지출액'])
    amount=net(row,actual or ZERO)
    status=receipt_status(row)
    formula='max(0, 실제지출 - 할인 - 기관부담 - 지원액)'
    notes=f'{row.get("출발지","")} → {row.get("도착지","")}; 좌석 {row.get("좌석등급","")}'
    reference='제9~15조; 별표 2·3; 지침 Ⅳ.2·Ⅴ.2'
    group=ctx.trip.meta.get('지급등급','제2호')
    if actual is None and mode not in ['자가용','공무용차량']: status=REVIEW
    if mode in ['무료교통','공무용차량']:
        amount=dec(row.get('통행료'))+dec(row.get('주차료'))
        formula='운임 0 + 증빙 있는 통행료 + 주차료'
    if mode=='자가용':
        if row.get('동승자'):
            amount=ZERO; status=EXCLUDED; notes+='; 동승자는 운임 제외'
        elif row.get('부득이한사유'):
            efficiency=dec(ctx.rules['fuel_efficiency'].get(row.get('유종','휘발유'),'0'))
            if not efficiency or row.get('유가') in ('',None) or row.get('거리(km)') in ('',None):
                status=REVIEW; amount=None
            else:
                amount=dec(row.get('거리(km)'))*dec(row.get('유가'))/efficiency+dec(row.get('통행료'))+dec(row.get('주차료'))
                amount=net(row,amount)
                formula=f'거리 {row.get("거리(km)")} × 단위가격 {row.get("유가")} ÷ 법정연비 {efficiency} + 통행료 + 주차료 - 지원'
                status=receipt_status(row,True)
                if not row.get('거리출처') or not row.get('유가출처'): status=REVIEW
        else:
            amount=net(row,dec(row.get('대중교통운임')))
            formula='같은 구간 법정 좌석의 철도·버스 운임 - 지원액'
            if row.get('대중교통운임') in ('',None) or not row.get('운임출처'): status=REVIEW
    if mode=='항공':
        allowed='일등석' if group=='제1호가' else '비즈니스' if group.startswith('제1호') else '이코노미'
        seat=row.get('좌석등급','이코노미')
        ranks={'이코노미':0,'프리미엄이코노미':1,'비즈니스':2,'일등석':3}
        if ranks.get(seat,99)>ranks[allowed]:
            if not(row.get('승인') and row.get('승인근거')): status=APPROVAL
            else: status=REVIEW; notes+='; 좌석 상향의 법정 대상·예산집행지침 별도 확인 필요'
        notes+=f'; 일반 지급 좌석 {allowed}'
        if row.get('마일리지처리')=='보너스항공권':
            amount=net(row,actual or ZERO)
            notes+='; 현금 실결제액만 입력(마일리지 환산액 중복 청구 제외)'
    if ctx.trip.kind=='국내' and mode=='철도' and group=='제2호' and row.get('좌석등급')=='특실':
        if not(row.get('승인') and row.get('승인근거')): status=APPROVAL
        else: status=REVIEW; notes+='; 동행 등급 조정의 법정 요건 확인 필요'
    if mode in ['택시','기타']:
        status=REVIEW; notes+='; 현지 일비와 중복되는 운임 여부 및 별도 지급 근거 확인 필요'
    if row.get('기관직접결제'):
        amount=ZERO; status=EXCLUDED; notes+='; 기관 직접결제: 개인 청구 제외'
    ctx.line('교통비',mode,day,actual,actual,amount,status,formula,reference,currency,amount,
             notes=notes,rate_id=row.get('환율ID',''))

def lodging(ctx):
    records=[]
    overseas=ctx.trip.kind=='국외'
    discount=overseas and ctx.trip.meta.get('숙박정산방식')=='할인정액'
    foreign_pool={}
    group=ctx.trip.meta.get('지급등급','제2호')
    for row in ctx.trip.lodgings:
        day=expense_date(ctx,row)
        currency=row.get('통화','KRW')
        ref='제16조; 별표 '+('4' if overseas else '2')+'; 지침 '+('Ⅱ.5·Ⅴ.3' if overseas else 'Ⅳ.3')
        if not row.get('실제숙박',True) or row.get('무료숙박'):
            ctx.line('숙박비','무료 또는 미숙박',day,amount=ZERO,status=EXCLUDED,reference=ref,
                     notes='실제 숙박이 없거나 숙박비가 발생하지 않음')
            continue
        effective_group=row.get('동행조정등급') or group
        if overseas:
            rates,reason=rates_for(ctx,row,effective_group)
            if not rates:
                ctx.line('숙박비','국외 숙박',day,status=REVIEW,reference=ref,notes=reason); continue
            usd_cap=Decimal(rates['숙박비'])
            if discount:
                # 지침 예시처럼 미달러 소수점 이하는 절사하며 동일 등급 합계로 계산.
                records.append((row,usd_cap,None,None,day,ref))
                continue
            cap_rate=ctx.fx('USD',day,True)
            if cap_rate is None:
                ctx.line('숙박비','국외 숙박',day,status=REVIEW,reference=ref,notes='상한 산정용 USD 현찰 구매 환율·출처·증빙 필요');continue
            cap=won(usd_cap*cap_rate)
            actual=dec(row.get('실제지출액'))
            local_net=net(row,actual)
            payment=row.get('결제수단','개인카드')
            if currency=='KRW':
                actual_rate=Decimal(1)
                net_amount=won(local_net)
                usd_actual=local_net/cap_rate
            else:
                cross=Decimal(1) if currency=='USD' else dec(row.get('1USD당현지통화'))
                if not cross or (currency!='USD' and not(row.get('현지환율출처') and row.get('현지환율기준일'))):
                    ctx.line('숙박비','국외 숙박',day,status=REVIEW,reference=ref,notes='신청 당시 1USD당 현지통화 환율·기준일·출처 필요');continue
                cross=cross.quantize(Decimal('0.0001'),rounding=ROUND_HALF_UP)
                local_cap=(usd_cap*cross).quantize(Decimal('1'),rounding=ROUND_HALF_UP)
                usd_actual=local_net/cross
                if payment=='현금':
                    if not row.get('현금사용사유'):
                        ctx.line('숙박비','국외 현금 숙박',day,status=REVIEW,reference=ref,notes='카드 사용 불가 등 현금 사용 사유 필요');continue
                    net_amount=won(usd_actual*cap_rate)
                    actual_rate=cap_rate/cross
                else:
                    if row.get('카드청구원화액') in ('',None):
                        ctx.line('숙박비','국외 카드 숙박',day,status=EVIDENCE,reference=ref,notes='수수료 포함 카드청구 원화액 필요. 임의환율 대신 카드사 청구액 입력');continue
                    claimed=dec(row.get('카드청구원화액'))
                    net_amount=won(claimed*local_net/actual) if actual else ZERO
                    actual_rate=claimed/actual if actual else Decimal(1)
                # 현지통화 반올림 상한 범위 안이면 USD 비교에서도 상한 이내로 처리.
                if local_net<=local_cap and usd_actual>usd_cap:usd_actual=usd_cap
        else:
            cap=None if effective_group.startswith('제1호') else Decimal(ctx.rules['domestic']['숙박상한'].get(row.get('지역구분','기타'),70000))
            actual=dec(row.get('실제지출액'))
            net_amount=won(net(row,actual))
        if row.get('실제지출액') in ('',None):
            ctx.line('숙박비','숙박 지출액 미입력',day,cap,status=REVIEW,reference=ref);continue
        status=receipt_status(row)
        if effective_group!=group and not(row.get('승인') and row.get('승인근거')): status=APPROVAL
        if row.get('기관직접결제'):
            ctx.line('숙박비','기관 직접결제 숙박',day,cap,actual,ZERO,EXCLUDED,reference=ref,
                     notes='기관 부담 숙박은 개인 청구와 상한 풀에서 제외');continue
        line=ctx.line('숙박비','숙박비 실비',day,cap,won(actual*actual_rate) if overseas else actual,ZERO,status,
            '출장 전체의 실제 순지출 합계와 날짜별 상한 합계 중 작은 금액을 순지출 비율로 배분',ref,
            notes=f'{row.get("국가", "")} {row.get("도시",row.get("지역구분",""))}; 승인 {row.get("승인근거","")}; 지원·할인 차감 후 {net_amount}원')
        line.currency=currency
        line.foreign_amount=actual if overseas else None
        line.rate=actual_rate if overseas else Decimal(1)
        if overseas:
            foreign_pool[id(line)]={'usd_actual':usd_actual,'usd_cap':usd_cap,'cap_rate':cap_rate}
            line.notes+=f'; USD 비교액 {usd_actual}, USD 상한 {usd_cap}; 결제수단 {row.get("결제수단","개인카드")}'
        records.append((row,cap,net_amount,line,day,ref))
    if discount:
        grouped={}
        for row,cap,_,__,day,ref in records:
            grouped.setdefault(cap,[]).append((row,day,ref))
        for cap,items in grouped.items():
            amount=won(cap*len(items)*Decimal('0.85'))
            status=CONFIRMED if ctx.trip.meta.get('할인정액승인') and ctx.trip.meta.get('할인정액승인근거') else APPROVAL
            ctx.line('숙박비','숙박비 할인정액',items[0][1],cap*len(items),None,amount,status,
                f'{cap} USD × {len(items)}박 × 85% → 달러 미만 절사',items[0][2],
                'USD',amount,True,notes=str(ctx.trip.meta.get('할인정액승인근거','')))
        return
    # 근거/증빙 미완료인 숙박은 확정된 풀과 혼합하지 않는다.
    for status in {r[3].status for r in records}:
        pool=[r for r in records if r[3].status==status]
        actual_total=sum((r[2] for r in pool),ZERO)
        base_cap=sum((r[1] if r[1] is not None else r[2] for r in pool),ZERO)
        allowed=min(actual_total,base_cap)
        if overseas:
            usd_total=sum((foreign_pool[id(r[3])]['usd_actual'] for r in pool),ZERO)
            usd_cap_total=sum((foreign_pool[id(r[3])]['usd_cap'] for r in pool),ZERO)
            if usd_total<=usd_cap_total:allowed=actual_total
            else:allowed=min(actual_total,base_cap)
            # 개인 카드·현금 지급금액의 십원 미만 절사(지침 Ⅱ.5 정산 예시).
            allowed=ten_won(allowed)
        remaining=allowed
        for i,record in enumerate(pool):
            line=record[3]
            line.amount=remaining if i==len(pool)-1 else won(allowed*record[2]/actual_total) if actual_total else ZERO
            remaining-=line.amount
            line.notes+=f'; 출장 정산풀 순지출 {actual_total}, 상한 {base_cap}, 인정 {allowed}원'
        if overseas:
            requested=[r for r in pool if r[0].get('초과신청')]
            if requested and usd_total>usd_cap_total:
                expanded_usd=usd_cap_total+sum((foreign_pool[id(r[3])]['usd_cap']/2 for r in requested),ZERO)
                expanded_krw=base_cap+sum((r[1]/2 for r in requested),ZERO)
                expanded_amount=actual_total if usd_total<=expanded_usd else min(actual_total,expanded_krw)
                extra=max(ZERO,ten_won(expanded_amount)-allowed)
                states=[receipt_status(r[0],True) for r in requested]
                extra_status=CONFIRMED if all(s==CONFIRMED for s in states) else EVIDENCE if EVIDENCE in states else APPROVAL
                if any(r[0].get('동행조정등급') for r in requested):extra_status=REVIEW
                ctx.line('숙박비','숙박비 초과 추가지급',requested[0][4],amount=extra,status=extra_status,
                    formula=f'USD 합계 {usd_total}와 확대 상한 {expanded_usd} 비교 후 원화액 십원 미만 절사; 기본 인정액 {allowed} 차감',
                    reference=requested[0][5]+'·제16조제1·2항',notes='; '.join(str(r[0].get('승인근거','')) for r in requested))
            continue
        excess=max(ZERO,actual_total-base_cap)
        if excess:
            for row,cap,net_amount,line,day,ref in pool:
                if not row.get('초과신청') or cap is None: continue
                extra=min(excess,cap*Decimal('0.5' if overseas else '0.3'))
                if row.get('동행조정등급'):
                    extra_status=REVIEW
                else: extra_status=receipt_status(row,True)
                ctx.line('숙박비','숙박비 초과 추가지급',day,amount=extra,status=extra_status,
                    formula=f'미충당 초과액과 상한 {cap} × {"50%" if overseas else "30%"} 중 작은 금액',
                    reference=ref+'·제16조제1·2항',notes=str(row.get('승인근거','')))
                excess-=extra
