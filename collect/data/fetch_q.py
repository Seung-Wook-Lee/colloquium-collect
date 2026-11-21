# 분기 원자료(야후): 번호·분기·매출·영업이익·순이익 — 계산은 features.py에서(DART 잠정으로 최신 분기 보충)
import pandas as pd, yfinance as yf, warnings
from concurrent.futures import ThreadPoolExecutor
warnings.filterwarnings('ignore')
N=pd.read_csv('in/닉스.csv',encoding='utf-8-sig')
t=N[(N['구분']=='개별주')&(N['시장'].isin(['한국','미국']))][['번호','yfinance 티커']]
KR=N[(N['구분']=='개별주')&(N['시장']=='한국')].set_index('번호')['코드' if '코드' in N else 'yfinance 티커'].astype(str).str.split('.').str[0].str.zfill(6).to_dict()   # 닉스.csv엔 코드 칸이 없어 야후 티커 앞부분
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
    # 11/21 23:47 의장 "그냥 한국거는 한투받아": 한국은 한투가 먼저, 한투가 비면 야후 값을 그대로 둔다
    print('한투 키', '있음' if kis.ready() else '없음')
    if kis.ready():
        ok=[]
        for n in KR:
            q=kis.quarterly_kr(KR[n])
            if q:
                R=[x for x in R if x['번호']!=n]+[dict(번호=n,분기=a,매출=b,영업이익=c,순이익=e,출처='한투') for a,b,c,e in q]; ok.append(n)
        print('한국 한투', len(ok), '/', len(KR), '| 야후로 남음', [n for n in KR if n not in ok])
except Exception as e: print('한투 분기 보충 실패', e)
d=pd.DataFrame(R); d.to_csv('in/분기원자료.csv',index=False,encoding='utf-8-sig'); print(len(d), d['번호'].nunique())
