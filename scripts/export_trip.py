"""화면 없이 JSON 입력으로 동일한 정산서를 생성한다."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from travel.models import Trip,Result,dumps,money
from travel.engine import calculate
from travel.excel import export_excel
from travel.word import export_word

def main():
    parser=argparse.ArgumentParser(description='출장 JSON에서 Excel·Word 정산서 생성')
    parser.add_argument('input',type=Path,help='입력 또는 저장 당시 결과 JSON')
    parser.add_argument('--output',type=Path,default=Path('local_data/exports'),help='출력 폴더')
    parser.add_argument('--recalculate',action='store_true',help='저장 결과 대신 현재 탑재 규칙으로 재계산')
    args=parser.parse_args()
    raw=json.loads(args.input.read_text(encoding='utf-8'))
    if 'lines' in raw and not args.recalculate: result=Result.from_dict(raw)
    else:result=calculate(Trip.from_dict(raw.get('trip',raw)))
    args.output.mkdir(parents=True,exist_ok=True)
    stem=f'{result.trip["kind"]}출장_출장비정산서_{result.trip["id"]}'
    (args.output/(stem+'.xlsx')).write_bytes(export_excel(result))
    (args.output/(stem+'.docx')).write_bytes(export_word(result))
    (args.output/(stem+'.json')).write_text(dumps(result.to_dict()),encoding='utf-8')
    print('확정 항목 청구액:',money(result.claim))
    print('미확정·입력 확인:',len(result.issues),'건')
    print('출력:',args.output.resolve())

if __name__=='__main__': main()
