"""시험용(의장 11/27 19:28, 나중에 지움): 하락 4번 바닥 구간(고점~저점 폭의 아래쪽 0.1)의 값으로 기준을 거꾸로 구한다.
- MI05 10년 금리 − 연준 기준금리(IOER, 2021-07-29부터 IORB = 목표 범위 위쪽)
- MI04 하이일드 스프레드(FRED가 2023-11부터만 공개 → 2025·2026 두 번만)
- MI08 낙폭(1년 최고 대비): S&P500·나스닥100·코스피
'네 번 다 잡는 기준' = 구간마다 가장 바닥 쪽 값 중 가장 덜 극단적인 값(그 값이면 네 구간 모두 하루 이상 켜짐).
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_mi as M  # noqa: E402


def series(m, P):
    tn = m["DGS10"].dropna()
    pol = pd.concat([m["IOER"].dropna(), m["IORB"].dropna()]).sort_index()
    pol = pol[~pol.index.duplicated(keep="last")].reindex(tn.index, method="ffill")
    dd = lambda px: (px / px.rolling(252, min_periods=1).max() - 1) * 100
    return {"MI05 10년 − 기준금리(%p)": (tn - pol).dropna(),
            "MI04 하이일드(%)": m["BAMLH0A0HYM2"].dropna(),
            "MI08 S&P500 낙폭(%)": dd(m["SPX"].dropna()),
            "MI08 나스닥100 낙폭(%)": dd(m["NDX"].dropna()),
            "MI08 코스피 낙폭(%)": dd(P["^KS11"].dropna())}


def run(m, P):
    spx = m["SPX"].dropna()
    rows, out = [], []
    for name, s in series(m, P).items():
        px = P["^KS11"].dropna() if "코스피" in name else m["NDX"].dropna() if "나스닥" in name else spx
        z = M.zones(px, spx)
        ext = {}
        for ep, (days, ld, low) in z.items():
            v = s.reindex(days).dropna()
            r = {"지표": name, "하락": ep, "구간": f"{days[0]:%y-%m-%d}~{days[-1]:%y-%m-%d}"}
            if len(v):
                r.update({"구간 최소": round(v.min(), 2), "구간 최대": round(v.max(), 2), "바닥날": round(s.asof(ld), 2)})
                ext[ep] = v
            rows.append(r)
        if not ext:
            continue
        hi_side = "하이일드" in name  # 클수록 바닥 쪽
        if hi_side:
            th, op = min(v.max() for v in ext.values()), ">="
        elif "낙폭" in name:
            th, op = max(v.min() for v in ext.values()), "<="
        else:
            th = None
        for o, t in (((op, th),) if th is not None else ((">=", max(v.max() for v in ext.values()) * 0 + min(v.max() for v in ext.values())),
                                                        ("<=", max(v.min() for v in ext.values())))):
            sig = s >= t if o == ">=" else s <= t
            sc = M.score(px, spx, sig)
            out.append({"지표": name, "역산 기준": f"{o} {t:.2f}", "잡은 하락": f"{len(ext)}번 중 {sum(1 for k in ext if sc[k] != '없음')}",
                        "구간 밖 켜진 날": sc["구간 밖 켜진 날"], "11/24 값": round(s.asof(pd.Timestamp('2026-11-24')), 2)})
    return pd.DataFrame(rows), pd.DataFrame(out)


if __name__ == "__main__":
    import check_episodes as E
    pd.set_option("display.width", 250)
    a, b = run(E.load("가격10년_시장지표"), E.load("가격10년_종가"))
    print(a.to_string(index=False))
    print(b.to_string(index=False))
