"""공동 출장자는 숙박비만 분담하며 다른 여비의 일정을 만들지 않는다."""
from .models import ZERO, EXCLUDED, dec, won


def participants(meta):
    count = dec(meta.get('공동숙박인원', 2))
    if count != int(count) or not 2 <= count <= 20:
        raise ValueError('공동숙박 인원은 본인을 포함해 2~20명으로 입력하세요.')
    group = meta.get('지급등급', '제2호')
    rows = [{'id': 'self', 'name': '본인' + (' · '+meta['성명'] if meta.get('성명') else ''), 'group': group}]
    companions = meta.get('공동숙박자', [])
    for i in range(int(count)-1):
        person = companions[i] if i < len(companions) else {}
        name = person.get('성명', '').strip()
        grade = person.get('지급등급') or group
        if grade not in ('제2호', '제1호가', '제1호나', '제1호다', '제1호라'):
            raise ValueError('공동 출장자의 지급 등급을 선택하세요.')
        rows.append({'id': f'companion{i+1}', 'name': f'공동 출장자 {i+1}' + (' · '+name if name else ''), 'group': grade})
    return rows


def split_amount(total, count):
    """원 단위 나머지는 마지막 분담자에게 배정하여 영수증 총액을 보존한다."""
    share = won(total/count)
    return [share]*(count-1) + [total-share*(count-1)]


def allocation(result):
    """화면과 출력 문서가 공통으로 사용하는 사람별 숙박 정산 내역."""
    people = {}
    for line in result.lines:
        if line.category != '숙박비' or not line.lodging_person_id:
            continue
        row = people.setdefault(line.lodging_person_id, {
            '정산 대상': line.lodging_person_name, '지급 등급': line.lodging_person_group,
            '숙박일': set(), '분담액': ZERO, '상한': ZERO, '예상 인정액': ZERO,
            '상태': set(), '실비': line.lodging_person_group.startswith('제1호')})
        row['숙박일'].add(line.date)
        row['분담액'] += line.actual or ZERO
        row['상한'] += line.basis or ZERO
        if line.status != EXCLUDED:
            row['예상 인정액'] += line.amount or ZERO
        row['상태'].add(line.status)
    return [{**row, '숙박일': len(row['숙박일']), '상한': '실비' if row['실비'] else row['상한'],
             '상태': ' · '.join(sorted(row['상태']))} for row in people.values()]


SCOPE_NOTE = '공동 출장자는 숙박비만 포함합니다. 일비·식비·교통비는 본인 1명분입니다.'
