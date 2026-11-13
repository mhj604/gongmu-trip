from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
import json
from uuid import uuid4
from zoneinfo import ZoneInfo

ZERO = Decimal('0')
CONFIRMED = '계산 확정'
EVIDENCE = '증빙 필요'
APPROVAL = '승인 필요'
REVIEW = '근거 확인 필요'
EXCLUDED = '지급 제외'
CATEGORIES = ['일비', '식비', '숙박비', '교통비', '기타 인정 여비']

def dec(value, default='0') -> Decimal:
    if value is None or str(value).strip() == '':
        return Decimal(default)
    try:
        result = Decimal(str(value).replace(',', ''))
    except InvalidOperation as e:
        raise ValueError(f'금액 또는 수량을 숫자로 입력하세요: {value}') from e
    if not result.is_finite() or result < 0:
        raise ValueError('금액과 수량은 0 이상의 유한한 숫자여야 합니다.')
    return result

def won(value: Decimal) -> Decimal:
    return value.quantize(Decimal('1'), rounding=ROUND_DOWN)

def ten_won(value: Decimal) -> Decimal:
    return (value / 10).quantize(Decimal('1'), rounding=ROUND_DOWN) * 10

def money(value) -> str:
    return '미입력' if value is None else f'{Decimal(str(value)):,.0f}원'

def now() -> str:
    return datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')

def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str, allow_nan=False)

@dataclass
class Trip:
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    kind: str = '국내'
    meta: dict = field(default_factory=dict)
    days: list[dict] = field(default_factory=list)
    lodgings: list[dict] = field(default_factory=list)
    transports: list[dict] = field(default_factory=list)
    specials: list[dict] = field(default_factory=list)
    fx: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    settings: dict = field(default_factory=lambda: {'기준 선택': '출장일 기준'})

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        return cls(**{k:v for k,v in value.items() if k in cls.__dataclass_fields__})

@dataclass
class Line:
    category: str
    name: str
    date: str
    basis: Decimal | None
    actual: Decimal | None
    amount: Decimal | None
    status: str
    formula: str
    reference: str
    source: str
    currency: str = 'KRW'
    foreign_amount: Decimal | None = None
    rate: Decimal | None = None
    notes: str = ''
    rule_version: str = ''

    def record(self):
        return dict(zip(['항목','내역','일자','기준금액(원)','실제지출액(원)','인정금액(원)',
                         '상태','계산식','적용근거','출처','통화','외화금액','환율','비고','규칙버전'], asdict(self).values()))

@dataclass
class Result:
    trip: dict
    lines: list[Line] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=now)
    rule_snapshot: dict = field(default_factory=dict)

    @property
    def recognized(self):
        return sum((x.amount or ZERO for x in self.lines if x.status == CONFIRMED), ZERO)

    @property
    def pending(self):
        return sum((x.amount or ZERO for x in self.lines if x.status not in (CONFIRMED,EXCLUDED)),ZERO)

    @property
    def estimated(self):
        """입력 조건으로 산출 가능한 참고액. 승인·증빙 확정액과 구분한다."""
        return self.recognized+self.pending

    @property
    def advance(self):
        return dec(self.trip['meta'].get('기지급액'))

    @property
    def claim(self):
        return max(ZERO, self.recognized-self.advance)

    @property
    def refund(self):
        return max(ZERO, self.advance-self.recognized)

    def summary(self):
        rows=[]
        for cat in CATEGORIES:
            ls=[x for x in self.lines if x.category==cat]
            rows.append({'항목':cat,
                '기준금액':sum((x.basis or ZERO for x in ls),ZERO),
                '실제 지출액':sum((x.actual or ZERO for x in ls),ZERO) if any(x.actual is not None for x in ls) else None,
                '인정금액':sum((x.amount or ZERO for x in ls if x.status==CONFIRMED),ZERO),
                '미확정금액':sum((x.amount or ZERO for x in ls if x.status not in (CONFIRMED,EXCLUDED)),ZERO)})
        return rows

    def to_dict(self):
        return {**asdict(self),'recognized':self.recognized,'pending':self.pending,'claim':self.claim,'refund':self.refund}

    @classmethod
    def from_dict(cls,data):
        lines=[]
        for raw in data['lines']:
            row=raw.copy()
            for key in ['basis','actual','amount','foreign_amount','rate']:
                row[key]=None if row.get(key) is None else Decimal(str(row[key]))
            lines.append(Line(**row))
        return cls(data['trip'],lines,data['issues'],data['generated_at'],data['rule_snapshot'])
