"""지수 분할 매수 판정 (11/21 의장).

질문: "다음 주 월요일부터 3주 동안 매주 월요일 종가에 현금 1/3씩 S&P500(또는 나스닥100)을 사겠다. 어때?"
답   : 오늘 켜진 신호와 같은 신호가 켜졌던 과거에, 똑같은 계획대로 샀으면 마지막 매수 13주 뒤 결과가 어땠나.
       '지금 시작(다음 주부터)'과 '1주 기다림(2주 뒤부터)'을 둘 다 계산해 나은 쪽을 답으로 낸다.

신호(강한 순서, 2006-08~ 금요일 종가 기준, 하락 한 번 = 한 건으로 셈)
  ① Opportunity Block 3개 모두 = B02 VIX>VIX3M · B06 CTA ≤ −4 · B06 변동성 목표 노출 < 0.6배
  ② Opportunity Block(B02·B06의 '기회' 공식) 5개 중 3개 이상 (B02 MOVE ≥100, VIX>VIX3M / B06 CTA ≤ −4, 변동성 목표 <0.6배, 시스템 매수 전환) — 11/23 의장: CTA 플러스 전환 뺌
  ③ 바닥 확률(8개 공식, lt_bottom) ≥ 50% + 일봉 RSI ≤ 30 + 주봉 RSI ≤ 35
  ④ 바닥 확률 ≥ 50%
  ⑤ 하락 구간 안(52주 고점 −5% 또는 −10%)
문턱은 blocks.yaml 공식 그대로(CTA·변동성 목표는 collect/flowpos.py 계산 그대로). 8개 공식 코드는 건드리지 않음.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[2] / 'collect')]

NAME = {'^GSPC': 'S&P500', '^NDX': '나스닥100'}
WIN_OK = 0.8          # 의장: "80%만 맞히면 됨"
MIN_N = 4             # 과거 사례가 이보다 적으면 그 신호로 답하지 않음


def _rsi(x, n=14):
    g = x.diff()
    u = g.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    d = (-g.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + u / d)


def load(start='1985-01-01'):
    import yfinance as yf
    t = ['^GSPC', '^NDX', '^RUT', '^VIX', '^VIX3M', '^MOVE', '^TNX']
    return yf.download(t, start=start, auto_adjust=True, progress=False)['Close']


def blocks(P):
    """B02·B06 기회 공식(일별)."""
    import flowpos as FP
    px = pd.DataFrame({'GSPC': P['^GSPC'], 'NDX': P['^NDX'], 'RUT': P['^RUT']}).dropna()
    cta = FP.cta_sigma(px)
    r = np.log(px['GSPC']).diff()
    rv = np.sqrt(0.5 * r.ewm(span=21).std() ** 2 + 0.5 * r.ewm(span=63).std() ** 2) * np.sqrt(252)
    volt = (FP.TV / rv).clip(upper=1.5)
    s = px['GSPC']
    sig = pd.DataFrame({n: s > s.shift(n) for n in (21, 63, 100)}).sum(axis=1)
    vv3 = (P['^VIX'] - P['^VIX3M']).reindex(px.index).ffill()
    move = P['^MOVE'].reindex(px.index).ffill()
    O = pd.DataFrame({
        'B02 MOVE ≥100': move >= 100,
        'B02 VIX > VIX3M': vv3 > 0,
        'B06 CTA ≤ −4': cta <= -4,
        'B06 변동성 목표 노출 < 0.6배': volt < 0.6,
        'B06 시스템 매수 전환': (sig > sig.shift(5)) & (cta.diff(5) > 0),
    }).astype(float)
    O[vv3.isna()] = np.nan
    V = pd.DataFrame({'CTA': cta, '변동성목표': volt, 'VIX−VIX3M': vv3, 'MOVE': move})
    return O, V


def weekly(P, tk, O):
    import lt_bottom as LB
    c = P[tk].dropna()
    hi = c.rolling(252, min_periods=1).max()
    W = pd.DataFrame({'c': c.resample('W-FRI').last(), 'hi': hi.resample('W-FRI').last(),
                      'r14': _rsi(c).resample('W-FRI').last(), 'wr': _rsi(c.resample('W-FRI').last())})
    W['dd'] = (W.c / W.hi - 1) * 100
    _, _ = LB.hazard(c, P['^VIX'], P['^TNX'])
    _, raw = LB.hazard.last
    W['p8'] = raw.reindex(W.index)
    Ow = O.resample('W-FRI').agg({k: ('max' if '전환' in k else 'last') for k in O})
    W['기회수'] = Ow.sum(axis=1, min_count=4)
    W['공포3'] = Ow[['B02 VIX > VIX3M', 'B06 CTA ≤ −4', 'B06 변동성 목표 노출 < 0.6배']].sum(axis=1, min_count=3)
    return W.dropna(subset=['c'])


def episodes(W, th):
    ep = pd.Series(np.nan, index=W.index)
    v, h = W.c.values, W.hi.values
    i = k = 0
    while i < len(v):
        if v[i] <= (1 - th / 100) * h[i]:
            P0 = h[i]; k += 1; j = i
            while j < len(v) and v[j] < P0:
                ep.iloc[j] = k; j += 1
            i = j
        else:
            i += 1
    return ep


NEED = {'^GSPC': 11, '^NDX': 13}   # 11/21 의장 4가지 검증: S&P −5%·−10% 11개↑ 7·6번 모두, 나스닥 −10% 13개↑ 5번 모두(−20%면 8개↑ 5번 모두). S&P 14개↑는 오히려 나빠짐


def pool(P, tk, O):
    """Opportunity Block 20개(과거 자료로 다시 계산되는 blocks.yaml '기회'·바닥 공식, 지수 판). 주(금요일) 단위 True/False."""
    import lt_bottom as LB   # noqa: F401
    c = P[tk].dropna(); w = c.resample('W-FRI').last()
    ma, sd = c.rolling(20).mean(), c.rolling(20).std(); pb = (c - (ma - 2 * sd)) / (4 * sd)
    md = c.rolling(20).apply(lambda a: np.mean(np.abs(a - a.mean())), raw=True); cci = (c - ma) / (0.015 * md)
    lo, hi = c.rolling(14).min(), c.rolling(14).max(); stk = (c - lo) / (hi - lo) * 100
    m = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean(); osc = m - m.ewm(span=9, adjust=False).mean()
    wm = w.ewm(span=12, adjust=False).mean() - w.ewm(span=26, adjust=False).mean(); wo = wm - wm.ewm(span=9, adjust=False).mean()
    m5 = c.resample('ME').last().rolling(5).mean()
    vix = P['^VIX'].reindex(c.index).ffill(); vv3 = O['B02 VIX > VIX3M'].reindex(c.index).ffill()
    D = pd.DataFrame({
        'B11·B16 50일 이격 ≤ 90': c / c.rolling(50).mean() * 100 <= 90,
        'B11·B16 일봉 RSI ≤ 30': _rsi(c) <= 30,
        'B11 VIX ≥ 30 또는 VIX > VIX3M': (vix >= 30) | (vv3 > 0),
        'B16 볼린저 %B ≤ 0.05': pb <= 0.05,
        'B16 CCI ≤ −100': cci <= -100,
        'B16 스토캐스틱 ≤ 20': stk <= 20,
        'B16 일봉 MACD 막대 줄어듦': osc > osc.shift(1),
        'B13 52주 고점 −20% 이하': (c / c.rolling(252).max() - 1) * 100 <= -20,
    }).resample('W-FRI').max()
    D['B17 주봉 MACD 오실레이터 상승'] = wo > wo.shift(1)
    D['B17 주봉 오실레이터 2주 연속 상승'] = (wo > wo.shift(1)) & (wo.shift(1) > wo.shift(2))
    D['B17 월봉 5개월선 아래'] = w < m5.reindex(w.index, method='ffill')
    D['B17 주봉 RSI ≤ 40'] = _rsi(w) <= 40
    D['B17 60주선 터치(이격 ≤ 102)'] = w / w.rolling(60).mean() * 100 <= 102
    Ow = O.resample('W-FRI').agg({k: ('max' if '전환' in k else 'last') for k in O})
    for k in O:
        D[k] = Ow[k] > 0
    return D


SIGNALS = [
    ('Opportunity Block 기준 이상', lambda W: W['opp'] >= W.attrs['need']),
    ('Opportunity Block 3개(VIX>VIX3M·CTA ≤ −4·변동성 목표 <0.6배) 모두', lambda W: W['공포3'] >= 3),
    ('Opportunity Block 5개 중 3개 이상', lambda W: W['기회수'] >= 3),
    ('바닥 확률 ≥50% + RSI 30↓·주RSI 35↓', lambda W: (W.p8 >= .5) & (W.r14 <= 30) & (W.wr <= 35)),
    ('바닥 확률 ≥50%', lambda W: W.p8 >= .5),
    ('하락 구간 안', lambda W: pd.Series(True, index=W.index)),
]


def simulate(W, mask, th, offset=1, n_buy=3, hold=13, since='2006-08-01', daily=None):
    """신호가 처음 켜진 금요일(종가로 신호 확인) 다음 주 월요일부터 n_buy주 월요일 종가에 같은 금액씩(11/21 의장 "월요일에 살 거라니까").
    offset=1 → 바로 다음 주 월요일, 2 → 1주 기다림. 평가 = 마지막 매수 hold주 뒤 종가."""
    W = W.copy(); W['ep'] = episodes(W, th)
    X = W[(W.index >= since)]
    f = X[mask.reindex(X.index).fillna(False) & X.ep.notna() & (X.dd <= -th)].groupby('ep').head(1)
    c = daily.dropna()
    out = []
    for d in f.index:
        days = [d + pd.Timedelta(days=3 + 7 * (offset - 1 + i)) for i in range(n_buy)]
        end = days[-1] + pd.Timedelta(weeks=hold)
        if end > c.index[-1]:
            continue
        p = np.array([c[c.index >= x].iloc[0] for x in days])
        avg = n_buy / np.sum(1 / p)
        out.append(dict(날짜=str(d.date()), 수익=c[:end].iloc[-1] / avg - 1, 단가=avg / W.c.loc[d] - 1))
    return pd.DataFrame(out)


def judge(P=None, offset=1, n_buy=3, hold=13):
    P = load() if P is None else P
    O, V = blocks(P)
    rows, lit = [], {}
    for tk in ('^GSPC', '^NDX'):
        W = weekly(P, tk, O)
        F = pool(P, tk, O).reindex(W.index).fillna(False).astype(bool)
        F['8개 공식 바닥 확률 ≥ 50%'] = W.p8 >= .5
        W['opp'] = F.sum(axis=1); W.attrs['need'] = NEED[tk]
        t = W.iloc[-1]
        th = 10 if t.dd <= -10 else 5
        res = []
        for nm, fn in SIGNALS:
            m = fn(W)
            on = bool(m.iloc[-1]) and t.dd <= -th
            a = simulate(W, m, th, offset, n_buy, hold, daily=P[tk])
            b = simulate(W, m, th, offset + 1, n_buy, hold, daily=P[tk])
            res.append(dict(신호=nm, 오늘=on, 사례=len(a),
                            이김=(a.수익 > 0).mean() if len(a) else np.nan, 수익중앙값=a.수익.median() if len(a) else np.nan,
                            최악=a.수익.min() if len(a) else np.nan, 단가=a.단가.median() if len(a) else np.nan,
                            기다림_이김=(b.수익 > 0).mean() if len(b) else np.nan, 기다림_수익중앙값=b.수익.median() if len(b) else np.nan,
                            기다림_최악=b.수익.min() if len(b) else np.nan, 날짜=', '.join(a.날짜.tail(5)) if len(a) else ''))
        R = pd.DataFrame(res)
        best = R[R.오늘 & (R.사례 >= MIN_N)].head(1)
        stronger_near = None
        if not R.iloc[0].오늘:
            stronger_near = f"{int(t.opp)}/{F.shape[1]} ({NEED[tk]}개까지 {NEED[tk] - int(t.opp)}개)"
        if len(best):
            b = best.iloc[0]
            go = b.이김 >= WIN_OK
            wait_better = (b.기다림_이김 > b.이김) or (b.기다림_이김 == b.이김 and b.기다림_최악 > b.최악)
            if go and not wait_better:
                verdict = '오케이, 지금 시작'
            elif go:
                verdict = '오케이, 다만 1주 기다리면 과거엔 더 나았음'
            else:
                verdict = '1주 더 기다리세요'
        else:
            b = R[R.오늘].tail(1).iloc[0] if R.오늘.any() else None
            verdict = '하락 구간 아님' if b is None else '1주 더 기다리세요'
        rows.append(dict(지수=NAME[tk], 기준하락=th, 낙폭=t.dd, 바닥확률=t.p8, RSI=t.r14, 주RSI=t.wr, 판정=verdict,
                         근거=None if b is None else b.to_dict(), 다음단계=stronger_near, 표=R,
                         켜짐=F.iloc[-1].to_dict(), 켜진수=int(t.opp), 전체=F.shape[1], 기준=NEED[tk]))
        lit = {k: bool(v) for k, v in O.iloc[-1].items() if not pd.isna(v)}
    return dict(지수=rows, 블록=lit, 값=V.iloc[-1].round(2).to_dict(), 날짜=str(P.index[-1].date()),
                계획=dict(시작=f'{offset}주 뒤 월요일', 횟수=n_buy, 평가=f'마지막 매수 {hold}주 뒤'))


if __name__ == '__main__':
    J = judge()
    print(J['날짜'], J['블록'], J['값'])
    for r in J['지수']:
        print(f"\n{r['지수']} 판정: {r['판정']} | 낙폭 {r['낙폭']:.1f}% 바닥확률 {r['바닥확률']:.1%} RSI {r['RSI']:.1f} 주RSI {r['주RSI']:.1f} | 다음 {r['다음단계']}")
        print(r['표'].round(3).to_string())
