# ======================================================================
# [블록 0] 준비 — 모든 블록이 쓰는 공통 바탕 (항상 맨 먼저 실행)
#   하는 일  : 오늘 날짜(한국 시각) 정하기, 키 읽기, 드라이브 파일 준비, 스튜디오 톰앤수 100 종목 목록 읽기
#              GitHub에서 돌 때: 드라이브 창구(drive.py)로 필요한 파일을 내려받아 work/ 폴더에 두고,
#                                마지막 블록 11이 결과를 드라이브에 올린다.
#              코랩에서 돌 때  : 드라이브를 연결해 그대로 읽고 쓴다.
#   읽는 것  : 10년치 데이터베이스 유니버스 칸(1_data/가격10년_유니버스.csv.gz, 11/26 의장 "하나로 통일해")
#              (2026-10-28 의장: 표는 csv. 예전 .xlsx도 읽지만 같은 날짜면 csv가 먼저)
#              드라이브 콜로키움 수집데이터/00_누적/ (가격 이력, 실적 저장본 등 이어 쓰는 파일 전부)
#   키       : KIS_APP_KEY, KIS_APP_SECRET, FRED_KEY, DART_KEY, SEC_EMAIL (+ GitHub에서는 DRIVE_URL, DRIVE_TOKEN)
#              GitHub에서는 Secrets(환경변수), 코랩에서는 코랩 Secrets. 값은 화면·파일에 남기지 않는다.
#   만드는 것: 다음 블록이 쓰는 변수 u(종목표), TICKERS, SEC(키), TODAY, NOW, DAY, KEEP, log()
#   고칠 곳  : 드라이브 폴더 이름이 바뀌면 D_ROOT, D_DATA
# ======================================================================
import glob, hashlib, io, os, shutil, time, datetime as dt, traceback, unicodedata
import pandas as pd, requests, yfinance as yf

D_ROOT, D_DATA = '콜로키움', '콜로키움 수집데이터'      # 드라이브 폴더 이름
KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime.now(KST)
TODAY = NOW.strftime('%Y%m%d')
LOG = []      # 점검 요약 줄
FATAL = False
ONLY = globals().get('ONLY', [])   # run.py에 블록 번호를 주면 그 목록(시험 실행), 아니면 빈 목록
nfc = lambda x: unicodedata.normalize('NFC', x)


def log(msg):
    print(msg, flush=True)
    LOG.append(msg)


try:
    from google.colab import drive as _colab_drive, userdata as _userdata
    IN_COLAB = True
except ImportError:
    IN_COLAB = False

KEYS = ['KIS_APP_KEY', 'KIS_APP_SECRET', 'FRED_KEY', 'DART_KEY', 'SEC_EMAIL',
        'NAVER_CLIENT_ID', 'NAVER_CLIENT_SECRET', 'FINNHUB_KEY', 'TAVILY_KEY']   # 뉴스 키 4개는 2026-10-31 추가(없으면 그 통로만 건너뜀)
SEC = {}
for n in KEYS:
    try:
        SEC[n] = ((_userdata.get(n) if IN_COLAB else os.environ.get(n)) or '').strip()
    except Exception:
        SEC[n] = ''

if IN_COLAB:
    _colab_drive.mount('/content/drive')
    BASE_DIR = '/content/drive/MyDrive'
else:
    import drive as gdrive
    BASE_DIR = os.path.abspath('work')
ROOT = f'{BASE_DIR}/{D_ROOT}'
UNIV_DIR = f'{ROOT}/포트폴리오'
UNIV_DB = '유니버스_데이터베이스칸.csv'   # 11/26: 10년치 데이터베이스 유니버스 칸을 받아 두는 이름(로컬)
DATA = f'{BASE_DIR}/{D_DATA}'
DAY = f'{DATA}/{TODAY}'        # 그날 파일
KEEP = f'{DATA}/00_누적'        # 이어 쓰는 파일(가격 이력, 실적 저장본, 회사번호 목록)
for p in [UNIV_DIR, DAY, KEEP]:
    os.makedirs(p, exist_ok=True)

SYNC = {}   # GitHub: 내려받은 파일 → 내용 지문 (블록 11이 바뀐 파일만 올린다)


def _fp(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


def _pull(dfolder, name, local):
    data = gdrive.get(f'{dfolder}/{name}')
    if data is None:
        return False
    with open(local, 'wb') as f:
        f.write(data)
    SYNC[local] = _fp(local)
    return True


def _is_univ(name):
    name = nfc(name)
    return name.startswith('콜로키움100_유니버스_') and name.endswith(('.csv', '.xlsx'))


def _univ_key(name):
    # 날짜 순, 같은 날짜면 csv를 뒤로(= 선택)
    stem, ext = os.path.splitext(nfc(name))
    return stem, ext == '.csv'


pulled = 0
if not IN_COLAB:
    if not gdrive.ready():
        raise RuntimeError('DRIVE_URL·DRIVE_TOKEN 없음 (GitHub Secrets 확인)')
    # 1) 스튜디오 톰앤수 100 종목표: 가장 최신 것 하나만
    # 11/26 의장 "하나로 통일해": 유니버스 = 10년치 데이터베이스 칸(1_data/가격10년_유니버스) 하나
    import sys; sys.path.insert(0, os.path.abspath('data'))
    import px_store as PS
    _U = PS.universe(gdrive, log)
    if not len(_U):
        raise FileNotFoundError('10년치 데이터베이스에 유니버스 칸이 없습니다')
    _U.to_csv(f'{UNIV_DIR}/{UNIV_DB}', index=False, encoding='utf-8-sig')
    # 2) 00_누적 전부 (드라이브 수정 시각을 그대로 붙여 '며칠마다 새로 받기' 판단이 맞게)
    for n in PS.KEEP_DROP:   # 11/26 의장 카드 '안 쓰는 5개만 지움'
        if gdrive.trash(f'{D_DATA}/00_누적/{n}'):
            log(f'[준비] 안 쓰는 00_누적/{n} 휴지통')
    for f in gdrive.ls(f'{D_DATA}/00_누적'):
        if f['name'] in PS.KEEP_DB:   # 매일 쓰는 이력은 10년치 데이터베이스 칸에서(아래)
            continue
        local = f'{KEEP}/{f["name"]}'
        if _pull(f'{D_DATA}/00_누적', f['name'], local):
            t = dt.datetime.fromisoformat(f['modified'].replace('Z', '+00:00')).timestamp()
            os.utime(local, (t, t))
            SYNC[local] = _fp(local)
            pulled += 1
    # 2-1) 매일 쓰는 이력 4개 = 10년치 데이터베이스 칸(1_data/가격10년_{칸}). 칸이 없으면 PS.fetch가 옛 00_누적 파일을 옮기고 휴지통.
    import gzip as _gz
    for n, k in PS.KEEP_DB.items():
        if PS.fetch(gdrive, k, KEEP, log):
            local = f'{KEEP}/{n}'
            open(local, 'wb').write(_gz.decompress(open(f'{KEEP}/{PS.name(k)}', 'rb').read()))
            os.remove(f'{KEEP}/{PS.name(k)}')
            SYNC[local] = _fp(local)
            pulled += 1
    # 3) 같은 날 다시 돌릴 때 이어 쓰는 점검 파일
    _pull(f'{D_DATA}/{TODAY}', f'{TODAY}_수집점검.txt', f'{DAY}/{TODAY}_수집점검.txt')

where = 'GitHub' if not IN_COLAB else '코랩'
log(f'[준비] {NOW:%Y-%m-%d %H:%M} KST | 실행 {where} | 저장 폴더 {D_DATA}/{TODAY} | '
    + (f'드라이브에서 받은 누적 파일 {pulled}개 | ' if not IN_COLAB else '')
    + f'한투 키 {sum(bool(SEC[k]) for k in SEC if k.startswith("KIS"))}/2 | FRED 키 {"있음" if SEC["FRED_KEY"] else "없음"} | '
    f'DART 키 {"있음" if SEC["DART_KEY"] else "없음"} | SEC 이메일 {"있음" if SEC["SEC_EMAIL"] else "없음"} | '
    f'뉴스 키 네이버 {"있음" if SEC["NAVER_CLIENT_ID"] and SEC["NAVER_CLIENT_SECRET"] else "없음"}·'
    f'Finnhub {"있음" if SEC["FINNHUB_KEY"] else "없음"}·Tavily {"있음" if SEC["TAVILY_KEY"] else "없음"}')

# 유니버스: 포트폴리오 폴더의 최신 스튜디오 톰앤수 100 종목표 (드라이브 한글 이름이 NFD일 수 있어 NFC로 맞춰 찾는다)
cands = sorted((f for f in os.listdir(UNIV_DIR) if _is_univ(f)), key=_univ_key)
if os.path.exists(f'{UNIV_DIR}/{UNIV_DB}'):   # GitHub: 데이터베이스 칸에서 받은 것만 씀
    cands = [UNIV_DB]
if not cands:
    raise FileNotFoundError(f'포트폴리오 폴더에 콜로키움100_유니버스 csv가 없습니다: {os.listdir(UNIV_DIR)}')
UNIV_FILE = f'{UNIV_DIR}/{cands[-1]}'
if UNIV_FILE.endswith('.csv'):
    u = pd.read_csv(UNIV_FILE, dtype={'코드': str}, encoding='utf-8-sig')
else:
    u = pd.read_excel(UNIV_FILE, sheet_name='유니버스', dtype={'코드': str})
u = u[u['yfinance 티커'].notna()].copy()
try:   # 11/26 의장 편출은 collect/layers.py OUT 한 곳(새 유니버스 파일 만들지 않음)
    import layers as _layers
    u = _layers.drop_out(u).copy()
except ImportError:
    pass
u['yfinance 티커'] = u['yfinance 티커'].astype(str).str.strip()
u['코드'] = u['코드'].astype(str).str.strip()
import layers   # 11/25 새 층(U0~U7·K0~K5) → 분석 묶음(S0~S6), collect/layers.py
u = layers.apply(u)
TICKERS = u['yfinance 티커'].tolist()
log(f'[유니버스] {nfc(os.path.basename(UNIV_FILE))} → {len(u)}종목')

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/129.0 Safari/537.36'}


def get(url, retry=2, **kw):
    """키 없는 웹 요청 (실패하면 None)"""
    headers = kw.pop('headers', UA)
    for n in range(retry + 1):
        try:
            r = requests.get(url, headers=headers, timeout=30, **kw)
            r.raise_for_status()
            return r
        except Exception as e:
            if n == retry:
                print(f'  실패 {url[:70]}: {e}')
                return None
            time.sleep(3 * (n + 1))


def stamp():
    return dt.datetime.now(KST).strftime('%Y-%m-%d %H:%M')
