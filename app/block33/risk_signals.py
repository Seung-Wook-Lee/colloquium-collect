"""시장 위험 신호. 11/22 23:16 의장 "번호를 늘리지 말고 비슷한 블록 안에 넣고 판단력이 오르는지 확인, 아니면 넣지 않음" →
block_ab.py(2006~ B02 판단력 IC, S&P 12달) 결과로 B02에 코폭 급반전(부담, IC 0.118→0.155)·VIX 33.5 이상(기회, →0.179)·코폭 0 아래 반등(기회, →0.191)만 넣음.
항복 C1·C2·C4는 B02 IC를 0.005 이하로만 바꿔 넣지 않음(B35 폐지), S&P–AAA 괴리는 B03 IC를 0.138→0.092로 떨어뜨려 뺌. 아래 칸은 표시용으로 계속 계산.
(옛 설명) B35 항복 C1·C2·C4 + 표시용 C3·C5, B03 S&P–AAA 회사채 괴리.
입력 표 D: 날짜 색인, 칸 SPX·SPX_VOL·GOLD·SILVER·BTC·TLT·VIX·VIX3M·DAAA (collect/data/fetch_risk_daily.py가 만든 시장위험.csv).
검증(2026-11-22, risk_lab.py): 켜진 첫날 S&P 12달 뒤 — C1 +20.3%(95%, 21번, 1950~) · C2 +12.7%(78%, 47번) · C4 +11.0%(85%, 17번)
vs 아무 날 +8.5~10.6%. C3 폭포수 +7.4%·C5 VIX 백워데이션 +3.5%는 아무 날보다 못해 판정에서 빼고 표시만.
AAA 괴리(S&P 고점 5% 안 + AAA 수익률 6달 +0.5%p) 6달 뒤 +2.0% vs 아무 날 +5.1% → 부담."""
import numpy as np
import pandas as pd

# 11/22 23:35 의장 "앵커드 Vwap을 B2에 넣어": QQQ:RSP 비율의 저점 앵커드 VWAP(거래대금 가중 누적 평균).
# 앵커 = 비율 10% 지그재그 저점(반대로 10% 올라 확정된 날부터 씀), 앵커 뒤 3년 안의 선만. 비율 상승 추세(252일 플러스) 중 선 −5%~+1% 안 = 1(기회).
# −5%: 의장 "선을 약간 밑돌았다가 그 근처에서 반등한 것도 지지". 검증 qqq_b02v2.py·b02_bottom_test.py(2006~).


def qqq_rsp_avwap(D):
    need = ('QQQ', 'RSP', 'QQQ_VOL', 'RSP_VOL')
    if not all(k in D for k in need):
        return None, None
    x = D[list(need)].dropna()
    if len(x) < 300:
        return None, None
    R = x['QQQ'] / x['RSP']; W = x['QQQ'] * x['QQQ_VOL'] + x['RSP'] * x['RSP_VOL']; i = R.index
    lows = []; mode, ext, et = 0, R.iloc[0], i[0]
    for t, v in R.items():
        if mode == 0:
            if v >= ext * 1.10: mode, ext, et = 1, v, t
            elif v <= ext / 1.10: mode, ext, et = -1, v, t
        elif mode == 1:
            if v > ext: ext, et = v, t
            elif v <= ext / 1.10: mode, ext, et = -1, v, t
        else:
            if v < ext: ext, et = v, t
            elif v >= ext * 1.10: lows.append((et, t)); mode, ext, et = 1, v, t
    t_now = i[-1]; best = None; on = 0
    for t0, tc in lows:
        if t_now < tc or t_now > t0 + pd.Timedelta(days=1095):
            continue
        av = float((R * W).loc[t0:].sum() / W.loc[t0:].sum()); gp = float(R.iloc[-1] / av - 1)
        if best is None or abs(gp) < abs(best): best = gp
        if -0.05 <= gp <= 0.01: on = 1
    up = R.iloc[-1] > R.iloc[-253] if len(R) > 252 else False
    return float(on and up), (round(best * 100, 2) if best is not None else None)


# 11/22 23:47 의장 1순위 "CTM 빨간불 들어오면 모든 분석을 멈추고 현금으로" → B01 최상위 스위치.
# CTM(Chande Trend Meter, StockCharts) 구성: 고가·저가·종가의 볼린저 밴드 위치(20·50·75·100봉), 100봉 표준편차 대비 가격 변화, RSI(14), 2봉 채널 돌파 → 0~100.
# 가중은 비공개 → 그림 값에 맞춘 재현 가중(ctm_fit.py). 주봉(금요일 끝, 이번 주는 지금까지). 빨간불 = 30 아래 4주 연속.
CTM_W = dict(BB=8, PC=0, RSI=3, BO=0)


def ctm(D, k='SPX'):
    c = D[k].dropna()
    h = D[f'{k}_HIGH'].reindex(c.index).fillna(c) if f'{k}_HIGH' in D else c
    l = D[f'{k}_LOW'].reindex(c.index).fillna(c) if f'{k}_LOW' in D else c
    C, Hh, L = c.resample('W-FRI').last().dropna(), h.resample('W-FRI').max().dropna(), l.resample('W-FRI').min().dropna()
    if len(C) < 110:
        return pd.Series(dtype=float)
    def pb(x, n):
        m = C.rolling(n).mean(); s = C.rolling(n).std()
        return ((x - (m - 2 * s)) / (4 * s)).clip(0, 1)
    BB = pd.concat([pb(x, n) for n in (20, 50, 75, 100) for x in (Hh, L, C)], axis=1).mean(axis=1)
    z = (C - C.shift(1)) / C.diff().rolling(100).std(); PC = ((z + 2) / 4).clip(0, 1)
    d = C.diff(); up = d.clip(lower=0).ewm(alpha=1 / 14).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1 / 14).mean(); RSI = up / (up + dn)
    BO = pd.Series(np.where(C > Hh.shift(1).rolling(2).max(), 1.0, np.where(C < L.shift(1).rolling(2).min(), 0.0, 0.5)), index=C.index)
    w = CTM_W; tw = sum(w.values())
    return 100 * (w['BB'] * BB + w['PC'] * PC + w['RSI'] * RSI + w['BO'] * BO) / tw


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
                **_ctm_out(D),
                **dict(zip(('QQRSP_AVWAP', 'QQRSP_AVWAP_GAP'), qqq_rsp_avwap(D))),
                COPPOCK=last(cop), COP_UP0=last(up0) if len(cop.dropna()) else None, COP_REV=last(rev) if len(cop.dropna()) > 60 else None)


def _ctm_out(D):
    out = {}
    for k in ('SPX', 'QQQ'):
        if k not in D:
            continue
        t = ctm(D, k).dropna()
        if len(t) >= 4:
            out[f'CTM_{k}'] = round(float(t.iloc[-1]), 1)
            if k == 'SPX':
                out['CTM_RED'] = float((t.tail(4) < 30).all())
                out['CTM_LOW_WEEKS'] = int((t[::-1] < 30).cumprod().sum())
                # 11/22 의장 "CTM선에서 다시 오르기 시작하면 알려줘야" → 초록불(반등 시작): 26주 최고 70 이상 → 8주 최저 45 아래 → 그 최저보다 +10점
                # 검증(ctm_green.py, 1964~ 67번): QQQ 26주 +8.1%(승률 79%) vs 같은 낙폭 아무 주 +5.8%, 26주 안 최대 낙폭 −8.1%
                mn8 = t.rolling(8).min()
                out['CTM_GREEN'] = float(t.rolling(26).max().iloc[-1] >= 70 and mn8.iloc[-1] < 45 and t.iloc[-1] - mn8.iloc[-1] >= 10)
                out['CTM_GREEN_AT'] = round(float(mn8.iloc[-1]) + 10, 1)   # 이 값 이상이면 초록불(8주 최저 + 10)
    # 11/22 의장 카드 선택 "둘 중 하나 켜지면 현금": MA 클러스터(S&P 주봉 50·55·60·65·70·75주선) ④ 빨간불 = 종가 < 클러스터 맨 아래 + 가운데 4주 기울기 < 0
    if 'SPX' in D:
        C = D['SPX'].dropna().resample('W-FRI').last().dropna()
        if len(C) >= 80:
            M = pd.concat([C.rolling(n).mean() for n in (50, 55, 60, 65, 70, 75)], axis=1); bot, mid = M.min(axis=1), M.mean(axis=1)
            out['MA_CLUSTER_RED'] = float(C.iloc[-1] < bot.iloc[-1] and mid.iloc[-1] < mid.iloc[-5])
            out['MA_CLUSTER_BOT'] = round(float(bot.iloc[-1]), 1); out['MA_CLUSTER_TOP'] = round(float(M.max(axis=1).iloc[-1]), 1)
            out['MA_CLUSTER_SLOPE'] = round(float(mid.iloc[-1] / mid.iloc[-5] - 1) * 100, 2)
    out['CASH_SWITCH'] = float(out.get('CTM_RED') == 1 or out.get('MA_CLUSTER_RED') == 1)
    return out
