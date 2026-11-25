"""블록점수이력용 B18 업종 ETF 60주선 이격 과거 값 (11/24 의장 "B1~B18 다 채웠나?").
features.py는 오늘 시타델.csv(업종 ETF 60주 이격)만 읽어 과거 주에도 같은 값이 들어갔다(그래서 비웠음).
여기서는 시타델 주봉 창고(10년치 저장본 칸 가격10년_섹터주봉, 한투 주봉 2000~)로 그 주 금요일까지의 60주선 이격을 다시 계산한다.
종목↔업종 ETF 연결은 오늘 시타델.csv의 상위 10(과거 구성 기록 없음 — 지금 구성으로 씀). 상위 10에 없는 개별주는 features와 같이 같은 시장·층 중앙값.
sec_flow5(업종 ETF 자금)는 과거 좌수 기록이 없어 아직 비움.
쓰는 곳: backtest._one → apply(f, t, d)"""
import os

import numpy as np
import pandas as pd

import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'collect', 'data'))
import px_store as PS  # noqa: E402  10년치 저장본(11/26 의장: 따로 있던 과거 자료도 저장본 칸)

VARS = {'sec_gap60'}
_W = None


def _load(d):
    y = f'{d}/시타델.csv'
    W = PS.table(d, '섹터주봉', usecols=['티커', '날짜', '종가'], dtype={'티커': str}) if os.path.exists(y) else pd.DataFrame()   # 저장본 칸(옛 00_누적/00_시타델_주봉)
    if not len(W):
        return None
    W['날짜'] = pd.to_datetime(W['날짜'].astype(str), errors='coerce'); W['종가'] = pd.to_numeric(W['종가'], errors='coerce')
    C = W.dropna().pivot_table(index='날짜', columns='티커', values='종가', aggfunc='last').sort_index()
    Y = pd.read_csv(y, encoding='utf-8-sig', dtype=str)
    h = Y[Y['구분'] == '종목'][['ETF', '티커']].copy()
    h['티커'] = h['티커'].astype(str).str.upper()
    return C, h.groupby('티커')['ETF'].first()


def apply(f, t, d):
    global _W
    if _W is None:
        _W = _load(d) or (None, None)
    C, link = _W
    if C is None:
        return f
    c = C.loc[:pd.Timestamp(t)].tail(60)
    gap = (c.iloc[-1] / c.mean() * 100).where(c.notna().sum() >= 60) if len(c) else pd.Series(dtype=float)
    f = f.copy()
    key = f['ticker'].astype(str).str.upper().str.replace(r'\.(KS|KQ)$', '', regex=True)
    f['sec_gap60'] = key.map(link).map(gap).astype(float).values
    fill = f.groupby(['시장', 'layer'])['sec_gap60'].transform('median')
    f['sec_gap60'] = f['sec_gap60'].where(f['sec_gap60'].notna() | (f['구분'] != '개별주'), fill)
    return f
