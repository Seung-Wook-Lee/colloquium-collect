"""나스닥100 맥클렐런 오실레이터 재료(11/22 의장 그림 '−70 하향 돌파'): 나스닥100 지금 구성 종목(위키백과 표)의 일별 종가 → 날마다 오른 종목 수·내린 종목 수.
주의: 지금 구성 종목만 씀(과거에 빠진 종목 없음 = 생존 편향). 결과 collect/research/out/NDX_AD.csv (날짜, 상승, 하락, 종목수)"""
import os, io, pandas as pd, requests, yfinance as yf
os.makedirs('collect/research/out', exist_ok=True)
tk = None
try:
    html = requests.get('https://en.wikipedia.org/wiki/Nasdaq-100', headers={'User-Agent': 'Mozilla/5.0 (research script)'}, timeout=60).text
    for t in pd.read_html(io.StringIO(html)):
        cs = [c for c in t.columns if any(k in str(c).lower() for k in ('ticker', 'symbol'))]
        print('표', t.shape, list(t.columns)[:4])
        if cs and len(t) > 90: tk = [str(x).replace('.', '-') for x in t[cs[0]].dropna()]; break
except Exception as e:
    print('위키 실패', e)
if not tk:
    try:
        j = requests.get('https://api.nasdaq.com/api/quote/list-type/nasdaq100', headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}, timeout=60).json()
        tk = [r['symbol'] for r in j['data']['data']['rows']]
    except Exception as e:
        print('나스닥 실패', e)
if not tk:   # 마지막 수단: 2026년 기준 구성 종목(손으로 적은 목록)
    tk = """AAPL MSFT NVDA AMZN GOOGL GOOG META AVGO TSLA COST NFLX PLTR AMD ASML CSCO TMUS AZN LIN INTU ISRG PEP TXN QCOM BKNG ADBE AMGN AMAT
    ARM PDD HON GILD MU LRCX PANW ADP ADI KLAC CMCSA APP VRTX MELI CRWD SBUX INTC CEG DASH MSTR ORLY CTAS MAR MDLZ CDNS SNPS FTNT ABNB
    PYPL REGN MRVL ASML WDAY ADSK CSX AXON ROP CHTR NXPI MNST PCAR AEP PAYX FAST CPRT KDP ROST LULU DDOG EXC IDXX TTWO BKR XEL EA
    VRSK CCEP ODFL CTSH FANG KHC ZS GEHC TEAM CSGP ANSS DXCM BIIB ON TTD CDW GFS WBD MCHP LIN SHOP""".split()
    tk = list(dict.fromkeys(tk))
print('구성 종목', len(tk), tk[:10])
px = yf.download(tk, period='max', auto_adjust=True, progress=False, threads=True)['Close']
px.index = pd.to_datetime(px.index).tz_localize(None).normalize()
ch = px.diff()
A = (ch > 0).sum(axis=1); Dn = (ch < 0).sum(axis=1); N = px.notna().sum(axis=1)
out = pd.DataFrame({'상승': A, '하락': Dn, '종목수': N}); out = out[out['종목수'] >= 20]; out.index.name = '날짜'
out.to_csv('collect/research/out/NDX_AD.csv', encoding='utf-8-sig'); print(out.shape, out.index.min(), out.index.max()); print(out.tail())
