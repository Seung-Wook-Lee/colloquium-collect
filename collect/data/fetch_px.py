import os, datetime as dt, pandas as pd, yfinance as yf
N=pd.read_csv('in/닉스.csv',encoding='utf-8-sig')
t=[x for x in N['yfinance 티커'].dropna().astype(str).unique()]
# 11/25 의장 "드라이브에 다 저장해 놓으라고 했잖아. 그냥 오늘 가격만 받아오면 되는 거 아님?" "월요일마다 뭘 또 받아":
#   드라이브 저장본(가격·고가·저가·거래량 2년, 전날 사본)에 저장본 마지막 날 이후 가격만 받아 덧붙인다(겹침 3일).
#   2년치는 저장본에 없는 새 종목만, 그 종목만 받는다. 저장본 자체가 없을 때만 전부 2년.
OLD={}
for k,f in (('Close','가격2년'),('High','고가2년'),('Low','저가2년'),('Volume','거래량2년')):
    try: OLD[k]=pd.read_csv(f'in/{f}.csv',index_col=0,parse_dates=True,encoding='utf-8-sig')
    except Exception: pass
_c=OLD.get('Close')
FULL=_c is None or not len(_c.dropna(how='all'))
NEW=t if FULL else [x for x in t if x not in _c.columns or _c[x].dropna().empty]
OLDT=[x for x in t if x not in NEW]
S0=None if FULL else (_c.dropna(how='all').index.max()-pd.Timedelta(days=3)).date()
DAYS=730 if FULL else (dt.date.today()-S0).days+1
print('가격 받기', '저장본 없음 → 2년 전부' if FULL else f'저장본 {S0 + dt.timedelta(days=3)}까지 + 그 뒤 {DAYS}일만 {len(OLDT)}종목' + (f' · 새 종목 2년 {NEW}' if NEW else ''))
D=yf.download(OLDT, start=str(S0), auto_adjust=True, progress=False, threads=True) if OLDT else None
if NEW:
    D2=yf.download(NEW, period='2y', auto_adjust=True, progress=False, threads=True)
    D=D2 if D is None else pd.concat([D, D2], axis=1)
px=D['Close']
# 11/21 의장: 야후가 막아 빈 종목(최근 5일 값 없음)은 한투 일봉으로 채운다
try:
    import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import kis
    print('한투 키', '있음' if kis.ready() else '없음')
    if kis.ready():
        M=N.dropna(subset=['yfinance 티커']).drop_duplicates('yfinance 티커').set_index('yfinance 티커')
        # 11/21 23:47 의장: 한국 종목은 전부 한투 일봉, 미국은 야후가 빈 것만 한투
        kr=[x for x in t if M.loc[x].get('시장')=='한국']
        bad=kr+[x for x in t if x not in kr and (x not in px.columns or px[x].tail(5).isna().all())]
        got=[]
        for x in bad:
            r=M.loc[x]; mk=r.get('시장')
            if mk=='한국': k=kis.daily_kr(str(r.get('코드') or x).split('.')[0], days=730 if x in NEW else DAYS)
            elif mk=='미국': k=kis.daily_us(r.get('코드') or x, r.get('거래소'), days=730 if x in NEW else DAYS, pages=8 if x in NEW else 1)
            else: continue
            if not len(k): continue
            for col in ('Close','High','Low','Volume'):
                D=D.reindex(D.index.union(k.index)); D[(col,x)]=k[col].reindex(D.index)
            got.append(x)
        px=D['Close']; print('한투 일봉', len(got), '/', len(bad), '| 못 받음', [x for x in bad if x not in got])
except Exception as e: print('한투 일봉 보충 실패', e)
def _merge(k, new):   # 새로 받은 값이 우선, 없는 날·종목은 저장본
    o=OLD.get(k)
    if FULL or o is None: return new
    new=new.copy(); new.index=pd.to_datetime(new.index)
    m=new.combine_first(o).sort_index()
    return m[m.index>=m.index.max()-pd.Timedelta(days=735)]
px=_merge('Close', px)
px.to_csv('in/가격2년.csv', encoding='utf-8-sig')
# 11/19 의장 B20 매집·분산(CMF·MFI): 고가·저가·거래량도 함께(야후 무료)
for k, f in (('High', '고가2년'), ('Low', '저가2년'), ('Volume', '거래량2년')):
    _merge(k, D[k]).to_csv(f'in/{f}.csv', encoding='utf-8-sig')
print(px.shape, px.index[-1])
