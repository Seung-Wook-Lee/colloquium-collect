"""B35 항복·B03 AAA 괴리용 매일 자료(야후 2년 + FRED DAAA) → in/시장위험.csv (11/22 의장 승인)"""
import os
import pandas as pd, requests, yfinance as yf
YF = {'SPX': '^GSPC', 'GOLD': 'GC=F', 'SILVER': 'SI=F', 'BTC': 'BTC-USD', 'TLT': 'TLT', 'VIX': '^VIX', 'VIX3M': '^VIX3M'}
cols = {}
for k, t in YF.items():
    try:
        h = yf.Ticker(t).history(period='2y', auto_adjust=True)
        h.index = pd.to_datetime(h.index).tz_localize(None).normalize()
        cols[k] = h['Close']
        if k == 'SPX': cols['SPX_VOL'] = h['Volume']
    except Exception as e:
        print(k, e)
try:
    r = requests.get('https://api.stlouisfed.org/fred/series/observations', params=dict(series_id='DAAA', api_key=os.environ.get('FRED_KEY'),
                     file_type='json', observation_start=str(pd.Timestamp.today().date() - pd.Timedelta(days=730))), timeout=60).json()
    cols['DAAA'] = pd.Series({pd.Timestamp(o['date']): pd.to_numeric(o['value'], errors='coerce') for o in r['observations']})
except Exception as e:
    print('DAAA', e)
D = pd.DataFrame(cols).sort_index(); D.index.name = '날짜'
if 'SPX' not in D or D['SPX'].dropna().empty:
    raise SystemExit('S&P500 없음')
D.to_csv('in/시장위험.csv', encoding='utf-8-sig')
print(D.shape)
