"""1-1 가격: 유니버스 전 종목 + 지수 10년 일별 시가·고가·저가·종가·거래량(야후, 배당·분할 보정 종가)."""
import pandas as pd

from .common import universe, write

NAME = '가격'
IDX = ['^GSPC', '^NDX', '^KS11', '^KQ11', '^VIX']
LONG = ['^GSPC', '^NDX', '^KS11']   # 11/22 의장: 지수 장기 일봉(코스닥 제외), 가능한 가장 긴 기간


def run(ctx, c):
    import yfinance as yf
    U = universe(ctx)
    t = sorted(set(U['yfinance 티커'].dropna()) | set(c.get('추가', [])) | set(IDX))
    D = yf.download(t, period=f"{c.get('년', 10)}y", auto_adjust=True, progress=False, threads=True)
    for k, f in (('Close', '종가'), ('Open', '시가'), ('High', '고가'), ('Low', '저가'), ('Volume', '거래량')):
        write(ctx, f'가격10년_{f}.csv.gz', D[k], index=True)
    L = yf.download(LONG, period='max', auto_adjust=True, progress=False)
    L = L[['Open', 'High', 'Low', 'Close', 'Volume']].stack(level=1, future_stack=True).dropna(how='all')
    L.columns = ['시가', '고가', '저가', '종가', '거래량']
    write(ctx, '지수_장기.csv.gz', L.rename_axis(['날짜', '지수']).reset_index())
    ctx['P_raw'] = D['Close']
    ctx['V_raw'] = D['Volume']
    return {'종목': D['Close'].shape[1], '시작': str(D.index.min().date()), '끝': str(D.index.max().date())}
