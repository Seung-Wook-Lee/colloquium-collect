"""자기역사 PER 3년 밴드(11/16 의장: 3년치만). 일별 주가 ÷ 그 시점에 알려진 EPS(연간 EPS, 결산 90일 뒤 반영 + 최근 TTM).
출력 in/PER3년.csv: 번호, per_now, per_med3, per_pct3(오늘 PER의 3년 백분위, 0=가장 쌈), per_med1·per_pct1(52주, 11/20 의장 '52주 중앙값보다 비싸면 추천 안 함')"""
import sys, pandas as pd, numpy as np, yfinance as yf, concurrent.futures as cf
sys.path.insert(0,'qblocks'); import features as F
f=F.stocks('in'); f=f[(f['구분']=='개별주')&f['시장'].isin(['한국','미국'])]
def one(a):
    n,t=a
    try:
        T=yf.Ticker(t); px=T.history(period='3y',auto_adjust=False)['Close']
        px.index=px.index.tz_localize(None)
        A=T.income_stmt; Qd=T.quarterly_income_stmt
        key=[k for k in ('Diluted EPS','Basic EPS') if k in A.index]
        steps=[]
        if key:
            for d,v in A.loc[key[0]].dropna().items(): steps.append((pd.Timestamp(d)+pd.Timedelta(days=90),float(v)))
        qk=[k for k in ('Diluted EPS','Basic EPS') if k in Qd.index]
        if qk:
            q=Qd.loc[qk[0]].dropna().sort_index()
            for i in range(3,len(q)): steps.append((pd.Timestamp(q.index[i])+pd.Timedelta(days=45),float(q.iloc[i-3:i+1].sum())))
        if not steps: return dict(번호=n)
        s=pd.Series(dict(sorted(steps))).sort_index()
        eps=s.reindex(px.index.union(s.index)).ffill().reindex(px.index)
        # 11/22 의장 'PER 오류 고쳐라': 재무 통화가 주가 통화와 다르면(TSM: 주가 달러, EPS 대만 달러) 그날 환율로 바꾸고,
        # ADR 비율(1 ADR = 원주 n주)은 야후 trailingEps(주가 통화·ADR 기준)와 맞춘다
        info=T.info or {}
        cur=info.get('currency'); fin=info.get('financialCurrency')
        fx_note=''
        if cur and fin and cur!=fin:
            fx=yf.download(f'{fin}{cur}=X',period='3y',auto_adjust=False,progress=False)['Close']
            fx=(fx.iloc[:,0] if hasattr(fx,'columns') else fx); fx.index=pd.to_datetime(fx.index).tz_localize(None)
            fx=fx.reindex(px.index.union(fx.index)).ffill().reindex(px.index)
            if fx.notna().sum()==0: return dict(번호=n,경고=f'환율 {fin}{cur} 없음')
            eps=eps*fx
            te=info.get('trailingEps')
            if te and te>0 and eps.dropna().iloc[-1]>0:
                r=te/eps.dropna().iloc[-1]
                if 0.2<r<20 and abs(r-1)>0.15: eps=eps*r
            fx_note=f'{fin}→{cur} 환산'
        per=(px/eps).where(eps>0).dropna()
        if len(per)<250: return dict(번호=n)
        now=per.iloc[-1]
        # 자료 정련: PER이 상식 밖(2배 미만·2000배 초과)이면 쓰지 않고 경고(11/22 TSM 0.65 사건)
        if not (2<=now<=2000): return dict(번호=n,경고=f'PER {now:.2f} 상식 밖 {fx_note}'.strip())
        p1=per[per.index>=per.index[-1]-pd.Timedelta(days=365)]
        return dict(번호=n,per_now=round(now,2),per_med3=round(per.median(),2),per_pct3=round((per<now).mean(),3),
                    per_med1=round(p1.median(),2),per_pct1=round((p1<now).mean(),3),경고=fx_note)
    except Exception as e:
        return dict(번호=n)
with cf.ThreadPoolExecutor(10) as ex: R=list(ex.map(one,zip(f['번호'],f['ticker'])))
D=pd.DataFrame(R); D.to_csv('in/PER3년.csv',index=False,encoding='utf-8-sig')
print(len(D), D['per_pct3'].notna().sum()); print(D.dropna(subset=['per_now']).head(10))
if '경고' in D: print(D[D['경고'].fillna('')!=''].to_string())
