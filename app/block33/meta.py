"""메타라벨링(로페즈 데 프라도, Advances in Financial ML 3장).

1차 모델 = 우리 블록 엔진: '추천·관찰'(사라)을 낸다.
2차 모델 = 메타: 그 1차 신호가 실제로 맞을 확률 p를 내고, p로 비중 배수(0~1)를 정한다. 방향은 바꾸지 않는다.

- 신호장부: 매일 1차 신호(추천·관찰)와 그때의 칸(종합점수·분산승수·블록예비율·변동성·베타·고점낙폭·국면·시장)을 쌓는다.
- 정답(트리플 배리어): 신호일 종가에서 출발해 '기간' 거래일 안에 위 벽(+배수×변동성) 먼저 = 1, 아래 벽 먼저 = 0,
  둘 다 안 닿으면 기간 끝 수익률 > 0 이면 1. 벽 크기 = 배수 × 60일 변동성(연율) × sqrt(기간/252).
- 학습: 정답이 확정된(기간이 끝난) 신호만 쓴다 → 미래 정보 없음(퍼지). 표본이 '최소표본' 미만이면 학습하지 않고
  메타배수 = 1(1차 신호 그대로)과 '학습 대기 n/최소표본'을 출력한다.
- 모형: 로지스틱 회귀(numpy, L2). 칸은 학습 표본 평균·표준편차로 표준화.
- 비중 배수: m = 2Φ(z) − 1, z = (p − 0.5) / sqrt(p(1 − p)) (p ≤ 0.5 면 0).
"""
import math
import os

import numpy as np
import pandas as pd

KEYS = ['기준일', '번호', 'ticker', '시장', '추천']


def _phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def size(p):
    if p is None or pd.isna(p) or p <= 0.5:
        return 0.0
    p = min(p, 1 - 1e-9)
    return 2 * _phi((p - 0.5) / math.sqrt(p * (1 - p))) - 1


def label(L, P, H, mult):
    """신호장부 L에 트리플 배리어 정답을 붙인다(확정 안 된 줄은 NaN)."""
    y = []
    idx = P.index
    for _, r in L.iterrows():
        t = r['ticker']; d0 = pd.Timestamp(r['기준일'])
        if t not in P.columns or d0 not in idx:
            y.append(np.nan); continue
        i0 = idx.get_loc(d0)
        px = P[t].iloc[i0:i0 + H + 1].dropna()
        vol = r.get('vol60')
        if len(P[t].iloc[i0:]) < H + 1 or len(px) < 2 or pd.isna(vol):
            y.append(np.nan); continue      # 기간이 아직 안 끝남 = 정답 미확정
        w = mult * float(vol) / 100 * math.sqrt(H / 252)
        ret = px / px.iloc[0] - 1
        up = ret[ret >= w].index.min(); dn = ret[ret <= -w].index.min()
        if pd.isna(up) and pd.isna(dn):
            y.append(float(ret.iloc[-1] > 0))
        elif pd.isna(dn) or (not pd.isna(up) and up < dn):
            y.append(1.0)
        else:
            y.append(0.0)
    return pd.Series(y, index=L.index)


def _fit(X, y, lam=1.0, it=500, lr=0.1):
    w = np.zeros(X.shape[1]); b = 0.0
    for _ in range(it):
        p = 1 / (1 + np.exp(-(X @ w + b)))
        g = p - y
        w -= lr * (X.T @ g / len(y) + lam * w / len(y)); b -= lr * g.mean()
    return w, b


def _X(D, cols, mu=None, sd=None):
    X = D[cols].astype(float)
    if mu is None:
        mu, sd = X.mean(), X.std().replace(0, 1).fillna(1)
    return ((X - mu) / sd).fillna(0).values, mu, sd


def run(S, f, P, m, cfg, ledger):
    """S: 판정표(추천·종합점수 등), f: 칸, P: 가격, m: 시장 칸. 반환: S에 메타확률·메타배수·메타상태 추가."""
    cols = cfg.get('칸', ['종합점수', '분산승수', '블록예비율', 'vol60', 'beta', 'dd52', '방어', '한국', '시장부담', '시장기회'])
    H = cfg.get('기간', 20); mult = cfg.get('벽배수', 1.0); nmin = cfg.get('최소표본', 200)
    sig = set(cfg.get('1차신호', ['추천', '관찰']))
    d0 = P.index.max().strftime('%Y-%m-%d') if len(P) else None
    fx = f.drop_duplicates('번호').set_index('번호')
    T = S[['번호', '종목', '시장', '추천'] + [c for c in ('종합점수', '분산승수', '블록예비율') if c in S]].copy()
    T['ticker'] = T['번호'].map(fx['ticker']) if 'ticker' in fx else None
    for c in ('vol60', 'beta', 'dd52'):
        T[c] = T['번호'].map(fx[c]) if c in fx else np.nan
    T['방어'] = [int(bool(m.get(f'DEF_{k}'))) for k in T['시장']]
    T['한국'] = (T['시장'] == '한국').astype(int)
    T['시장부담'] = m.get('시장부담', np.nan); T['시장기회'] = m.get('시장기회', np.nan)
    T['기준일'] = d0
    # 1) 오늘 1차 신호를 장부에 쌓기(같은 날 같은 종목은 마지막 실행으로 덮음)
    if ledger and d0:
        os.makedirs(os.path.dirname(ledger), exist_ok=True)
        new = T[T['추천'].isin(sig)]
        old = pd.read_csv(ledger, encoding='utf-8-sig') if os.path.exists(ledger) else pd.DataFrame(columns=new.columns)
        L = pd.concat([old[old['기준일'] != d0], new], ignore_index=True)
        L.to_csv(ledger, index=False, encoding='utf-8-sig')
    else:
        L = T[T['추천'].isin(sig)].copy()
    # 2) 정답 붙이기 → 학습
    L = L.copy(); L['정답'] = label(L, P, H, mult) if len(L) else []
    D = L.dropna(subset=['정답'])
    S = S.copy()
    if len(D) < nmin or D['정답'].nunique() < 2:
        S['메타확률'] = np.nan; S['메타배수'] = 1.0
        S['메타상태'] = f'학습 대기(확정 정답 {len(D)}/{nmin}, 그때까지 1차 신호 그대로)'
        return S, dict(표본=len(D), 학습=False)
    X, mu, sd = _X(D, cols)
    w, b = _fit(X, D['정답'].values, cfg.get('L2', 1.0))
    Xt, *_ = _X(T, cols, mu, sd)
    p = 1 / (1 + np.exp(-(Xt @ w + b)))
    S['메타확률'] = np.round(p, 3)
    S['메타배수'] = [round(size(x), 3) if r in sig else 1.0 for x, r in zip(p, T['추천'])]
    S['메타상태'] = f"학습됨(정답 {len(D)}개, 적중 {D['정답'].mean():.0%})"
    return S, dict(표본=len(D), 학습=True, 계수=dict(zip(cols, np.round(w, 3))))
