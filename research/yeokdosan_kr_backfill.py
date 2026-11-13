# 미스터 역도산 국내 창고 채우기(한 번만, 11/9 의장 "해외·국내 같은 방식"):
#   국내 섹터 ETF 13개(yeokdosan/etfs_kr.csv)의 한투 구성종목 상위 10을 받고,
#   ETF·상위 10·KODEX 200(069500, 국내 기준) 주봉을 2003~지금 거슬러 받아
#   드라이브 '00_누적/00_역도산_주봉.csv'(해외와 같은 창고)에 합치고 '00_누적/00_역도산_국내구성.csv'를 올린다.
#   이후는 매일 수집 블록(b09_yeokdosan)이 최근 주와 구성을 갱신한다.
#   실행: Actions '콜로키움 조사 실행' → script = yeokdosan_kr_backfill.py
import os, sys, io, time, requests, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, f'{ROOT}/yeokdosan')
import yeokdosan as ydo, drive
K, S = os.environ['KIS_APP_KEY'], os.environ['KIS_APP_SECRET']
OUT = f'{ROOT}/research/out/yeokdosan'; os.makedirs(OUT, exist_ok=True)
SP, CP = '콜로키움 수집데이터/00_누적/00_역도산_주봉.csv', '콜로키움 수집데이터/00_누적/00_역도산_국내구성.csv'
TOK = None
for _ in range(6):
    j = requests.post(f'{ydo.BASE}/oauth2/tokenP', timeout=10, json={'grant_type': 'client_credentials', 'appkey': K, 'appsecret': S}).json()
    TOK = j.get('access_token')
    if TOK: break
    print('토큰 대기:', j.get('error_code'), j.get('error_description'), flush=True); time.sleep(65)
if not TOK: sys.exit('한투 토큰 발급 실패')
E = pd.read_csv(f'{ROOT}/yeokdosan/etfs_kr.csv', dtype={'ETF': str})
comp, log = [], []
for e in E.ETF:
    try:
        c = ydo.kr_components(TOK, K, S, e)
        comp += [dict(ETF=e, 순위=a, 티커=b, 이름=n, 비중=w) for a, b, n, w in c]
        log.append(dict(티커=e, 결과=f'구성 {len(c)}종목'))
    except Exception as x:
        log.append(dict(티커=e, 결과=f'구성 실패: {x}'[:150]))
    print(log[-1], flush=True)
C = pd.DataFrame(comp, columns=['ETF', '순위', '티커', '이름', '비중'])
C.to_csv(f'{OUT}/00_역도산_국내구성.csv', index=False, encoding='utf-8-sig')
syms = list(dict.fromkeys(['069500'] + list(E.ETF) + list(C.티커)))
frames = []
for tk in syms:
    try:
        f = ydo.kr_week_all(TOK, K, S, tk)
        if f is None or not len(f): raise RuntimeError('빈 응답')
        frames.append(f)
        log.append(dict(티커=tk, 결과='성공', 줄수=len(f), 처음=f.날짜.min().date(), 마지막=f.날짜.max().date()))
    except Exception as x:
        log.append(dict(티커=tk, 결과=f'실패: {x}'[:150]))
    print(log[-1], flush=True)
old = None
if drive.ready():
    b = drive.get(SP)
    if b: old = pd.read_csv(io.BytesIO(b), parse_dates=['날짜'], dtype={'티커': str}); print('드라이브 창고', old.티커.nunique(), '종목', flush=True)
store = ydo.merge(old, pd.concat(frames) if frames else None)
store.to_csv(f'{OUT}/00_역도산_주봉.csv', index=False, encoding='utf-8-sig')
pd.DataFrame(log).to_csv(f'{OUT}/국내_수집결과.csv', index=False, encoding='utf-8-sig')
try:
    if drive.ready() and old is not None and frames:
        drive.put(SP, open(f'{OUT}/00_역도산_주봉.csv', 'rb').read())
        if len(C): drive.put(CP, open(f'{OUT}/00_역도산_국내구성.csv', 'rb').read())
        drive.put('콜로키움 수집데이터/미스터역도산/국내_수집결과.csv', open(f'{OUT}/국내_수집결과.csv', 'rb').read())
        print('드라이브 업로드 끝')
    else:
        print('드라이브 업로드 건너뜀(창고를 못 읽었거나 받은 것 없음)')
except Exception as x:
    print('드라이브 업로드 실패:', x)
print('끝', store.티커.nunique(), '종목', len(store), '줄')
