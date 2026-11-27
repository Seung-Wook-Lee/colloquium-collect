"""시험용(의장 11/27 20:43, 나중에 지움): 작은 조정 바닥(7/29 같은)까지 넣어 MI 기준 역산.
저점 = 최근 10년 종가 지그재그 5%(check_lows.zigzag). 미국은 S&P500·나스닥100 저점 둘 다, 한국은 코스피.
바닥 구간 = 고점~저점 폭의 아래쪽 0.1(고점부터 저점 뒤 그 선 위로 올라갈 때까지).
기준마다: 지금 기준으로 맞힌 저점 수, 모든 저점·3/4·절반을 맞히려면 필요한 값(역산값), 그때 바닥 구간 밖에서 켜진 날 수.
VIX·MOVE는 5거래일 유지라 5일 최고값으로 본다.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vote as V  # noqa: E402
from check_lows import zigzag  # noqa: E402

START = "2016-11-21"


def zones(px):
    """→ [(고점, 저점, 바닥 구간 날짜들)]"""
    out = []
    for pk, tr in zigzag(px):
        hi, lo = px[pk], px[tr]
        line = lo + 0.1 * (hi - lo)
        after = px[tr:]
        up = after[after > line].index
        w = px[pk:up[0]] if len(up) else px[pk:]
        out.append((pk, tr, w[w <= line].index))
    return out


def judge(x, zs, sign, now):
    """sign=+1: x ≥ 기준이면 켜짐, −1: x ≤ 기준이면 켜짐"""
    x = x.dropna()
    x = x[x.index >= START]
    inzone = pd.DatetimeIndex(sorted(set().union(*[set(z) for _, _, z in zs])))
    best = []
    for pk, tr, z in zs:
        v = x.reindex(z).dropna()
        if len(v):
            best.append((tr, v.max() if sign > 0 else v.min()))
    if not best:
        return None
    b = pd.Series(dict(best)).sort_index()
    out_days = x[~x.index.isin(inzone)]
    lit = (lambda t: out_days >= t) if sign > 0 else (lambda t: out_days <= t)
    hit = (lambda t: (b >= t).sum()) if sign > 0 else (lambda t: (b <= t).sum())
    row = {"저점 수": len(b), "지금 기준": now, "맞힘": int(hit(now)), "밖 켜진 날": int(lit(now).sum())}
    for q, nm in ((1.0, "전부"), (0.75, "3/4"), (0.5, "절반")):
        t = b.quantile(1 - q) if sign > 0 else b.quantile(q)
        t = float(np.round(t, 2))
        row[f"{nm} 값"] = t
        row[f"{nm} 맞힘"] = int(hit(t))
        row[f"{nm} 밖"] = int(lit(t).sum())
    row["7/29 값"] = round(float(x.asof(pd.Timestamp("2026-07-29"))), 2) if len(x[:"2026-07-29"]) else None
    return row


def run(m, P, Vol):
    v = V.values(m, P, Vol)
    spx, ndx, ks = m["SPX"].dropna(), m["NDX"].dropna(), P["^KS11"].dropna()
    us = zones(spx[START:]) + zones(ndx[START:])
    kr = zones(ks[START:])
    h5 = lambda s: s.dropna().rolling(5, min_periods=1).max()
    US = [("MI01 공포와 탐욕", v["MI01"], -1, 15), ("MI02 CTA", v["MI02"], -1, -3.3), ("MI03 VIX(5일 최고)", h5(v["MI03"]), 1, 30),
          ("MI04 하이일드", v["MI04"], 1, 3), ("MI05 10년−기준금리", v["MI05"], 1, 0.52), ("MI06 MOVE(5일 최고)", h5(v["MI06"]), 1, 105),
          ("MI07 WTI", v["MI07"], 1, 80), ("MI08 S&P 낙폭", v["MI08"], -1, -10), ("MI08 나스닥100 낙폭", v["MI08 나스닥100"], -1, -15),
          ("MI10 VIX÷VIX3M", v["MI10"], 1, 1), ("MI11 풋콜", v["MI11"], 1, 1.0), ("MI15 맥클렐런 미국", v["MI15"], -1, -50)]
    if "MI14" in v:
        US.append(("MI14 QQQM÷RSP 주황선 대비 %", v["MI14"], -1, 10))
    KR = [("MI08 코스피 낙폭", v["MI08 코스피"], -1, -20), ("MI12 코스피 50일 이격도", v["MI12"], -1, 93),
          ("MI15 맥클렐런 한국", v["MI15 한국"], -1, -80)]
    rows = []
    for mk, lst, zs in (("미국", US, us), ("한국", KR, kr)):
        for nm, x, sg, now in lst:
            r = judge(x, zs, sg, now)
            if r:
                rows.append({"시장": mk, "기준": nm, **r})
    return pd.DataFrame(rows), us, kr


if __name__ == "__main__":
    import check_episodes as E
    m, P, Vol = E.load("가격10년_시장지표"), E.load("가격10년_종가"), E.load("가격10년_거래량")
    t, us, kr = run(m, P, Vol)
    print("미국 저점", len(us), "한국 저점", len(kr))
    print("7/29 포함:", [str(tr.date()) for _, tr, _ in us + kr if "2026-07" in str(tr)])
    pd.set_option("display.width", 300)
    print(t.to_string(index=False))
