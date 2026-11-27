"""수급분석센터 · 미국 (의장 11/28 0:38 "수급은 한국과 미국을 엄격히 나눠, 완전 다른 시장")
읽는 자료(드라이브만): 가격10년_공매도(FINRA 2주마다), 가격10년_거래량, 가격10년_ETF좌수일별.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common as FC  # noqa: E402

RULES = [  # (번호, 이름, 계산, 출처)
    ("FLOW01", "공매도 커버일수", "공매도 잔고 ÷ 일평균 거래량(일), 길수록 약함", "Asquith·Pathak·Ritter, 2005"),
    ("FLOW02", "공매도 잔고 변화", "이번 ÷ 지난 결제일 − 1(%), 늘면 약함", "Asquith·Pathak·Ritter, 2005"),
    ("FLOW03", "거래량 급증", "마지막 날 거래량 ÷ 앞 20일 평균(배)", "Gervais·Kaniel·Mingelgrin, 2001"),
    ("FLOW04", "ETF 좌수 증감 20일", "상장좌수 변화(%) — 미국 ETF", "Ben-David·Franzoni·Moussawi, 2018"),
    ("FLOW05", "기관 보유 변화(13F, 분기)", "자료 없음(받아야 함)", "Gompers·Metrick, 2001"),
]


def table(S, V, E, tickers):
    S = S.copy()
    S["결제일"] = pd.to_datetime(S["결제일"])
    rows = {}
    for t in tickers:
        if t.endswith((".KS", ".KQ")) or t.startswith("^"):
            continue
        r = {}
        x = S[S["ticker"] == t].sort_values("결제일")
        if len(x):
            last = x.iloc[-1]
            r["FLOW01"] = float(last["커버일수"])
            r["FLOW02"] = (last["공매도주식"] / last["전기공매도주식"] - 1) * 100 if last["전기공매도주식"] else np.nan
            r["공매도 결제일"] = last["결제일"].date()
        if t in V:
            r["FLOW03"] = FC.volume_surge(V[t])
        r["FLOW04"] = FC.etf_units(E, t)
        r["FLOW05"] = np.nan
        rows[t] = r
    return pd.DataFrame(rows).T


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    import drive as DR
    S, V, E = DR.long("가격10년_공매도"), DR.wide("가격10년_거래량"), DR.long("가격10년_ETF좌수일별", dtype={"코드": str})
    print(table(S, V, E, ["GOOGL", "META", "AAPL", "NVDA", "QQQM", "SPYM", "CB", "MA", "DRAM"]).to_string())
