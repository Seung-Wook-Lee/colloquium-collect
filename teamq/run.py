# 팀 Q 과거 데이터 일괄 수집 — 실행 순서
#   python teamq/run.py            → 전부
#   python teamq/run.py prices macro → 고른 단계만 (앞 단계 결과는 로컬이나 팀 Q 드라이브에서 읽음)
# 기존 07시 수집(run.py)과 무관. 결과: teamq_out/ → 드라이브 Team_Q__chatgpt/
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_part, upload_all, save, STATUS, OUT, log, q_ready
import market, fundamentals, build

PARTS = [('prices', market.part_prices), ('prices_process', market.part_prices_process), ('fomc', market.part_fomc), ('etf', market.part_etf), ('macro', market.part_macro),
         ('fund_us', fundamentals.part_fund_us), ('fund_us_std', fundamentals.part_fund_us_std), ('fund_kr', fundamentals.part_fund_kr), ('fund_kr_fix', fundamentals.part_fund_kr_fix), ('fund_jp', fundamentals.part_fund_jp),
         ('earnings_dates', fundamentals.part_earnings_dates),
         ('valuation', build.part_valuation), ('events', build.part_events), ('quality', build.part_quality), ('summary', build.part_summary)]

want = [a for a in sys.argv[1:] if a.strip()]
FIX_ONLY = {'prices_process', 'fund_us_std'}    # 이어받은 원본을 다시 가공할 때만 (전체 실행에선 앞 단계가 이미 함)
for name, fn in PARTS:
    if (not want and name not in FIX_ONLY) or name in want:
        run_part(name, fn)
n = upload_all()
log(f'끝. 드라이브에 올린 파일 {n}개 (창구 준비: {q_ready()}), 로컬 {OUT}')
