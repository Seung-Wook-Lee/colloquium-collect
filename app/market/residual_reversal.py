"""시장 대비 초과분 되돌림(잔차 반전) 정확도 검정 (11/23 의장: "좋은 종목 가운데 시장보다 더 오르면 조정이 깊고, 더 떨어지면 상승이 크다").
표준 공식 그대로:
- 잔차 반전(Blitz·Huij·Lansdorp·Verbeek 2013): 252일 회귀로 시장 몫을 빼고, 최근 L일 잔차 합 ÷ 잔차 표준편차. 점수 = −값.
- s-score(Avellaneda & Lee 2010): 60일 잔차 누적을 AR(1)=OU로 맞춰 s=(X−m)/σ_eq. 점수 = −s. (반감기 30일 넘는 것은 빼는 원식 조건 포함)
- 비교: 단순 단기 반전(−20일 수익), 52주 고점 대비 낙폭(B29 계산).
대상: Core50(Ver.20261122_1815) 개별주. 시장: 미국 SPY, 한국 코스피. 자료: 우리 자료(ourdata)만.
정확도: 매주 금요일 단면 순위상관(IC, 앞으로 20·60거래일 시장 대비 초과수익), 상위20%−하위20% 초과수익 차.
조건: 전체 / 나스닥100 52주 고점 대비 −10% 이하인 주. 기간: 2017~2021 / 2022~."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ourdata as O

OUT = Path('/mnt/project-files/유니버스/start/잔차반전/')
U = Path('/mnt/project-files/유니버스/')
K = pd.read_csv(U / 'Core50_AI_비AI_Ver.20261122_1815.csv')
UNI = pd.read_csv(U / '콜로키움100_유니버스_20261121.csv')
tk = dict(zip(UNI['번호'], UNI['yfinance 티커']))
K = K[K['구분'] == '개별주'].copy(); K['티커'] = K['번호'].map(tk)
px = O._px10()
K = K[K['티커'].isin(px.columns)]
mk = O.get('SPY', '코스피')
P = px[K['티커'].tolist()]
MK = {'미국': mk['SPY'], '한국': mk['코스피']}
ndx = O.get('나스닥100')['나스닥100'].dropna()
ndx_dd = ndx / ndx.rolling(252, min_periods=200).max() - 1


def signals(s, m):
    d = pd.concat([s, m], axis=1, keys=['s', 'm'], sort=True).dropna()
    r = np.log(d).diff().dropna()
    out = {}
    cov = r['s'].rolling(252, min_periods=200).cov(r['m']); var = r['m'].rolling(252, min_periods=200).var()
    b = (cov / var).shift(1); a = (r['s'].rolling(252, min_periods=200).mean() - b * r['m'].rolling(252, min_periods=200).mean()).shift(1)
    e = r['s'] - a - b * r['m']
    sd = e.rolling(252, min_periods=200).std()
    for L in (5, 10, 20):
        out[f'잔차반전 {L}일'] = -(e.rolling(L).sum() / (sd * np.sqrt(L)))
    out['단순반전 20일'] = -(d['s'] / d['s'].shift(20) - 1)
    out['52주 고점 대비 낙폭(B29 계산)'] = -(d['s'] / d['s'].rolling(252, min_periods=200).max() - 1)
    # s-score: 60일 창, 금요일만 계산
    fr = r.index[r.index.dayofweek == 4]
    ss = {}
    for t in fr:
        w = r.loc[:t].iloc[-60:]
        if len(w) < 60:
            continue
        bb, aa = np.polyfit(w['m'], w['s'], 1)
        X = np.cumsum(w['s'] - aa - bb * w['m']).values
        b1, a1 = np.polyfit(X[:-1], X[1:], 1)
        if not (0 < b1 < 1):
            continue
        kappa = -np.log(b1) * 252
        if kappa < 252 / 30:  # 반감기 30일 넘으면 뺀다(원식)
            continue
        z = X[1:] - (a1 + b1 * X[:-1])
        seq = np.sqrt(z.var() / (1 - b1 ** 2)); m_ = a1 / (1 - b1)
        ss[t] = -(X[-1] - m_) / seq
    out['s-score(OU)'] = pd.Series(ss)
    fwd = {}
    for h in (20, 60):
        fwd[h] = (d['s'].shift(-h) / d['s'] - 1) - (d['m'].shift(-h) / d['m'] - 1)
    return out, fwd


S, F = {}, {20: {}, 60: {}}
for _, row in K.iterrows():
    o, f = signals(P[row['티커']], MK[row['시장']])
    for k, v in o.items():
        S.setdefault(k, {})[(row['시장'], row['티커'])] = v
    for h in f:
        F[h][(row['시장'], row['티커'])] = f[h]
S = {k: pd.DataFrame(v) for k, v in S.items()}
F = {h: pd.DataFrame(v) for h, v in F.items()}
fri = S['s-score(OU)'].index


def ic_table(sig, h, dates):
    ics, spr = [], []
    for t in dates:
        if t not in sig.index or t not in F[h].index:
            continue
        for mkt in ('미국', '한국'):
            x = sig.loc[t, mkt] if mkt in sig.columns.get_level_values(0) else None
            y = F[h].loc[t, mkt]
            j = pd.concat([x, y], axis=1).dropna()
            if len(j) < 8:
                continue
            ics.append(j.iloc[:, 0].rank().corr(j.iloc[:, 1].rank()))
            q = j.iloc[:, 0].rank(pct=True)
            spr.append(j.iloc[:, 1][q >= .8].mean() - j.iloc[:, 1][q <= .2].mean())
    ics = pd.Series(ics).dropna()
    if len(ics) < 5:
        return dict(IC=np.nan, t=np.nan, 적중률=np.nan, 상하위차=np.nan, 주수=len(ics))
    return dict(IC=round(ics.mean(), 3), t=round(ics.mean() / ics.std() * np.sqrt(len(ics)), 1),
                적중률=round((ics > 0).mean() * 100), 상하위차=round(np.nanmean(spr) * 100, 2), 주수=len(ics))


cond = {'전체': fri, '나스닥100 −10% 이하': fri[ndx_dd.reindex(fri, method='ffill').values <= -0.10]}
per = {'2017~2021': lambda d: d[d.year <= 2021], '2022~': lambda d: d[d.year >= 2022]}
rows = []
for k, sig in S.items():
    sig = sig.reindex(fri) if k != 's-score(OU)' else sig
    for cn, dts in cond.items():
        for pn, pf in per.items():
            for h in (20, 60):
                rows.append(dict(공식=k, 조건=cn, 기간=pn, 앞으로=f'{h}일', **ic_table(sig, h, pf(dts))))
T = pd.DataFrame(rows)
T.to_csv(OUT / '잔차반전_정확도.csv', index=False, encoding='utf-8-sig')
pd.set_option('display.width', 200)
for h in ('20일', '60일'):
    print(f'\n== 앞으로 {h} 시장 대비 초과수익 ==')
    print(T[T['앞으로'] == h].pivot_table(index='공식', columns=['조건', '기간'], values=['IC', 't'], aggfunc='first').round(3).to_string())
print('\n종목 수', len(K), '(미국', (K['시장'] == '미국').sum(), '한국', (K['시장'] == '한국').sum(), ')')
print('출처:', O.source_line('SPY', '코스피', '나스닥100'), '· 종목=가격10년_종가.csv.gz')
