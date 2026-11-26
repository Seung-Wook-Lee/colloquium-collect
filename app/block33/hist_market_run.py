"""시장 블록(B01~B10) 과거 값을 GitHub Actions에서 만들고 드라이브에 보관 (11/24 의장 "자료들은 드라이브에 체계적으로 보관").
1) 우리 수집 코드로 긴 자료를 받음: collect/data/fetch_risk.py(시장 지표 장기 일봉·공포탐욕·지정학위험), fetch_cpce.py(CPCE), ccc_history.py(하이일드)
2) 드라이브 1_data 가격10년_종가·가격10년_지수장기, 00_퀀트입력 유니버스 → hist_market.py
3) 받은 자료와 결과를 드라이브 10년치 저장본 칸으로 올림(11/26 의장 "10년치 저장본 밖에 따로 있는 과거 자료들을 저장본에 합치시오"):
   시장 지표 5개 → 1_data/가격10년_시장지표.csv.gz 한 칸(PS.market), 결과 → 1_data/가격10년_시장블록.csv.gz. 옛 파일은 휴지통."""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [os.path.join(REPO, 'collect')]
import drive  # noqa: E402
sys.path.insert(0, os.path.join(REPO, 'collect', 'data'))
import px_store as PS  # noqa: E402  11/26 의장: 과거 자료는 10년치 저장본 칸으로
import gzip  # noqa: E402


def put_db(k, p):
    """과거 자료를 10년치 저장본 칸(1_data/가격10년_{k}.csv.gz)으로 올림."""
    b = open(p, 'rb').read()
    drive.put(f'{D}/1_data/{PS.name(k)}', b if p.endswith('.gz') else gzip.compress(b)); print('드라이브 올림', PS.name(k))
D = '콜로키움 수집데이터'; W = os.path.join(REPO, 'work_hm'); os.makedirs(W, exist_ok=True)
os.makedirs(os.path.join(REPO, 'history'), exist_ok=True)


def nbim():   # 11/24 의장 "확보해보시고": B21 펀드 자체 공시 — 노르웨이 국부펀드 보유 이력(1998~, 반기)
    r = subprocess.run([sys.executable, f'{REPO}/collect/data/fetch_nbim.py', W], capture_output=True, text=True, timeout=2400)
    print('[노르웨이]', r.returncode, (r.stdout + r.stderr).strip()[-800:])
    if os.path.exists(f'{W}/가격10년_노르웨이보유.csv.gz'):
        put_db('노르웨이보유', f'{W}/가격10년_노르웨이보유.csv.gz')


if os.environ.get('HM_ONLY') == 'nbim':   # 이 단계만 손으로 돌릴 때
    nbim(); sys.exit(0)
nbim()
for s in ('fetch_risk.py', 'fetch_cpce.py', 'ccc_history.py'):
    r = subprocess.run([sys.executable, f'collect/data/{s}'], cwd=REPO, capture_output=True, text=True, timeout=3000)
    print(f'[{s}]', r.returncode, (r.stdout + r.stderr).strip()[-600:])
PS.market(drive, os.path.join(REPO, 'history'), W)   # 새로 받은 것 > 저장본 칸 > 옛 파일, 옛 파일 5개 휴지통
for src, dst in ((f'{D}/1_data/가격10년_종가.csv.gz', '가격10년_종가.csv.gz'), (f'{D}/1_data/{PS.name("지수장기")}', PS.name('지수장기')),
                 ):
    b = drive.get(src)
    if b: open(f'{W}/{dst}', 'wb').write(b)
    print(dst, '받음' if b else '없음')
_U = PS.universe(drive)   # 11/26 의장 "하나로 통일해": 유니버스 = 10년치 데이터베이스 칸(회의 원고 daily.pull_univ와 같음)
if len(_U): _U.to_csv(f'{W}/유니버스.csv', index=False, encoding='utf-8-sig')
print('유니버스.csv', '받음' if len(_U) else '없음')
# 11/24 B21 장기 펀드 13F 과거 기록(2013~, 공시일 기준) — 우리 수집 코드 fetch_13f.py --full
r = subprocess.run([sys.executable, f'{REPO}/collect/data/fetch_13f.py', W, f'{W}/13F캐시', '--full'], capture_output=True, text=True, timeout=3000)
print('[13F]', r.returncode, (r.stdout + r.stderr).strip()[-500:])
if os.path.exists(f'{W}/가격10년_13F.csv.gz'):
    put_db('13F', f'{W}/가격10년_13F.csv.gz')
# 11/24 B22 미국 공매도 잔고 과거 기록(FINRA)
r = subprocess.run([sys.executable, f'{REPO}/collect/data/hist_short.py', W], capture_output=True, text=True, timeout=3000)
print('[공매도]', r.returncode, (r.stdout + r.stderr).strip()[-600:])
if os.path.exists(f'{W}/가격10년_공매도.csv.gz'):
    put_db('공매도', f'{W}/가격10년_공매도.csv.gz')
# 11/24 B20 ETF 좌수 과거 기록(State Street 공식 이력)
r = subprocess.run([sys.executable, f'{REPO}/collect/data/hist_etf_flow.py', W], capture_output=True, text=True, timeout=1500)
print('[ETF좌수]', r.returncode, (r.stdout + r.stderr).strip()[-600:])
if os.path.exists(f'{W}/가격10년_ETF좌수.csv.gz'):
    put_db('ETF좌수', f'{W}/가격10년_ETF좌수.csv.gz')
y = os.path.join(os.environ.get('QC_PRIVATE', ''), 'blocks.yaml')
r = subprocess.run([sys.executable, '-W', 'ignore', f'{HERE}/hist_market.py', W, y], capture_output=True, text=True, timeout=5000)
print(r.stdout[-3000:], r.stderr[-2000:])
if r.returncode == 0:
    put_db('시장블록', f'{W}/{PS.name("시장블록")}')
    if drive.get(f'{D}/1_data/{PS.name("시장블록")}'):   # 올라간 것 확인 뒤 옛 자리 2곳 휴지통
        for o in ('1_data/장기/시장블록이력.csv', '00_퀀트입력/시장블록이력.csv'):   # 옛 이름
            if drive.trash(f'{D}/{o}'):
                print('[저장본] 옛', o, '휴지통')
sys.exit(r.returncode)
