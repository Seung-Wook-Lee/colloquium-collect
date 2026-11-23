"""좋은 주식이 시장과 함께 떨어졌을 때: 덜 떨어진 것과 많이 떨어진 것 중 어느 쪽이 더 반등했나 (11/23 의장).
하락장 = S&P500 고점→종가 바닥(crash_low): 2018, 2020, 2022, 2025. 이번 = 2026-10-06 고점 → 마지막 날.
종목 낙폭 = S&P 고점일 → S&P 바닥일 가격 변화. 시장 대비 = 종목 − 자기 시장(미국 SPY, 한국 코스피).
반등 = S&P 바닥일 → 60·120·250거래일 뒤 시장 대비 초과수익.
하방베타(Ang·Chen·Xing 2006) = 고점 전 252일 중 시장이 내린 날만의 베타.
좋은 주식 = Core50(Ver.20261122_1815) 개별주, 비교 = 가격10년 나머지 개별주. 우리 자료(ourdata)만."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ourdata as O

OUT = Path('/mnt/project-files/유니버스/start/잔차반전/')
U = Path('/mnt/project-files/유니버스/')
UNI = pd.read_csv(U / '콜로키움100_유니버스_20261121.csv')
UNI = UNI[UNI['구분'] == '개별주']
K = pd.read_csv(U / 'Core50_AI_비AI_Ver.20261122_1815.csv')
core = set(K['번호'])
px = O._px10()
UNI = UNI[UNI['yfinance 티커'].isin(px.columns)].drop_duplicates('yfinance 티커')
mk = O.get('SPY', '코스피', 'S&P500')
spx = mk['S&P500'].dropna(); us = spx.index
EP = {'2018': ('2018-09-20', '2018-12-24'), '2020': ('2020-02-19', '2020-03-23'),
      '2022': ('2022-01-03', '2022-10-12'), '2025': ('2025-02-19', '2025-04-08')}


def val(s, d):
    s = s.dropna(); i = s.index.searchsorted(pd.Timestamp(d), side='right') - 1
    return float(s.iloc[i]) if i >= 0 else np.nan


def fwd(d, n):
    j = us.searchsorted(pd.Timestamp(d)) + n
    return us[j] if j < len(us) else None


def dbeta(s, m, end):
    r = pd.concat([s, m], axis=1, sort=True).ffill().loc[:end].iloc[-253:].pct_change().dropna()
    r = r[r.iloc[:, 1] < 0]
    return np.polyfit(r.iloc[:, 1], r.iloc[:, 0], 1)[0] if len(r) > 30 else np.nan



if __name__ == '__main__':
    rows = []
    for e, (pk, bt) in EP.items():
        bt = O.crash_low(spx, pd.Timestamp(bt))[0]
        for _, u in UNI.iterrows():
            t = u['yfinance 티커']; s = px[t]; m = mk['SPY' if u['시장'] == '미국' else '코스피']
            a, b = val(s, pk), val(s, bt)
            if not (a > 0 and b > 0) or s.dropna().index[0] > pd.Timestamp(pk) - pd.Timedelta(days=365):
                continue
            r = dict(하락장=e, 번호=u['번호'], 티커=t, 시장=u['시장'], 좋은주식=u['번호'] in core,
                     낙폭=(b / a - 1) * 100, 시장대비낙폭=((b / a) - (val(m, bt) / val(m, pk))) * 100, 하방베타=dbeta(s, m, pk))
            for n in (60, 120, 250):
                f = fwd(bt, n)
                r[f'반등{n}'] = ((val(s, f) / b) - (val(m, f) / val(m, bt))) * 100 if f is not None else np.nan
            rows.append(r)
    D = pd.DataFrame(rows)
    D.to_csv(OUT / '좋은주식_하락장_종목별.csv', index=False, encoding='utf-8-sig')

    res = []
    for (e, g), x in D.groupby(['하락장', '좋은주식']):
        for n in (60, 120, 250):
            y = x[['시장대비낙폭', '하방베타', f'반등{n}']].dropna()
            if len(y) < 8:
                continue
            q = y['시장대비낙폭'].rank(pct=True)
            res.append(dict(하락장=e, 묶음='Core50' if g else '나머지', 종목수=len(y), 뒤=f'{n}일',
                            **{'상관(덜 떨어짐↔반등)': round(y['시장대비낙폭'].rank().corr(y[f'반등{n}'].rank()), 2),
                               '덜 떨어진 1/3 반등': round(y[f'반등{n}'][q >= 2 / 3].mean(), 1),
                               '많이 떨어진 1/3 반등': round(y[f'반등{n}'][q <= 1 / 3].mean(), 1),
                               '상관(하방베타↔반등)': round(y['하방베타'].rank().corr(y[f'반등{n}'].rank()), 2)}))
    R = pd.DataFrame(res)
    R.to_csv(OUT / '좋은주식_하락장_요약.csv', index=False, encoding='utf-8-sig')
    pd.set_option('display.width', 220)
    print(R.to_string(index=False))

    # 이번(2026-10-06 고점 → 마지막 날) 낙폭 위치
    pk = spx['2026-09-01':].idxmax(); last = spx.index[-1]
    now = []
    for _, u in UNI.iterrows():
        t = u['yfinance 티커']; s = px[t]; m = mk['SPY' if u['시장'] == '미국' else '코스피']
        a, b = val(s, pk), val(s, last)
        if a > 0 and b > 0:
            now.append(dict(번호=u['번호'], 티커=t if u['시장'] == '미국' else u['정식 종목명'], 시장=u['시장'], 좋은주식=u['번호'] in core,
                            낙폭=round((b / a - 1) * 100, 1), 시장대비낙폭=round(((b / a) - (val(m, last) / val(m, pk))) * 100, 1),
                            하방베타=round(dbeta(s, m, pk), 2)))
    N = pd.DataFrame(now)
    N['Core50 안 순위(많이 떨어진 순)'] = N[N['좋은주식']].groupby('시장')['시장대비낙폭'].rank().reindex(N.index)
    N.to_csv(OUT / '좋은주식_이번_낙폭.csv', index=False, encoding='utf-8-sig')
    print(f'\n이번 S&P 고점 {pk:%Y-%m-%d} → {last:%Y-%m-%d}')
    print(N[N['티커'].isin(['NVDA', '삼성전자'])].to_string(index=False))
    print('Core50 미국', (N['좋은주식'] & (N['시장'] == '미국')).sum(), '한국', (N['좋은주식'] & (N['시장'] == '한국')).sum())
    print('출처:', O.source_line('SPY', '코스피', 'S&P500'), '· 종목=가격10년_종가.csv.gz')

