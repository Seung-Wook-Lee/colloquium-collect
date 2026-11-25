"""블록점수이력용 B21 장기 펀드 13F 칸 과거 값 (11/24 의장 "b21은 13F 자료를 못받는다고?").
features.py는 오늘 장기펀드13F.csv만 읽어 과거 주에는 같은 값이 들어갔다(그래서 비웠음).
여기서는 10년치 저장본 13F 칸(fetch_13f.py --full, 종목×분기, '공시일' = 그 분기 13F가 모두 나온 마지막 날)에서
그 주까지 공시된 분기만 골라, 오늘 규칙과 같이 최근 두 분기 안의 마지막 값(lt_net 있는 것)을 쓴다.
쓰는 곳: backtest._one → apply(f, t, d)"""
import os

import numpy as np
import pandas as pd

import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'collect', 'data'))
import px_store as PS  # noqa: E402  10년치 저장본(11/26 의장: 따로 있던 과거 자료도 저장본 칸)

VARS = {'lt_up', 'lt_dn', 'lt_net', 'lt_net_prev'}
_R = None


def _load(d):
    R = PS.table(d, '13F')   # 저장본 칸(옛 1_data/장기/장기펀드13F_이력)
    if not len(R):
        return None
    R['공시일'] = pd.to_datetime(R['공시일'], errors='coerce'); R['분기'] = pd.to_datetime(R['분기'], errors='coerce')
    R['ticker'] = R['ticker'].astype(str).str.upper()
    return R.dropna(subset=['공시일', '분기'])


def apply(f, t, d):
    global _R
    if _R is None:
        _R = _load(d)
        if _R is None: _R = False
    if _R is False:
        return f
    t = pd.Timestamp(t)
    x = _R[_R['공시일'] <= t]
    f = f.copy()
    if not len(x):
        for k in VARS: f[k] = np.nan
        return f
    recent = sorted(x['분기'].unique())[-2:]
    L = x[x['분기'].isin(recent)].dropna(subset=['lt_net']).sort_values('분기').groupby('ticker').tail(1).set_index('ticker')
    key = f['ticker'].astype(str).str.upper()
    for k in VARS:
        f[k] = key.map(L[k]).astype(float).values if k in L else np.nan
    return f
