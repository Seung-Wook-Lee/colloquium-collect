"""1-1 가격: 드라이브 저장본(1_data/가격10년_*)에 새 날짜만 덧붙인다(11/25 의장).
의장: "일요일에 10년치를 통째로 왜 다시 받지? 그걸 왜 코딩을 한거야. 당장 지워. 지금 10년치 있잖아."
→ 10년치 통째 받기를 지움. 규칙은 px_store.py(저장본에 있는 종목은 마지막 날 뒤만, 저장본에 없는 종목만 과거치).
지수 장기(저장본 칸 가격10년_지수장기, 옛 지수_장기.csv.gz)도 저장본 마지막 날 뒤만 받아 덧붙인다."""
import pandas as pd

from . import px_store as PS
from .common import read, universe, write

NAME = '가격'
IDX = ['^GSPC', '^NDX', '^KS11', '^KQ11', '^VIX']
LONG = ['^GSPC', '^NDX', '^KS11']   # 11/22 의장: 지수 장기 일봉(코스닥 제외), 가능한 가장 긴 기간


def _base(ctx):
    B = {}
    for k in PS.F:
        d = read(ctx, PS.name(k), index_col=0, parse_dates=True)
        if d is not None:
            d.index = pd.to_datetime(d.index)
            B[k] = d
    return B


def _long(ctx, yf):
    if ctx.get('drive'):   # 11/26 의장: 지수 장기도 10년치 저장본 칸 — 칸이 아직 없으면 옛 지수_장기.csv.gz를 칸으로 옮기고 휴지통
        import drive
        PS.fetch(drive, '지수장기', ctx['out'])
    old = read(ctx, PS.name('지수장기'))
    if old is not None and len(old):
        old['날짜'] = pd.to_datetime(old['날짜'])
        s0 = (old['날짜'].max() - pd.Timedelta(days=PS.OVERLAP_DAYS)).date()
        L = yf.download(LONG, start=str(s0), auto_adjust=True, progress=False)
    # 저장본이 없을 때만 전체(period=max)
    else:
        old, L = None, yf.download(LONG, period='max', auto_adjust=True, progress=False)
    L = L[['Open', 'High', 'Low', 'Close', 'Volume']].stack(level=1, future_stack=True).dropna(how='all')
    L.columns = ['시가', '고가', '저가', '종가', '거래량']
    L = L.rename_axis(['날짜', '지수']).reset_index()
    if old is not None:
        L = pd.concat([L, old]).drop_duplicates(['날짜', '지수'], keep='first').sort_values(['날짜', '지수'])
    write(ctx, PS.name('지수장기'), L)


def run(ctx, c):
    import yfinance as yf
    U = universe(ctx)
    t = sorted(set(U['yfinance 티커'].dropna()) | set(c.get('추가', [])) | set(IDX))
    B = _base(ctx)
    S0 = PS.start(B)
    NEW = PS.missing(B, t)
    OLDT = [x for x in t if x not in NEW]
    parts = []
    if OLDT and S0:
        parts.append(yf.download(OLDT, start=str(S0), auto_adjust=True, progress=False, threads=True))
    if NEW:   # 저장본에 없는 종목만 과거치
        parts.append(yf.download(NEW, period='10y', auto_adjust=True, progress=False, threads=True))
    N = {}
    if parts:
        D = pd.concat(parts, axis=1, sort=True)
        for k in PS.F:
            if k in D.columns.get_level_values(0):
                N[k] = D[k].dropna(how='all')
    B = PS.merge(B, N)
    B, _ = PS.keep(B, t)   # 11/25 의장: 유니버스에 없는 종목 기록은 지움
    for k, d in B.items():
        write(ctx, PS.name(k), d, index=True)
    _long(ctx, yf)
    ctx['P_raw'] = B['Close']
    ctx['V_raw'] = B.get('Volume')
    return {'종목': B['Close'].shape[1], '새로 받은 날': str(S0), '새 종목': len(NEW),
            '시작': str(B['Close'].index.min().date()), '끝': str(B['Close'].index.max().date())}
