# ======================================================================
# 팀 Q 과거 데이터 — 공통 바탕
#   기존 07시 수집(run.py, blocks/)과 완전히 별개. 이 폴더(teamq/)만 쓴다.
#   쓰는 곳 : 드라이브 'Team_Q__chatgpt/' 한 곳뿐 (팀 Q 전용 창구 TEAMQ_DRIVE_URL·TEAMQ_DRIVE_TOKEN)
#   읽는 곳 : 기존 키(KIS·DART·FRED·SEC_EMAIL)는 읽기 전용 조회에만 사용
#             기존 드라이브 자료는 기존 창구(DRIVE_URL)로 '읽기(get)'만 한다 — 쓰기 없음
#   결과    : 로컬 teamq_out/ 에 먼저 쓰고 마지막에 드라이브로 올린다(창구가 없으면 Actions 산출물로만 남김)
# ======================================================================
import base64, datetime as dt, io, json, os, time, traceback
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get('TEAMQ_OUT', os.path.join(os.getcwd(), 'teamq_out'))
DRIVE_ROOT = 'Team_Q__chatgpt'
START = '2015-11-01'                       # 10년 전 (지시서: 최근 10년)
NOW_KST = dt.datetime.utcnow() + dt.timedelta(hours=9)
TODAY = NOW_KST.strftime('%Y-%m-%d')
COLLECTED_AT = NOW_KST.strftime('%Y-%m-%d %H:%M KST')

KEY = {k: (os.environ.get(k) or '').strip() for k in
       ['KIS_APP_KEY', 'KIS_APP_SECRET', 'FRED_KEY', 'DART_KEY', 'SEC_EMAIL', 'ECOS_KEY', 'EDINET_KEY',
        'KRX_ID', 'KRX_PW', 'TEAMQ_DRIVE_URL', 'TEAMQ_DRIVE_TOKEN', 'DRIVE_URL', 'DRIVE_TOKEN']}

U = pd.read_csv(os.path.join(HERE, 'universe_20261120.csv'), dtype=str)
U = U.rename(columns={'번호': 'id', '정식 종목명': 'name', '시장': 'country', '거래소': 'exchange', '구분': 'kind',
                      '섹터/테마': 'sector', '코드': 'code', 'yfinance 티커': 'yticker'})[
    ['id', 'name', 'country', 'exchange', 'kind', 'sector', 'code', 'yticker']]
U['kind'] = U['kind'].map({'개별주': 'stock', 'ETF': 'etf'}).fillna(U['kind'])
U['currency'] = U['country'].map({'한국': 'KRW', '미국': 'USD', '일본': 'JPY'})
U['tz'] = U['country'].map({'한국': 'Asia/Seoul', '미국': 'America/New_York', '일본': 'Asia/Tokyo'})

STATUS = []   # 항목별 결과 (metadata/run_status 로 저장)


def log(*a):
    print(f'[{(dt.datetime.utcnow() + dt.timedelta(hours=9)).strftime("%H:%M:%S")}]', *a, flush=True)


def status(part, item, ok, rows=0, note=''):
    STATUS.append({'part': part, 'item': item, 'ok': bool(ok), 'rows': int(rows), 'note': str(note)[:300],
                   'collected_at': COLLECTED_AT})


def save(df, rel):
    """rel 예: 'raw/prices/yahoo_daily.parquet'. 빈 표도 컬럼은 남긴다."""
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    df = df.copy()
    for c in df.columns:                      # 섞인 형식은 문자로 (parquet 저장 오류 방지)
        if df[c].dtype == object:
            df[c] = df[c].map(lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
    df.to_parquet(p, index=False)
    log(f'  저장 {rel} ({len(df):,}행)')
    return p


def load(rel):
    """로컬에 없으면 팀 Q 드라이브에서 내려받는다(앞 단계를 따로 돌렸을 때)."""
    p = os.path.join(OUT, rel)
    if not os.path.exists(p) and q_ready():
        b = _drive(KEY['TEAMQ_DRIVE_URL'], KEY['TEAMQ_DRIVE_TOKEN'], {'action': 'get', 'path': f'{DRIVE_ROOT}/{rel}'})
        if b.get('found'):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'wb').write(base64.b64decode(b['data']))
    return pd.read_parquet(p) if os.path.exists(p) else None


def get(url, params=None, headers=None, retry=3, pause=0.0, timeout=60):
    for n in range(retry + 1):
        try:
            time.sleep(pause)
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code == 429 or r.status_code >= 500:
                raise RuntimeError(f'HTTP {r.status_code}')
            return r
        except Exception as e:
            if n == retry:
                log(f'  실패 {url.split("?")[0][:80]}: {e}')
                return None
            time.sleep(3 * (2 ** n))


# ---------------- 드라이브 ----------------
def _drive(url, token, payload, retry=3):
    for n in range(retry + 1):
        try:
            r = requests.post(url, json={'token': token, **payload}, timeout=600)
            r.raise_for_status()
            j = r.json()
            if not j.get('ok'):
                raise RuntimeError(j.get('error'))
            return j
        except Exception as e:
            if n == retry or '토큰' in str(e) or '허용되지' in str(e):
                raise RuntimeError(f'드라이브 {payload.get("action")} {payload.get("path")}: {e}') from None
            time.sleep(10 * (n + 1))


def q_ready():
    return bool(KEY['TEAMQ_DRIVE_URL'] and KEY['TEAMQ_DRIVE_TOKEN'])


def read_existing(path):
    """기존 스튜디오 톰앤수 드라이브 자료 읽기 전용 (예: '콜로키움 수집데이터/00_누적/00_가격이력.csv')"""
    if not (KEY['DRIVE_URL'] and KEY['DRIVE_TOKEN']):
        return None
    try:
        j = _drive(KEY['DRIVE_URL'], KEY['DRIVE_TOKEN'], {'action': 'get', 'path': path})
        return base64.b64decode(j['data']) if j.get('found') else None
    except Exception as e:
        log('  기존 자료 읽기 실패:', e)
        return None


MIME = {'.parquet': 'application/octet-stream', '.csv': 'text/csv', '.txt': 'text/plain', '.json': 'application/json'}


def upload_all(only_prefix=None):
    """작은 파일부터 올리고, 실패한 파일은 건너뛰고 끝에 목록을 남긴다."""
    if not q_ready():
        log('팀 Q 드라이브 창구(TEAMQ_DRIVE_URL·TOKEN)가 없어 드라이브에 올리지 않음 → Actions 산출물(teamq_out)로만 남김')
        return 0
    try:
        j = _drive(KEY['TEAMQ_DRIVE_URL'], KEY['TEAMQ_DRIVE_TOKEN'], {'action': 'list', 'path': DRIVE_ROOT}, retry=1)
        log(f'  창구 연결 확인: Team_Q__chatgpt 안 파일 {len(j.get("files", []))}개')
    except Exception as e:
        log(f'  창구 연결 실패(주소·배포·토큰 확인 필요): {e}')
        raise
    files = []
    for root, _, fs in os.walk(OUT):
        for f in fs:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, OUT).replace(os.sep, '/')
            if not only_prefix or rel.startswith(only_prefix):
                files.append((os.path.getsize(full), rel, full))
    n, bad = 0, []
    for size, rel, full in sorted(files):
        try:
            data = open(full, 'rb').read()
            _drive(KEY['TEAMQ_DRIVE_URL'], KEY['TEAMQ_DRIVE_TOKEN'],
                   {'action': 'put', 'path': f'{DRIVE_ROOT}/{rel}', 'mime': MIME.get(os.path.splitext(rel)[1], 'application/octet-stream'),
                    'data': base64.b64encode(data).decode()}, retry=2)
            n += 1
            log(f'  올림 {rel} ({size/1e6:.1f}MB)')
        except Exception as e:
            bad.append((rel, size))
            log(f'  실패 {rel} ({size/1e6:.1f}MB): {e}')
    log(f'  드라이브 올리기: 성공 {n}개, 실패 {len(bad)}개 {bad}')
    return n


def run_part(name, fn):
    t = time.time()
    log(f'===== {name} 시작')
    try:
        fn()
        status(name, '(단계 전체)', True, note=f'{time.time()-t:.0f}초')
    except Exception as e:
        traceback.print_exc()
        status(name, '(단계 전체)', False, note=f'{type(e).__name__}: {e}')
    log(f'===== {name} 끝 ({time.time()-t:.0f}초)')
