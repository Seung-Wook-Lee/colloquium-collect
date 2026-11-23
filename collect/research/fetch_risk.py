"""시장 위험 지표 장기 자료(11/22 의장: B35 항복 블록, 골드만 패닉 근사, S&P–AAA 회사채 괴리).
야후(키 없음): ^GSPC(OHLCV), ^NDX, GC=F 금, SI=F 은, BTC-USD, TLT, LQD, QLTA, ^VIX, ^VIX3M, ^SKEW, ^VVIX — 상장 이후 전체 일봉
FRED(FRED_KEY): DAAA(무디스 AAA 회사채 수익률), BAMLC0A1CAAA(ICE AAA 회사채 OAS), DGS10(10년물)
결과: history/시장위험_장기.csv (날짜 × 칸)"""
import os, time
import pandas as pd, requests, yfinance as yf
os.makedirs('history', exist_ok=True)
YF = {'SPX': '^GSPC', 'NDX': '^NDX', 'GOLD': 'GC=F', 'SILVER': 'SI=F', 'BTC': 'BTC-USD', 'TLT': 'TLT', 'LQD': 'LQD', 'QLTA': 'QLTA',
      'VIX': '^VIX', 'VIX3M': '^VIX3M', 'SKEW': '^SKEW', 'VVIX': '^VVIX', 'MOVE': '^MOVE', 'QQQ': 'QQQ', 'RSP': 'RSP', 'IEF': 'IEF', 'SHY': 'SHY', 'AGG': 'AGG', 'BIL': 'BIL', 'NVDA': 'NVDA', 'SPYG': 'SPYG', 'IVW': 'IVW', 'IWF': 'IWF', 'IWD': 'IWD', 'MGK': 'MGK', 'COMPQ': '^IXIC', 'RUT': '^RUT'}   # 11/22 의장 IWF:IWD 월봉 일목, MGK 주봉, 나스닥 종합 코폭   # 11/22 의장 BIL:SPYG 일목 검증   # 11/22 의장 NVDA 앵커드 VWAP   # 11/22 의장 QQQ:RSP 앵커드 VWAP(거래량 포함)
RAW = ('QQQ', 'RSP', 'SPYG', 'BIL', 'IWF', 'IWD')   # 11/22 변곡점 판: 비율 그림 원본 재현
cols = {}
for k, t in YF.items():
    for _ in range(3):
        try:
            h = yf.Ticker(t).history(period='max', auto_adjust=True)
            if len(h):
                cols[k] = h['Close']
                if k == 'SPX': cols['SPX_VOL'] = h['Volume']; cols['SPX_LOW'] = h['Low']; cols['SPX_HIGH'] = h['High']
                if k in ('QQQ', 'RSP', 'NVDA', 'MGK'): cols[f'{k}_VOL'] = h['Volume']; cols[f'{k}_LOW'] = h['Low']; cols[f'{k}_HIGH'] = h['High']
                if k in RAW: cols[f'{k}_RAW'] = yf.Ticker(t).history(period='max', auto_adjust=False)['Close']   # 비율 그림은 배당 안 고친 값(StockCharts와 같게)
                break
        except Exception as e:
            print(k, e); time.sleep(3)
    print(k, len(cols.get(k, [])))
for k in cols:
    cols[k].index = pd.to_datetime(cols[k].index).tz_localize(None).normalize()
key = os.environ.get('FRED_KEY')
for s in ('DAAA', 'BAMLC0A1CAAA', 'DGS10', 'BAMLH0A0HYM2', 'STLFSI4', 'T10Y2Y', 'DTB3', 'DGS2', 'DGS5', 'SOFR', 'IORB', 'IOER'):   # 11/22 의장 B01 경보 때 채권·현금 대체 수익
    try:
        r = requests.get('https://api.stlouisfed.org/fred/series/observations', params=dict(series_id=s, api_key=key, file_type='json'), timeout=60).json()
        x = pd.Series({pd.Timestamp(o['date']): pd.to_numeric(o['value'], errors='coerce') for o in r['observations']})
        cols[s] = x; print(s, len(x))
    except Exception as e:
        print(s, e)
D = pd.DataFrame(cols).sort_index()
D.index.name = '날짜'
D.to_csv('history/시장위험_장기.csv', encoding='utf-8-sig')
print(D.shape, D.index.min(), D.index.max())
# 11/24 의장 '시장 블록 과거 값 채워': B05 공포탐욕 일별 이력(2011~, fear_greed.HIST_URL), B10 지정학 위험 일별 이력(1985~, b09_gpr과 같은 출처)
try:
    H = pd.read_csv('https://raw.githubusercontent.com/whit3rabbit/fear-greed-data/main/fear-greed.csv', parse_dates=['Date'])
    H.set_index('Date')[['Fear Greed']].rename_axis('날짜').to_csv('history/공포탐욕_이력.csv', encoding='utf-8-sig'); print('공포탐욕', len(H))
except Exception as e:
    print('공포탐욕', e)
try:
    import io
    for u in ('https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls',):
        g = pd.read_excel(io.BytesIO(requests.get(u, timeout=120, headers={'User-Agent': 'Mozilla/5.0'}).content))
        g.columns = [str(c).strip() for c in g.columns]
        dcol = next(c for c in g.columns if c.lower() in ('date', 'day'))
        g['날짜'] = pd.to_datetime(g[dcol].astype(str).str[:10], errors='coerce', format='mixed')
        g = g.dropna(subset=['날짜']).sort_values('날짜')
        g[['날짜', 'GPRD']].set_index('날짜').to_csv('history/지정학위험_이력.csv', encoding='utf-8-sig'); print('지정학위험', len(g), g['날짜'].min())
except Exception as e:
    print('지정학위험', e)
