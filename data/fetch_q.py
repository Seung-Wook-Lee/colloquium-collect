# 분기 원자료(야후): 번호·분기·매출·영업이익·순이익 — 계산은 features.py에서(DART 잠정으로 최신 분기 보충)
import pandas as pd, yfinance as yf, warnings
from concurrent.futures import ThreadPoolExecutor
warnings.filterwarnings('ignore')
N=pd.read_csv('in/닉스.csv',encoding='utf-8-sig')
t=N[(N['구분']=='개별주')&(N['시장'].isin(['한국','미국']))][['번호','yfinance 티커']]
def one(a):
    no,tk=a; out=[]
    try:
        q=yf.Ticker(tk).quarterly_income_stmt
        for c in q.columns:
            g=lambda k: q.loc[k,c] if k in q.index else None
            out.append(dict(번호=no,분기=str(c.date()),매출=g('Total Revenue'),영업이익=g('Operating Income'),순이익=g('Net Income'),출처='야후'))
    except Exception: pass
    return out
with ThreadPoolExecutor(10) as ex: R=sum(ex.map(one,t.itertuples(index=False)),[])
d=pd.DataFrame(R); d.to_csv('in/분기원자료.csv',index=False,encoding='utf-8-sig'); print(len(d), d['번호'].nunique())
