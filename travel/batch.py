"""출장별 결과와 법령 자료집을 보존하는 일괄 계산 모델."""
from dataclasses import dataclass, field
from uuid import uuid4
from .models import Trip, Result, ZERO, CATEGORIES, EXCLUDED, now
from .quick import build_schedule, calculate_preview


@dataclass
class BatchResult:
    results: list[Result]
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    title: str = ''
    generated_at: str = field(default_factory=now)

    def total(self, name):
        # 청구·반납액은 출장별 기지급액을 각각 차감한 후 합산한다.
        return sum((getattr(r,name) for r in self.results),ZERO)

    @property
    def estimated(self):
        return self.total('estimated')

    @property
    def incomplete(self):
        return any(line.amount is None and line.status != EXCLUDED
                   for result in self.results for line in result.lines)

    def category(self, category):
        return sum((line.amount or ZERO for r in self.results for line in r.lines
                    if line.category == category and line.status != EXCLUDED),ZERO)

    def rows(self):
        rows = []
        for i, result in enumerate(self.results,1):
            meta = result.trip['meta']
            row = {'번호':i,'출장명':meta.get('출장명') or f'출장 {i}',
                   '출장 유형':result.trip['kind'],'출발일':meta.get('시작일시','')[:10],
                   '복귀일':meta.get('종료일시','')[:10]}
            for category in CATEGORIES:
                row[category] = sum((line.amount or ZERO for line in result.lines
                                    if line.category == category and line.status != EXCLUDED),ZERO)
            row.update({'예상 출장비':result.estimated,'확정 인정액':result.recognized,
                        '미확정금액':result.pending,'기지급액':result.advance,
                        '확정 청구액':result.claim,'반납예정액':result.refund,
                        '상태':'일부 금액 미산출' if any(line.amount is None and line.status != EXCLUDED for line in result.lines) else '예상액 산출'})
            rows.append(row)
        return rows

    def to_dict(self):
        return {'schema_version':1,'id':self.id,'title':self.title,'generated_at':self.generated_at,
                'results':[r.to_dict() for r in self.results],
                'totals':{name:self.total(name) for name in ('estimated','recognized','pending','advance','claim','refund')}}

    @classmethod
    def from_dict(cls, data):
        return cls([Result.from_dict(r) for r in data['results']],data['id'],data.get('title',''),data['generated_at'])


def calculate_batch(trips, snapshots=None, *, identifier=None, title=''):
    if not trips:
        raise ValueError('출장을 한 건 이상 추가하세요.')
    if len({t.id for t in trips}) != len(trips):
        raise ValueError('같은 출장을 중복해서 추가할 수 없습니다.')
    results = []
    for i, trip in enumerate(trips,1):
        try:
            if trip.meta.get('_금액입력오류'):
                raise ValueError(' · '.join(trip.meta['_금액입력오류'])+'에 올바른 금액을 입력하세요.')
            if not trip.meta.get('_상세입력',not trip.meta.get('간편입력',False)):
                build_schedule(trip)
            results.append(calculate_preview(trip,(snapshots or {}).get(trip.id)))
        except (ValueError,KeyError,TypeError,ArithmeticError) as error:
            raise ValueError(f'출장 {i}: {error}') from error
    return BatchResult(results,identifier or uuid4().hex[:12],title)
