"""B35 항복·B03 AAA 괴리용 매일 자료(야후 2년 + FRED DAAA) → in/시장위험.csv (11/22 의장 승인)"""
import os
import pandas as pd, requests, yfinance as yf
YF = {'SPX': '^GSPC', 'GOLD': 'GC=F', 'SILVER': 'SI=F', 'BTC': 'BTC-USD', 'TLT': 'TLT', 'VIX': '^VIX', 'VIX3M': '^VIX3M', 'NDX': '^NDX', 'QQQ': 'QQQ', 'RSP': 'RSP',
      'SPYG': 'SPYG', 'BIL': 'BIL', 'IWF': 'IWF', 'IWD': 'IWD', 'NVDA': 'NVDA', 'MGK': 'MGK', 'COMPQ': '^IXIC', 'QLTA': 'QLTA',
      'RUT': '^RUT', 'MOVE': '^MOVE', 'TNX': '^TNX', 'KS11': '^KS11', 'KQ11': '^KQ11', 'DJI': '^DJI', 'SOX': '^SOX',
      'VWO': 'VWO', 'BND': 'BND'}   # 11/26 2-15 카나리아도 저장본에서(회의 때 받던 것 없앰)   # 11/25 의장: 블록이 지수를 저장본에서만 읽도록(app/market/stored.py)   # 11/22 의장 변곡점 판(SPYG:BIL·IWF:IWD 일목, NVDA 앵커드 VWAP)   # 11/22 의장 B02 앵커드 VWAP(QQQ:RSP)
# 11/25 의장 "드라이브에 다 저장해 놓으라고 했잖아. 오늘 가격만 받으면 되지": 저장본(in/시장위험.csv, 드라이브 전날 사본)이 있으면
#   그 마지막 날 5일 전부터만 받아 덧붙인다(전체 기간은 저장본에 이미 있음). 저장본에 없는 칸만 원래대로 전체를 받는다.
try:
    OLD = pd.read_csv('in/시장위험.csv', index_col=0, parse_dates=True, encoding='utf-8-sig')
except Exception:
    OLD = None
def _s0(c):   # 이 칸을 어디서부터 받을지(None = 전체)
    if OLD is None or c not in OLD or OLD[c].dropna().empty: return None
    return (OLD[c].dropna().index.max() - pd.Timedelta(days=5)).date()
print('저장본', '없음 → 전체' if OLD is None else f'{OLD.index.max():%Y-%m-%d}까지, 그 뒤만 받음')
cols = {}
for k, t in YF.items():
    try:
        s0 = _s0(k)
        h = yf.Ticker(t).history(start=str(s0), auto_adjust=True) if s0 else yf.Ticker(t).history(period='max' if k in ('NDX', 'QQQ', 'RSP', 'SPX', 'SPYG', 'BIL', 'IWF', 'IWD', 'NVDA', 'VIX', 'MGK', 'COMPQ', 'QLTA', 'VIX3M', 'RUT', 'MOVE', 'TNX', 'KS11', 'KQ11', 'DJI', 'SOX') else '2y', auto_adjust=True)   # 코폭은 월봉 10년 필요
        h.index = pd.to_datetime(h.index).tz_localize(None).normalize()
        cols[k] = h['Close']
        if k in ('QQQ', 'RSP', 'SPYG', 'BIL', 'IWF', 'IWD'):   # 11/22 변곡점 판: 비율 그림은 배당 안 고친 값(StockCharts와 같게)
            s1 = _s0(f'{k}_RAW'); r0 = yf.Ticker(t).history(start=str(s1), auto_adjust=False) if s1 else yf.Ticker(t).history(period='max', auto_adjust=False); r0.index = pd.to_datetime(r0.index).tz_localize(None).normalize(); cols[f'{k}_RAW'] = r0['Close']
        if k in ('SPX', 'QQQ', 'RSP', 'NVDA'): cols[f'{k}_VOL'] = h['Volume']
        if k in ('SPX', 'QQQ', 'NVDA', 'MGK'): cols[f'{k}_HIGH'] = h['High']; cols[f'{k}_LOW'] = h['Low']   # 11/22 CTM(고가·저가 볼린저 위치)
    except Exception as e:
        print(k, e)
try:
    r = requests.get('https://api.stlouisfed.org/fred/series/observations', params=dict(series_id='DAAA', api_key=os.environ.get('FRED_KEY'),
                     file_type='json', observation_start=str(_s0('DAAA') or (pd.Timestamp.today().date() - pd.Timedelta(days=730)))), timeout=60).json()
    cols['DAAA'] = pd.Series({pd.Timestamp(o['date']): pd.to_numeric(o['value'], errors='coerce') for o in r['observations']})
except Exception as e:
    print('DAAA', e)
try:   # 11/22 변곡점 판: SPYG:BIL 2007 전 현금 지수(DTB3)
    r = requests.get('https://api.stlouisfed.org/fred/series/observations', params=dict(series_id='DTB3', api_key=os.environ.get('FRED_KEY'), file_type='json', **({'observation_start': str(_s0('DTB3'))} if _s0('DTB3') else {})), timeout=60).json()
    cols['DTB3'] = pd.Series({pd.Timestamp(o['date']): pd.to_numeric(o['value'], errors='coerce') for o in r['observations']})
except Exception as e:
    print('DTB3', e)
try:   # 11/22 의장 B02: CBOE 주식 풋/콜(CPCE) 최근 70일(10일 EMA·20일 켜짐에 충분) — cpce.py 검증 IC 0.178→0.209
    cp = {}
    for d in pd.bdate_range(pd.Timestamp(_s0('CPCE') or (pd.Timestamp.today().normalize() - pd.Timedelta(days=70))), pd.Timestamp.today().normalize()):
        try:
            r = requests.get(f"https://cdn.cboe.com/data/us/options/market_statistics/daily/{d.strftime('%Y-%m-%d')}_daily_options", headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
            if r.status_code == 200:
                cp.update({d: float(x['value']) for x in r.json().get('ratios', []) if 'EQUITY' in str(x.get('name', '')).upper()})
        except Exception:
            pass
    cols['CPCE'] = pd.Series(cp, dtype=float); print('CPCE', len(cp))
except Exception as e:
    print('CPCE', e)
D = pd.DataFrame(cols).sort_index()
if OLD is not None:   # 새로 받은 값이 우선, 나머지는 저장본
    D = D.combine_first(OLD).sort_index()
D.index.name = '날짜'
if 'SPX' not in D or D['SPX'].dropna().empty:
    raise SystemExit('S&P500 없음')
D.to_csv('in/시장위험.csv', encoding='utf-8-sig')
print(D.shape)
