"""법령 시행일, 별표 원문 및 도시 예외 조회. 실행 중 인터넷을 사용하지 않는다."""
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import json

@lru_cache
def load_rules():
    return json.loads((Path(__file__).parent/'data/rules.json').read_text(encoding='utf-8'))

def select_law(day, rules=None):
    rules=rules or load_rules()
    candidates=[v for v in rules['law_versions'] if v['id'] <= str(day)[:10]]
    if not candidates:
        return None
    return candidates[-1]

def select_guideline(day, rules=None):
    candidates=[v for v in (rules or load_rules())['guidelines'] if v['id'] <= str(day)[:10]]
    return candidates[-1] if candidates else None

COUNTRY_ALIASES={'호주':'오스트레일리아','대만':'타이완','태국':'타이','튀르키예':'터키',
 '키르기스스탄':'키르키즈공화국','에스와티니':'스와질란드','북마케도니아':'마케도니아',
 '홍콩':'중국','Singapore':'싱가포르','Japan':'일본','USA':'미국','China':'중국'}
CITY_ALIASES={'동경':'도쿄','북경':'베이징','LA':'로스엔젤레스','로스앤젤레스':'로스엔젤레스',
 '워싱턴':'워싱턴 D.C.','워싱턴DC':'워싱턴 D.C.','뉴욕시':'뉴욕','Tokyo':'도쿄','Beijing':'베이징'}

def destination(country,city='',nearest='',evidence='',rules=None):
    rules=rules or load_rules()
    country=COUNTRY_ALIASES.get(country.strip(),country.strip())
    city=CITY_ALIASES.get(city.strip(),city.strip())
    if not city and country=='싱가포르': city='싱가포르'
    for item in rules['cities']:
        if country==item['국가'] and city==item['도시']:
            return item['등급'],'별표 4 비고 2 국가·도시 예외'
    if not city:
        return None,'도시 미입력: 국가 내 도시 예외를 판정할 수 없습니다.'
    if country in rules['countries']:
        return rules['countries'][country]['등급'],'별표 4 비고 2 국가 일반등급'
    if nearest in rules['countries'] and evidence.strip():
        return rules['countries'][nearest]['등급'],f'별표 4 비고 3: 최인접 수도 국가 {nearest}; 거리 근거 {evidence}'
    return None,'별표 미열거 국가: 가장 가까운 수도의 국가와 거리 출처를 입력하세요(별표 4 비고 3).'

def snapshot():
    return deepcopy(load_rules())
