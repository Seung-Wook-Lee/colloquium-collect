"""회의 직전 가격: 드라이브 저장본(1_data/가격10년_*, in/에 받아 둠)에 새 거래일만 덧붙인다(11/25 의장).
규칙은 px_store.py(update): 시장별로 저장본에 없는 새 거래일이 있을 때만 받음, 새 종목만 그 종목 과거치.
결과: in/가격10년_*.csv.gz(드라이브에 다시 올림) + 회의용 in/가격2년·고가2년·저가2년·거래량2년.csv(저장본에서 잘라 만듦)."""
import datetime as dt
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import px_store as PS  # noqa: E402

N = pd.read_csv('in/닉스.csv', encoding='utf-8-sig')
t = [x for x in N['yfinance 티커'].dropna().astype(str).unique()]
now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).replace(tzinfo=None)
B = PS.update(PS.load('in'), N, now, log=print)   # 닉스.csv: yfinance 티커·시장(한국 코드는 티커 앞 6자리)
saved = PS.save(B, 'in')
two = PS.two_years(B, 'in', t)
c = B['Close']
print('저장본', c.shape, '마지막 날', c.index[-1].date(), '| 저장', saved, two)
