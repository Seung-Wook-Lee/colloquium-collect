"""2. 밸류센터 (미스 밸류) V01~V11 — 의장 11/28 0:38 "그냥 만들어", 번호 V01·V02…
기존 2-1 표의 PER·EPS·PEG(source/stock 매일 수집)에 더한다.
읽는 자료(드라이브만): 가격10년_SEC재무(미국 분기), 가격10년_DART재무(한국 분기), 가격10년_종가.
흐름 항목(매출·이익·현금흐름)은 최근 4분기 합(TTM), 잔액 항목(자본·자산·부채·현금)은 최근 분기 값.
시가총액 = 종가 × 희석 주식수(순이익 4분기 합 ÷ 희석 EPS 4분기 합, 없으면 공시 주식수).
DART 자료에는 자본·자산·부채·현금이 없어 한국은 V01·V02·V05·V07·V08·V10이 빈칸. V06 배당은 배당 자료가 없어 빈칸.
"""
import numpy as np
import pandas as pd

RULES = [  # (번호, 이름, 계산, 출처)
    ("V01", "PBR", "시가총액 ÷ 자본", "Fama·French, 1992"),
    ("V02", "ROE", "순이익(4분기 합) ÷ 자본", "듀폰 분석"),
    ("V03", "매출 증가율", "매출(4분기 합) ÷ 1년 전 4분기 합 − 1", "표준 재무비율"),
    ("V04", "영업이익률", "영업이익 ÷ 매출(4분기 합)", "표준 재무비율"),
    ("V05", "부채비율", "부채 ÷ 자본", "표준 재무비율"),
    ("V06", "배당수익률", "주당 배당 ÷ 주가 (배당 자료 없음 → 빈칸)", "표준"),
    ("V07", "EV/EBITDA", "(시가총액 + 차입금 − 현금) ÷ (영업이익 + 감가상각)", "Loughran·Wellman, 2011"),
    ("V08", "총이익 ÷ 총자산", "매출총이익(4분기 합) ÷ 자산", "Novy-Marx, 2013"),
    ("V09", "잉여현금흐름 수익률", "(영업현금흐름 − 설비투자) ÷ 시가총액", "표준"),
    ("V10", "피오트로스키 F점수", "재무 건전성 9개 항목 중 맞는 수 (0~9)", "Piotroski, 2000"),
    ("V11", "실적 발표 뒤 흐름(예상 밖 이익)", "(이번 분기 EPS − 1년 전 같은 분기) ÷ 그 차이의 8분기 표준편차", "Bernard·Thomas, 1989"),
]
FLOW = ["매출", "매출총이익", "영업이익", "순이익", "영업현금흐름", "설비투자", "감가상각"]
STOCK = ["자본", "자산", "부채", "현금", "단기부채", "장기부채", "유동자산", "유동부채", "주식수"]


def quarters(F, t):
    """한 종목 → 분기말 × 항목 표"""
    x = F[F["ticker"] == t]
    if x.empty:
        return pd.DataFrame()
    q = x.sort_values("공시일").pivot_table(index="분기말", columns="항목", values="값", aggfunc="last")
    q.index = pd.to_datetime(q.index)
    return q.sort_index()


def ttm(q, k, lag=0):
    if k not in q:
        return np.nan
    s = q[k].dropna()
    s = s.iloc[: len(s) - lag] if lag else s
    return s.iloc[-4:].sum() if len(s) >= 4 else np.nan


def bal(q, k, lag=0):
    if k not in q:
        return np.nan
    s = q[k].dropna()
    return s.iloc[-1 - lag] if len(s) > lag else np.nan


def fscore(q):
    """Piotroski 9개: 1년 전(4분기 전)과 비교"""
    ni, ni0 = ttm(q, "순이익"), ttm(q, "순이익", 4)
    cfo = ttm(q, "영업현금흐름")
    a, a0 = bal(q, "자산"), bal(q, "자산", 4)
    if any(v != v for v in (ni, cfo, a)):
        return np.nan
    roa, roa0 = ni / a, (ni0 / a0 if a0 == a0 and a0 else np.nan)
    lev = lambda lag: bal(q, "장기부채", lag) / bal(q, "자산", lag)
    cr = lambda lag: bal(q, "유동자산", lag) / bal(q, "유동부채", lag)
    gm = lambda lag: ttm(q, "매출총이익", lag) / ttm(q, "매출", lag)
    at = lambda lag: ttm(q, "매출", lag) / bal(q, "자산", lag)
    tests = [roa > 0, cfo > 0, roa > roa0, cfo > ni, lev(0) < lev(4), cr(0) > cr(4),
             bal(q, "주식수") <= bal(q, "주식수", 4), gm(0) > gm(4), at(0) > at(4)]
    return float(sum(bool(x) for x in tests))      # 비교할 수 없는 항목(빈칸)은 못 맞춘 것으로 센다


def sue(q):
    if "희석EPS" not in q:
        return np.nan
    e = q["희석EPS"].dropna()
    d = (e - e.shift(4)).dropna()
    if len(d) < 4:
        return np.nan
    sd = d.iloc[-8:].std()
    return d.iloc[-1] / sd if sd else np.nan


def one(q, price):
    if q.empty:
        return {}
    eps = ttm(q, "희석EPS")
    sh = ttm(q, "순이익") / eps if eps == eps and abs(eps) > 1e-9 else bal(q, "주식수")   # 희석 주식수(여러 종류 주식 합)
    if not (sh == sh and sh > 0):
        sh = bal(q, "주식수")
    cap = price * sh if sh == sh else np.nan
    eq, sales = bal(q, "자본"), ttm(q, "매출")
    ebitda = ttm(q, "영업이익") + (ttm(q, "감가상각") if "감가상각" in q else np.nan)
    debt = np.nansum([bal(q, "단기부채"), bal(q, "장기부채")]) if ("단기부채" in q or "장기부채" in q) else np.nan
    ev = cap + debt - bal(q, "현금") if debt == debt else np.nan
    pos = lambda v: v if v == v and v > 0 else np.nan
    return {
        "재무 분기": q["매출"].dropna().index[-1].date() if "매출" in q and q["매출"].notna().any() else q.index[-1].date(),
        "V01": cap / pos(eq),
        "V02": ttm(q, "순이익") / pos(eq) * 100,
        "V03": (sales / pos(ttm(q, "매출", 4)) - 1) * 100,
        "V04": ttm(q, "영업이익") / pos(sales) * 100,
        "V05": bal(q, "부채") / pos(eq) * 100,
        "V06": np.nan,
        "V07": ev / pos(ebitda),
        "V08": ttm(q, "매출총이익") / pos(bal(q, "자산")) * 100,
        "V09": (ttm(q, "영업현금흐름") - ttm(q, "설비투자")) / pos(cap) * 100,
        "V10": fscore(q) if "자산" in q else np.nan,
        "V11": sue(q),
    }


def table(SEC, DART, C, tickers):
    rows = {}
    for t in tickers:
        kr = t.endswith((".KS", ".KQ"))
        q = quarters(DART if kr else SEC, t if kr else t.replace("-", "."))
        if q.empty and not kr:
            q = quarters(SEC, t)
        price = C[t].dropna().iloc[-1] if t in C and C[t].notna().any() else np.nan
        r = one(q, price)
        if r:
            rows[t] = r
    return pd.DataFrame(rows).T


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import drive as DR
    SEC, DART, C = DR.long("가격10년_SEC재무"), DR.long("가격10년_DART재무"), DR.wide("가격10년_종가")
    pd.set_option("display.width", 250)
    print(table(SEC, DART, C, ["GOOGL", "META", "AAPL", "NVDA", "CB", "MA", "005930.KS", "000660.KS"]).to_string())
