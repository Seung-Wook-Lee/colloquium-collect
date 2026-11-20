# Piotroski F-Score(9) + Altman Z — 야후 연간 재무제표, 최근 2년
import pandas as pd, numpy as np, yfinance as yf, warnings
from concurrent.futures import ThreadPoolExecutor
warnings.filterwarnings('ignore')
N=pd.read_csv('in/닉스.csv',encoding='utf-8-sig')
t=N[(N['구분']=='개별주')&(N['시장'].isin(['한국','미국']))][['번호','yfinance 티커']]
def g(df,keys,col):
    for k in keys:
        if k in df.index and col < df.shape[1]:
            v=df.loc[k].iloc[col]
            if pd.notna(v): return float(v)
    return np.nan
def one(a):
    no,tk=a; r={'번호':no}
    try:
        T=yf.Ticker(tk); I=T.income_stmt; B=T.balance_sheet; C=T.cashflow; info=T.info
        ni=[g(I,['Net Income'],i) for i in (0,1)]; ta=[g(B,['Total Assets'],i) for i in (0,1,2)]
        cfo=g(C,['Operating Cash Flow'],0)
        ltd=[g(B,['Long Term Debt'],i) for i in (0,1)]
        ca=[g(B,['Current Assets'],i) for i in (0,1)]; cl=[g(B,['Current Liabilities'],i) for i in (0,1)]
        sh=[g(B,['Ordinary Shares Number','Share Issued'],i) for i in (0,1)]
        gp=[g(I,['Gross Profit'],i) for i in (0,1)]; rev=[g(I,['Total Revenue'],i) for i in (0,1)]
        roa=[ni[i]/ta[i+1] if ta[i+1] else np.nan for i in (0,1)]
        tests=[ni[0]>0 if pd.notna(ni[0]) else None, cfo>0 if pd.notna(cfo) else None,
               roa[0]>roa[1] if pd.notna(roa[0]) and pd.notna(roa[1]) else None,
               cfo>ni[0] if pd.notna(cfo) and pd.notna(ni[0]) else None,
               (ltd[0]/ta[0])<=(ltd[1]/ta[1]) if all(pd.notna([ltd[0],ltd[1],ta[0],ta[1]])) else None,
               (ca[0]/cl[0])>(ca[1]/cl[1]) if all(pd.notna([ca[0],cl[0],ca[1],cl[1]])) else None,
               sh[0]<=sh[1]*1.001 if all(pd.notna(sh)) else None,
               (gp[0]/rev[0])>(gp[1]/rev[1]) if all(pd.notna([gp[0],rev[0],gp[1],rev[1]])) else None,
               (rev[0]/ta[1])>(rev[1]/ta[2]) if all(pd.notna([rev[0],rev[1],ta[1],ta[2]])) else None]
        ok=[x for x in tests if x is not None]
        r['F점수']=round(sum(ok)*9/len(ok),1) if len(ok)>=6 else np.nan   # 빈 항목은 비율로 9점 환산
        tl=g(B,['Total Liabilities Net Minority Interest'],0); re_=g(B,['Retained Earnings'],0)
        ebit=g(I,['EBIT','Operating Income'],0); mv=info.get('marketCap')
        if all(pd.notna([ta[0],tl,ebit,rev[0]])) and mv and ta[0]:
            wc=(ca[0]-cl[0]) if pd.notna(ca[0]) and pd.notna(cl[0]) else 0
            r['Z점수']=round(1.2*wc/ta[0]+1.4*(re_ if pd.notna(re_) else 0)/ta[0]+3.3*ebit/ta[0]+0.6*mv/tl+rev[0]/ta[0],2)
    except Exception as e: r['오류']=str(e)[:30]
    return r
with ThreadPoolExecutor(10) as ex: R=list(ex.map(one,t.itertuples(index=False)))
d=pd.DataFrame(R); d.to_csv('in/FZ점수.csv',index=False,encoding='utf-8-sig'); print(d[['F점수','Z점수']].notna().sum().to_dict(), len(d))
