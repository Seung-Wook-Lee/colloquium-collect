import pandas as pd, yfinance as yf
N=pd.read_csv('in/닉스.csv',encoding='utf-8-sig')
t=[x for x in N['yfinance 티커'].dropna().astype(str).unique()]
px=yf.download(t, period='2y', auto_adjust=True, progress=False, threads=True)['Close']
px.to_csv('in/가격2년.csv', encoding='utf-8-sig')
print(px.shape, px.index[-1])
