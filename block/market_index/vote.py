"""MI 초록불과 켜진 비율 (의장 11/27)

바닥을 찾는다: 바닥 조건에 맞으면 초록불(1), 아니면 꺼짐(0). 켜진 비율(%) = 켜진 수 ÷ 자료가 있는 기준 수 × 100.
19:27 "과반수가 아니라 %로", 19:44·19:54 기준 확정.
  MI01 공포와 탐욕 ≤ 15
  MI02 CTA 근사값 ≤ −3.3σ
  MI03 VIX ≥ 30, 켜진 날부터 5거래일 유지
  MI04 하이일드 스프레드 ≥ 3%
  MI05 10년 금리 − 연준 기준금리(IOER, 2021-07-29부터 IORB) ≥ +0.52%p
  MI06 MOVE ≥ 100, 켜진 날부터 5거래일 유지
  MI07 WTI ≥ 80달러
  MI08 낙폭(1년 최고 대비): S&P500 ≤ −10%, 나스닥100 ≤ −15%, 코스피 ≤ −20% (19:55 "작은 조정도 잡게")
       미국은 S&P500·나스닥100 둘 중 하나라도 맞으면 켜짐, 한국은 코스피
  MI09 뺌(19:54) — 과매도 지표 검토 중
  MI10 VIX ÷ VIX3M ≥ 1
  MI11 주식 풋콜 비율(Cboe) ≥ 1.0
  MI12 코스피 50일 이격도 ≤ 93 (한국만)
  MI13 외국인 순매도(한국만, 의장 20:06·20:10): 한국 유니버스 개별주 외국인 순매수 합을 주별(월~금)로 더해,
       전주가 순매도였고 이번 주 순매도가 전주보다 줄었으면(매수로 돈 경우 포함) 그 주 거래일에 초록불.
       이번 주는 그날까지 더한 값으로 전주와 비교한다. MI14 QQQM vs RSP Anchored VWAP·MI15 맥클렐런 오실레이터(유니버스판) — 기준 확정 대기.
  신용잔고는 기준에서 뺌(20:06).
미국 = MI01~MI08·MI10·MI11, 한국 = 여기에 MI08을 코스피로 바꾸고 MI12를 더함.
"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "source", "market"))
import cta as C  # noqa: E402

RULES = [  # (번호, 이름, 기준 글)
    ("MI01", "공포와 탐욕 지수", "15 이하"),
    ("MI02", "CTA 근사값", "−3.3σ 이하"),
    ("MI03", "VIX", "30 이상, 5거래일 유지"),
    ("MI04", "하이일드 스프레드", "3% 이상"),
    ("MI05", "10년 금리 − 연준 기준금리", "+0.52%p 이상"),
    ("MI06", "MOVE", "100 이상, 5거래일 유지"),
    ("MI07", "WTI", "80달러 이상"),
    ("MI08", "지수 낙폭 (1년 최고 대비)", "S&P −10% 또는 나스닥 −15% / 코스피 −20%"),
    ("MI10", "VIX ÷ VIX3M", "1 이상"),
    ("MI11", "주식 풋콜 비율", "1.0 이상"),
    ("MI12", "코스피 50일 이격도", "93 이하 (한국만)"),
    ("MI13", "외국인 순매수 (주별 합)", "전주 순매도보다 이번 주 매도가 줄면 (한국만)"),
]


def hold(s, n):
    """켜진 날부터 n거래일 유지 (켜진 날 포함)"""
    return s.astype(int).rolling(n, min_periods=1).max() > 0


def rate_gap(m):
    """10년 금리 − 연준 기준금리(지급준비금 이자율 IOER, 2021-07-29부터 IORB = 목표 범위 위쪽), %p"""
    tn = m["DGS10"].dropna()
    pol = pd.concat([m["IOER"].dropna(), m["IORB"].dropna()]).sort_index()
    pol = pol[~pol.index.duplicated(keep="last")].reindex(tn.index, method="ffill")
    return (tn - pol).dropna()


def foreign_week(F):
    """F: 가격10년_국내수급(날짜·코드·외국인 …, 백만원) → 주별 외국인 순매수 합(억원), 날짜별 MI13 켜짐"""
    F = F.copy()
    F["날짜"] = pd.to_datetime(F["날짜"].astype(str))
    F = F.drop_duplicates(["날짜", "코드"], keep="last")
    day = F.groupby("날짜")["외국인"].sum() / 100
    wk = day.groupby(day.index.to_period("W-FRI"))
    to_date = wk.cumsum()                       # 이번 주 그날까지의 합
    full = wk.sum()                             # 주 전체 합
    prev = pd.Series(full.shift(1).reindex(day.index.to_period("W-FRI")).values, index=day.index)
    on = (to_date > prev) & (prev < 0)
    return full, on.astype(float)


def values(m, P=None):
    """기준에 쓰는 값(그날 숫자)"""
    spx = m["SPX"].dropna()
    v = {"MI01": m["공포탐욕"].dropna(), "MI02": C.cta(m[["SPX", "NDX", "RUT"]])["CTA σ"],
         "MI03": m["VIX"].dropna(), "MI04": m["BAMLH0A0HYM2"].dropna(), "MI05": rate_gap(m),
         "MI06": m["MOVE"].dropna(), "MI07": m["WTI"].dropna(),
         "MI08": (spx / spx.rolling(252, min_periods=1).max() - 1) * 100,
         "MI08 나스닥100": (lambda n: (n / n.rolling(252, min_periods=1).max() - 1) * 100)(m["NDX"].dropna()),
         "MI10": (m["VIX"] / m["VIX3M"]).dropna(), "MI11": m["CPCE"].dropna()}
    if P is not None and "^KS11" in P:
        ks = P["^KS11"].dropna()
        v["MI08 코스피"] = (ks / ks.rolling(252, min_periods=1).max() - 1) * 100
        v["MI12"] = ks / ks.rolling(50).mean() * 100
    return v


def _count(D):
    cols = [c for c in D.columns if c.startswith("MI")]
    D["켜진 수"] = D[cols].sum(axis=1)
    D["자료 수"] = D[cols].notna().sum(axis=1)
    D["켜진 비율"] = D["켜진 수"] / D["자료 수"] * 100
    return D


def signals(m, P=None):
    """기준마다 켜짐(1)·꺼짐(0) — 각 자료의 날짜 그대로. 미국용 MI08과 한국용 MI08 코스피·MI12."""
    v = values(m, P)
    f = lambda b: b.astype(float)
    ndx = v["MI08 나스닥100"]
    us08 = pd.concat([v["MI08"] <= -10, ndx <= -15], axis=1).ffill(limit=3).fillna(False).any(axis=1)
    S = {"MI01": f(v["MI01"] <= 15), "MI02": f(v["MI02"] <= -3.3), "MI03": f(hold(v["MI03"] >= 30, 5)),
         "MI04": f(v["MI04"] >= 3), "MI05": f(v["MI05"] >= 0.52), "MI06": f(hold(v["MI06"] >= 100, 5)),
         "MI07": f(v["MI07"] >= 80), "MI08": f(us08), "MI10": f(v["MI10"] >= 1), "MI11": f(v["MI11"] >= 1)}
    if "MI12" in v:
        S["MI08 코스피"] = f(v["MI08 코스피"] <= -20)
        S["MI12"] = f(v["MI12"] <= 93)
    return S


def _table(S, idx, cols):
    D = pd.DataFrame({k: S[k] for k in cols})
    D = D.reindex(D.index.union(idx)).ffill(limit=3).reindex(idx)
    return _count(D)


def table(m, P=None):
    """미국: 날마다 MI 켜짐(1)·꺼짐(0), 켜진 수, 켜진 비율(%). 날짜 = S&P500 거래일."""
    S = signals(m)
    return _table(S, m["SPX"].dropna().index, ["MI01", "MI02", "MI03", "MI04", "MI05", "MI06", "MI07", "MI08",
                                              "MI10", "MI11"])


def table_kr(m, P, F=None):
    """한국: 미국 것에서 MI08을 코스피 낙폭으로 바꾸고 MI12(코스피 50일 이격도)·MI13(외국인)을 더함. 날짜 = 코스피 거래일.
    F = 가격10년_국내수급(없으면 MI13 빼고)."""
    S = signals(m, P)
    S["MI08"] = S.pop("MI08 코스피")
    cols = ["MI01", "MI02", "MI03", "MI04", "MI05", "MI06", "MI07", "MI08", "MI10", "MI11", "MI12"]
    if F is not None:
        S["MI13"] = foreign_week(F)[1]
        cols.append("MI13")
    return _table(S, P["^KS11"].dropna().index, cols)


if __name__ == "__main__":
    import check_episodes as E
    m, P = E.load("가격10년_시장지표"), E.load("가격10년_종가")
    print(table(m).tail(8).to_string())
    print(table_kr(m, P).tail(8).to_string())
