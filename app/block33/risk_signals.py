"""시장 위험 신호(11/22 의장 승인): B35 항복 C1·C2·C4 + 표시용 C3·C5, B03 S&P–AAA 회사채 괴리.
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
    last = lambda x: float(x.iloc[-1]) if len(x) and pd.notna(x.iloc[-1]) else None
    return dict(CAP_VOL=last(c1), CAP_FORCED=last(c2), CAP_XASSET=last(c4), CAP_WATERFALL=last(c3), CAP_VIXBW=last(c5),
                AAA_GAP=last(gap), AAA_6M=last(aaa - aaa.shift(126)))
