"""화면·엑셀·워드가 공동으로 사용하는 유일한 계산 진입점."""
from datetime import datetime, date, timedelta
from decimal import Decimal
from .models import *
from .rules import snapshot
from .context import Context
from . import domestic, overseas, expenses, special

def calculate(trip:Trip,rules=None)->Result:
    rules=rules or snapshot()
    result=Result(trip.to_dict(),rule_snapshot=rules)
    ctx=Context(trip,result,rules)
    basic_missing=[key for key in ['성명','소속기관','출장명','출장목적','시작일시','종료일시','지급등급'] if not trip.meta.get(key)]
    result.issues.extend(f'필수 기본정보 미입력: {k}' for k in basic_missing)
    try:
        start=datetime.fromisoformat(trip.meta['시작일시'])
        end=datetime.fromisoformat(trip.meta['종료일시'])
        if start.tzinfo is None or end.tzinfo is None: raise ValueError('시간대 필요')
        if end<start: raise ValueError('종료가 시작보다 빠름')
    except (ValueError,KeyError,TypeError):
        result.issues.append('시작·종료 일시와 시간대를 확인하세요.')
        return result
    if trip.kind not in ['국내','국외','특수']:
        result.issues.append('출장 유형을 확인하세요.'); return result
    if trip.meta.get('지급등급') not in rules['overseas_rates']:
        result.issues.append('별표 1 지급등급 확인 필요.'); return result
    seen=set()
    eligible=[]
    if trip.kind!='특수' and not trip.days: result.issues.append('일별 일정 미입력')
    for day in trip.days:
        d=str(day.get('일자',''))
        try: date.fromisoformat(d)
        except ValueError: result.issues.append('일별 일정 날짜 형식을 확인하세요.');continue
        if d in seen and not day.get('날짜변경선근거'):
            result.issues.append(f'{d}: 일정 중복. 같은 날 여러 근무지 내 출장은 1개 행으로 합산하세요.');continue
        seen.add(d)
        if d<start.date().isoformat() or d>end.date().isoformat():
            if not day.get('날짜변경선근거'):
                result.issues.append(f'{d}: 출장기간 밖 일정, 날짜변경선 이동 근거 확인 필요.');continue
        if not day.get('여비인정일',True):
            ctx.line('일비','비공무 일정',d,amount=ZERO,status=EXCLUDED,reference='제4·5조',notes='일비·식비 인정일에서 제외');continue
        if trip.kind=='국내':
            is_local,reason=domestic.local_trip(ctx,day)
            if is_local is None:
                ctx.line('일비','근무지 판정',d,status=REVIEW,reference='제18조',notes=reason);continue
            if is_local:
                domestic.local(ctx,day)
            else:
                domestic.daily(ctx,day,rules['domestic']['일비'],rules['domestic']['식비'])
                eligible.append(day)
        elif trip.kind=='국외':
            overseas.calculate_day(ctx,day)
            eligible.append(day)
    if trip.kind!='특수':
        expected={str(start.date()+timedelta(days=i)) for i in range((end.date()-start.date()).days+1)}
        for d in sorted(expected-seen):
            result.issues.append(f'{d}: 일정 누락. 공무·이동·개인 일정을 모두 기록하세요.')
            ctx.line('일비','일정 누락',d,status=REVIEW,reference='제5·16조')
    domestic.mileage_bonus(ctx,eligible)
    local_dates={r.date for r in result.lines if r.name=='근무지 내 출장'}
    unresolved_dates={r.date for r in result.lines if r.name=='근무지 판정'}
    for row in trip.transports:
        d=expenses.expense_date(ctx,row)
        if not row.get('일자') or d<start.date().isoformat() or d>end.date().isoformat():
            ctx.line('교통비','운임 일자 확인',d,status=REVIEW,reference='제4·5조',notes='이동일 미입력 또는 출장기간 밖 지출');continue
        if d in unresolved_dates:
            ctx.line('교통비','근무지 판정 후 운임 산출',d,status=REVIEW,reference='제18조',notes='근무지 내·외 구분 확인 필요');continue
        if trip.kind=='국내' and d in local_dates:
            ctx.line('교통비','근무지 내 별도운임',d,actual=dec(row.get('실제지출액')),amount=ZERO,status=EXCLUDED,
                reference='지침 Ⅲ.2',notes='근무지 내 여비에 포함. 불가피한 유료 도서연결 통행료 예외는 별도 법적 검토 필요.')
        else: expenses.transport(ctx,row)
    lodging_dates=set()
    lodgings=[]
    for row in trip.lodgings:
        d=expenses.expense_date(ctx,row)
        if not row.get('숙박일'):
            ctx.line('숙박비','숙박일 미입력',d,status=REVIEW,reference='제16조제4항');continue
        if d in lodging_dates:
            result.issues.append(f'{d}: 숙박 중복. 숙박 1건으로 합산하세요.');continue
        lodging_dates.add(d)
        if d in local_dates:
            ctx.line('숙박비','근무지 내 별도숙박',d,amount=ZERO,status=EXCLUDED,reference='지침 Ⅲ.2');continue
        if d in unresolved_dates:
            ctx.line('숙박비','근무지 판정 후 숙박 산출',d,status=REVIEW,reference='제18조');continue
        if d<start.date().isoformat() or d>=end.date().isoformat():
            if not row.get('주간숙박사유'):
                ctx.line('숙박비','출장 숙박일 확인',d,status=REVIEW,reference='제16조제4항',notes='복귀일 숙박·기간 밖 숙박은 주간숙박 등 사유 필요');continue
        lodgings.append(row)
    original=trip.lodgings
    trip.lodgings=lodgings
    try: expenses.lodging(ctx)
    finally: trip.lodgings=original
    for row in trip.specials: special.calculate(ctx,row)
    if trip.kind=='국외': overseas.finalize_fixed_rounding(ctx)
    # 등급과 기관의 지급 결정은 프로그램이 임의로 승인하지 않는다.
    if not trip.meta.get('공무원',True):
        if not trip.meta.get('별표9기준') or not trip.meta.get('비공무원등급근거'):
            result.issues.append('비공무원의 별표 9 구분 및 지급등급 결정 근거 미입력')
            for line in result.lines:
                if line.status==CONFIRMED: line.status=REVIEW
    if trip.meta.get('직위직급') in ['대통령','국무총리']:
        result.issues.append('대통령·국무총리의 일비·식비는 실비 대상이며 자동 정액 계산을 지원하지 않습니다.')
        for line in result.lines:
            if line.category in ['일비','식비']: line.status=REVIEW
    if not trip.meta.get('출장승인'):
        result.issues.append('출장 명령 승인 전: 계산 금액은 승인 대기입니다.')
        for line in result.lines:
            if line.status==CONFIRMED: line.status=APPROVAL
    if basic_missing:
        for line in result.lines:
            if line.status==CONFIRMED: line.status=REVIEW
    for line in result.lines:
        if line.status not in [CONFIRMED,EXCLUDED]:
            result.issues.append(f'{line.date} {line.name}: {line.status} — {line.notes}')
    return result
