"""오피넷 공개 일별 전국 평균판매가격. 요청한 날짜와 제품이 일치할 때만 반환한다."""
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import re
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

OIL_URL = 'https://www.opinet.co.kr/user/dopospdrg/dopOsPdrgSelect.do'
LPG_URL = 'https://www.opinet.co.kr/user/dopvsavsel/dopVsAvselSelect.do'
PRODUCTS = {'보통휘발유':'B027', '자동차용경유':'D047', '자동차부탄':'K015'}


class FuelPriceError(ValueError):
    pass


@dataclass(frozen=True)
class FuelQuote:
    day: str
    product: str
    price: str
    source: str
    fetched_at: str

    def record(self):
        return asdict(self)


class PriceTable(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], [], None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []
        elif tag in ('td','th'):
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('td','th') and self.cell is not None:
            self.row.append(''.join(self.cell).strip())
            self.cell = None
        elif tag == 'tr' and self.row:
            self.rows.append(self.row)
            self.row = []


def parse_quote(html, day, product):
    parser = PriceTable()
    parser.feed(html)
    column = None
    for row in parser.rows:
        if row[0] in ('구분','기간'):
            column = next((i for i, label in enumerate(row) if label.startswith(product)), None)
            continue
        match = re.fullmatch(r'(\d{2}|\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', row[0])
        if not match or column is None or column >= len(row):
            continue
        year, month, day_number = map(int, match.groups())
        year = 2000+year if year < 100 else year
        try:
            row_day = date(year,month,day_number).isoformat()
        except ValueError:
            continue
        if row_day != day:
            continue
        try:
            price = Decimal(row[column].replace(',',''))
        except InvalidOperation:
            break
        if price.is_finite() and price > 0:
            return str(price)
        break
    raise FuelPriceError(f'{day} {product} 일별 유가를 확인할 수 없습니다. 다른 날짜의 가격으로 대체하지 않았습니다.')


def product_for(fuel, hybrid_product='보통휘발유'):
    if fuel in ('하이브리드','플러그인하이브리드(연료)'):
        return hybrid_product if hybrid_product in ('보통휘발유','자동차용경유') else '보통휘발유'
    return {'휘발유':'보통휘발유','경유':'자동차용경유','LPG':'자동차부탄'}.get(fuel)


def fetch_quote(day, product):
    selected = date.fromisoformat(day)
    today = datetime.now(ZoneInfo('Asia/Seoul')).date()
    if selected >= today:
        raise FuelPriceError('선택한 날짜의 일별 평균 유가는 아직 발표되지 않았습니다. 일별 통계는 전일 가격을 공개합니다.')
    if selected < date(2008,4,15) or product not in PRODUCTS:
        raise FuelPriceError('해당 날짜 또는 유종의 일별 자동 조회를 지원하지 않습니다.')
    params = {'TERM':'D'}
    for prefix in ('STA','END'):
        params.update({prefix+'_Y':str(selected.year), prefix+'_M':f'{selected.month:02}', prefix+'_D':f'{selected.day:02}'})
    if product == '자동차부탄':
        url = LPG_URL
        params['OIL_CD_K015_P'] = 'Y'
    else:
        url = OIL_URL
        params.update({'OIL_CD_'+PRODUCTS[product]:'Y','INIF_FLAG':'N','all_chk_cnt':'5','chk_cnt':'1'})
    try:
        request = Request(url, data=urlencode(params).encode(), headers={'User-Agent':'GongmuTrip/1.0','Referer':url})
        with urlopen(request,timeout=8) as response:
            html = response.read().decode('utf-8')
    except (URLError, TimeoutError, OSError, UnicodeError) as error:
        raise FuelPriceError('오피넷에 연결하지 못했습니다. 잠시 후 다시 조회하거나 단가를 직접 입력하세요.') from error
    price = parse_quote(html,day,product)
    return FuelQuote(day,product,price,url,datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds'))


def apply_quote(meta, day, product, quote):
    """실패·미발표·날짜 변경 시 이전 단가가 계산에 남지 않게 한다."""
    meta['간편유가'] = ''
    meta['간편유가출처'] = ''
    meta['간편유가기준일'] = ''
    meta['간편유가조회'] = {}
    if quote is None:
        return
    if quote.day != day or quote.product != product:
        raise FuelPriceError('조회된 유가의 날짜·유종이 선택값과 다릅니다.')
    meta['간편유가'] = quote.price
    meta['간편유가기준일'] = day
    meta['간편유가출처'] = f'오피넷(한국석유공사) 전국 평균판매가격 / {day} / {product} / {quote.source}'
    meta['간편유가조회'] = quote.record()
