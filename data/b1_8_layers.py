"""1-8 층 L1~L5: 정제 가격(1-6)으로 연 변동성(최근 N년, 제외 구간 뺌) → 종류별 문턱 → 의장 지정 우선."""
import pandas as pd

import universe_layers as UL
from .common import need, write


def run(ctx, c):
    u, U = ctx['ucfg'], ctx['U']
    P = need(ctx, 'P', '가격10년_정제.csv.gz', index_col=0, parse_dates=True)
    P = UL.asof(P, u)   # '재분류: 월' → 지난달 마지막 거래일 기준(한 달에 한 번 이동)
    P5 = P[P.index >= P.index.max() - pd.DateOffset(years=u['변동성_년'])]
    L = UL.classify(U, u, UL.vol_from(P5, U['yfinance 티커'].dropna().tolist(), u.get('제외_구간', [])))
    L['층_기준일'] = UL.base_day(P, u)
    write(ctx, '유니버스_층.csv.gz', L)
    ctx['L'] = L
    return pd.crosstab(L['종류'], L['층']).to_dict()
