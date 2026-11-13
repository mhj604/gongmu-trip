"""공통 보고 모델. 모든 입력은 두 형식에서 같은 경로로 출력한다."""
from datetime import date, timedelta
from .models import *

INPUT_LABELS={'id':'출장 식별자','kind':'출장 유형','meta':'기본정보','days':'일별 일정','lodgings':'숙박 내역',
 'transports':'교통 내역','specials':'특수 여비','fx':'환율','evidence':'증빙 목록','settings':'계산 설정'}

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
