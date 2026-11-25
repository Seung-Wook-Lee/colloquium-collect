import os, datetime as dt, pandas as pd, yfinance as yf
N=pd.read_csv('in/닉스.csv',encoding='utf-8-sig')
t=[x for x in N['yfinance 티커'].dropna().astype(str).unique()]
# 11/25 의장 "드라이브에 다 저장해 놓으라고 했잖아. 그냥 오늘 가격만 받아오면 되는 거 아님?":
#   드라이브에 저장된 2년 가격(전날 사본)이 있으면 최근 15일만 받아 덧붙인다. 2년 전부 다시 받기는
#   ① 저장본이 없거나 ② 마지막 날짜가 10일보다 오래됐거나 ③ 새 종목이 있거나 ④ 월요일(배당 수정 주가를 주 1회 맞춤)일 때만.
OLD={}
for k,f in (('Close','가격2년'),('High','고가2년'),('Low','저가2년'),('Volume','거래량2년')):
    try: OLD[k]=pd.read_csv(f'in/{f}.csv',index_col=0,parse_dates=True,encoding='utf-8-sig')
    except Exception: pass
_c=OLD.get('Close')
FULL=(_c is None or not len(_c) or (pd.Timestamp.today()-_c.index.max()).days>10 or any(x not in _c.columns for x in t) or dt.date.today().weekday()==0 or os.environ.get('PX_FULL')=='1')
DAYS=730 if FULL else 15
print('가격 받기', '2년 전부' if FULL else f'최근 {DAYS}일만(저장본 {_c.index.max():%Y-%m-%d}까지에 덧붙임)')
D=yf.download(t, period='2y' if FULL else '1mo', auto_adjust=True, progress=False, threads=True)
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
            if mk=='한국': k=kis.daily_kr(str(r.get('코드') or x).split('.')[0], days=DAYS)
            elif mk=='미국': k=kis.daily_us(r.get('코드') or x, r.get('거래소'), days=DAYS, pages=8 if FULL else 1)
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
