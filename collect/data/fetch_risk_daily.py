"""B35 항복·B03 AAA 괴리용 매일 자료(야후 2년 + FRED DAAA) → in/시장위험.csv (11/22 의장 승인)"""
import os
import pandas as pd, requests, yfinance as yf
YF = {'SPX': '^GSPC', 'GOLD': 'GC=F', 'SILVER': 'SI=F', 'BTC': 'BTC-USD', 'TLT': 'TLT', 'VIX': '^VIX', 'VIX3M': '^VIX3M', 'NDX': '^NDX', 'QQQ': 'QQQ', 'RSP': 'RSP',
      'SPYG': 'SPYG', 'BIL': 'BIL', 'IWF': 'IWF', 'IWD': 'IWD', 'NVDA': 'NVDA'}   # 11/22 의장 변곡점 판(SPYG:BIL·IWF:IWD 일목, NVDA 앵커드 VWAP)   # 11/22 의장 B02 앵커드 VWAP(QQQ:RSP)
cols = {}
for k, t in YF.items():
    try:
        h = yf.Ticker(t).history(period='max' if k in ('NDX', 'QQQ', 'RSP', 'SPX', 'SPYG', 'BIL', 'IWF', 'IWD', 'NVDA', 'VIX') else '2y', auto_adjust=True)   # 코폭은 월봉 10년 필요
        h.index = pd.to_datetime(h.index).tz_localize(None).normalize()
        cols[k] = h['Close']
        if k in ('SPX', 'QQQ', 'RSP', 'NVDA'): cols[f'{k}_VOL'] = h['Volume']
        if k in ('SPX', 'QQQ', 'NVDA'): cols[f'{k}_HIGH'] = h['High']; cols[f'{k}_LOW'] = h['Low']   # 11/22 CTM(고가·저가 볼린저 위치)
    except Exception as e:
        print(k, e)
try:
    r = requests.get('https://api.stlouisfed.org/fred/series/observations', params=dict(series_id='DAAA', api_key=os.environ.get('FRED_KEY'),
                     file_type='json', observation_start=str(pd.Timestamp.today().date() - pd.Timedelta(days=730))), timeout=60).json()
    cols['DAAA'] = pd.Series({pd.Timestamp(o['date']): pd.to_numeric(o['value'], errors='coerce') for o in r['observations']})
except Exception as e:
    print('DAAA', e)
try:   # 11/22 변곡점 판: SPYG:BIL 2007 전 현금 지수(DTB3)
    r = requests.get('https://api.stlouisfed.org/fred/series/observations', params=dict(series_id='DTB3', api_key=os.environ.get('FRED_KEY'), file_type='json'), timeout=60).json()
    cols['DTB3'] = pd.Series({pd.Timestamp(o['date']): pd.to_numeric(o['value'], errors='coerce') for o in r['observations']})
except Exception as e:
    print('DTB3', e)
D = pd.DataFrame(cols).sort_index(); D.index.name = '날짜'
if 'SPX' not in D or D['SPX'].dropna().empty:
    raise SystemExit('S&P500 없음')
D.to_csv('in/시장위험.csv', encoding='utf-8-sig')
print(D.shape)
