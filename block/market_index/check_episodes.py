"""MI 검증: 바닥 인근 10% (의장 11/27)

질문: 신호가 켜졌을 때 지수가 '최종 저점에서 10% 안'이었나.
하락 4번(의장 지정): 2020 코로나, 2022 금리인상, 2025 관세, 2026 이란 전쟁. 미국 S&P500 + 한국 코스피(같은 신호).
신호(의장 기준): 공포와 탐욕 ≤ 15, CTA 근사값 ≤ −3.3σ, VIX ≥ 30 (켜진 뒤 5거래일 유효), 그리고 둘·셋 동시.
- 미국 최종 저점 = 지정 기간 안 S&P500 종가 최저. 한국 = 미국 저점 앞뒤 30일 안 코스피 종가 최저.
- 고점 = 저점 앞 최고 종가. 첫 신호는 고점 뒤부터 센다.
자료: 드라이브 1_data/가격10년_시장지표(SPX·NDX·RUT·VIX·공포탐욕), 가격10년_종가(^KS11).

실행: python block/market_index/check_episodes.py   (시크릿 DRIVE_URL, DRIVE_TOKEN)
"""
import base64
import io
import json
import os
import sys

import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "source", "market"))
import cta as C  # noqa: E402

DB = "콜로키움 수집데이터/1_data"
EP = {"2020 코로나": ("2020-01-01", "2020-06-30"), "2022 금리인상": ("2022-01-01", "2022-12-31"),
      "2025 관세": ("2025-02-01", "2025-05-31"), "2026 이란 전쟁": ("2026-01-01", "2026-05-31")}
BAND = 0.10


def load(name):
    body = {"token": os.environ["DRIVE_TOKEN"], "action": "get", "path": f"{DB}/{name}.csv.gz"}
    out = requests.post(os.environ["DRIVE_URL"], data=json.dumps(body), timeout=300).json()
    d = pd.read_csv(io.BytesIO(base64.b64decode(out["data"])), compression="gzip", index_col=0)
    d.index = pd.to_datetime(d.index, errors="coerce")
    return d[d.index.notna()].sort_index()


def signals(m):
    spx = m["SPX"].dropna()
    f = lambda s: s.reindex(spx.index).fillna(False).astype(bool)
    s = {"공포탐욕 ≤15": f(m["공포탐욕"].dropna() <= 15),
         "CTA ≤ −3.3σ": f(C.cta(m[["SPX", "NDX", "RUT"]])["CTA σ"] <= -3.3),
         "VIX ≥30 (5거래일)": f((m["VIX"].dropna() >= 30).astype(int).rolling(5, min_periods=1).max() > 0)}
    s["공포탐욕+CTA"] = s["공포탐욕 ≤15"] & s["CTA ≤ −3.3σ"]
    s["세 개 동시"] = s["공포탐욕+CTA"] & s["VIX ≥30 (5거래일)"]
    return spx, s


def table(m, ks):
    spx, sig = signals(m)
    rows = []
    for mk, px in (("미국 S&P500", spx), ("한국 코스피", ks)):
        for ep, (a, b) in EP.items():
            us = spx[a:b]
            ul = us.idxmin()
            w = px[a:b]
            low_d = ul if px is spx else w[ul - pd.Timedelta(days=30):ul + pd.Timedelta(days=30)].idxmin()
            low = w[low_d]
            pk = w[:low_d].idxmax()
            for name, s in sig.items():
                on = s.reindex(w.index).fillna(False).astype(bool)[pk:]
                on = on[on]
                r = {"시장": mk, "하락": ep, "고점": pk.date(), "최종 저점": low_d.date(), "낙폭%": round((low / w[pk] - 1) * 100, 1),
                     "신호": name}
                if len(on):
                    r.update({"첫 신호일": on.index[0].date(), "첫 신호 때 저점보다%": round((px[on.index[0]] / low - 1) * 100, 1),
                              "10% 안": px[on.index[0]] <= low * (1 + BAND),
                              "신호일 중 10% 안": f"{len(on)}일 중 {(px[on.index] <= low * (1 + BAND)).sum()}일",
                              "저점 대비 날수": (on.index[0] - low_d).days})
                rows.append(r)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    t = table(load("가격10년_시장지표"), load("가격10년_종가")["^KS11"].dropna())
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 20)
    print(t.to_string(index=False))
