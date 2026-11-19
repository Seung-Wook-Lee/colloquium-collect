import pandas as pd, yfinance as yf
N=pd.read_csv('in/닉스.csv',encoding='utf-8-sig')
t=[x for x in N['yfinance 티커'].dropna().astype(str).unique()]
D=yf.download(t, period='2y', auto_adjust=True, progress=False, threads=True)
px=D['Close']
px.to_csv('in/가격2년.csv', encoding='utf-8-sig')
# 11/19 의장 B20 매집·분산(CMF·MFI): 고가·저가·거래량도 함께(야후 무료)
for k, f in (('High', '고가2년'), ('Low', '저가2년'), ('Volume', '거래량2년')):
    D[k].to_csv(f'in/{f}.csv', encoding='utf-8-sig')
print(px.shape, px.index[-1])
