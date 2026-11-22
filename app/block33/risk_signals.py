"""시장 위험 신호. 11/22 23:16 의장 "번호를 늘리지 말고 비슷한 블록 안에 넣고 판단력이 오르는지 확인, 아니면 넣지 않음" →
block_ab.py(2006~ B02 판단력 IC, S&P 12달) 결과로 B02에 코폭 급반전(부담, IC 0.118→0.155)·VIX 33.5 이상(기회, →0.179)·코폭 0 아래 반등(기회, →0.191)만 넣음.
항복 C1·C2·C4는 B02 IC를 0.005 이하로만 바꿔 넣지 않음(B35 폐지), S&P–AAA 괴리는 B03 IC를 0.138→0.092로 떨어뜨려 뺌. 아래 칸은 표시용으로 계속 계산.
(옛 설명) B35 항복 C1·C2·C4 + 표시용 C3·C5, B03 S&P–AAA 회사채 괴리.
입력 표 D: 날짜 색인, 칸 SPX·SPX_VOL·GOLD·SILVER·BTC·TLT·VIX·VIX3M·DAAA (collect/data/fetch_risk_daily.py가 만든 시장위험.csv).
검증(2026-11-22, risk_lab.py): 켜진 첫날 S&P 12달 뒤 — C1 +20.3%(95%, 21번, 1950~) · C2 +12.7%(78%, 47번) · C4 +11.0%(85%, 17번)
vs 아무 날 +8.5~10.6%. C3 폭포수 +7.4%·C5 VIX 백워데이션 +3.5%는 아무 날보다 못해 판정에서 빼고 표시만.
AAA 괴리(S&P 고점 5% 안 + AAA 수익률 6달 +0.5%p) 6달 뒤 +2.0% vs 아무 날 +5.1% → 부담."""
import pandas as pd


def signals(D):
    D = D.sort_index()
    s = D['SPX'].dropna(); i = s.index
    g = lambda k: D[k].reindex(i).ffill(limit=3) if k in D else pd.Series(index=i, dtype=float)
    r = lambda x, n: x / x.shift(n) - 1
    vol = g('SPX_VOL'); down = s.pct_change() < 0
    c1 = (down & (vol >= 2 * vol.rolling(50).mean().shift(1))).astype(int).rolling(5).max()
    mets = [g(k) for k in ('GOLD', 'SILVER', 'BTC')]
    c2 = ((sum((r(m, 5) <= -0.05).astype(int) for m in mets) >= 2) & (r(s, 5) < 0)).astype(int)
    c3 = ((r(s, 10) <= -0.10) & (r(s, 5) < r(s, 5).shift(5))).astype(int)
    tlt, gold = g('TLT'), g('GOLD')
    c20 = s.pct_change().rolling(20).corr(tlt.pct_change())
    c4 = ((r(s, 20) < 0) & (r(gold, 20) < 0) & (r(tlt, 20) < 0) & (c20 > 0.3)).astype(int)
    c5 = (g('VIX') / g('VIX3M') >= 1.10).astype(int)
    aaa = g('DAAA').ffill(limit=5)
    gap = ((s / s.rolling(252).max() - 1 >= -0.05) & (aaa - aaa.shift(126) >= 0.5)).astype(int)
    # 코폭(나스닥100 월봉 14·11·10): 지난달 말까지 확정된 값만
    n = D['NDX'].dropna() if 'NDX' in D else pd.Series(dtype=float)
    mo = n.resample('ME').last()
    if len(n) and n.index[-1] < mo.index[-1]: mo = mo.iloc[:-1]   # 이번 달은 아직 안 끝남
    cop = ((mo / mo.shift(14) - 1) + (mo / mo.shift(11) - 1)) * 100
    w = pd.Series(range(1, 11), dtype=float)
    cop = cop.rolling(10).apply(lambda x: (x * w.values).sum() / w.sum(), raw=True)
    up0 = ((cop < 0) & (cop > cop.shift(1))).astype(int)
    hi = cop.rolling(120, min_periods=60).quantile(.8)
    rev = ((cop.shift(1) >= hi.shift(1)) & (cop < cop.shift(1)) & (cop.shift(1) - cop >= cop.diff().abs().rolling(120, min_periods=60).median() * 2)).astype(int)
    last = lambda x: float(x.iloc[-1]) if len(x) and pd.notna(x.iloc[-1]) else None
    return dict(CAP_VOL=last(c1), CAP_FORCED=last(c2), CAP_XASSET=last(c4), CAP_WATERFALL=last(c3), CAP_VIXBW=last(c5),
                AAA_GAP=last(gap), AAA_6M=last(aaa - aaa.shift(126)),
                COPPOCK=last(cop), COP_UP0=last(up0) if len(cop.dropna()) else None, COP_REV=last(rev) if len(cop.dropna()) > 60 else None)
