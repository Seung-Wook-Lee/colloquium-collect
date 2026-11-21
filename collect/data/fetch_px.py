import pandas as pd, yfinance as yf
N=pd.read_csv('in/닉스.csv',encoding='utf-8-sig')
t=[x for x in N['yfinance 티커'].dropna().astype(str).unique()]
D=yf.download(t, period='2y', auto_adjust=True, progress=False, threads=True)
px=D['Close']
# 11/21 의장: 야후가 막아 빈 종목(최근 5일 값 없음)은 한투 일봉으로 채운다
try:
    import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import kis
    if kis.ready():
        M=N.dropna(subset=['yfinance 티커']).drop_duplicates('yfinance 티커').set_index('yfinance 티커')
        # 11/21 23:47 의장: 한국 종목은 전부 한투 일봉, 미국은 야후가 빈 것만 한투
        kr=[x for x in t if M.loc[x].get('시장')=='한국']
        bad=kr+[x for x in t if x not in kr and (x not in px.columns or px[x].tail(5).isna().all())]
        got=[]
        for x in bad:
            r=M.loc[x]; mk=r.get('시장')
            if mk=='한국': k=kis.daily_kr(str(r.get('코드') or x).split('.')[0])
            elif mk=='미국': k=kis.daily_us(r.get('코드') or x, r.get('거래소'))
            else: continue
            if not len(k): continue
            for col in ('Close','High','Low','Volume'):
                D=D.reindex(D.index.union(k.index)); D[(col,x)]=k[col].reindex(D.index)
            got.append(x)
        px=D['Close']; print('한투 일봉', len(got), '/', len(bad), '| 못 받음', [x for x in bad if x not in got])
except Exception as e: print('한투 일봉 보충 실패', e)
px.to_csv('in/가격2년.csv', encoding='utf-8-sig')
# 11/19 의장 B20 매집·분산(CMF·MFI): 고가·저가·거래량도 함께(야후 무료)
for k, f in (('High', '고가2년'), ('Low', '저가2년'), ('Volume', '거래량2년')):
    D[k].to_csv(f'in/{f}.csv', encoding='utf-8-sig')
print(px.shape, px.index[-1])
