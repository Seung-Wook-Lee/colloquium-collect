"""시험용(의장 11/27 19:25, 나중에 지움): 최근 10년 단기 저점을 모두 찾아 하락 폭 5·10·15·20%로 나누고,
바닥 구간(고점~저점 폭의 아래쪽 0.1)에 MI 다수결 신호가 몇 개 켜졌는지 센다.
저점 찾기: 종가 지그재그 5%(직전 고점에서 5% 이상 빠졌다가 저점에서 5% 이상 오르면 저점 하나).
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vote as V  # noqa: E402


def zigzag(px, th=0.05):
    """→ [(고점일, 저점일)]"""
    out, pk, tr, mode = [], px.index[0], None, "down"
    for d, v in px.items():
        if mode == "down":
            if v > px[pk] and tr is None:
                pk = d
            if v <= px[pk] * (1 - th) and (tr is None or v < px[tr]):
                tr = d
            if tr is not None and v >= px[tr] * (1 + th):
                out.append((pk, tr))
                pk, tr = d, None
            elif tr is not None and v > px[pk]:
                pk, tr = d, None
    return out


def bucket(x):
    return "20% 이상" if x >= 20 else "15~20%" if x >= 15 else "10~15%" if x >= 10 else "5~10%"


def run(px, D):
    rows = []
    for pk, tr in zigzag(px):
        hi, low = px[pk], px[tr]
        line = low + 0.1 * (hi - low)
        after = px[tr:]
        out = after[after > line].index
        w = px[pk:out[0]] if len(out) else px[pk:]
        zone = [d for d in w[w <= line].index if d in D.index]
        if not zone:
            continue
        b = max(zone, key=lambda d: D.at[d, "켜진 수"])
        depth = (1 - low / hi) * 100
        rows.append({"고점": pk.date(), "저점": tr.date(), "하락%": round(depth, 1), "종류": bucket(depth),
                     "구간 최다": int(D.at[b, "켜진 수"]), "자료 수": int(D.at[b, "자료 수"]),
                     "과반": bool(D.loc[zone, "과반"].any())})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import check_episodes as E
    m, P = E.load("가격10년_시장지표"), E.load("가격10년_종가")
    for nm, px, D in (("S&P500", m["SPX"].dropna()["2016-11-21":], V.table(m, P)),
                      ("코스피", P["^KS11"].dropna(), V.table_kr(m, P))):
        t = run(px, D)
        print(nm)
        print(t.to_string(index=False))
        print(t.groupby("종류").agg(횟수=("과반", "size"), 과반=("과반", "sum"), 평균최다=("구간 최다", "mean")).round(1))
