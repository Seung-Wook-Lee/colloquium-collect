"""시험용(의장 11/27 20:38, 나중에 지움): 한국 2026-06-22 고점 때 MI 켜진 비율이 무엇을 보여 주는지.
- 6/22 앞뒤 기준별 켜짐·꺼짐, 켜진 비율
- 10년 켜진 비율 구간별 코스피 20·60일 뒤 수익, 60일 안 최대 낙폭
- 코스피 50일 이격도 130 이상 날(의장 19:20 '130 고점') 60일 뒤
"""
import io
import json
import base64
import os
import sys

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vote as V  # noqa: E402
import check_episodes as E  # noqa: E402


def flow():
    body = {"token": os.environ["DRIVE_TOKEN"], "action": "get", "path": f"{E.DB}/가격10년_국내수급.csv.gz"}
    out = requests.post(os.environ["DRIVE_URL"], data=json.dumps(body), timeout=300).json()
    return pd.read_csv(io.BytesIO(base64.b64decode(out["data"])), compression="gzip", dtype={"코드": str, "날짜": str})


if __name__ == "__main__":
    m, P, Vol = E.load("가격10년_시장지표"), E.load("가격10년_종가"), E.load("가격10년_거래량")
    kr = V.table_kr(m, P, flow(), Vol)
    ks = P["^KS11"].dropna()
    cols = [c for c in kr.columns if c.startswith("MI")]
    print(kr.loc["2026-06-01":"2026-07-10", cols + ["켜진 비율"]].assign(코스피=ks).round(1).to_string())
    r = kr["켜진 비율"].dropna()
    f20, f60 = ks.shift(-20) / ks - 1, ks.shift(-60) / ks - 1
    dd60 = ks[::-1].rolling(60, min_periods=1).min()[::-1].shift(-1) / ks - 1
    for lo, hi in [(0, 8), (8, 16), (16, 24), (24, 40), (40, 101)]:
        d = r[(r >= lo) & (r < hi)].index
        print(f"{lo}~{hi}%: {len(d)}일, 20일 뒤 {f20.reindex(d).mean()*100:.1f}%, 60일 뒤 {f60.reindex(d).mean()*100:.1f}%, "
              f"60일 안 최대 낙폭 {dd60.reindex(d).mean()*100:.1f}%, 60일 뒤 하락 {(f60.reindex(d) < 0).mean()*100:.0f}%")
    g = ks / ks.rolling(50).mean() * 100
    d = g[g >= 130].index
    print("50일 이격도 130 이상:", [x.date() for x in d], f"60일 뒤 {f60.reindex(d).mean()*100:.1f}%")
