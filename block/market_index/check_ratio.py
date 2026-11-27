"""시험용(의장 11/27 19:27, 나중에 지움): 켜진 비율(%) 구간별로 그날이 실제 바닥 구간 안이었던 비율.
바닥 구간 = 최근 10년 단기 저점(check_lows.zigzag 5%)마다 고점~저점 폭의 아래쪽 0.1에 든 날.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_lows as L  # noqa: E402
import vote as V  # noqa: E402

BINS = [-0.1, 10, 20, 30, 40, 50, 60, 100]
LABELS = ["0~10%", "10~20%", "20~30%", "30~40%", "40~50%", "50~60%", "60% 이상"]


def inside_days(px):
    ins = pd.Series(False, index=px.index)
    for pk, tr in L.zigzag(px):
        low, hi = px[tr], px[pk]
        line = low + 0.1 * (hi - low)
        after = px[tr:]
        out = after[after > line].index
        w = px[pk:out[0]] if len(out) else px[pk:]
        ins[w[w <= line].index] = True
    return ins


def prob(px, D):
    r = D["켜진 비율"].reindex(px.index).dropna()
    ins = inside_days(px).reindex(r.index)
    t = pd.DataFrame({"비율": pd.cut(r, BINS, labels=LABELS), "안": ins})
    g = t.groupby("비율", observed=False)["안"].agg(["size", "sum"])
    g["바닥 구간 안 확률(%)"] = (g["sum"] / g["size"] * 100).round(1)
    return g.rename(columns={"size": "날 수", "sum": "바닥 구간 안"})


if __name__ == "__main__":
    import check_episodes as E
    pd.set_option("display.width", 250)
    m, P = E.load("가격10년_시장지표"), E.load("가격10년_종가")
    for nm, px, D in (("S&P500", m["SPX"].dropna()["2016-11-21":], V.table(m, P)),
                      ("코스피", P["^KS11"].dropna()["2016-11-21":], V.table_kr(m, P))):
        print(nm)
        print(prob(px, D).to_string())
        print(D["2026-11-18":].round(1).to_string())
