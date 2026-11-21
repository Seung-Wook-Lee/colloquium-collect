# 분기 원자료(야후): 번호·분기·매출·영업이익·순이익 — 계산은 features.py에서(DART 잠정으로 최신 분기 보충)
import pandas as pd, yfinance as yf, warnings
from concurrent.futures import ThreadPoolExecutor
warnings.filterwarnings('ignore')
N=pd.read_csv('in/닉스.csv',encoding='utf-8-sig')
t=N[(N['구분']=='개별주')&(N['시장'].isin(['한국','미국']))][['번호','yfinance 티커']]
KR=N[(N['구분']=='개별주')&(N['시장']=='한국')].set_index('번호')['코드'].astype(str).str.split('.').str[0].str.zfill(6).to_dict()
def one(a):
    no,tk=a; out=[]
    q=None
    for _ in range(2):   # 11/21: 한 번 실패(기아)하면 한 번 더
        try:
            q=yf.Ticker(tk).quarterly_income_stmt
            if q is not None and len(q.columns): break
        except Exception: q=None
    try:
        for c in q.columns:
            g=lambda k: q.loc[k,c] if k in q.index else None
            out.append(dict(번호=no,분기=str(c.date()),매출=g('Total Revenue'),영업이익=g('Operating Income'),순이익=g('Net Income'),출처='야후'))
    except Exception: pass
    return out
with ThreadPoolExecutor(10) as ex: R=sum(ex.map(one,t.itertuples(index=False)),[])
# 11/21 의장: 야후가 빈칸으로 준 한국 종목은 한투 분기 손익으로(해외 재무는 한투에 없음)
try:
    import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import kis
    have={x['번호'] for x in R if x.get('매출') is not None and x['매출']==x['매출']}
    miss=[n for n in KR if n not in have]
    if kis.ready() and miss:
        R=[x for x in R if x['번호'] not in miss]; ok=0
        for n in miss:
            q=kis.quarterly_kr(KR[n]); ok+=bool(q)
            R+=[dict(번호=n,분기=a,매출=b,영업이익=c,순이익=e,출처='한투') for a,b,c,e in q]
        print('한투로 채움', ok, '/', len(miss), miss)
except Exception as e: print('한투 분기 보충 실패', e)
d=pd.DataFrame(R); d.to_csv('in/분기원자료.csv',index=False,encoding='utf-8-sig'); print(len(d), d['번호'].nunique())
