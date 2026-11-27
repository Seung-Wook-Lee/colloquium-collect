"""MI 다수결 (의장 11/27 19:23 "단독이 아니죠. 다수결")

미국 쪽 MI 11개를 날마다 켜짐(1)·꺼짐(0)으로 세고, 자료가 있는 것 중 켜진 비율이 절반을 넘으면 '과반'.
기준(의장 11/27, 임시 표시 = 아직 정하는 중):
  MI01 공포와 탐욕 ≤ 15 / MI02 CTA 근사값 ≤ −3.3σ / MI03 VIX ≥ 30 (5거래일 유지) / MI04 하이일드 ≥ 4% (임시)
  MI05 10년 금리 ≤ 4.8% (임시, 기준금리 대비 방식 찾는 중) / MI06 MOVE ≥ 100 (2거래일 유지) / MI07 WTI ≤ 80달러
  MI08 S&P500 낙폭(1년 최고 대비) ≤ −20% (아래쪽 10% 들어갈 때 평균 −20.4%) / MI09 미국 유니버스 150일선 아래 ≥ 80%
  MI10 VIX ÷ VIX3M ≥ 1 / MI11 주식 풋콜 ≥ 1.0
한국 전용 MI12 코스피 50일 이격도 ≤ 93, MI13(외국인)은 자료 준비 뒤 더함. MI14 신용잔고·고객예탁금은 값만(투표 안 함).
"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "source", "market"))
import check_mi as M  # noqa: E402
import cta as C  # noqa: E402


def table(m, P):
    spx = m["SPX"].dropna()
    on = lambda s: s.reindex(spx.index).astype(float)
    us = [c for c in P.columns if not c.startswith("^") and not c.endswith((".KS", ".KQ"))]
    vix, mv = m["VIX"].dropna(), m["MOVE"].dropna()
    S = {"MI01": on(m["공포탐욕"].dropna() <= 15),
         "MI02": on(C.cta(m[["SPX", "NDX", "RUT"]])["CTA σ"] <= -3.3),
         "MI03": on(M.hold(vix >= 30, 4)),
         "MI04": on(m["BAMLH0A0HYM2"].dropna() >= 4),
         "MI05": on(m["DGS10"].dropna() <= 4.8),
         "MI06": on(M.hold(mv >= 100, 2)),
         "MI07": on(m["WTI"].dropna() <= 80),
         "MI08": on(spx / spx.rolling(252, min_periods=1).max() - 1 <= -0.20),
         "MI09": on(M.breadth_below(P, us, 150) >= 80),
         "MI10": on((vix / m["VIX3M"]).dropna() >= 1),
         "MI11": on(m["CPCE"].dropna() >= 1)}
    D = pd.DataFrame(S).ffill(limit=3)
    D["켜진 수"] = D[list(S)].sum(axis=1)
    D["자료 수"] = D[list(S)].notna().sum(axis=1)
    D["과반"] = D["켜진 수"] / D["자료 수"] > 0.5
    return D


def table_kr(m, P):
    """코스피용: 미국 MI 중 MI08·MI09를 한국 것으로 바꾸고 MI12를 더함.
    MI08 코스피 낙폭 ≤ −20% (아래쪽 10% 들어갈 때 평균 −23.4%) / MI09 한국 유니버스 150일선 아래 ≥ 80% / MI12 코스피 50일 이격도 ≤ 93"""
    D = table(m, P).drop(columns=["켜진 수", "자료 수", "과반"])
    ks = P["^KS11"].dropna()
    kr = [c for c in P.columns if c.endswith((".KS", ".KQ"))]
    D = D.reindex(D.index.union(ks.index)).ffill(limit=3)
    on = lambda s: s.reindex(D.index).astype(float).ffill(limit=3)
    D["MI08"] = on(ks / ks.rolling(252, min_periods=1).max() - 1 <= -0.20)
    D["MI09"] = on(M.breadth_below(P, kr, 150) >= 80)
    D["MI12"] = on(ks / ks.rolling(50).mean() * 100 <= 93)
    cols = [c for c in D.columns if c.startswith("MI")]
    D["켜진 수"] = D[cols].sum(axis=1)
    D["자료 수"] = D[cols].notna().sum(axis=1)
    D["과반"] = D["켜진 수"] / D["자료 수"] > 0.5
    return D.reindex(ks.index)


if __name__ == "__main__":
    import check_episodes as E
    m, P = E.load("가격10년_시장지표"), E.load("가격10년_종가")
    D = table(m, P)
    spx = m["SPX"].dropna()
    for nm, px in (("미국", spx), ("코스피", P["^KS11"].dropna())):
        for ep, (d, ld, low) in M.zones(px, spx).items():
            dd = [x for x in d if x in D.index]
            b = max(dd, key=lambda x: D.at[x, "켜진 수"])
            print(nm, ep, f"구간 최다 {int(D.at[b, '켜진 수'])}/{int(D.at[b, '자료 수'])}", b.date())
    print(D.tail(5).to_string())
