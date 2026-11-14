"""간편 입력을 기존 계산 엔진의 일정으로 변환한다."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal, ROUND_DOWN
from .models import Trip, ZERO, REVIEW, EXCLUDED, dec
from .engine import calculate


def build_schedule(trip):
    """한 출장지의 합계 입력. 금액의 마지막 나머지도 보존한다."""
    m = trip.meta
    start = date.fromisoformat(m['시작일시'][:10])
    end = date.fromisoformat(m['종료일시'][:10])
    nights = (end-start).days
    if not 0 <= nights <= 730:
        raise ValueError('복귀일은 출발일 이후, 730일 이내로 입력하세요.')
    country = m.get('기본국가', '대한민국') if trip.kind == '국외' else '대한민국'
    place = {'국가': country, '도시': m.get('기본도시', '')}
    local = trip.kind == '국내' and m.get('간편출장범위') == '근무지 내'
    trip.days = [{**place, '일자': str(start+timedelta(days=i)), '여비인정일': True,
                  '공무용차량': m.get('간편공용차량', False), '도착다음날기산일수': str(i),
                  '동일행정구역': local, '출장시간(h)': m.get('간편시간', '8'),
                  '왕복거리(km)': m.get('간편거리', '') if local else '',
                  '거리출처': '사용자 입력' if local else '',
                  '거리구간확인': '' if local else '다른 시군·왕복 12km 이상',
                  '근거리운임': m.get('간편교통비', '0'), '근거리식비': m.get('간편근거리식비', '0')}
                 for i in range(nights+1)]
    total = dec(m.get('간편숙박비'))
    share = (total/nights).quantize(Decimal('1'), rounding=ROUND_DOWN) if nights else ZERO
    trip.lodgings = [{**place, '숙박일': str(start+timedelta(days=i)),
                      '지역구분': m.get('간편지역', '기타'), '실제숙박': True,
                      '실제지출액': str(share if i < nights-1 else total-share*(nights-1)),
                      '통화': 'KRW', '결제수단': '국내원화예약', '증빙확인': False,
                      '입력방식': '출장 전체 숙박비 합계',
                      '배분설명': '계산을 위한 균등배분. 일별 실제 지출은 상세 입력에서 작성.'}
                     for i in range(nights)] if total else []
    fare = dec(m.get('간편교통비'))
    trip.transports = [{'일자': str(start), '교통수단': m.get('간편교통수단', '철도'),
                        '좌석등급': '이코노미' if m.get('간편교통수단') == '항공' else '일반실',
                        '도착지': place['도시'], '실제지출액': str(fare), '통화': 'KRW',
                        '증빙확인': False, '입력방식': '출장 전체 왕복 교통비 합계'}] if fare and not local else []
    if m.get('간편교통수단') == '자가용' and not local:
        trip.transports = [{'일자': str(start), '교통수단': '자가용', '통화': 'KRW',
            '도착지': place['도시'], '입력방식': '출장 전체 자가용 왕복 합계',
            '자가용정산방식': m.get('간편자가용방식','대중교통 운임'),
            '대중교통운임': m.get('간편대중교통운임',''), '운임출처': m.get('간편운임출처',''),
            '거리(km)': m.get('간편주행거리',''), '거리출처': m.get('간편거리출처',''),
            '유종': m.get('간편유종','휘발유'), '유가': m.get('간편유가',''),
            '유가출처': m.get('간편유가출처',''), '통행료': m.get('간편통행료','0'),
            '주차료': m.get('간편주차료','0'), '부득이한사유': m.get('간편자가용사유',''),
            '동승자': m.get('간편동승자',False), '승인': m.get('간편자가용승인',False),
            '승인근거': m.get('간편자가용승인근거',''), '증빙확인': m.get('간편자가용증빙',False)}]
    if trip.kind == '국외':
        trip.fx = [{'통화': 'USD', '1단위당 원화': m.get('간편환율', ''),
                    '기준일': str(start), '출처': '사용자 입력 예상 환율',
                    '환율종류': '현찰 매입(출장자 구매)', '증빙확인': False}]


def calculate_preview(trip, rules=None):
    """미확인 환율은 예상액에만 사용하며 확정 청구액을 만들지 않는다."""
    preview = deepcopy(trip)
    provisional = [r for r in preview.fx if r.get('출처') == '사용자 입력 예상 환율'
                   and not r.get('증빙확인') and dec(r.get('1단위당 원화')) > 0]
    for row in provisional:
        row['증빙확인'] = True
    result = calculate(preview, rules)
    result.trip = trip.to_dict()
    if provisional:
        result.issues.insert(0, '사용자 입력 예상 환율로 계산했습니다. 실제 환율과 증빙을 입력하기 전에는 확정 청구액이 아닙니다.')
        for line in result.lines:
            if line.status != EXCLUDED:
                line.status = REVIEW
                line.notes += '; 예상 환율을 사용한 참고 계산'
    return result
