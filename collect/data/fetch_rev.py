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
d=pd.DataFrame(r,columns=['번호','연매출(원)','통화'])
# 11/21 의장: 야후가 막아 빈 한국 종목은 한투 최근 4분기 매출 합(원)
try:
    import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import kis
    KR=N[(N['구분']=='개별주')&(N['시장']=='한국')].set_index('번호')['코드'].astype(str).str.split('.').str[0].str.zfill(6).to_dict()
    # 11/21 23:47 의장: 한국은 한투가 먼저(최근 4분기 매출 합), 한투가 비면 야후 값
    if kis.ready():
        ok=0
        for n in KR:
            v=[b for _,b,_,_ in kis.quarterly_kr(KR[n])][-4:]
            if len(v)==4 and all(x is not None for x in v): d.loc[d['번호']==n,['연매출(원)','통화']]=[float(sum(v)),'KRW']; ok+=1
        print('한국 한투 연매출', ok, '/', len(KR))
except Exception as e: print('한투 매출 보충 실패', e)
d["환율"]=fx
d.to_csv('in/연매출.csv',index=False,encoding='utf-8-sig'); print(fx, d['연매출(원)'].notna().sum(), len(d))
