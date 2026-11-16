# 연매출(TTM, 원화) — 야후 totalRevenue, 달러는 오늘 환율로 원화 환산
import pandas as pd, yfinance as yf
from concurrent.futures import ThreadPoolExecutor
N=pd.read_csv('in/닉스.csv',encoding='utf-8-sig')
t=N[(N['구분']=='개별주')&(N['시장'].isin(['한국','미국']))][['번호','yfinance 티커']]
fx=float(yf.Ticker('KRW=X').history(period='5d')['Close'].iloc[-1])
def one(a):
    no,tk=a
    try:
        i=yf.Ticker(tk).info; v=i.get('totalRevenue'); c=i.get('financialCurrency') or i.get('currency')
        return no, (v*(fx if c=='USD' else 1) if v else None), c
    except Exception: return no,None,None
with ThreadPoolExecutor(12) as ex: r=list(ex.map(one,t.itertuples(index=False)))
d=pd.DataFrame(r,columns=['번호','연매출(원)','통화']); d['환율']=fx
d.to_csv('in/연매출.csv',index=False,encoding='utf-8-sig'); print(fx, d['연매출(원)'].notna().sum(), len(d))
