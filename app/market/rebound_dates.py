"""장기채·금·나스닥100·코스피·S&P500·SOXX(필라델피아 반도체) 반등 시작일과 낙폭·반등 폭: 2020·2025·이번 (11/23 의장). 우리 자료만(ourdata).
폭락 구간 저점 = S&P500 종가 바닥일 앞뒤 15거래일 창 안의 종가 최저일(ourdata.crash_low). 날수는 S&P 거래일.
낙폭 = S&P 고점일 값 → 자산 저점. 반등 = 자산 저점 → 20·60 S&P 거래일 뒤.
SOXX는 필라델피아 반도체 지수를 따르는 ETF(2021-06 이전 PHLX SOX, 이후 NYSE 반도체 지수). 지수 자체(SOX)는 한투로 받아 추가자료에 넣는다."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ourdata as O

OUT = Path('/mnt/project-files/유니버스/start/covid_rotation/')
A = ['장기채', '금', '나스닥100', '코스피', 'S&P500', 'SOX', 'SOXX']
P = O.get(*A)
spx = P['S&P500'].dropna(); us = spx.index
td = lambda a, b: int(us.searchsorted(b) - us.searchsorted(a))


def at(s, d):
    s = s.dropna(); return float(s.iloc[min(s.index.searchsorted(d), len(s) - 1)])


def after(s, d, n):
    s = s.dropna(); j = us.searchsorted(d) + n
    if j >= len(us):
        return None
    return float(s[:us[j]].iloc[-1])


rows = {}
for e, peak, bot in (('2020', '2020-02-19', '2020-03-23'), ('2025', '2025-02-19', '2025-04-08')):
    b, pk = pd.Timestamp(bot), pd.Timestamp(peak)
    lo = {k: O.crash_low(P[k], b) for k in A}
    rows[f'{e} 종가 저점일'] = {k: v[0].strftime('%Y-%m-%d') for k, v in lo.items()}
    rows[f'{e} S&P 바닥({b:%m/%d})과 차이(거래일)'] = {k: td(b, v[0]) for k, v in lo.items()}
    rows[f'{e} 낙폭 S&P 고점({pk:%m/%d})→저점(%)'] = {k: round((v[1] / at(P[k], pk) - 1) * 100, 1) for k, v in lo.items()}
    for n in (20, 60):
        rows[f'{e} 저점 뒤 {n}거래일 상승(%)'] = {k: round((after(P[k], v[0], n) / v[1] - 1) * 100, 1) for k, v in lo.items()}
pk = spx['2026-09-01':].idxmax()
lo = {k: (P[k].dropna()[pk:].idxmin(), float(P[k].dropna()[pk:].min())) for k in A}
rows[f'이번 종가 저점일(S&P 고점 {pk:%m/%d} 뒤)'] = {k: v[0].strftime('%Y-%m-%d') for k, v in lo.items()}
rows[f'이번 낙폭 S&P 고점({pk:%m/%d})→저점(%)'] = {k: round((v[1] / at(P[k], pk) - 1) * 100, 1) for k, v in lo.items()}
rows['이번 저점 대비 마지막 값(%)'] = {k: round((P[k].dropna().iloc[-1] / v[1] - 1) * 100, 1) for k, v in lo.items()}
rows['마지막 값 날짜'] = {k: P[k].dropna().index[-1].strftime('%Y-%m-%d') for k in A}
T = pd.DataFrame(rows).T[A]
T.to_csv(OUT / '반등시작일_2020_2025_이번.csv', encoding='utf-8-sig')
print(T.to_string()); print('출처:', O.source_line(*A))
