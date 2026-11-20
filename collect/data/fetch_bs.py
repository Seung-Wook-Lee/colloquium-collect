# 200종목 재무 건전성(야후 info): 총부채·EBITDA·FCF·시총, 연매출(원화)
import pandas as pd, yfinance as yf
from concurrent.futures import ThreadPoolExecutor
N=pd.read_csv('in/닉스.csv',encoding='utf-8-sig')
t=N[(N['구분']=='개별주')&(N['시장'].isin(['한국','미국']))][['번호','yfinance 티커']]
def one(a):
    no,tk=a
    try:
        i=yf.Ticker(tk).info
        return dict(번호=no,총부채=i.get('totalDebt'),EBITDA=i.get('ebitda'),FCF=i.get('freeCashflow'),시총=i.get('marketCap'),부채비율=i.get('debtToEquity'))
    except Exception: return dict(번호=no)
with ThreadPoolExecutor(12) as ex: r=list(ex.map(one,t.itertuples(index=False)))
d=pd.DataFrame(r); d.to_csv('in/재무건전성.csv',index=False,encoding='utf-8-sig'); print(d.notna().sum().to_dict())
