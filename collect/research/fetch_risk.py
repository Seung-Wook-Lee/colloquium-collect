"""시장 위험 지표 장기 자료(11/22 의장: B35 항복 블록, 골드만 패닉 근사, S&P–AAA 회사채 괴리).
야후(키 없음): ^GSPC(OHLCV), ^NDX, GC=F 금, SI=F 은, BTC-USD, TLT, LQD, QLTA, ^VIX, ^VIX3M, ^SKEW, ^VVIX — 상장 이후 전체 일봉
FRED(FRED_KEY): DAAA(무디스 AAA 회사채 수익률), BAMLC0A1CAAA(ICE AAA 회사채 OAS), DGS10(10년물)
결과: history/시장위험_장기.csv (날짜 × 칸)"""
import os, time
import pandas as pd, requests, yfinance as yf
os.makedirs('history', exist_ok=True)
YF = {'SPX': '^GSPC', 'NDX': '^NDX', 'GOLD': 'GC=F', 'SILVER': 'SI=F', 'BTC': 'BTC-USD', 'TLT': 'TLT', 'LQD': 'LQD', 'QLTA': 'QLTA',
      'VIX': '^VIX', 'VIX3M': '^VIX3M', 'SKEW': '^SKEW', 'VVIX': '^VVIX', 'MOVE': '^MOVE', 'QQQ': 'QQQ', 'RSP': 'RSP'}   # 11/22 의장 QQQ:RSP 앵커드 VWAP(거래량 포함)
cols = {}
for k, t in YF.items():
    for _ in range(3):
        try:
            h = yf.Ticker(t).history(period='max', auto_adjust=True)
            if len(h):
                cols[k] = h['Close']
                if k == 'SPX': cols['SPX_VOL'] = h['Volume']; cols['SPX_LOW'] = h['Low']; cols['SPX_HIGH'] = h['High']
                if k in ('QQQ', 'RSP'): cols[f'{k}_VOL'] = h['Volume']; cols[f'{k}_LOW'] = h['Low']; cols[f'{k}_HIGH'] = h['High']
                break
        except Exception as e:
            print(k, e); time.sleep(3)
    print(k, len(cols.get(k, [])))
for k in cols:
    cols[k].index = pd.to_datetime(cols[k].index).tz_localize(None).normalize()
key = os.environ.get('FRED_KEY')
for s in ('DAAA', 'BAMLC0A1CAAA', 'DGS10', 'BAMLH0A0HYM2', 'STLFSI4', 'T10Y2Y'):
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
