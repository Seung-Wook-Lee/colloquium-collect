"""B24 '이익 전망이 오르나?'에 더하는 실제 이익 공식 3개 (11/24 의장 "없으면 블록을 바꾸던지, 지우는 것은 허락받고").
애널리스트 추정치(est30·est90·up30·dn30)는 과거 기록이 없어 B24가 과거 점수를 못 냈다. 원래 공식 3개는 그대로 두고(지우지 않음),
과거부터 있는 우리 자료 1_data/PER_EPS_주별(SEC·DART 공시일 기준 EPS TTM)로 같은 질문을 묻는 공식 3개를 더한다.
  eps_chg90  = EPS TTM 13주 전 대비 변화(%)             ↔ est90(내년 EPS 추정 90일 변화)
  eps_up2    = EPS TTM 26주 전 < 13주 전 < 지금(두 번 연속 증가)  ↔ up30 ≥ dn30(상향 건수 ≥ 하향)
  peer_eps90 = 같은 층 개별주 안 eps_chg90 순위(0~1)      ↔ peer_est30(동료 중 추정치 상향 큰 쪽)
오늘(features)과 과거(backtest) 모두 이 함수 하나로 계산한다(같은 식)."""
import os

import numpy as np
import pandas as pd

VARS = {'eps_chg90', 'eps_up2', 'peer_eps90'}
_P = {}


def load(d):
    p = f'{d}/장기/PER_EPS_주별.csv.gz'
    if p in _P:
        return _P[p]
    P = None
    if os.path.exists(p):
        P = pd.read_csv(p, usecols=['날짜', 'ticker', 'EPS_TTM'], parse_dates=['날짜']).dropna(subset=['EPS_TTM']).sort_values('날짜')
    _P[p] = P
    return P


def _at(P, t, back, win=10):
    x = P[(P['날짜'] <= t - pd.Timedelta(days=back)) & (P['날짜'] >= t - pd.Timedelta(days=back + win))]
    return x.drop_duplicates('ticker', keep='last').set_index('ticker')['EPS_TTM']


def apply(f, t, d):
    P = load(d)
    if P is None:
        return f
    t = pd.Timestamp(t) if t is not None else P['날짜'].max()
    e0, e13, e26 = _at(P, t, 0), _at(P, t, 91), _at(P, t, 182)
    k = f['ticker'].astype(str)
    a, b, c = k.map(e0).astype(float), k.map(e13).astype(float), k.map(e26).astype(float)
    f = f.copy()
    f['eps_chg90'] = ((a - b) / b.abs() * 100).where(b.abs() > 0).values
    f['eps_up2'] = ((a > b) & (b > c)).astype(float).where(a.notna() & b.notna() & c.notna()).values
    stk = f['구분'] == '개별주'
    f['peer_eps90'] = f['eps_chg90'].where(stk).groupby(f['layer']).rank(pct=True).values
    return f
