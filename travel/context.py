from datetime import date
from decimal import Decimal, ROUND_DOWN
from .models import *
from .rules import select_law, select_guideline

class Context:
    def __init__(self,trip,result,rules):
        self.trip,self.result,self.rules=trip,result,rules

    def day_basis(self,day):
        return self.trip.settings.get('재계산 기준일',day) if self.trip.settings.get('기준 선택')=='지정일 기준 재계산' else day

    def law(self,day):
        return select_law(self.day_basis(day),self.rules)

    def guideline(self,day):
        return select_guideline(self.day_basis(day),self.rules)

    def fx(self,currency,day,fixed=False,rate_id=''):
        if currency=='KRW': return Decimal(1)
        rows=[r for r in self.trip.fx if r.get('통화')==currency and (not rate_id or r.get('환율ID')==rate_id)]
        rows=[r for r in rows if r.get('기준일') and (str(r['기준일'])<=day or (rate_id and not fixed)) and r.get('출처') and r.get('증빙확인')]
        if not rows: return None
        row=sorted(rows,key=lambda r:str(r['기준일']))[-1]
        rate=dec(row.get('1단위당 원화'))
        if rate<=0: return None
        if fixed and row.get('환율종류')!='현찰 매입(출장자 구매)': return None
        return rate.quantize(Decimal('1'),rounding=ROUND_DOWN) if fixed else rate

    def line(self,category,name,day,basis=None,actual=None,amount=None,status=CONFIRMED,
             formula='',reference='',currency='KRW',foreign=None,fixed=False,notes='',rate_id=''):
        law=self.law(day)
        guideline=self.guideline(day)
        if law is None:
            status=REVIEW
            notes+='; 2026-01-02 이전 법령 자료 미탑재'
        if day>self.rules['as_of'] and self.day_basis(day)>self.rules['as_of']:
            status=REVIEW
            notes+='; 법령 자료집 기준일 이후 출장: 적용 법령 갱신 필요'
        if '지침' in reference and guideline is None:
            status=REVIEW
            notes+='; 해당 날짜의 업무지침 미확보'
        source=law['url'] if law else 'https://www.law.go.kr/법령/공무원여비규정'
        if '지침' in reference and guideline:
            source+='\n'+guideline['url']
        rate=self.fx(currency,day,fixed,rate_id)
        if currency!='KRW':
            if rate is None:
                status=REVIEW
                notes+='; 환율·기준일·출처·증빙 확인 필요'+(' (정액은 현찰 구매 환율)' if fixed else '')
                basis=actual=amount=None
            else:
                basis=won(basis*rate) if basis is not None else None
                actual=won(actual*rate) if actual is not None else None
                amount=won(amount*rate) if amount is not None else None
        else:
            basis=won(basis) if basis is not None else None
            actual=won(actual) if actual is not None else None
            amount=won(amount) if amount is not None else None
        item=Line(category,name,day,basis,actual,amount,status,formula,reference,source,currency,foreign,rate,notes,
                  (law['number']+' / '+law['id'] if law else '근거 확인 필요')+
                  (' / '+guideline['number'] if guideline and '지침' in reference else '')+' / '+self.rules['version'])
        self.result.lines.append(item)
        return item

def receipt_status(row,needs_approval=False):
    if not row.get('증빙확인'):
        return EVIDENCE
    if needs_approval and not (row.get('승인') and row.get('승인근거')):
        return APPROVAL
    return CONFIRMED

def net(row,amount):
    return max(ZERO,amount-dec(row.get('할인액'))-dec(row.get('기관부담액'))-dec(row.get('지원액')))
