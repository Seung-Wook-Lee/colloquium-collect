"""장기채·금·코스피·나스닥100 반등 시작일(= 하락 구간 저점일): 2018·2020·2025와 이번, 금 바닥 기준 날수로 이번 날짜 예상 (11/23 의장).
행 = 항목, 열 = 장기채·금·코스피·나스닥100. 날수는 미국 거래일."""
from pathlib import Path
import pandas as pd
import yfinance as yf
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

OUT = Path('/mnt/project-files/유니버스/start/covid_rotation/')
A = {'TLT': '장기채', 'GLD': '금', '^KS11': '코스피', '^NDX': '나스닥100'}
P = yf.download(list(A) + ['^GSPC'], start='2018-01-01', auto_adjust=True, progress=False)['Close']
us = P['^GSPC'].dropna().index
EP = {'2018': ('2018-10-01', '2019-01-31'), '2020': ('2020-02-19', '2020-04-30'), '2025': ('2025-02-19', '2025-05-15'), '이번': ('2026-10-06', '2026-11-23')}
low = {e: {A[t]: P[t].dropna()[a:b].idxmin() for t in A} for e, (a, b) in EP.items()}
td = lambda a, b: us.searchsorted(b) - us.searchsorted(a)
rows = {}
for e in ('2018', '2020', '2025'):
    g = low[e]['금']
    rows[f'{e} 반등 시작일'] = {k: v.strftime('%Y-%m-%d') for k, v in low[e].items()}
    rows[f'{e} 금 바닥 뒤(거래일)'] = {k: td(g, v) for k, v in low[e].items()}
g = low['이번']['금']
last = {A[t]: P[t].dropna().index[-1] for t in A}
rows['이번 지금까지 저점일'] = {k: v.strftime('%Y-%m-%d') for k, v in low['이번'].items()}
rows['이번 저점 대비 지금(%)'] = {A[t]: round((P[t].dropna().iloc[-1] / P[t].dropna()[EP['이번'][0]:].min() - 1) * 100, 1) for t in A}
cbd = CustomBusinessDay(calendar=USFederalHolidayCalendar())
ds = [rows[f'{e} 금 바닥 뒤(거래일)'] for e in ('2018', '2020', '2025')]
rows['2020 날수 적용 예상일'] = {k: (g + ds[1][k] * cbd).strftime('%Y-%m-%d') for k in A.values()}
rows['3번 범위 적용 예상일(가장 빠름~가장 늦음)'] = {k: f"{(g + min(d[k] for d in ds) * cbd):%m/%d} ~ {(g + max(d[k] for d in ds) * cbd):%m/%d}" for k in A.values()}
T = pd.DataFrame(rows).T[list(A.values())]
T.to_csv(OUT / '반등시작일_예상.csv', encoding='utf-8-sig')
print(T.to_string())
