"""블록 성적표(backtest.py)용 긴 가격: 10년 종가·고가·저가·거래량 + 지수(야후 무료). 일주일에 한 번이면 충분.
쓰는 법: python fetch_long.py <입력폴더>  →  <입력폴더>/장기/가격2년.csv 등(이름은 엔진과 같게, 기간만 10년)"""
import os, sys
import pandas as pd, yfinance as yf

d = sys.argv[1] if len(sys.argv) > 1 else 'in'
o = f'{d}/장기'; os.makedirs(o, exist_ok=True)
N = pd.read_csv(f'{d}/닉스.csv', encoding='utf-8-sig')
t = [x for x in N['yfinance 티커'].dropna().astype(str).unique()]
D = yf.download(t, period='10y', auto_adjust=True, progress=False, threads=True)
for k, f in (('Close', '가격2년'), ('Open', '시가2년'), ('High', '고가2년'), ('Low', '저가2년'), ('Volume', '거래량2년')):
    D[k].to_csv(f'{o}/{f}.csv', encoding='utf-8-sig')
I = yf.download(['^GSPC', '^KS11', '^KQ11'], period='10y', auto_adjust=True, progress=False)['Close']
I.to_csv(f'{o}/지수2년.csv', encoding='utf-8-sig')
print(D['Close'].shape, D.index[0], D.index[-1])
