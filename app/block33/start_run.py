"""start 블록을 GitHub Actions에서 돌리는 창구 (11/22 23:30 의장 "하나의 흐름으로").
1) 엔진 입력 모으기: 드라이브 최신 07시 파일(오늘이 없으면 가장 가까운 앞 날짜)·유니버스·팀Q·보조 자료(00_퀀트입력) — 회의 원고(daily.py)와 같은 함수.
   --fetch 면 야후 보조 자료를 새로 받음(아니면 전날까지 받은 것).
2) start 자료: 1_data 가격10년_종가·지수_장기, 00_퀀트입력 블록점수이력, 비공개 Core50, 드라이브 start/질문장부.
3) start.py 실행(그 안에서 엔진 ①블록 계산 ②거르기를 직접 돈다) → 결과를 드라이브 '콜로키움 수집데이터/start/'에 올림.
  python app/block33/start_run.py "<질문>" [core50|전체] [주식|ETF|모두] [4|12|26|52] [N미국] [N한국] [--fetch]"""
import datetime as dt, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(REPO, 'meeting')]
import daily as DL   # noqa: E402  (경로 설정·드라이브 받기 함수)
import drive         # noqa: E402
args = [a for a in sys.argv[1:] if a != '--fetch']; FETCH = '--fetch' in sys.argv
W = os.path.join(REPO, 'work_start'); IN = f'{W}/in'; SD = f'{W}/sd'; OUT = f'{W}/out'
shutil.rmtree(W, ignore_errors=True)
for p in (IN, SD, OUT): os.makedirs(p)
os.symlink(HERE, os.path.join(W, 'qblocks'))   # fetch_*.py가 'in/'·'qblocks/'를 상대 경로로 씀(in은 IN 그 자체)
KST = dt.timezone(dt.timedelta(hours=9)); now = dt.datetime.now(KST)
day = None
for k in range(0, 10):
    d = (now - dt.timedelta(days=k)).strftime('%Y%m%d')
    if DL.pull_day(d, IN): day = d; break
if not day: sys.exit('최근 10일 안 07시 파일이 드라이브에 없습니다.')
DL.pull_univ(IN); DL.pull_teamq(IN); DL.pull_carry(IN, True); DL.pull_advisors(IN, True)
if FETCH:
    os.chdir(W); DL.fetch(W, IN)
D = DL.D_DATA
for src, dst in ((f'{D}/1_data/가격10년_종가.csv.gz', '가격10년_종가.csv.gz'), (f'{D}/1_data/지수_장기.csv.gz', '지수_장기.csv.gz'),
                 (f'{DL.CARRY}/블록점수이력.csv', 'bhist.csv')):
    b = drive.get(src)
    if b is None: sys.exit(f'드라이브에 {src} 없음')
    open(f'{SD}/{dst}', 'wb').write(b)
core = os.path.join(os.environ.get('QC_PRIVATE', ''), 'start', 'Core50.csv')
shutil.copy(core, f'{SD}/Core50.csv')
lg = drive.get(f'{D}/start/질문장부.csv')
if lg: open(f'{OUT}/질문장부.csv', 'wb').write(lg)
env = dict(os.environ, START_IN=IN, START_DIR=SD, START_OUT=OUT, START_INDATE=f'{day} 07시 파일' + (' + 야후 새로 받음' if FETCH else ''))
r = subprocess.run([sys.executable, os.path.join(HERE, 'start.py')] + args, env=env, cwd=W)
for f in sorted(os.listdir(OUT)):
    drive.put(f'{D}/start/{f}', open(f'{OUT}/{f}', 'rb').read())
print('드라이브 올림:', len(os.listdir(OUT)), '파일')
sys.exit(r.returncode)
