import yfinance as yf, pandas as pd, sys, warnings
warnings.filterwarnings('ignore')
n=pd.read_csv('in/닉스.csv',encoding='utf-8-sig')
t=n[(n['구분']=='개별주')&(n['시장'].isin(['한국','미국']))][['번호','yfinance 티커']]
if len(sys.argv)>1: t=t[t['번호'].isin(sys.argv[1].split(','))]
rows=[]
for no,tk in t.itertuples(index=False):
    r={'번호':no}
    try:
        q=yf.Ticker(tk).quarterly_income_stmt
        rev=q.loc['Total Revenue'] if 'Total Revenue' in q.index else None
        if 'Operating Income' in q.index and rev is not None:
            d=pd.DataFrame({'rev':rev,'x':q.loc['Operating Income']}).dropna().sort_index(); d['m']=d.x/d.rev*100; r['실적지표']='영업이익'
        else:
            # 금융: 영업이익 칸 없음 → 순이익÷영업수익(Total Revenue)을 이익률로
            d=pd.DataFrame({'rev':rev,'x':q.loc['Net Income']}).dropna().sort_index() if rev is not None else pd.DataFrame({'x':q.loc['Net Income'],'rev':None}).dropna(subset=['x']).sort_index()
            d['m']=d.x/d.rev*100 if rev is not None else None; r['실적지표']='순이익'
        r['최근분기']=str(d.index[-1].date()); x=d.x.tolist()
        if len(x)>=5:
            r['이익_전년비']=(x[-1]/x[-5]-1)*100 if x[-5]>0 else (999 if x[-1]>0 else -999)
        if d['m'].notna().any():
            m=d.m.tolist()
            if len(m)>=5: r['OPM_전년비']=m[-1]-m[-5]
            if len(m)>=3: r['OPM_2연속']=int(m[-1]>m[-2]>m[-3])
            r['OPM']=m[-1]
            if len(d)>=5: r['매출_전년비']=(d.rev.iloc[-1]/d.rev.iloc[-5]-1)*100
    except Exception as e: r['실적오류']=str(e)[:40]
    try:
        tr=yf.Ticker(tk).eps_trend; row=tr.loc['+1y'] if '+1y' in tr.index else tr.iloc[-1]
        cur=row['current']
        r['추정_30일']=(cur/row['30daysAgo']-1)*100 if row.get('30daysAgo') else None
        r['추정_90일']=(cur/row['90daysAgo']-1)*100 if row.get('90daysAgo') else None
        rv=yf.Ticker(tk).eps_revisions; rr=rv.loc['+1y'] if '+1y' in rv.index else rv.iloc[-1]
        r['상향30']=rr.get('upLast30days'); r['하향30']=rr.get('downLast30days')
    except Exception: pass
    rows.append(r)
new=pd.DataFrame(rows)
if len(sys.argv)>1:
    old=pd.read_csv('in/분기실적.csv',encoding='utf-8-sig'); new=pd.concat([old[~old['번호'].isin(new['번호'])],new])
new.to_csv('in/분기실적.csv',index=False,encoding='utf-8-sig')
print(len(rows))
