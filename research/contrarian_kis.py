# 미스터 역발상(2026-11-07 의장) — SPDR 섹터 ETF 11개와 상위 10종목 주봉을 한투에서 받는다. 조회만.
#   실행: Actions '콜로키움 조사 실행' → script = contrarian_kis.py
#   만드는 것: research/out/contrarian/px/티커.csv (d,o,h,l,c,v 주봉, 수정주가 MODP=1)
#             research/out/contrarian/holdings_ssga_오늘.csv (SSGA 보유 종목 파일이 받아지면, 오늘 상위 10 확인용)
#             research/out/contrarian/수집결과.csv (종목별 거래소·행 수·처음·마지막 주·실패 사유)
#   드라이브 창구(DRIVE_URL/TOKEN)가 있으면 '콜로키움 수집데이터/미스터역발상/' 에도 올린다.
import os, sys, io, time, requests, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = 'https://openapi.koreainvestment.com:9443'
K, S = os.environ['KIS_APP_KEY'], os.environ['KIS_APP_SECRET']
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = f'{HERE}/out/contrarian'; os.makedirs(f'{OUT}/px', exist_ok=True)
TOK = requests.post(f'{BASE}/oauth2/tokenP', timeout=10, json={'grant_type': 'client_credentials', 'appkey': K, 'appsecret': S}).json()['access_token']
HD = {'content-type': 'application/json; charset=utf-8', 'authorization': f'Bearer {TOK}', 'appkey': K, 'appsecret': S, 'tr_id': 'HHDFS76240000', 'custtype': 'P'}

def page(ex, sym, bymd):
    for n in range(3):
        try:
            time.sleep(0.25)
            j = requests.get(f'{BASE}/uapi/overseas-price/v1/quotations/dailyprice', headers=HD, timeout=15,
                             params={'AUTH': '', 'EXCD': ex, 'SYMB': sym, 'GUBN': '1', 'BYMD': bymd, 'MODP': '1'}).json()
            if j.get('rt_cd') == '0': return [r for r in (j.get('output2') or []) if r.get('xymd')]
            err = f"{j.get('msg_cd')} {j.get('msg1')}"
        except Exception as e: err = str(e)[:80]
        time.sleep(1 + 2 * n)
    raise RuntimeError(err)

def weekly(sym):
    names = [sym, sym.replace('-', '/'), sym.replace('-', '.')] if '-' in sym else [sym]
    for ex in ('NYS', 'NAS', 'AMS'):
        for nm in names:
            try: first = page(ex, nm, '')
            except Exception as e: first = []; last_err = str(e)
            if not first: continue
            rows, bymd = list(first), ''
            for _ in range(20):                                   # 100주씩 뒤로, 최대 약 2,000주(2003년 이전까지)
                old = min(r['xymd'] for r in rows)
                if old <= '20021231' or bymd == old: break
                bymd = old; nxt = page(ex, nm, (pd.Timestamp(old) - pd.Timedelta(days=1)).strftime('%Y%m%d'))
                if not nxt: break
                rows += nxt
            d = pd.DataFrame(rows).drop_duplicates('xymd')
            d = pd.DataFrame({'d': pd.to_datetime(d.xymd), 'o': pd.to_numeric(d.open), 'h': pd.to_numeric(d.high),
                              'l': pd.to_numeric(d.low), 'c': pd.to_numeric(d.clos), 'v': pd.to_numeric(d.tvol)}).sort_values('d')
            return ex, nm, d[d.c > 0]
    return None, None, None

H = pd.read_csv(f'{HERE}/contrarian/holdings_top10.csv')
syms = ['SPY'] + list(dict.fromkeys(H.ETF)) + list(H.티커)
log = []
for s in syms:
    try:
        ex, nm, d = weekly(s)
        if d is None: log.append(dict(티커=s, 결과='실패: 세 거래소 모두 빈 응답')); continue
        d.to_csv(f'{OUT}/px/{s}.csv', index=False)
        log.append(dict(티커=s, 결과='성공', 거래소=ex, 한투코드=nm, 행수=len(d), 처음=d.d.iloc[0].date(), 마지막=d.d.iloc[-1].date()))
    except Exception as e:
        log.append(dict(티커=s, 결과=f'실패: {e}'[:120]))
    print(log[-1], flush=True)
pd.DataFrame(log).to_csv(f'{OUT}/수집결과.csv', index=False, encoding='utf-8-sig')

# SSGA 오늘 보유 종목(상위 10 확인용). Actions에서는 접속된다(10/29 PR #15 확인).
hold = []
for e in dict.fromkeys(H.ETF):
    try:
        r = requests.get(f'https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/holdings-daily-us-en-{e.lower()}.xlsx',
                         headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        x = pd.read_excel(io.BytesIO(r.content), skiprows=4).dropna(subset=['Ticker'])
        x = x[x.Ticker.astype(str).str.match(r'^[A-Z.\-]+$')].head(12)
        for i, row in enumerate(x.itertuples(), 1): hold.append(dict(ETF=e, 순위=i, 티커=row.Ticker, 이름=row.Name, 비중=row.Weight))
    except Exception as ex: hold.append(dict(ETF=e, 순위=0, 티커='', 이름=f'실패 {str(ex)[:60]}'))
pd.DataFrame(hold).to_csv(f'{OUT}/holdings_ssga_오늘.csv', index=False, encoding='utf-8-sig')

try:
    import drive
    if drive.ready():
        for root, _, fs in os.walk(OUT):
            for f in fs:
                p = os.path.join(root, f); rel = os.path.relpath(p, OUT)
                drive.put(f'콜로키움 수집데이터/미스터역발상/{rel}', open(p, 'rb').read())
        print('드라이브 업로드 끝')
except Exception as e: print('드라이브 업로드 건너뜀:', e)
print('끝', sum(1 for l in log if l['결과'] == '성공'), '/', len(log))
