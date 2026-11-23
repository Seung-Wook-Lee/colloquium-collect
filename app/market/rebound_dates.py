"""장기채·금·코스피·나스닥100 반등 시작일(= 폭락 구간 종가 저점일): 2020·2025·이번 (11/23 의장). 우리 자료만(ourdata).
폭락 구간 저점 = S&P500 종가 바닥일 앞뒤 15거래일 창 안의 종가 최저일(ourdata.crash_low). 날수는 S&P 거래일."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ourdata as O

OUT = Path('/mnt/project-files/유니버스/start/covid_rotation/')
A = ['장기채', '금', '코스피', '나스닥100']
P = O.get('S&P500', *A)
spx = P['S&P500'].dropna(); us = spx.index
td = lambda a, b: int(us.searchsorted(b) - us.searchsorted(a))
rows = {}
for e, bot in (('2020', '2020-03-23'), ('2025', '2025-04-08')):
    b = pd.Timestamp(bot)
    lo = {k: O.crash_low(P[k], b)[0] for k in A}
    rows[f'{e} 종가 저점일'] = {k: v.strftime('%Y-%m-%d') for k, v in lo.items()}
    rows[f'{e} S&P 바닥({b:%m/%d})과 차이(거래일)'] = {k: td(b, v) for k, v in lo.items()}
pk = spx['2026-09-01':].idxmax()
lo = {k: P[k].dropna()[pk:].idxmin() for k in A}
rows['이번 종가 저점일(S&P 고점 ' + f'{pk:%m/%d} 뒤)'] = {k: v.strftime('%Y-%m-%d') for k, v in lo.items()}
rows['이번 저점 대비 마지막 값(%)'] = {k: round((P[k].dropna().iloc[-1] / P[k].dropna()[pk:].min() - 1) * 100, 1) for k in A}
rows['마지막 값 날짜'] = {k: P[k].dropna().index[-1].strftime('%Y-%m-%d') for k in A}
T = pd.DataFrame(rows).T[A]
T.to_csv(OUT / '반등시작일_2020_2025_이번.csv', encoding='utf-8-sig')
print(T.to_string()); print('출처:', O.source_line('S&P500', *A))
