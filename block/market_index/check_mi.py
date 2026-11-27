"""MI 기준 시험: 바닥 인근 10% (의장 11/27 19:11)

check_episodes.py 와 같은 하락 4번·같은 잣대(첫 신호 때 가격이 최종 저점에서 10% 안이었나)로
의장이 준 기준과 찾은 표준 후보를 시험한다. '4번 밖 켜진 날' = 2016-11 이후 하락 4번(고점~바닥 10% 구간 끝) 밖에서 켜진 날 수.

자료: 드라이브 1_data/가격10년_시장지표(SPX·VIX·MOVE·DGS10·BAMLH0A0HYM2·WTI·CPCE), 가격10년_종가(^KS11, 유니버스 종목).
실행: python block/market_index/check_mi.py   (시크릿 DRIVE_URL, DRIVE_TOKEN)
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


def score(px, spx, s):
    s = s.reindex(px.index).fillna(False).astype(bool)
    eps = episodes(px, spx)
    r, hit, inside = {}, 0, pd.Series(False, index=px.index)
    for ep, (pk, low_d, low, end) in eps.items():
        inside[pk:end] = True
        on = s[pk:end]
        on = on[on]
        if len(on) == 0:
            r[ep] = "신호 없음"
            continue
        d = on.index[0]
        x = (px[d] / low - 1) * 100
        hit += x <= BAND * 100
        r[ep] = f"{d:%y-%m-%d}, {x:.1f}%"
    r["10% 안"] = f"{hit}/4"
    r["4번 밖 켜진 날"] = int((s & ~inside)["2016-11-21":].sum())
    return r


def build(m, P):
    spx = m["SPX"].dropna()
    ks = P["^KS11"].dropna()
    us_cols = [c for c in P.columns if not c.startswith("^") and not c.endswith((".KS", ".KQ"))]
    kr_cols = [c for c in P.columns if c.endswith((".KS", ".KQ"))]
    hy, mv, tn, wti, pc = (m[c].dropna() for c in ("BAMLH0A0HYM2", "MOVE", "DGS10", "WTI", "CPCE"))
    US = {
        "MI04 하이일드 ≥ 6%": hy >= 6, "MI04 하이일드 ≥ 8% (T. Rowe Price 800bp)": hy >= 8,
        "MI04 하이일드 20일 +1%p": hy.diff(20) >= 1,
        "MI05 10년 금리 ≤ 4.8%": tn <= 4.8,
        "MI06 MOVE ≥ 100, 5거래일 유지": hold(mv >= 100, 5),
        "MI07 WTI ≤ 1년 최고 × 70%": wti <= wti.rolling(252, min_periods=60).max() * 0.7,
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
    for ma, ths in ((20, (90, 85, 80)), (60, (90, 85, 80)), (200, (90, 85, 80))):
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
