"""MI 기준 시험: 바닥 인근 10% (의장 11/27 19:11)

하락 4번(check_episodes.EP). 잣대(의장 11/27 19:21): 바닥 구간 = 고점~저점 폭을 1로 놓은 아래쪽 0.1 안의 날들(zones).
그 구간 안에 신호가 하루라도 켜지면 맞음. '구간 밖 켜진 날' = 2016-11 이후 네 구간 밖에서 켜진 날 수(헛신호).

자료: 드라이브 1_data/가격10년_시장지표(SPX·VIX·MOVE·DGS10·BAMLH0A0HYM2·WTI·CPCE), 가격10년_종가(^KS11, 유니버스 종목).
실행: python analysis/market_index/check_mi.py   (시크릿 DRIVE_URL, DRIVE_TOKEN)
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_episodes as E  # noqa: E402

BAND = 0.10


def hold(s, n):
    """켜진 뒤 n거래일 더 유지"""
    return s.astype(int).rolling(n + 1, min_periods=1).max() > 0


def breadth_below(P, cols, ma):
    """유니버스 종목 중 ma일선 아래 비율(%)"""
    X = P[cols].astype(float)
    X = X[X.notna().sum(axis=1) >= len(cols) * 0.5]  # 그 시장이 열린 날만 (미국·한국 휴장일이 섞여 있음)
    avg = X.rolling(ma, min_periods=int(ma * 0.9)).mean()
    below = (X < avg).astype(float).where(avg.notna() & X.notna())
    n = below.notna().sum(axis=1)
    return (below.sum(axis=1) / n.where(n >= 10) * 100).dropna()


def episodes(px, spx):
    out = {}
    for ep, (a, b) in E.EP.items():
        us = spx[a:b]
        ul = us.idxmin()
        w = px[a:b]
        low_d = ul if px is spx else w[ul - pd.Timedelta(days=30):ul + pd.Timedelta(days=30)].idxmin()
        low = w[low_d]
        pk = w[:low_d].idxmax()
        after = px[low_d:]
        end = after[after > low * (1 + BAND)].index
        out[ep] = (pk, low_d, low, end[0] if len(end) else after.index[-1])
    return out


def zones(px, spx):
    """바닥 구간(의장 11/27 19:21): 고점~저점 폭을 1로 놓고 아래쪽 0.1 안(종가 ≤ 저점 + 0.1×(고점−저점))에
    들어간 날부터 저점 뒤 그 선 위로 나온 날 전까지."""
    z = {}
    for ep, (pk, low_d, low, _) in episodes(px, spx).items():
        line = low + 0.1 * (px[pk] - low)
        after = px[low_d:]
        out = after[after > line].index
        w = px[pk:out[0]] if len(out) else px[pk:]
        z[ep] = (w[w <= line].index, low_d, low)
    return z


def score(px, spx, s):
    s = s.reindex(px.index).fillna(False).astype(bool)
    r, hit, inside = {}, 0, pd.Series(False, index=px.index)
    for ep, (days, low_d, low) in zones(px, spx).items():
        inside[days] = True
        on = s[days]
        on = on[on]
        if len(on) == 0:
            r[ep] = "없음"
            continue
        hit += 1
        r[ep] = f"{on.index[0]:%m-%d} ({len(on)}일)"
    r["맞음"] = f"{hit}/4"
    r["구간 밖 켜진 날"] = int((s & ~inside)["2016-11-21":].sum())
    return r


def drawdown_ranges(m, P):
    """의장 11/27 19:18: 하락 4번의 바닥 10% 구간 날들의 낙폭(1년 최고 대비) 최소·최대, 낙폭 기준별 맞음."""
    spx = m["SPX"].dropna()
    idx = {"S&P500": spx, "나스닥100": m["NDX"].dropna(), "코스피": P["^KS11"].dropna()}
    rows, tests = [], []
    for nm, px in idx.items():
        dd = (px / px.rolling(252, min_periods=1).max() - 1) * 100
        for ep, (d, ld, low) in zones(px, spx).items():
            rows.append({"지수": nm, "하락": ep, "구간": f"{d[0]:%y-%m-%d}~{d[-1]:%y-%m-%d}",
                         "낙폭 얕은 쪽": round(dd[d].max(), 1), "낙폭 깊은 쪽": round(dd[d].min(), 1)})
        for th in (-8, -10, -12, -15, -20):
            tests.append({"지수": nm, "기준": f"낙폭 ≤ {th}%", **score(px, spx, dd <= th)})
    return pd.DataFrame(rows), pd.DataFrame(tests)


def lower_tenth(m, P):
    """의장 11/27 19:20: 고점~바닥 폭의 아래쪽 10%(종가 ≤ 바닥 + 0.1×(고점−바닥))에 들어간 날·나온 날의 고점 대비 낙폭."""
    spx = m["SPX"].dropna()
    rows = []
    for nm, px in (("S&P500", spx), ("나스닥100", m["NDX"].dropna()), ("코스피", P["^KS11"].dropna())):
        for ep, (pk, ld, low, end) in episodes(px, spx).items():
            hi = px[pk]
            line = low + 0.1 * (hi - low)
            before, after = px[pk:ld], px[ld:]
            ent, ex = before[before <= line].index[0], after[after > line].index[0]
            dd = lambda d: round((px[d] / hi - 1) * 100, 1)
            rows.append({"지수": nm, "하락": ep, "고점": pk.date(), "바닥": ld.date(), "바닥 낙폭": dd(ld),
                         "들어간 날": ent.date(), "들어갈 때 낙폭": dd(ent), "나온 날": ex.date(), "나올 때 낙폭": dd(ex)})
    return pd.DataFrame(rows)


def kospi_gap50(P):
    """코스피 50일 이격도(종가 ÷ 50일 평균 × 100): 하락 바닥날 값, 80 이하·130 이상 날."""
    ks = P["^KS11"].dropna()
    g = ks / ks.rolling(50).mean() * 100
    return g


def build(m, P):
    spx = m["SPX"].dropna()
    ks = P["^KS11"].dropna()
    us_cols = [c for c in P.columns if not c.startswith("^") and not c.endswith((".KS", ".KQ"))]
    kr_cols = [c for c in P.columns if c.endswith((".KS", ".KQ"))]
    hy, mv, tn, wti, pc = (m[c].dropna() for c in ("BAMLH0A0HYM2", "MOVE", "DGS10", "WTI", "CPCE"))
    # 연준 기준금리 = 지급준비금 이자율(IOER → 2021-07-29부터 IORB, 목표 범위 위쪽). 10년 금리 − 기준금리.
    pol = pd.concat([m["IOER"].dropna(), m["IORB"].dropna()]).sort_index()
    pol = pol[~pol.index.duplicated(keep="last")].reindex(tn.index, method="ffill")
    gap = (tn - pol).dropna()
    US = {
        "MI04 하이일드 ≥ 3%": hy >= 3, "MI04 하이일드 ≥ 3.5%": hy >= 3.5, "MI04 하이일드 ≥ 4%": hy >= 4,
        "MI05 10년 − 기준금리 ≤ −0.5%p": gap <= -0.5, "MI05 10년 − 기준금리 ≤ 0": gap <= 0,
        "MI05 10년 − 기준금리 ≥ +1%p": gap >= 1,
        "MI06 MOVE ≥ 100, 2거래일 유지": hold(mv >= 100, 2),
        "MI07 WTI ≤ 80달러": wti <= 80, "MI07 WTI ≥ 80달러": wti >= 80,
        "MI08 S&P500 낙폭 ≤ −10%": spx / spx.rolling(252, min_periods=1).max() - 1 <= -0.10,
        "MI08 S&P500 낙폭 ≤ −15%": spx / spx.rolling(252, min_periods=1).max() - 1 <= -0.15,
        "MI08 S&P500 낙폭 ≤ −20%": spx / spx.rolling(252, min_periods=1).max() - 1 <= -0.20,
    }
    b150 = breadth_below(P, us_cols, 150)
    b200 = breadth_below(P, us_cols, 200)
    for th in (70, 80, 90):
        US[f"MI09 미국 유니버스 150일선 아래 ≥ {th}%"] = b150 >= th
    US["MI09 미국 유니버스 200일선 아래 ≥ 80%"] = b200 >= 80
    for th in (1.0, 1.2):
        US[f"MI11 풋콜(주식) ≥ {th}"] = pc >= th
    US["MI11 풋콜(주식) 5일 평균 ≥ 1.0"] = pc.rolling(5).mean() >= 1.0
    KR = {
        "MI08 코스피 낙폭 ≤ −10%": ks / ks.rolling(252, min_periods=1).max() - 1 <= -0.10,
        "MI08 코스피 낙폭 ≤ −15%": ks / ks.rolling(252, min_periods=1).max() - 1 <= -0.15,
        "MI08 코스피 낙폭 ≤ −20%": ks / ks.rolling(252, min_periods=1).max() - 1 <= -0.20,
    }
    k150 = breadth_below(P, kr_cols, 150)
    for th in (70, 80, 90):
        KR[f"MI09 한국 유니버스 150일선 아래 ≥ {th}%"] = k150 >= th
    for ma, ths in ((50, (93, 90, 80)),):  # 의장: 50일 이격도, 기준 93(11/27)
        gap = ks / ks.rolling(ma).mean() * 100
        for th in ths:
            KR[f"MI12 코스피 {ma}일 이격도 ≤ {th}"] = gap <= th
    rows = []
    for name, s in US.items():
        rows.append({"신호": name, "대상": "미국 S&P500", **score(spx, spx, s)})
        rows.append({"신호": name, "대상": "한국 코스피", **score(ks, spx, s)})
    for name, s in KR.items():
        rows.append({"신호": name, "대상": "한국 코스피", **score(ks, spx, s)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    t = build(E.load("가격10년_시장지표"), E.load("가격10년_종가"))
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 20)
    print(t.to_string(index=False))
    a, b = drawdown_ranges(E.load("가격10년_시장지표"), E.load("가격10년_종가"))
    print(a.to_string(index=False))
    print(b.to_string(index=False))
