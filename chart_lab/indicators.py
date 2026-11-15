# ======================================================================
# 차트 실험실 — 보조지표 라이브러리 (2026-11-13 의장: 보조지표만으로 하는 기술적 분석 실험실)
#   한 종목의 봉(시가·고가·저가·종가·거래량) 표를 받아 지표 칸을 붙여 돌려준다.
#   일봉·주봉·월봉 모두 같은 함수(기간 숫자는 '봉' 단위).
#   패턴 판정(이중 바닥·넥라인 등)은 넣지 않는다(11/9 의장). 손절가 계산도 없다.
# ======================================================================
import numpy as np
import pandas as pd

MA_LIST = [5, 10, 20, 50, 60, 120, 150, 200]


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def rsi_wilder(c, n=14):
    """와일더식 RSI(룰 판정용)"""
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def rsi_simple(c, n=14):
    """단순평균식 RSI(미래에셋 차트와 같은 방식)"""
    d = c.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def add_all(df):
    """df: 날짜 순 정렬, 칸 open high low close volume. 지표 칸을 붙인 새 표."""
    o, h, l, c = df['open'], df['high'], df['low'], df['close']
    x = df.copy()
    # 이동평균·이격도(100 기준)
    for n in MA_LIST:
        x[f'ma{n}'] = c.rolling(n).mean()
        x[f'disp{n}'] = c / x[f'ma{n}'] * 100
    # MACD 12·26·9 (EMA, adjust=False). macd_pct = MACD÷종가×100 (종목·주가 수준 달라도 비교되게)
    x['macd'] = ema(c, 12) - ema(c, 26)
    x['macd_sig'] = ema(x['macd'], 9)
    x['macd_osc'] = x['macd'] - x['macd_sig']          # 오실레이터(막대)
    x['macd_pct'] = x['macd'] / c * 100
    x['osc_pct'] = x['macd_osc'] / c * 100
    # RSI 14
    x['rsi'] = rsi_wilder(c)
    x['rsi_s'] = rsi_simple(c)
    # CCI 20
    tp = (h + l + c) / 3
    mad = tp.rolling(20).apply(lambda v: np.mean(np.abs(v - v.mean())), raw=True)
    x['cci'] = (tp - tp.rolling(20).mean()) / (0.015 * mad)
    # 스토캐스틱 슬로우 14·3·3
    ll, hh = l.rolling(14).min(), h.rolling(14).max()
    fast_k = (c - ll) / (hh - ll).replace(0, np.nan) * 100
    x['stoch_k'] = fast_k.rolling(3).mean()
    x['stoch_d'] = x['stoch_k'].rolling(3).mean()
    # 볼린저 20·2
    mid, sd = c.rolling(20).mean(), c.rolling(20).std(ddof=0)
    x['bb_mid'], x['bb_up'], x['bb_dn'] = mid, mid + 2 * sd, mid - 2 * sd
    x['bb_pctb'] = (c - x['bb_dn']) / (4 * sd).replace(0, np.nan)
    x['bb_width'] = 4 * sd / mid * 100
    # 일목균형표 9·26·52 (구름은 26봉 앞으로 그린 것 = 오늘 자리의 구름은 26봉 전에 계산된 값)
    x['tenkan'] = (h.rolling(9).max() + l.rolling(9).min()) / 2
    x['kijun'] = (h.rolling(26).max() + l.rolling(26).min()) / 2
    span_a = (x['tenkan'] + x['kijun']) / 2
    span_b = (h.rolling(52).max() + l.rolling(52).min()) / 2
    x['span_a'], x['span_b'] = span_a.shift(26), span_b.shift(26)
    x['cloud_top'] = x[['span_a', 'span_b']].max(axis=1)
    x['cloud_bot'] = x[['span_a', 'span_b']].min(axis=1)
    # 고점 대비 하락(%), 지난 252봉(일봉 1년) 기준과 전체 기준
    x['dd252'] = (c / c.rolling(252, min_periods=20).max() - 1) * 100
    x['dd_all'] = (c / c.cummax() - 1) * 100
    # 하루(한 봉) 등락·양봉/음봉·꼬리
    x['chg'] = c.pct_change() * 100
    x['body'] = (c - o) / o * 100
    rng = (h - l).replace(0, np.nan)
    x['lower_tail'] = (np.minimum(o, c) - l) / rng      # 아랫꼬리 비율(0~1)
    x['upper_tail'] = (h - np.maximum(o, c)) / rng
    x['vol_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    return x


# ---------- 조건 문장에서 쓰는 도우미 (실험 설정 파일의 '조건' 줄) ----------
def cross_up(a, b=0):
    """a가 b를 아래에서 위로 넘은 봉(직전 봉 a<=b, 이번 봉 a>b)"""
    b_prev = b.shift(1) if isinstance(b, pd.Series) else b
    return (a > b) & (a.shift(1) <= b_prev)


def cross_down(a, b=0):
    b_prev = b.shift(1) if isinstance(b, pd.Series) else b
    return (a < b) & (a.shift(1) >= b_prev)


def turn_up(a):
    """a의 변화가 음/0에서 양으로 바뀐 봉(줄던 막대가 늘기 시작 등)"""
    d = a.diff()
    return (d > 0) & (d.shift(1) <= 0)


def turn_down(a):
    d = a.diff()
    return (d < 0) & (d.shift(1) >= 0)


def rising(a, n=1):
    """n봉 연속 상승"""
    return (a.diff() > 0).astype(int).rolling(n).sum() == n


def falling(a, n=1):
    return (a.diff() < 0).astype(int).rolling(n).sum() == n


def prev(a, n=1):
    return a.shift(n)


def within(cond, n):
    """지난 n봉 안(오늘 포함)에 cond가 한 번이라도 참"""
    return cond.astype(float).rolling(n, min_periods=1).max() > 0


def pctl(a, n=750, minp=250):
    """지난 n봉 안에서 오늘 값의 백분위(0~100, 과거 값만 씀)"""
    return a.rolling(n, min_periods=minp).rank(pct=True) * 100


HELPERS = dict(cross_up=cross_up, cross_down=cross_down, turn_up=turn_up, turn_down=turn_down,
               rising=rising, falling=falling, prev=prev, within=within, pctl=pctl, abs=abs)
