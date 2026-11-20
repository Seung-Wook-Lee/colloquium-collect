"""3-12 기술적 분석 기법 모음(바닥 위주). 교과서·논문 이름이 있는 기법만, 교과서 기본값 그대로.

각 기법은 그날 '바닥 신호가 새로 켜졌나'(True/False)를 낸다. 미래 값은 쓰지 않는다
(꼭짓점은 확인되는 날에야 쓴다). 켜고 끄기는 비공개 Team_Q blocks.yaml '3-12 켜기'(처음엔 전부 꺼짐).

기법 번호·이름·출처는 TECH 표. 숫자 기본값은 출처 교과서 값이다. 교과서에 숫자가 없는 곳은
'단순화'라고 적고 다른 블록에서 쓰는 정의를 다시 쓴다.
"""
import numpy as np
import pandas as pd
import talib

# 번호, 이름, 갈래, 출처, 단위(종목/시장)
TECH = [
    ('T01', 'RSI 14일 30 아래→위', '과매도', 'Wilder 1978', '종목'),
    ('T02', 'RSI 2일 10 아래(200일선 위)', '과매도', 'Connors·Alvarez 2009', '종목'),
    ('T03', '스토캐스틱 슬로우 20 아래 상향 교차', '과매도', 'Lane; Murphy 1999 10장', '종목'),
    ('T04', '윌리엄스 %R −80 위로 복귀', '과매도', 'Williams 1973', '종목'),
    ('T05', 'CCI −100 위로 복귀', '과매도', 'Lambert 1980', '종목'),
    ('T06', '볼린저 하단 밖→안', '과매도', 'Bollinger 2001', '종목'),
    ('T07', '켈트너 채널 하단 이탈', '과매도', 'Keltner 1960; Raschke', '종목'),
    ('T08', '20일 이격도 92 이하', '과매도', '이격도(일본식); Murphy 9장', '종목'),
    ('T09', '5일 연속 하락', '과매도', 'Connors·Alvarez 2009', '종목'),
    ('T10', '1개월 수익 하위 10%(단기 반전)', '과매도', 'Jegadeesh 1990; Lehmann 1990', '종목'),
    ('T11', '3년 수익 하위 10%(장기 반전)', '과매도', 'De Bondt·Thaler 1985', '종목'),
    ('T12', '윌리엄스 VIX Fix 급등', '과매도', 'Williams 2007', '종목'),
    ('T13', '과매도 B16 근사(5개 중 3개)', '과매도', '엔진 B16(비교 기준)', '종목'),
    ('T15', 'RSI 강세 다이버전스', '다이버전스', 'Murphy 10장', '종목'),
    ('T16', 'MACD 강세 다이버전스', '다이버전스', 'Appel 1979; Elder 1993', '종목'),
    ('T17', 'MACD 막대 0 아래 반등', '다이버전스', 'Elder 1993', '종목'),
    ('T18', 'OBV 강세 다이버전스', '다이버전스', 'Granville 1963', '종목'),
    ('T19', '스토캐스틱 강세 다이버전스', '다이버전스', 'Lane; Murphy 10장', '종목'),
    ('T20', 'MACD 0 아래 신호선 상향 교차', '전환', 'Appel 1979', '종목'),
    ('T21', '50·200일선 골든크로스', '전환', 'Brock·Lakonishok·LeBaron 1992', '종목'),
    ('T22', '10개월선 위로 복귀', '전환', 'Faber 2007', '종목'),
    ('T23', '30주선 돌파(거래량 2배)', '전환', 'Weinstein 1988', '종목'),
    ('T24a', '일목 전환선>기준선(구름 아래)', '전환', '호소다; Elliott 2007', '종목'),
    ('T24b', '일목 구름 위로 돌파', '전환', '호소다; Elliott 2007', '종목'),
    ('T25', '파라볼릭 SAR 매수 전환', '전환', 'Wilder 1978', '종목'),
    ('T26', 'DMI +DI가 −DI 위로', '전환', 'Wilder 1978', '종목'),
    ('T27', '돈치안 20일 고점 돌파', '전환', 'Donchian; Faith 2007', '종목'),
    ('T28', '코폭 곡선 0 아래 반등', '전환', 'Coppock 1962', '종목'),
    ('T29', '주봉 전환 B17 근사', '전환', '엔진 B17(비교 기준)', '종목'),
    ('T31', '이중 바닥', '바닥 모양', 'Edwards·Magee 1948; Lo·Mamaysky·Wang 2000', '종목'),
    ('T32', '삼중 바닥', '바닥 모양', 'Edwards·Magee 1948; Bulkowski 2005', '종목'),
    ('T33', '역헤드앤숄더', '바닥 모양', 'Edwards·Magee 1948; Lo·Mamaysky·Wang 2000', '종목'),
    ('T34', '하락 쐐기 돌파', '바닥 모양', 'Bulkowski 2005', '종목'),
    ('T35', '원형 바닥(단순화)', '바닥 모양', 'Edwards·Magee 1948', '종목'),
    ('T36', '컵앤핸들', '바닥 모양', "O'Neil 1988", '종목'),
    ('T37', '섬꼴 반전', '바닥 모양', 'Edwards·Magee 1948', '종목'),
    ('T38', '핵심 반전일', '바닥 모양', 'Murphy 4장', '종목'),
    ('T39', '피보나치 38.2~61.8% 되돌림 저점', '바닥 모양', 'Murphy 4장', '종목'),
    ('T40', '직전 저점 지지 확인', '바닥 모양', 'Murphy 4장', '종목'),
    ('T41', '망치형', '캔들', 'Nison 1991', '종목'),
    ('T42', '상승 장악형', '캔들', 'Nison 1991', '종목'),
    ('T43', '샛별형', '캔들', 'Nison 1991', '종목'),
    ('T44', '관통형', '캔들', 'Nison 1991', '종목'),
    ('T45', '상승 잉태형', '캔들', 'Nison 1991', '종목'),
    ('T46', '적삼병', '캔들', 'Nison 1991', '종목'),
    ('T47', '셀링 클라이맥스', '투매', 'Wyckoff; Pruden 2007; Murphy 7장', '종목'),
    ('T48', '와이코프 스프링', '투매', 'Pruden 2007', '종목'),
    ('T49', '터틀 수프', '투매', 'Raschke·Connors 1995', '종목'),
    ('T50a', 'TD 시퀀셜 매수 셋업 9', '투매', 'DeMark 1994', '종목'),
    ('T50b', 'TD 시퀀셜 카운트다운 13', '투매', 'DeMark 1994', '종목'),
    ('T51', '거래량 3-11 근사(투매+MFI 20)', '투매', '엔진 3-11(비교 기준)', '종목'),
    ('T52', '츠바이크 브레드스 스러스트', '시장 전체', 'Zweig 1986', '시장'),
    ('T53', '90% 하락일 뒤 90% 상승일', '시장 전체', 'Desmond 2002(Lowry)', '시장'),
    ('T54a', '맥클렐런 오실레이터 −100 위로', '시장 전체', 'McClellan 1969', '시장'),
    ('T54b', '200일선 위 종목 20% 위로 복귀', '시장 전체', 'Murphy 13장', '시장'),
    ('T54c', '코폭 곡선 지수 반등', '시장 전체', 'Coppock 1962', '시장'),
]
META = pd.DataFrame(TECH, columns=['번호', '기법', '갈래', '출처', '단위']).set_index('번호')


def _up(x, lvl):
    """x가 lvl 아래에서 위로(어제 < lvl ≤ 오늘)."""
    return (x.shift(1) < lvl) & (x >= lvl)


def _cross(a, b):
    return (a.shift(1) <= b.shift(1)) & (a > b)


def _onset(b):
    b = b.fillna(False).astype(bool)
    return b & ~b.shift(1, fill_value=False)


def _pivots(x, k=5):
    """꼭짓점(앞뒤 k일 안 최저/최고). 확인 날짜 = 꼭짓점 + k일. 반환: [(확인 i, 꼭짓점 i, 값, 'L'/'H')]"""
    v = x.values
    n = len(v)
    out = []
    for i in range(k, n - k):
        w = v[i - k:i + k + 1]
        if np.isnan(w).any():
            continue
        if v[i] == w.min() and (w == v[i]).sum() == 1:
            out.append((i + k, i, v[i], 'L'))
        elif v[i] == w.max() and (w == v[i]).sum() == 1:
            out.append((i + k, i, v[i], 'H'))
    return out


def _flag(n, idx):
    a = np.zeros(n, dtype=bool)
    for i in idx:
        if 0 <= i < n:
            a[i] = True
    return a


def _divergence(price, ind, k=5, gap=(10, 60), ind_max=None):
    """강세 다이버전스(Murphy 10장): 가격 저점은 낮아지고 지표 저점은 높아짐. 확인일에 켜짐."""
    P = _pivots(price, k)
    lows = [(c, p, v) for c, p, v, t in P if t == 'L']
    iv = ind.values
    hit = []
    for j in range(1, len(lows)):
        c2, p2, v2 = lows[j]
        for c1, p1, v1 in reversed(lows[:j]):
            if p2 - p1 > gap[1]:
                break
            if p2 - p1 < gap[0]:
                continue
            if v2 < v1 and not np.isnan(iv[p1]) and not np.isnan(iv[p2]) and iv[p2] > iv[p1] \
                    and (ind_max is None or iv[p1] <= ind_max):
                hit.append(c2)
            break
    return pd.Series(_flag(len(price), hit), index=price.index)


def _lmw(price, k=3, win=38, tol=0.015):
    """Lo·Mamaysky·Wang(2000) 방식: 꼭짓점 5개(E1~E5)로 모양 판정. 꼭짓점은 3일 이동평균(커널 대신, 단순화)에서.
    반환: dict 모양 → 확인일 목록."""
    s = price.rolling(3, center=False).mean()
    P = _pivots(s, k)
    out = {'DBOT': [], 'IHS': [], 'TBOT3': [], 'WEDGE': []}
    for j in range(4, len(P)):
        E = P[j - 4:j + 1]
        if E[-1][1] - E[0][1] > win * 3:   # 5개 꼭짓점이 너무 멀면 버림(이중·삼중 바닥은 길이 허용)
            continue
        if E[0][3] != 'L' or [e[3] for e in E] != ['L', 'H', 'L', 'H', 'L']:
            continue
        e = [x[2] for x in E]
        conf = E[-1][0]
        m15 = (e[0] + e[4]) / 2
        m24 = (e[1] + e[3]) / 2
        # 역헤드앤숄더(LMW IHS): E3가 가장 낮고, E1·E5, E2·E4 각각 평균의 1.5% 안
        if e[2] < e[0] and e[2] < e[4] and abs(e[0] - m15) <= tol * m15 and abs(e[1] - m24) <= tol * m24 \
                and E[-1][1] - E[0][1] <= win:
            out['IHS'].append(conf)
        # 삼중 바닥: E1·E3·E5가 평균의 1.5% 안
        m135 = (e[0] + e[2] + e[4]) / 3
        if all(abs(x - m135) <= tol * m135 for x in (e[0], e[2], e[4])):
            out['TBOT3'].append(conf)
        # 하락 쐐기(Bulkowski): 저점·고점 모두 낮아지며 고점 쪽이 더 빨리 내려옴
        if e[0] > e[2] > e[4] and e[1] > e[3] and (e[1] - e[3]) / e[1] > (e[0] - e[4]) / e[0] > 0:
            out['WEDGE'].append(conf)
    # 이중 바닥(LMW DBOT): 저점 두 개가 평균의 1.5% 안, 22일 이상 떨어짐, 사이 고점이 더 높음
    lows = [x for x in P if x[3] == 'L']
    for j in range(1, len(lows)):
        c2, p2, v2, _ = lows[j]
        for c1, p1, v1, _ in reversed(lows[:j]):
            if p2 - p1 > 250:
                break
            if p2 - p1 < 22:
                continue
            m = (v1 + v2) / 2
            if abs(v1 - m) <= tol * m and abs(v2 - m) <= tol * m:
                mid = s.iloc[p1:p2 + 1].max()
                if mid > max(v1, v2) * (1 + tol):
                    out['DBOT'].append(c2)
                    break
    return out


def _breakout(close, conf_idx, level_fn, within=30):
    """모양 확인 뒤 within일 안에 기준선 위로 종가가 올라서는 날(Bulkowski 확인)."""
    c = close.values
    hit = []
    for i in conf_idx:
        lvl = level_fn(i)
        if lvl is None or np.isnan(lvl):
            continue
        for t in range(i, min(i + within, len(c))):
            if c[t] > lvl:
                hit.append(t)
                break
    return hit


def per_ticker(o, h, l, c, v):
    """한 종목: 기법 번호 → 신호(bool Series). o,h,l,c,v = Series(같은 날짜)."""
    idx = c.index
    n = len(c)
    O, H, L, C = (x.astype(float).values for x in (o, h, l, c))
    V = v.astype(float).fillna(0).values
    S = {}
    rsi = pd.Series(talib.RSI(C, 14), idx)
    S['T01'] = _up(rsi, 30)
    rsi2 = pd.Series(talib.RSI(C, 2), idx)
    ma200 = c.rolling(200).mean()
    S['T02'] = _onset((rsi2 < 10) & (c > ma200))
    k_, d_ = talib.STOCH(H, L, C, 14, 3, 0, 3, 0)
    K, D = pd.Series(k_, idx), pd.Series(d_, idx)
    S['T03'] = _cross(K, D) & (K < 20)
    S['T04'] = _up(pd.Series(talib.WILLR(H, L, C, 14), idx), -80)
    S['T05'] = _up(pd.Series(talib.CCI(H, L, C, 20), idx), -100)
    up, mid, lo = talib.BBANDS(C, 20, 2, 2)
    lo = pd.Series(lo, idx)
    S['T06'] = (c.shift(1) < lo.shift(1)) & (c >= lo)
    ema20 = pd.Series(talib.EMA(C, 20), idx)
    atr10 = pd.Series(talib.ATR(H, L, C, 10), idx)
    S['T07'] = _onset(c < ema20 - 2 * atr10)
    ma20 = c.rolling(20).mean()
    S['T08'] = _onset(c / ma20 * 100 <= 92)
    dn = (c < c.shift(1)).astype(int)
    S['T09'] = _onset(dn.rolling(5).sum() == 5)
    # 윌리엄스 VIX Fix: (22일 최고 종가 − 오늘 저가) ÷ 22일 최고 종가, 볼린저 20·2 상단 돌파
    wvf = (c.rolling(22).max() - l) / c.rolling(22).max() * 100
    S['T12'] = _onset(wvf > wvf.rolling(20).mean() + 2 * wvf.rolling(20).std())
    pctb = (c - lo) / (pd.Series(up, idx) - lo)
    cci = pd.Series(talib.CCI(H, L, C, 20), idx)
    b16 = (rsi <= 30).astype(int) + (c / c.rolling(50).mean() * 100 <= 90).astype(int) + (pctb <= 0.05).astype(int) \
        + (cci <= -100).astype(int) + (K <= 20).astype(int)
    S['T13'] = _onset(b16 >= 3)
    macd, sig, hist = (pd.Series(x, idx) for x in talib.MACD(C, 12, 26, 9))
    S['T15'] = _divergence(c, rsi, ind_max=30)
    S['T16'] = _divergence(c, macd) & (macd < 0)
    S['T17'] = (hist < 0) & (hist > hist.shift(1)) & (hist.shift(1) < hist.shift(2))
    obv = pd.Series(talib.OBV(C, V), idx)
    S['T18'] = _divergence(c, obv)
    S['T19'] = _divergence(c, K, ind_max=20)
    S['T20'] = _cross(macd, sig) & (macd < 0)
    S['T21'] = _cross(c.rolling(50).mean(), ma200)
    # 월말 기준(Faber): 월말 종가가 10개월 평균 위로
    me = c.groupby(idx.to_period('M')).tail(1)
    m10 = me.rolling(10).mean()
    S['T22'] = pd.Series(False, idx)
    S['T22'].loc[me.index] = ((me.shift(1) <= m10.shift(1)) & (me > m10)).values
    # 와인스타인: 주말 종가가 30주선 위로, 30주선이 내려가지 않음, 그 주 거래량 ≥ 직전 4주 평균 2배
    wk = idx.to_period('W-FRI')
    wc = c.groupby(wk).tail(1)
    wv = v.groupby(wk).sum()
    wv.index = wc.index
    w30 = wc.rolling(30).mean()
    cond = (wc.shift(1) <= w30.shift(1)) & (wc > w30) & (w30 >= w30.shift(1)) & (wv >= 2 * wv.shift(1).rolling(4).mean())
    S['T23'] = pd.Series(False, idx)
    S['T23'].loc[wc.index] = cond.values
    # 일목: 전환선 9, 기준선 26, 선행스팬 26일 앞
    tenkan = (h.rolling(9).max() + l.rolling(9).min()) / 2
    kijun = (h.rolling(26).max() + l.rolling(26).min()) / 2
    spanA = ((tenkan + kijun) / 2).shift(26)
    spanB = ((h.rolling(52).max() + l.rolling(52).min()) / 2).shift(26)
    ctop = pd.concat([spanA, spanB], axis=1).max(axis=1)
    cbot = pd.concat([spanA, spanB], axis=1).min(axis=1)
    S['T24a'] = _cross(tenkan, kijun) & (c < cbot)
    S['T24b'] = (c.shift(1) <= ctop.shift(1)) & (c > ctop)
    sar = pd.Series(talib.SAR(H, L, 0.02, 0.2), idx)
    S['T25'] = (c.shift(1) < sar.shift(1)) & (c > sar)
    S['T26'] = _cross(pd.Series(talib.PLUS_DI(H, L, C, 14), idx), pd.Series(talib.MINUS_DI(H, L, C, 14), idx))
    S['T27'] = c > h.shift(1).rolling(20).max()
    # 코폭(월봉): WMA10(ROC14 + ROC11), 0 아래에서 고개 듦
    mc = me
    cop = pd.Series(talib.WMA((mc.pct_change(14) * 100 + mc.pct_change(11) * 100).values, 10), mc.index)
    S['T28'] = pd.Series(False, idx)
    S['T28'].loc[mc.index] = ((cop < 0) & (cop > cop.shift(1)) & (cop.shift(1) <= cop.shift(2))).values
    # B17 근사: 주봉 MACD 막대 2주 연속 상승 + 주봉 RSI ≤ 40
    _, _, wh = talib.MACD(wc.values.astype(float), 12, 26, 9)
    wh = pd.Series(wh, wc.index)
    wr = pd.Series(talib.RSI(wc.values.astype(float), 14), wc.index)
    S['T29'] = pd.Series(False, idx)
    S['T29'].loc[wc.index] = _onset((wh > wh.shift(1)) & (wh.shift(1) > wh.shift(2)) & (wr <= 40)).values
    # 모양(LMW)
    pat = _lmw(c)
    sm = c.rolling(3).mean().values

    def neck(i, back=60):
        return np.nanmax(sm[max(0, i - back):i + 1])
    S['T31'] = pd.Series(_flag(n, _breakout(c, pat['DBOT'], lambda i: neck(i, 60))), idx)
    S['T32'] = pd.Series(_flag(n, _breakout(c, pat['TBOT3'], lambda i: neck(i, 60))), idx)
    S['T33'] = pd.Series(_flag(n, _breakout(c, pat['IHS'], lambda i: neck(i, 38))), idx)
    S['T34'] = pd.Series(_flag(n, _breakout(c, pat['WEDGE'], lambda i: neck(i, 20))), idx)
    # 원형 바닥(단순화): 120일 종가 2차 곡선 위로 볼록(a>0), 맞음 R² ≥ 0.8, 꼭짓점이 가운데 1/3, 왼쪽 시작가 돌파
    t = np.arange(120)
    rb = np.zeros(n, dtype=bool)
    for i in range(120, n, 5):
        y = C[i - 120:i]
        if np.isnan(y).any():
            continue
        a, b, cc = np.polyfit(t, y, 2)
        if a <= 0:
            continue
        fit = a * t * t + b * t + cc
        r2 = 1 - ((y - fit) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        vx = -b / (2 * a)
        if r2 >= 0.8 and 40 <= vx <= 80 and C[i] > y[0] >= C[i - 1]:
            rb[i] = True
    S['T35'] = pd.Series(rb, idx)
    # 컵앤핸들(O'Neil): 왼쪽 고점 → 12~33% 깊이 컵(7~65주) → 오른쪽 고점(왼쪽의 5% 안) → 손잡이 5~20일 ≤12% → 돌파 + 거래량 ≥ 50일 평균 1.4배
    pv = _pivots(c, 5)
    highs = [x for x in pv if x[3] == 'H']
    v50 = v.rolling(50).mean().values
    ch = []
    for j in range(1, len(highs)):
        c2, p2, v2, _ = highs[j]
        for c1, p1, v1, _ in reversed(highs[:j]):
            if p2 - p1 > 325:
                break
            if p2 - p1 < 35 or abs(v2 - v1) > 0.05 * v1:
                continue
            depth = 1 - np.nanmin(C[p1:p2 + 1]) / v1
            if 0.12 <= depth <= 0.33:
                for tt in range(p2 + 5, min(p2 + 21, n)):
                    hd = 1 - np.nanmin(C[p2:tt]) / v2
                    if hd > 0.12:
                        break
                    if C[tt] > max(v1, v2) and V[tt] >= 1.4 * v50[tt] and tt >= c2:
                        ch.append(tt)
                        break
            break
    S['T36'] = pd.Series(_flag(n, ch), idx)
    # 섬꼴 반전: 하락 갭(고가 < 전날 저가) 뒤 1~20일 안 상승 갭(저가 > 섬 구간 고가), 하락 갭 때 50일선 아래
    ma50 = c.rolling(50).mean().values
    isl = []
    for i in range(1, n):
        if H[i] < L[i - 1] and C[i] < ma50[i]:
            for tt in range(i + 1, min(i + 21, n)):
                if L[tt] > np.nanmax(H[i:tt]):
                    isl.append(tt)
                    break
    S['T37'] = pd.Series(_flag(n, isl), idx)
    # 핵심 반전일: 20일 새 저가를 찍고 종가는 전날 종가 위
    S['T38'] = (l < l.shift(1).rolling(20).min()) & (c > c.shift(1))
    # 피보나치: 직전 상승(저점→고점)의 38.2~61.8% 되돌림 안에서 새 저점 확인
    fib, sup = [], []
    for j in range(2, len(pv)):
        a1, a2, a3 = pv[j - 2], pv[j - 1], pv[j]
        if (a1[3], a2[3], a3[3]) == ('L', 'H', 'L') and a2[2] > a1[2]:
            r = (a2[2] - a3[2]) / (a2[2] - a1[2])
            if 0.382 <= r <= 0.618:
                fib.append(a3[0])
    lowsP = [x for x in pv if x[3] == 'L']
    for j in range(1, len(lowsP)):
        c2, p2, v2, _ = lowsP[j]
        for c1, p1, v1, _ in reversed(lowsP[:j]):
            if p2 - p1 > 250:
                break
            if p2 - p1 >= 20 and abs(v2 - v1) <= 0.015 * v1:
                sup.append(c2)
                break
    S['T39'] = pd.Series(_flag(n, fib), idx)
    S['T40'] = pd.Series(_flag(n, sup), idx)
    # 캔들(TA-Lib 정의) + 앞선 하락(10일 전보다 낮음, Nison: 반전형은 하락 뒤에만 뜻이 있음)
    downtrend = (c.shift(1) < c.shift(11))
    for k, f in (('T41', talib.CDLHAMMER), ('T42', talib.CDLENGULFING), ('T43', talib.CDLMORNINGSTAR),
                 ('T44', talib.CDLPIERCING), ('T45', talib.CDLHARAMI), ('T46', talib.CDL3WHITESOLDIERS)):
        S[k] = (pd.Series(f(O, H, L, C), idx) > 0) & downtrend
    # 셀링 클라이맥스: 20일 새 저가 + 거래량 ≥ 50일 평균 2배(3-11 투매 정의) → 5일 안 그날 고가 위 종가(자동 반등)
    v50s = v.rolling(50).mean()
    scd = ((l <= l.rolling(20).min()) & (v >= 2 * v50s) & (c < c.shift(1))).values
    sc = []
    for i in np.where(scd)[0]:
        for tt in range(i + 1, min(i + 6, n)):
            if C[tt] > H[i]:
                sc.append(tt)
                break
    S['T47'] = pd.Series(_flag(n, sc), idx)
    # 스프링: 50일 박스 바닥 아래로 깼다가 같은 날 위로 마감, 거래량 50일 평균 이하(Pruden: 거래량 적은 스프링)
    box = l.shift(1).rolling(50).min()
    S['T48'] = (l < box) & (c > box) & (v <= v50s)
    # 터틀 수프(Raschke·Connors): 오늘 20일 새 저가, 직전 20일 저가가 4일 이상 전, 종가가 직전 20일 저가 위
    prev20 = l.shift(1).rolling(20).min()
    age = l.shift(1).rolling(20).apply(lambda w: 19 - np.nanargmin(w), raw=True)
    S['T49'] = (l < prev20) & (age >= 3) & (c > prev20)
    # TD 시퀀셜(DeMark): 셋업 = 종가가 4일 전보다 낮은 날 9일 연속(직전 날은 아님 = 가격 뒤집기)
    lt4 = (c < c.shift(4)).astype(int).values
    run = np.zeros(n, dtype=int)
    for i in range(1, n):
        run[i] = run[i - 1] + 1 if lt4[i] else 0
    s9 = run == 9
    S['T50a'] = pd.Series(s9, idx)
    # 카운트다운: 셋업 9 뒤 종가 ≤ 2일 전 저가인 날을 13번(연속 아님), 매도 셋업(4일 전보다 높은 날 9연속) 나오면 취소
    gt4 = (c > c.shift(4)).astype(int).values
    run2 = np.zeros(n, dtype=int)
    for i in range(1, n):
        run2[i] = run2[i - 1] + 1 if gt4[i] else 0
    cd = []
    cnt, active = 0, False
    for i in range(2, n):
        if s9[i]:
            active, cnt = True, 0
        if active:
            if run2[i] >= 9:
                active = False
                continue
            if C[i] <= L[i - 2]:
                cnt += 1
                if cnt == 13:
                    cd.append(i)
                    active = False
    S['T50b'] = pd.Series(_flag(n, cd), idx)
    # 3-11 근사: 5일 안 하락일 거래량 ≥ 20일 평균 2배 + MFI 14 ≤ 20
    mfi = pd.Series(talib.MFI(H, L, C, V, 14), idx)
    capit = ((v >= 2 * v.rolling(20).mean()) & (c < c.shift(1))).rolling(5).max() > 0
    S['T51'] = _onset(capit & (mfi <= 20))
    return {k: s.fillna(False).astype(bool) for k, s in S.items()}


def cross_section(C, tickers, me_only=True):
    """T10·T11: 같은 나라 종목 안 순위(월말). 새로 하위 10%에 들어온 달 월말에 켜짐."""
    Cn = C[tickers]
    me_idx = Cn.groupby(Cn.index.to_period('M')).tail(1).index
    out = {}
    for k, lb in (('T10', 21), ('T11', 756)):
        r = Cn.pct_change(lb, fill_method=None).loc[me_idx]
        q = r.rank(axis=1, pct=True) <= 0.10
        new = q & ~q.shift(1, fill_value=False)
        full = pd.DataFrame(False, index=Cn.index, columns=tickers)
        full.loc[me_idx] = new.values
        out[k] = full
    return out


def market(C, V, tickers, index_close):
    """시장 전체 기법(같은 나라 유니버스로 오름·내림 종목 수를 셈). 반환: 번호 → bool Series(지수 날짜)."""
    Cn, Vn = C[tickers], V[tickers]
    r = Cn.pct_change(fill_method=None)
    adv, dec = (r > 0).sum(axis=1), (r < 0).sum(axis=1)
    ok = (adv + dec) >= 10
    S = {}
    # 츠바이크: 상승 비율 10일 EMA가 0.40 아래에서 10일 안에 0.615 위로
    ar = (adv / (adv + dec)).where(ok)
    e = ar.ewm(span=10, adjust=False).mean()
    low_recent = (e < 0.40).rolling(10).max() > 0
    S['T52'] = _onset((e > 0.615) & low_recent)
    # 데즈먼드: 하락 거래량 90% 이상인 날 뒤 3달(63일) 안에 상승 거래량 90% 이상인 날
    dv = (Vn * (r < 0)).sum(axis=1)
    uv = (Vn * (r > 0)).sum(axis=1)
    tot = (dv + uv).replace(0, np.nan)
    d90 = (dv / tot >= 0.9)
    u90 = (uv / tot >= 0.9)
    S['T53'] = u90 & (d90.shift(1).rolling(63).max() > 0)
    # 맥클렐런(비율 조정): 1000×(A−D)/(A+D)의 19일 EMA − 39일 EMA, −100 아래에서 위로
    rana = (1000 * (adv - dec) / (adv + dec)).where(ok)
    mo = rana.ewm(span=19, adjust=False).mean() - rana.ewm(span=39, adjust=False).mean()
    S['T54a'] = _up(mo, -100)
    above = (Cn > Cn.rolling(200).mean()).where(Cn.rolling(200).count() >= 200)
    pa = above.mean(axis=1)
    S['T54b'] = _up(pa, 0.20)
    me = index_close.groupby(index_close.index.to_period('M')).tail(1)
    cop = pd.Series(talib.WMA((me.pct_change(14) * 100 + me.pct_change(11) * 100).values.astype(float), 10), me.index)
    s = pd.Series(False, index_close.index)
    s.loc[me.index] = ((cop < 0) & (cop > cop.shift(1)) & (cop.shift(1) <= cop.shift(2))).values
    S['T54c'] = s
    return {k: v.reindex(index_close.index).fillna(False).astype(bool) for k, v in S.items()}
