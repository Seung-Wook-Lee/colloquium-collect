"""시장 블록(B01~B10) 과거 값을 GitHub Actions에서 만들고 드라이브에 보관 (11/24 의장 "자료들은 드라이브에 체계적으로 보관").
1) 우리 수집 코드로 긴 자료를 받음: collect/data/fetch_risk.py(시장위험_장기·공포탐욕·지정학위험), fetch_cpce.py(CPCE), ccc_history.py(하이일드)
2) 드라이브 1_data 가격10년_종가·가격10년_지수장기, 00_퀀트입력 유니버스 → hist_market.py
3) 받은 자료와 결과를 드라이브 '콜로키움 수집데이터/1_data/장기/'에, 시장블록이력.csv는 00_퀀트입력에도 올림."""
import os, shutil, subprocess, sys
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
for src, dst in (('history/시장위험_장기.csv', '시장위험_장기.csv'), ('history/공포탐욕_이력.csv', '공포탐욕_이력.csv'), ('history/지정학위험_이력.csv', '지정학위험_이력.csv'),
                 ('history/CPCE.csv', 'CPCE.csv'), ('history/신용스프레드_이력.csv', '신용스프레드_이력.csv')):
    p = os.path.join(REPO, src)
    if os.path.exists(p):
        shutil.copy(p, f'{W}/{dst}'); drive.put(f'{D}/1_data/장기/{dst}', open(p, 'rb').read()); print('드라이브 올림', dst)
    else:
        b = drive.get(f'{D}/1_data/장기/{dst}')   # 이번에 못 받으면 지난번 보관본
        if b: open(f'{W}/{dst}', 'wb').write(b); print('지난 보관본 사용', dst)
for src, dst in ((f'{D}/1_data/가격10년_종가.csv.gz', '가격10년_종가.csv.gz'), (f'{D}/1_data/{PS.name("지수장기")}', PS.name('지수장기')),
                 ('콜로키움/포트폴리오/' + max((f['name'] for f in drive.ls('콜로키움/포트폴리오') if f['name'].startswith('콜로키움100_유니버스_') and f['name'].endswith('.csv')), default='없음'), '유니버스.csv')):   # 회의 원고(daily.pull_univ)와 같은 최신 유니버스
    b = drive.get(src)
    if b: open(f'{W}/{dst}', 'wb').write(b)
    print(dst, '받음' if b else '없음')
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
    b = open(f'{W}/시장블록이력.csv', 'rb').read()
    drive.put(f'{D}/1_data/장기/시장블록이력.csv', b); drive.put(f'{D}/00_퀀트입력/시장블록이력.csv', b); print('드라이브 올림 시장블록이력.csv')
sys.exit(r.returncode)
