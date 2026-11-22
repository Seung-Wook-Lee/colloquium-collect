"""나스닥100 맥클렐런 오실레이터 재료(11/22 의장 그림 '−70 하향 돌파'): 나스닥100 지금 구성 종목(위키백과 표)의 일별 종가 → 날마다 오른 종목 수·내린 종목 수.
주의: 지금 구성 종목만 씀(과거에 빠진 종목 없음 = 생존 편향). 결과 collect/research/out/NDX_AD.csv (날짜, 상승, 하락, 종목수)"""
import os, io, pandas as pd, requests, yfinance as yf
os.makedirs('collect/research/out', exist_ok=True)
html = requests.get('https://en.wikipedia.org/wiki/Nasdaq-100', headers={'User-Agent': 'Mozilla/5.0'}, timeout=60).text
tk = None
for t in pd.read_html(io.StringIO(html)):
    for c in t.columns:
        if str(c).lower() in ('ticker', 'symbol'):
            tk = [str(x).replace('.', '-') for x in t[c].dropna()]; break
    if tk and len(tk) > 90: break
print('구성 종목', len(tk), tk[:10])
px = yf.download(tk, period='max', auto_adjust=True, progress=False, threads=True)['Close']
px.index = pd.to_datetime(px.index).tz_localize(None).normalize()
ch = px.diff()
A = (ch > 0).sum(axis=1); Dn = (ch < 0).sum(axis=1); N = px.notna().sum(axis=1)
out = pd.DataFrame({'상승': A, '하락': Dn, '종목수': N}); out = out[out['종목수'] >= 20]; out.index.name = '날짜'
out.to_csv('collect/research/out/NDX_AD.csv', encoding='utf-8-sig'); print(out.shape, out.index.min(), out.index.max()); print(out.tail())
