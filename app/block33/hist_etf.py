"""블록점수이력용 B20 ETF 자금 과거 값 (11/24 B20).
features.py는 오늘 ETF자금.csv·시타델.csv만 읽어 과거 주에도 같은 값이 들어갔다(그래서 비웠음).
여기서는 10년치 저장본 ETF좌수 칸(State Street 공식 이력, 일별 좌수·NAV)로 그 주 금요일까지를 블록 9-ETF자금과 같은 식으로 다시 계산한다.
  하루 유입 = 좌수 변화 × NAV, 5일·20일 = 마지막 5·20 거래일 합(백만달러)
  etf_flow5·etf_flow20 = 그 ETF 자신, sec_flow5 = 종목이 상위 10에 든 업종 ETF의 5일(연결은 오늘 시타델.csv, hist_sector와 같음)
  money_ok는 features와 같은 규칙으로 다시 계산(그 주 값으로).
이력이 없는 ETF(한국·SPDR 아닌 미국)는 비움(오늘 값을 과거에 넣지 않음).
쓰는 곳: backtest._one → apply(f, t, d)"""
import os

import numpy as np
import pandas as pd

import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'collect', 'data'))
import px_store as PS  # noqa: E402  10년치 저장본(11/26 의장: 따로 있던 과거 자료도 저장본 칸)

VARS = {'etf_flow5', 'etf_flow20', 'sec_flow5'}
_E = None


def _load(d):
    H = PS.table(d, 'ETF좌수')   # 저장본 칸(옛 1_data/장기/ETF좌수_이력)
    if not len(H):
        return None
    H['날짜'] = pd.to_datetime(H['날짜'], errors='coerce')
    H = H.dropna(subset=['날짜']).sort_values(['코드', '날짜'])
    H['daily'] = H.groupby('코드')['상장좌수'].diff() * H['NAV'] / 1e6
    link = pd.Series(dtype=str)
    y = f'{d}/시타델.csv'
    if os.path.exists(y):
        Y = pd.read_csv(y, encoding='utf-8-sig', dtype=str)
        h = Y[Y['구분'].isin(['종목', 'ETF'])][['ETF', '티커']].copy()   # 11/26: 섹터 ETF 자기 값(상위 종목 없음)
        h['티커'] = h['티커'].astype(str).str.upper()
        link = h.groupby('티커')['ETF'].first()
    return H, link


def _money(r):
    if r['구분'] != '개별주':
        v = r.get('etf_flow5'); return np.nan if pd.isna(v) else int(v > 0)
    if r['시장'] == '한국':
        if pd.isna(r.get('f5')): return np.nan
        return int(r['f5'] > 0 and ((r.get('f20') or 0) > 0 or (r.get('fstreak') or 0) >= 3))
    v = r.get('sec_flow5'); return np.nan if pd.isna(v) else int(v > 0)


def apply(f, t, d):
    global _E
    if _E is None:
        _E = _load(d) or False
    if _E is False:
        return f
    H, link = _E
    t = pd.Timestamp(t); f = f.copy()
    x = H[(H['날짜'] <= t) & (H['날짜'] >= t - pd.Timedelta(days=45))]
    g = x.groupby('코드')['daily']
    f5 = g.apply(lambda s: s.tail(5).sum() if s.tail(5).notna().all() and len(s) >= 5 else np.nan)
    f20 = g.apply(lambda s: s.tail(20).sum() if s.tail(20).notna().all() and len(s) >= 20 else np.nan)
    key = f['ticker'].astype(str).str.upper()
    etf = f['구분'] != '개별주'
    f['etf_flow5'] = key.map(f5).where(etf).astype(float).values
    f['etf_flow20'] = key.map(f20).where(etf).astype(float).values
    k2 = key.str.replace(r'\.(KS|KQ)$', '', regex=True)
    f['sec_flow5'] = k2.map(link).map(f5).astype(float).values
    fill = f.groupby(['시장', 'layer'])['sec_flow5'].transform('median')   # features와 같이: 상위 10에 없는 개별주는 같은 시장·층 중앙값
    f['sec_flow5'] = f['sec_flow5'].where(f['sec_flow5'].notna() | (f['구분'] != '개별주'), fill)
    if 'money_ok' in f:
        f['money_ok'] = f.apply(_money, axis=1)
    return f
