"""ETF 보유 종목(상위 10) 표 + 유니버스 밖 구성 종목 재무 값(야후). 출력 in/ETF보유.csv, in/ETF멤버.csv"""
import sys, pandas as pd, yfinance as yf, concurrent.futures as cf
sys.path.insert(0,'qblocks'); import features as F
f=F.stocks('in'); tk=dict(zip(f['번호'],f['ticker'])); U=set(f['ticker'])
E=f[f['구분']!='개별주']
M=pd.read_csv('/mnt/project-files/위원공부/미스ETF/ETF구성_20261115.csv',dtype={'코드':str})
rows=[]
for _,r in M.iterrows():
    c=str(r['코드']).strip()
    t=c+'.KS' if c[:1].isdigit() and len(c)==6 else c
    rows.append(dict(번호=r['번호'],멤버=t,이름=r['이름'],비중=r['비중']))
have=set(M['번호'])
def th(n):
    try:
        h=yf.Ticker(tk[n]).funds_data.top_holdings
        return [dict(번호=n,멤버=s,이름=x['Name'],비중=round(x['Holding Percent']*100,2)) for s,x in h.iterrows()]
    except Exception as e: return []
need=[n for n in E['번호'] if n not in have and str(n).startswith('G')]
with cf.ThreadPoolExecutor(8) as ex:
    for r in ex.map(th,need): rows+=r
H=pd.DataFrame(rows); H.to_csv('in/ETF보유.csv',index=False,encoding='utf-8-sig')
print('ETF',H['번호'].nunique(),'rows',len(H)); print('빈 ETF',[n for n in E['번호'] if n not in set(H['번호'])])
mem=sorted(set(H['멤버'])-U)
def info(t):
    try:
        i=yf.Ticker(t).info
        g=lambda k:i.get(k)
        return dict(멤버=t,eqg=g('earningsQuarterlyGrowth'),eg=g('earningsGrowth'),revg=g('revenueGrowth'),tpe=g('trailingPE'),fpe=g('forwardPE'),
                    teps=g('trailingEps'),feps=g('forwardEps'),roe=g('returnOnEquity'),fcf=g('freeCashflow'),debt=g('totalDebt'),ebitda=g('ebitda'),
                    rec=g('recommendationMean'))
    except Exception: return dict(멤버=t)
with cf.ThreadPoolExecutor(12) as ex: R=list(ex.map(info,mem))
pd.DataFrame(R).to_csv('in/ETF멤버.csv',index=False,encoding='utf-8-sig'); print('members',len(R))
