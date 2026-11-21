# 연매출(TTM, 원화) — 야후 totalRevenue, 달러는 오늘 환율로 원화 환산
import pandas as pd, yfinance as yf
from concurrent.futures import ThreadPoolExecutor
N=pd.read_csv('in/닉스.csv',encoding='utf-8-sig')
t=N[(N['구분']=='개별주')&(N['시장'].isin(['한국','미국']))][['번호','yfinance 티커']]
fx=float(yf.Ticker('KRW=X').history(period='5d')['Close'].iloc[-1])
FX={'USD':fx,'KRW':1.0}
def krw(c):   # 11/21: 대만달러(TSMC)·유로(ASML) 등 달러 아닌 통화도 원화로(전에는 그대로 써서 TSMC 4.9조·ASML 39억원으로 잘못 나옴)
    if c not in FX:
        try: FX[c]=float(yf.Ticker(f'{c}KRW=X').history(period='5d')['Close'].iloc[-1])
        except Exception: FX[c]=None
    return FX[c]
def one(a):
    no,tk=a
    try:
        T_=yf.Ticker(tk); i=T_.info; v=i.get('totalRevenue'); c=i.get('financialCurrency') or i.get('currency')
        if not v:   # 11/21: info에 매출이 없으면(기업은행) 최근 4분기 매출 합
            try:
                q=T_.quarterly_income_stmt.loc['Total Revenue'].dropna().head(4)
                v=float(q.sum()) if len(q)==4 else None
            except Exception: v=None
        r_=krw(c or 'USD'); return no, (v*r_ if v and r_ else None), c
    except Exception: return no,None,None
with ThreadPoolExecutor(12) as ex: r=list(ex.map(one,t.itertuples(index=False)))
d=pd.DataFrame(r,columns=['번호','연매출(원)','통화']); d['환율']=fx
d.to_csv('in/연매출.csv',index=False,encoding='utf-8-sig'); print(fx, d['연매출(원)'].notna().sum(), len(d))
