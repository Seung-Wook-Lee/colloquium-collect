# 미스터 역도산 창고 처음 채우기(한 번만): 한투 주봉 2003~지금을 100주씩 거슬러 받아
#   드라이브 '콜로키움 수집데이터/00_누적/00_역도산_주봉.csv' 에 올린다. 이후는 매일 수집 블록(b09_yeokdosan)이 최근 주를 덧붙인다.
#   실행: Actions '콜로키움 조사 실행' → script = yeokdosan_backfill.py
#   만드는 것: research/out/yeokdosan/00_역도산_주봉.csv, 수집결과.csv (종목별 거래소·줄 수·처음·마지막·실패 사유)
import os, sys, time, requests, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, f'{ROOT}/yeokdosan')
import yeokdosan as ydo
K, S = os.environ['KIS_APP_KEY'], os.environ['KIS_APP_SECRET']
OUT = f'{ROOT}/research/out/yeokdosan'; os.makedirs(OUT, exist_ok=True)
TOK = None
for _ in range(6):   # 1분 1회 발급 제한·서버 에러면 기다렸다 다시
    j = requests.post(f'{ydo.BASE}/oauth2/tokenP', timeout=10, json={'grant_type': 'client_credentials', 'appkey': K, 'appsecret': S}).json()
    TOK = j.get('access_token')
    if TOK: break
    print('토큰 대기:', j.get('error_code'), j.get('error_description'), flush=True); time.sleep(65)
if not TOK: sys.exit('한투 토큰 발급 실패')
H = pd.read_csv(f'{ROOT}/yeokdosan/holdings_top10.csv')
syms = ['SPY'] + list(dict.fromkeys(H.ETF)) + list(H.티커)
frames, log = [], []
for tk in syms:
    try:
        ex, nm, rows = ydo.find_exchange(TOK, K, S, tk)
        if not rows: log.append(dict(티커=tk, 결과='실패: 세 거래소 모두 빈 응답')); print(log[-1], flush=True); continue
        rows = list(rows)
        for _ in range(20):                               # 100주씩 뒤로
            old = min(r['xymd'] for r in rows)
            if old <= '20021231': break
            nxt = ydo.kis_week_page(TOK, K, S, ex, nm, (pd.Timestamp(old) - pd.Timedelta(days=1)).strftime('%Y%m%d'))
            if not nxt or min(r['xymd'] for r in nxt) >= old: break
            rows += nxt
        f = ydo.to_frame(tk, rows); frames.append(f)
        log.append(dict(티커=tk, 결과='성공', 거래소=ex, 한투코드=nm, 줄수=len(f), 처음=f.날짜.min().date(), 마지막=f.날짜.max().date()))
    except Exception as e:
        log.append(dict(티커=tk, 결과=f'실패: {e}'[:120]))
    print(log[-1], flush=True)
store = ydo.merge(None, pd.concat(frames))
store.to_csv(f'{OUT}/00_역도산_주봉.csv', index=False, encoding='utf-8-sig')
pd.DataFrame(log).to_csv(f'{OUT}/수집결과.csv', index=False, encoding='utf-8-sig')
try:
    import drive
    if drive.ready():
        drive.put('콜로키움 수집데이터/00_누적/00_역도산_주봉.csv', open(f'{OUT}/00_역도산_주봉.csv', 'rb').read())
        drive.put('콜로키움 수집데이터/미스터역도산/수집결과.csv', open(f'{OUT}/수집결과.csv', 'rb').read())
        print('드라이브 업로드 끝')
except Exception as e:
    print('드라이브 업로드 실패:', e)
print('끝', sum(1 for l in log if l['결과'] == '성공'), '/', len(log))
