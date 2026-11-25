"""블록점수이력용 한국 수급 칸 과거 값 (11/24 의장 "외국인과 기관 수급은 한투에서 받을 수 없나?").
features.py는 오늘 국내수급.csv(b09_kflow, 최근 30영업일)만 읽어 과거 주에는 같은 값이 들어갔다(그래서 비웠음).
여기서는 10년치 저장본 국내수급 칸(한투 FHPTJ04160001, collect/data/hist_kflow.py)로 그 주 금요일까지 30영업일을 잘라
b09_kflow와 같은 식으로 f5·f20·inst5·ind5(억원)·fstreak(외국인 연속 순매수 +, 순매도 −)·fz5·iz5(5일 합의 자기 30일 z)를 다시 만든다.
쓰는 곳: backtest._one → apply(f, t, d)"""
import os

import numpy as np
import pandas as pd

import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'collect', 'data'))
import px_store as PS  # noqa: E402  10년치 저장본(11/26 의장: 따로 있던 과거 자료도 저장본 칸)

VARS = {'f5', 'f20', 'fstreak', 'inst5', 'ind5', 'fz5', 'iz5'}
_K = None


def _load(d):
    K = PS.table(d, '국내수급', dtype={'코드': str})   # 저장본 칸(옛 1_data/장기/국내수급_일별)
    if not len(K):
        return None
    K['날짜'] = pd.to_datetime(K['날짜'].astype(str), errors='coerce')
    return {c: g.set_index('날짜').sort_index() for c, g in K.dropna(subset=['날짜']).groupby('코드')}


def _one(g):
    v = {k: g[k].iloc[::-1].reset_index(drop=True) / 100 for k in ('외국인', '기관', '개인')}   # 0 = 가장 최근일, 억원
    f = v['외국인']; out = {}
    out['f5'], out['f20'] = f[:5].sum(), (f[:20].sum() if len(f) >= 20 else np.nan)
    out['inst5'], out['ind5'] = v['기관'][:5].sum(), v['개인'][:5].sum()
    sg = np.sign(f.values); st = 0
    if sg[0] != 0:
        for x in sg:
            if x != sg[0]: break
            st += 1
    out['fstreak'] = st * sg[0]
    for k, c in (('외국인', 'fz5'), ('기관', 'iz5')):
        s5 = v[k][::-1].rolling(5).sum().dropna()
        out[c] = float((s5.iloc[-1] - s5.mean()) / s5.std()) if len(s5) >= 15 and s5.std() > 0 else np.nan
    return out


def apply(f, t, d):
    global _K
    if _K is None:
        _K = _load(d) or {}
    if not _K:
        return f
    t = pd.Timestamp(t); f = f.copy()
    code = f['ticker'].astype(str).str.extract(r'^(\d{6})\.(?:KS|KQ)$')[0]
    R = {}
    for c in code.dropna().unique():
        g = _K.get(c)
        if g is None: continue
        g = g.loc[:t].tail(30)
        if len(g) >= 5 and g.index[-1] >= t - pd.Timedelta(days=10):
            R[c] = _one(g)
    for k in VARS:
        f[k] = code.map(lambda c: R.get(c, {}).get(k, np.nan) if isinstance(c, str) else np.nan).astype(float).values
    return f
