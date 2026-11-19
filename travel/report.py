"""공통 보고 모델. 모든 입력은 두 형식에서 같은 경로로 출력한다."""
from datetime import date, timedelta
from dataclasses import dataclass
from decimal import ROUND_HALF_UP
import re
from .models import *

INPUT_LABELS={'id':'출장 식별자','kind':'출장 유형','meta':'기본정보','days':'일별 일정','lodgings':'숙박 내역',
 'transports':'교통 내역','specials':'특수 여비','fx':'환율','evidence':'증빙 목록','settings':'계산 설정'}

COST_FIELDS={'실제지출액','할인액','기관부담액','지원액','식비지원액','식비조정액','근거리운임','근거리식비',
    '대중교통운임','통행료','주차료','식비실제지출','기본구간실비','초과구간실비','본인기준운임',
    '본인기준숙박비','본인기준일비식비','본인기준준비금','기관확정월액','기관확정일액','전직상당구간여비'}
KRW_FIELDS={'기지급액','카드청구원화액','간편숙박비','간편교통비','간편근거리식비','간편대중교통운임',
    '간편통행료','간편주차료','확정 인정액','미확정금액','현재 확정 항목 청구액','최종 청구 가능액','반납예정액'}
QUANTITY_FIELDS={'왕복거리(km)','출장시간(h)','도착다음날기산일수','거리(km)','유가','1USD당현지통화',
    '1단위당 원화','화물량','나이','인정출장일수','간편환율','간편시간','간편거리','간편주행거리','간편유가','price'}


@dataclass(frozen=True)
class ReportNumber:
    value: Decimal
    krw: bool = False


def report_number(value, decimals=2):
    """출력만 반올림한다. 저장값과 계산 엔진의 정밀도는 바꾸지 않는다."""
    if value is None:return '미입력'
    number=Decimal(str(value).replace(',','')).quantize(Decimal(1).scaleb(-decimals),rounding=ROUND_HALF_UP)
    text=format(number,',f')
    return text.rstrip('0').rstrip('.') if decimals else text


def report_text(text):
    """계산 설명에 들어간 소수도 원화 0자리, 비율·수량 2자리로 맞춘다."""
    def replace(match):
        currency=bool(re.match(r'원(?!\s*/)',str(text)[match.end():].lstrip()))
        return report_number(match.group(),0 if currency else 2)
    return re.sub(r'(?<![\w./])[-+]?\d[\d,]*\.\d+(?![\d./])',replace,str(text))


def formatted_flatten(value,path='',currency='KRW'):
    if isinstance(value,dict):
        currency=value.get('통화') or currency
        for key,item in value.items():
            child=f'{path} / {INPUT_LABELS.get(key,key)}' if path else INPUT_LABELS.get(key,key)
            yield from formatted_flatten(item,child,currency)
    elif isinstance(value,list):
        if not value:yield path,'해당 없음'
        for i,item in enumerate(value,1):yield from formatted_flatten(item,f'{path} {i}',currency)
    else:
        key=path.rsplit(' / ',1)[-1]
        krw=key in KRW_FIELDS or '(원)' in key or (key in COST_FIELDS and currency=='KRW')
        numeric=isinstance(value,(Decimal,int,float)) and not isinstance(value,bool)
        numeric_string=isinstance(value,str) and bool(re.fullmatch(r'[-+]?\d[\d,]*(?:\.\d+)?',value))
        if numeric or (numeric_string and (krw or key in COST_FIELDS or key in QUANTITY_FIELDS)):
            yield path,ReportNumber(Decimal(str(value).replace(',','')),krw)
        else:
            yield from flatten(value,path)

def flatten(value,path=''):
    if isinstance(value,dict):
        for k,v in value.items():
            yield from flatten(v,f'{path} / {INPUT_LABELS.get(k,k)}' if path else INPUT_LABELS.get(k,k))
    elif isinstance(value,list):
        if not value: yield path,'해당 없음'
        for i,v in enumerate(value,1): yield from flatten(v,f'{path} {i}')
    else:
        if value is None or value=='': value='미입력'
        elif isinstance(value,bool): value='예' if value else '아니오'
        yield path,value

def period(result):
    m=result.trip['meta']
    return f'{m.get("시작일시", "미입력")} ~ {m.get("종료일시", "미입력")}'

def status_label(result):
    return '현재 확정 항목 청구액' if result.issues else '최종 청구 가능액'

def deadlines(result):
    end=str(result.trip['meta'].get('종료일시',''))[:10]
    try: end=date.fromisoformat(end)
    except ValueError: return []
    return [
        {'항목':'운임·숙박비 일반 정산','기한':str(end+timedelta(days=14)),'근거':'제8조의2제2항'},
        {'항목':'초과여비 정산','기한':str(end+timedelta(days=14 if result.trip['kind']=='국외' else 7)),
         '근거':'제16조제2항 (지침상 국내 숙박 초과 정산기간 표현과 차이 있어 조문 기한 병기)'},
        {'항목':'국외 준비금','기한':'출국 전 또는 '+str(end+timedelta(days=14)),'근거':'제23조제2항'}]

def metadata(result):
    return {'생성일시':result.generated_at,'법령자료 버전':result.rule_snapshot['version'],
        '계산 상태':'미확정 항목 있음' if result.issues else '계산 확정','출장기간':period(result),
        '확정 인정액':result.recognized,'미확정금액':result.pending,'기지급액':result.advance,
        status_label(result):result.claim,'반납예정액':result.refund}
