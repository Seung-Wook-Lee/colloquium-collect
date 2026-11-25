"""B24 '이익 전망이 오르나?'에 더하는 실제 이익 공식 3개 (11/24 의장 "없으면 블록을 바꾸던지, 지우는 것은 허락받고").
애널리스트 추정치(est30·est90·up30·dn30)는 과거 기록이 없어 B24가 과거 점수를 못 냈다. 원래 공식 3개는 그대로 두고(지우지 않음),
10년치 데이터베이스 EPS 칸(SEC·DART 공시일 기준 EPS TTM)로 같은 질문을 묻는 공식 3개를 더한다.
  eps_chg90  = EPS TTM 13주 전 대비 변화(%)             ↔ est90(내년 EPS 추정 90일 변화)
  eps_up2    = EPS TTM 26주 전 < 13주 전 < 지금(두 번 연속 증가)  ↔ up30 ≥ dn30(상향 건수 ≥ 하향)
  peer_eps90 = 같은 층 개별주 안 eps_chg90 순위(0~1)      ↔ peer_est30(동료 중 추정치 상향 큰 쪽)
오늘(features)과 과거(backtest) 모두 이 함수 하나로 계산한다(같은 식).
11/24 12:12 의장 "B15도 다 채우고": 선행 PER(애널리스트 추정치, 과거 기록 없음) 공식 2개 자리에 과거부터 있는 자료로 같은 질문을 묻는 공식 2개.
  per_dn52 = PER(TTM) 52주 전보다 낮음 + 실제 EPS(TTM) 52주 전보다 큼(이익이 늘어서 싸지는 중)   ↔ fper < per_ttm
  peer_ev  = 같은 층 개별주 안 EV/EBITDA 낮은 순위(0~1, 1 = 가장 쌈). ev_ebitda는 hist_fund(과거)·features(오늘)가 채움 ↔ peer_fper"""
import os

import numpy as np
import pandas as pd

import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'collect', 'data'))
import px_store as PS  # noqa: E402  10년치 데이터베이스

VARS = {'eps_chg90', 'eps_up2', 'peer_eps90', 'per_dn52', 'peer_ev'}


def load(d):
    P = PS.per_weekly(d)   # 11/26 10년치 데이터베이스(EPS 칸, PER = 종가 ÷ EPS)
    return None if P is None else P.dropna(subset=['EPS_TTM'])


def _at(P, t, back, win=10, col='EPS_TTM'):
    x = P[(P['날짜'] <= t - pd.Timedelta(days=back)) & (P['날짜'] >= t - pd.Timedelta(days=back + win))]
    return x.drop_duplicates('ticker', keep='last').set_index('ticker')[col]


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
    e52 = k.map(_at(P, t, 364)).astype(float)
    p0, p52 = k.map(_at(P, t, 0, col='PER')).astype(float), k.map(_at(P, t, 364, col='PER')).astype(float)
    ok = p0.notna() & p52.notna() & a.notna() & e52.notna()
    f['per_dn52'] = ((p0 > 0) & (p0 < p52) & (a > e52)).astype(float).where(ok).values
    if 'ev_ebitda' in f:
        ev = f['ev_ebitda'].where(stk & (f['ev_ebitda'] > 0))
        f['peer_ev'] = (1 - ev.groupby(f['layer']).rank(pct=True) + 1 / ev.groupby(f['layer']).transform('count')).values
    else:
        f['peer_ev'] = np.nan
    return f
