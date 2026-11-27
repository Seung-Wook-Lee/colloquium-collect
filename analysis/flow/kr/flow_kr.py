"""수급분석센터 · 한국 (의장 11/28 0:38 "수급은 한국과 미국을 엄격히 나눠, 완전 다른 시장")
읽는 자료(드라이브만): 가격10년_국내수급(종목별 외국인·기관·개인 순매수 거래대금, 백만원), 가격10년_종가·거래량, 가격10년_ETF좌수일별.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common as FC  # noqa: E402

RULES = [  # (번호, 이름, 계산, 출처)
    ("FLOW01", "외국인 순매수 20일", "20일 순매수 합 ÷ 20일 거래대금(%)", "Choe·Kho·Stulz, 1999"),
    ("FLOW02", "기관 순매수 20일", "20일 순매수 합 ÷ 20일 거래대금(%)", "Sias, 2004"),
    ("FLOW03", "외국인·기관 같이 순매수한 날", "최근 20거래일 중 날 수", "Sias, 2004"),
    ("FLOW04", "개인 순매수 20일 (반대로 읽음)", "20일 순매수 합 ÷ 20일 거래대금(%), 많이 사면 약함", "Kaniel·Saar·Titman, 2008"),
    ("FLOW05", "거래량 급증", "마지막 날 거래량 ÷ 앞 20일 평균(배)", "Gervais·Kaniel·Mingelgrin, 2001"),
    ("FLOW06", "ETF 좌수 증감 20일", "상장좌수 변화(%) — 한국 ETF", "Ben-David·Franzoni·Moussawi, 2018"),
    ("FLOW07", "공매도 잔고", "한국거래소 공매도 잔고 — 자료 없음(받아야 함)", "Asquith·Pathak·Ritter, 2005"),
]


def table(F, C, V, E, tickers):
    F = F.copy()
    F["코드"] = F["코드"].astype(str).str.zfill(6)
    F["날짜"] = pd.to_datetime(F["날짜"].astype(str))
    F = F.drop_duplicates(["날짜", "코드"], keep="last")
    rows = {}
    for t in tickers:
        if not t.endswith((".KS", ".KQ")):
            continue
        code = t.split(".")[0]
        r = {}
        x = F[F["코드"] == code].sort_values("날짜").tail(20)
        if len(x) and t in C:
            val = (C[t] * V.get(t, np.nan)).reindex(x["날짜"]).sum() / 1e6     # 거래대금(백만원)
            if val:
                r["FLOW01"] = x["외국인"].sum() / val * 100
                r["FLOW02"] = x["기관"].sum() / val * 100
                r["FLOW04"] = x["개인"].sum() / val * 100
            r["FLOW03"] = float(((x["외국인"] > 0) & (x["기관"] > 0)).sum())
            r["수급 날짜"] = x["날짜"].iloc[-1].date()
        if t in V:
            r["FLOW05"] = FC.volume_surge(V[t])
        r["FLOW06"] = FC.etf_units(E, code)
        r["FLOW07"] = np.nan
        rows[t] = r
    return pd.DataFrame(rows).T


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    import drive as DR
    F = DR.long("가격10년_국내수급", dtype={"코드": str, "날짜": str})
    C, V, E = DR.wide("가격10년_종가"), DR.wide("가격10년_거래량"), DR.long("가격10년_ETF좌수일별", dtype={"코드": str})
    print(table(F, C, V, E, ["005930.KS", "000660.KS", "105560.KS", "069500.KS"]).to_string())
