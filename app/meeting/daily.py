"""아침 8시·저녁 8시 수집 뒤 자동 실행: 드라이브 읽기 → 사건·변수달력(규칙) → 블록33 엔진 → 위원 원고(코드) → 드라이브.
11/26 의장 "따로 받는 코드는 전부 싹 다 지워": 이 코드는 아무것도 받지 않는다. 자료는 수집 두 곳(collect/run.py·collect/data/supplement.py)이 드라이브에 쌓고,
가격은 10년치 데이터베이스(1_data/가격10년_*) 하나에서만 읽는다(tests/test_one_db.py가 막음).
사람·AI가 손으로 옮기거나 쓰는 단계가 없다(2026-11-17 의장).

  python meeting/daily.py                  # GitHub Actions(meeting.yml): 드라이브에서 받고 드라이브에 올림
  python meeting/daily.py --local <폴더>   # 손 시험: 그 폴더(날짜 앞머리 없는 이름)를 입력으로, 결과는 <폴더>/../원고/
  --date YYYYMMDD                          # 그날 자료로 다시 만들기

드라이브: 읽기 '콜로키움 수집데이터/YYYYMMDD/'(07시), '콜로키움 수집데이터/00_퀀트입력/'(전날까지의 보조 자료·사건 로그)
          쓰기 같은 날짜 폴더 YYYYMMDD_회의원고.txt·_회의원고.md(회의실 채팅용)·_발표.json·_오늘의한종목.csv·_판정표.csv·_시장블록.csv·_사건상태.csv·_변수달력.csv,
               '최신_회의원고.txt', 00_퀀트입력/ 보조 자료"""
import argparse
import datetime as dt
import glob
import os
import shutil
import subprocess
import sys
import traceback

import pandas as pd
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)            # 11/21 의장: 저장소는 두 폴더 — collect(매일 아침 수집)·app(나머지 전부)
COLLECT = os.path.join(os.path.dirname(REPO), 'collect')
DATA = os.path.join(COLLECT, 'data')   # 데이터 수집
MKT = os.path.join(REPO, 'market')     # 블록 2 마켓 센터
QC = os.path.join(REPO, 'block33')     # 블록 3 블록33
PYPATH = os.pathsep.join([REPO, COLLECT, QC, MKT])
sys.path[:0] = [REPO, COLLECT, MKT, QC, HERE]
import qc_config as QCC  # noqa: E402  비공개 설정(blocks.yaml·종목 목록·판단 코드) 위치
import events as EVT      # noqa: E402
import personas as PER    # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
D_DATA = '콜로키움 수집데이터'
CARRY = f'{D_DATA}/00_퀀트입력'
RENAME = {'DART실적': 'DART', 'SEC실적': 'SEC'}
# 전날까지 쌓인 저장본(드라이브 00_퀀트입력 → 없으면 비공개 seed/). 보조 자료는 아침 8시 수집(supplement.py)이 갱신함
sys.path.insert(0, DATA)
import px_store as PS   # noqa: E402  10년치 데이터베이스(1_data/가격10년_*)
from store_first import SLOW, MARK   # noqa: E402
CARRY_FILES = [MARK, '유니버스.csv', 'ETF보유.csv', 'ETF멤버.csv', '1달조합.csv', '블룸버그EPS.csv', '지수밸류.csv',
               '시장위험.csv'] + sorted(SLOW)
LOG = []


def log(s):
    print(s, flush=True)
    LOG.append(s)


def drive_ok():
    try:
        import drive
        return drive.ready()
    except Exception:
        return False


KR_EVENING = {'ETF겹침_반도체', 'ETF구성', 'ETF자금', 'ETF카드', '국내수급', '시타델'}   # 저녁 8시 한국 수집(한투)이 만드는 날짜 파일


def pull_day(today, IN):
    import drive
    day = f'{D_DATA}/{today}'
    files = drive.ls(day)
    got = 0
    for f in files:
        name = f['name']
        if not name.startswith(f'{today}_') or not name.endswith(('.csv', '.txt')):
            continue
        base, ext = os.path.splitext(name[len(today) + 1:])
        data = drive.get(f'{day}/{name}')
        if data is None:
            continue
        open(f'{IN}/{RENAME.get(base, base)}{ext}', 'wb').write(data)
        got += 1
    log(f'[받기] 아침 수집 파일 {got}개 ({day})')
    # 11/25 의장 "아침 8시 미국, 저녁 8시 한국": 한국(한투) 자료는 전날 저녁 8시 수집이 전날 날짜 폴더에 둔다 → 오늘 폴더에 없는 것만 거기서
    import datetime as _dt
    have = {n for n in os.listdir(IN)}
    d0 = _dt.datetime.strptime(today, '%Y%m%d').date()
    for back in range(1, 5):
        prev = (d0 - _dt.timedelta(days=back)).strftime('%Y%m%d')
        pf = drive.ls(f'{D_DATA}/{prev}')
        if not pf:
            continue
        n_prev = 0
        for f in pf:
            name = f['name']
            base, ext = os.path.splitext(name[len(prev) + 1:])
            if not name.startswith(f'{prev}_') or base not in KR_EVENING:
                continue
            if f'{RENAME.get(base, base)}{ext}' in have:
                continue
            data = drive.get(f'{D_DATA}/{prev}/{name}')
            if data:
                open(f'{IN}/{RENAME.get(base, base)}{ext}', 'wb').write(data)
                n_prev += 1
        log(f'[받기] 오늘 폴더에 없는 {n_prev}개는 {prev} 폴더(전날 저녁 한국 수집)에서')
        break
    return got


def _seed():
    try:
        return os.path.join(QCC.private_dir(), 'seed')
    except FileNotFoundError:
        return os.path.join(HERE, 'seed')


SEED = _seed()


def pull_carry(IN, use_drive):
    have = []
    for name in CARRY_FILES:
        data = None
        if use_drive:
            import drive
            try:
                data = drive.get(f'{CARRY}/{name}')
            except Exception as e:
                log(f'[받기] {name} 드라이브 실패: {e}')
        if os.path.exists(f'{IN}/{name}'):
            continue
        if data is None and os.path.exists(f'{SEED}/{name}'):
            data = open(f'{SEED}/{name}', 'rb').read()
            log(f'[받기] {name}: 비공개 초기본(seed) 사용')
        if data is not None:
            open(f'{IN}/{name}', 'wb').write(data)
            have.append(name)
    return have


def pull_advisors(IN, use_drive):
    """외부자문사 MP(S·C): 드라이브 00_퀀트입력/외부자문사/ → 없으면 저장소 meeting/seed/외부자문사/. 엔진 orders.advisors가 읽는다."""
    os.makedirs(f'{IN}/외부자문사', exist_ok=True)
    got = 0
    if use_drive:
        import drive
        try:
            for f in drive.ls(f'{CARRY}/외부자문사'):
                if '_MP_' in f['name'] and f['name'].endswith('.csv'):
                    data = drive.get(f'{CARRY}/외부자문사/{f["name"]}')
                    if data:
                        open(f'{IN}/외부자문사/{f["name"]}', 'wb').write(data); got += 1
        except Exception as e:
            log(f'[받기] 외부자문사 드라이브 실패: {e}')
    if not got:
        for fp in glob.glob(f'{SEED}/외부자문사/*_MP_*.csv'):
            shutil.copy(fp, f'{IN}/외부자문사/'); got += 1
    log(f'[받기] 외부자문사 MP {got}개')


def _dedup_univ(fp):
    """11/23: 같은 티커가 두 번호로 두 줄이면(예: U0-1·U0-1 SPYM) 가격표 칸이 겹쳐 3-30이 멈추고 '번호 중복'이 남 → 앞 번호 한 줄만 쓴다(드라이브 원본은 그대로)."""
    U = pd.read_csv(fp, dtype=str, encoding='utf-8-sig')
    t = U['yfinance 티커']
    dup = t.notna() & t.duplicated(keep='first')
    if dup.any():
        log('[받기] 유니버스 같은 티커 두 줄 → 뒤 번호 뺌: ' + ', '.join(f"{n}({k})" for n, k in zip(U.loc[dup, '번호'], t[dup])))
        U = U.loc[~dup]
    import layers   # 11/25 새 층(U0~U7·K0~K5) → 분석 묶음(S0~S6) 규칙은 collect/layers.py 한 곳
    layers.apply(U).to_csv(fp, index=False, encoding='utf-8-sig')


def pull_univ(IN):
    """유니버스: 10년치 데이터베이스 칸 하나(1_data/가격10년_유니버스, 11/26 의장 "하나로 통일해"), 없으면 이어 쓰는 사본."""
    import drive
    try:
        U = PS.universe(drive, log)
        if len(U) and '층' in U:
            U.to_csv(f'{IN}/유니버스.csv', index=False, encoding='utf-8-sig'); log(f'[받기] 유니버스 데이터베이스 칸 {len(U)}줄')
            _dedup_univ(f'{IN}/유니버스.csv')
            return
    except Exception as e:
        log(f'[받기] 유니버스 드라이브 실패: {e}')


def pull_db(IN):
    """10년치 데이터베이스(1_data/가격10년_시가·고가·저가·종가·거래량) → IN. 블록33·위원 원고는 PS.frame으로 여기서만 가격을 읽는다."""
    import drive
    want = [PS.name(k) for k in list(PS.F) + ['EPS']]   # 시가·고가·저가·종가·거래량 + EPS 칸(PER = 종가 ÷ EPS)
    got = [nm for nm in want if _save(drive.get(f'{D_DATA}/1_data/{nm}'), f'{IN}/{nm}')]
    log(f'[받기] 10년치 데이터베이스 {len(got)}/{len(want)}개')
    if PS.fetch(drive, '이익추정', IN, log):   # 미국 이익 추정치(매일 아침 그날 값)
        log('[받기] 이익추정 칸')
    if PS.fetch(drive, '투자의견', IN, log):   # 11/26 의장 "최근 일주일 보고서만": 한국 종목 증권사 보고서(엔진 '이익 추정치 하향'이 7일 것만 봄)
        log('[받기] 투자의견 칸')
    return got


def _save(b, p):
    if b:
        open(p, 'wb').write(b)
    return bool(b)


def backtest(W, IN, use_drive, tday, B, S):
    """11/19 의장: 블록 성적표·조합 시험(block33/backtest.py). 매 회의(11/26 의장: 지난주들은 금요일 그대로, 이번 주는 그날 가격으로 그날까지).
    11/26 의장 "10년치 하나에 넣으라니까": 블록 점수·N주 뒤 수익은 10년치 데이터베이스 칸(1_data/가격10년_블록점수.csv.gz)에 두고 새 날짜·빈 칸만 계산."""
    cache = f'{IN}/{PS.name("블록점수")}'
    S.to_csv(f'{W}/out_판정표.csv', index=False, encoding='utf-8-sig')   # 오늘 후보는 엔진 '후보'만
    if os.environ.get('SKIP_BACKTEST'):   # 11/26 의장 "10년치를 다 돌린다고? 필요한 부분만": 성적표(21분)는 원고에서 빼고 지난 결과 칸만 읽음
        if use_drive:
            import drive
            if PS.fetch(drive, '블록성적', IN, log):
                import gzip
                open(f'{IN}/블록성적.csv', 'wb').write(gzip.decompress(open(f'{IN}/{PS.name("블록성적")}', 'rb').read()))
        log('[성적표] 이번 원고에서는 건너뜀(지난 결과 ' + ('있음' if os.path.exists(f'{IN}/블록성적.csv') else '없음') + ')')
        return {}
    try:
        os.makedirs(f'{IN}/장기', exist_ok=True)   # 가격은 10년치 데이터베이스(IN/가격10년_*)를 그대로 씀
        if use_drive:   # 11/26 의장 "10년치 저장본 밖에 따로 있는 과거 자료들을 저장본에 합치시오": 블록 점수·재무·수급·13F·공매도·ETF 좌수는 저장본 칸
            import drive   # 칸이 아직 없으면 PS.fetch가 옛 파일을 칸으로 옮기고 옛 파일은 휴지통(11/26 의장 "옛 파일을 지우고")
            for k in ('블록점수', '조합시험', 'SEC재무', 'DART재무', '국내수급', '13F', '공매도', 'ETF좌수'):
                log(f'[성적표] 저장본 {PS.name(k)} ' + ('받음' if PS.fetch(drive, k, IN, log) else '없음'))
        r = subprocess.run([sys.executable, '-W', 'ignore', f'{QC}/backtest.py', IN], cwd=W, capture_output=True, text=True, timeout=5400, env={**os.environ, 'PYTHONPATH': PYPATH})
        if r.returncode != 0:
            raise RuntimeError((r.stderr.strip().splitlines() or ['?'])[-1])
        log('[성적표] ' + ' | '.join(l for l in r.stdout.strip().splitlines() if l.startswith(('날짜 ', 'N주', '이력에', '블록·칸')))[:400])
        out = {k: open(f'{W}/{k}', 'rb').read() for k in ('블록성적.csv', '조합시험.csv', '조합후보_오늘.csv') if os.path.exists(f'{W}/{k}')}
        if os.path.exists(f'{W}/블록성적.csv'):   # 뚜지(블록 정확도)가 읽음 — 매 회의 새로 계산하므로 따로 저장하지 않음
            shutil.copy(f'{W}/블록성적.csv', f'{IN}/블록성적.csv')
            if use_drive:   # 다음 원고가 다시 계산하지 않도록 10년치 데이터베이스 칸(가격10년_블록성적)에 둠
                import drive, gzip
                drive.put(f'{D_DATA}/1_data/{PS.name("블록성적")}', gzip.compress(open(f'{W}/블록성적.csv', 'rb').read()))
        if use_drive and os.path.exists(cache):
            import drive
            drive.put(f'{D_DATA}/1_data/{PS.name("블록점수")}', open(cache, 'rb').read())
            wc = f'{IN}/{PS.name("조합시험")}'
            if os.path.exists(wc):
                drive.put(f'{D_DATA}/1_data/{PS.name("조합시험")}', open(wc, 'rb').read())
        return out
    except Exception as e:
        log(f'[성적표] 실패 → 건너뜀: {str(e)[:160]}')
        return {}


def bottom(W, use_drive, B, S):
    """하위 블록 2-12 바닥 확률(11/21 의장: 연구된 모형으로) — Lunde & Timmermann(2004) 위험률 모형(market/lt_bottom.py,
    하락 구간 판정은 R bbdetection 필터 그대로). 출력 바닥확률.csv(나스닥100·S&P500 한 줄씩). 2-13 조정 단계표는 그대로."""
    try:
        X = set(B.get('_꺼짐', []))   # 하위 블록 2-12 바닥 확률 · 2-13 조정 단계
        if '2-12' not in X:
            try:
                import lt_bottom as LB
                T = LB.hazard_today(cfg=(B.get('바닥') or {}).get('하락구간'))
                T.to_csv(f'{W}/바닥확률.csv', index=False, encoding='utf-8-sig')
                for _, r in T.iterrows():
                    log(f"[바닥] {r['기준지수']} 이번 하락의 바닥일 확률 {r.get('확률')}% (낙폭 {r.get('지금낙폭')}%, {r.get('주수')}주) · 검정 AUC {r.get('검정_AUC')}")
            except Exception as e:   # noqa: BLE001
                log(f'[바닥] 실패: {str(e)[:160]}')
        try:   # 11/23 의장(11/20 금요일 놓침): 분할 매수 판정(market/buy_plan.py)도 매일 → 블록2 gate가 읽음
            import buy_plan as BP
            J = BP.judge()
            pd.DataFrame([dict(지수=r['지수'], 판정=r['판정'], 켜진수=r['켜진수'], 전체=r['전체'], 기준=r['기준'], 낙폭=round(r['낙폭'], 1),
                               사례=(r['근거'] or {}).get('사례'), 이김=(r['근거'] or {}).get('이김'), 수익중앙값=(r['근거'] or {}).get('수익중앙값'),
                               신호=(r['근거'] or {}).get('신호'), 남은조건=' · '.join(k for k, v in (r['켜짐'] or {}).items() if not v), 날짜=J['날짜']) for r in J['지수']]).to_csv(f'{W}/분할판정.csv', index=False, encoding='utf-8-sig')
            for r in J['지수']:
                log(f"[분할판정] {r['지수']} {r['판정']} (Opportunity Block {r['켜진수']}/{r['전체']}, 기준 {r['기준']})")
        except Exception as e:   # noqa: BLE001
            log(f'[분할판정] 실패: {str(e)[:160]}')
        for idx in (('^GSPC', '^NDX') if '2-13' not in X else ()):
            try:   # 11/20 의장: 조정 단계표(5·10·15·20·30%, 1년 횟수, 다음 단계 확률, 처음 닿은 날 사면 수익률)
                import correction as COR
                COR.run(W, idx, (B.get('바닥') or {}).get('조정'))
            except Exception as e:   # noqa: BLE001
                log(f'[조정단계] {idx} 실패: {str(e)[:120]}')
        for idx in ('^KS11', '^KQ11') if '2-13' not in X else ():   # 11/20 의장: 국내도 — 조정 단계표는 코스피·코스닥도
            try:
                import correction as COR   # 11/20 의장: 한국 단계 = 미국 단계 × 변동성 비율(창 길이는 비공개 결론 '한국_배수_년')
                COR.run(W, idx, {**((B.get('바닥') or {}).get('조정') or {}), '한국_배수_년': (B.get('결론') or {}).get('한국_배수_년')})
            except Exception as e:   # noqa: BLE001
                log(f'[조정단계] {idx} 실패: {str(e)[:120]}')
        return {os.path.basename(k): open(k, 'rb').read() for k in glob.glob(f'{W}/바닥확률*.csv') + glob.glob(f'{W}/분할판정*.csv') + glob.glob(f'{W}/조정*.csv')}
    except Exception as e:
        log(f'[바닥] 실패 → 건너뜀: {str(e)[:160]}')
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date'); ap.add_argument('--local')
    ap.add_argument('--session', default='국장전', choices=['국장전', '미장전'])   # 11/19 의장: 10시 국장전·22시 미장전
    a = ap.parse_args()
    now = dt.datetime.now(KST)
    today = a.date or now.strftime('%Y%m%d')
    tday = dt.date(int(today[:4]), int(today[4:6]), int(today[6:]))
    use_drive = not a.local and drive_ok()
    if not a.local and not use_drive:
        sys.exit('DRIVE_URL·DRIVE_TOKEN이 없어 드라이브를 쓸 수 없습니다(--local 로 시험).')
    if a.local:
        IN = os.path.abspath(a.local); W = os.path.dirname(IN); OUT = os.path.join(W, '원고')
    else:
        W = os.path.join(REPO, 'work_meeting'); IN = os.path.join(W, 'in'); OUT = os.path.join(W, 'out')
        shutil.rmtree(W, ignore_errors=True)
        os.makedirs(IN)
    os.makedirs(OUT, exist_ok=True)
    os.environ['MKT_STORE'] = f'{IN}/시장위험.csv'   # 11/25 의장: 블록은 지수를 이 저장본에서만 읽음(app/market/stored.py)
    R = yaml.safe_load(open(f'{HERE}/rules.yaml', encoding='utf-8'))
    B = QCC.load_blocks()
    if B.get('결론'):   # 11/20 의장 결론 칸 규칙 숫자는 비공개 blocks.yaml에만(공개 저장소에 매수 규칙 숫자를 두지 않음)
        R['결론'] = B['결론']
    if B.get('의장 장기 후보') and R.get('결론'):   # 11/20 의장 장기 후보(번호 목록), 결론 칸에 매일 낙폭·PER 위치 표시
        R['결론'] = {**R['결론'], '장기후보': B['의장 장기 후보']}
    if B.get('엘피스_200일선'):   # 11/20 의장: 200일선 근처(하단~상단)만 싼 눌림, 하단 아래 = 추세 무너짐. 문턱은 비공개
        R['엘피스_200일선'] = B['엘피스_200일선']
    carry_up = []
    if use_drive:
        if not pull_day(today, IN):
            sys.exit(f'{today} 07시 파일이 드라이브에 없습니다.')
        pull_univ(IN)
        pull_db(IN)
    pull_carry(IN, use_drive)
    if use_drive:   # 11/23 의장 "PER 찾아봐" → 우리 수집(b09_valuation)이 매주 토요일 S&P500 구성종목 503개 선행 EPS를 합산한 00_지수선행PE.csv를 먼저 쓴다
        try:
            import drive
            if PS.fetch(drive, '지수선행PE', IN, log):   # 10년치 데이터베이스 칸(11/26, 옛 00_누적 파일은 옮기고 휴지통)
                import gzip as _gz
                open(f'{IN}/지수선행PE.csv', 'wb').write(_gz.decompress(open(f'{IN}/{PS.name("지수선행PE")}', 'rb').read()))
                log('[받기] 지수선행PE (데이터베이스 칸, 구성종목 합산)')
        except Exception as e:   # noqa: BLE001
            log(f'[받기] 지수선행PE.csv 실패: {e}')
    if not os.path.isdir(f'{IN}/외부자문사'):
        pull_advisors(IN, use_drive)

    # 1) 사건상태·변수달력(규칙)
    note = []
    try:
        old = pd.DataFrame(columns=EVT.LOG_COLS)
        if use_drive:
            import drive, io
            raw = drive.get(f'{CARRY}/00_사건로그.csv')
            if raw:
                old = pd.read_csv(io.BytesIO(raw), encoding='utf-8-sig')
        logdf = EVT.update_log(old, EVT.news_csv_rows(IN, R, tday), tday)   # RSS는 수집(supplement.py)이 로그에 쌓아 둠
        EV = EVT.event_state(R, logdf, tday)
        CAL = EVT.calendar(R, IN, tday)
        EV.to_csv(f'{IN}/사건상태.csv', index=False, encoding='utf-8-sig')
        CAL.to_csv(f'{IN}/변수달력.csv', index=False, encoding='utf-8-sig')
        logdf.to_csv(f'{W}/00_사건로그.csv', index=False, encoding='utf-8-sig')
        log(f'[사건] 사건로그 {len(logdf)}줄, 진행 중 사건 {EV["사건"].nunique() if len(EV) else 0}개, 변수 {len(CAL)}줄(확정 {int((CAL["확정"] == "예").sum()) if len(CAL) else 0})')
    except Exception as e:
        traceback.print_exc(); log(f'[사건] 실패 → 사건·변수 없이 진행: {e}')
        EV, CAL = pd.DataFrame(columns=['업종', '사건', '상태', '날짜', '출처']), pd.DataFrame()

    # 3) 엔진
    import engine as ENG
    S, D, M, m = ENG.run(IN)
    import features as F
    f = F.stocks(IN)
    if F.MISSING:   # 11/21 의장 '병렬식': 빠진 자료는 그 칸만 비우고 원고는 만든다
        log('[빠진 자료] ' + ' / '.join(f'{k}({v})' for k, v in F.MISSING.items()))
    BAND = pd.DataFrame()
    try:   # 11/20 의장 '어느 가격이 적당한가, 블록 조합으로' → 가격대.csv(결론 칸이 읽음)
        if '3-28' in B.get('_꺼짐', []):
            raise RuntimeError('하위 블록 3-28 가격대 꺼짐')
        import price_band as PB
        BAND = PB.run(S, ENG.run.last_f, B)
        BAND.to_csv(f'{IN}/가격대.csv', index=False, encoding='utf-8-sig')
        log(f"[가격대] {len(BAND)}종목")
    except Exception as e:   # noqa: BLE001
        log(f'[가격대] 실패: {e}')
    log(f"[엔진] {S['추천'].value_counts().to_dict()}")
    # 11/26 의장 "뭘 금요일만 하냐. 그날 가격 가지고 그 주를 평가하면 되잖아": 성적표(하위 블록 5-1)는 매 회의 돈다.
    # 지난 주들은 10년치 데이터베이스(가격10년_블록점수)에 이어 두고, 이번 주는 오늘 가격으로 다시 매긴다(backtest.py).
    BTO = backtest(W, IN, use_drive, tday, B, S) if '5-1' not in B.get('_꺼짐', []) else {}
    BTO.update(bottom(W, use_drive, B, S))

    # 4) 위원 원고
    c, sec = PER.build(IN, S, M, m, f, R, B.get('추천', {}), tday, EV, CAL, session=a.session)
    if m.get('CASH_SWITCH') == 1 or m.get('CTM_RED') == 1:   # 11/22 의장 1순위: CTM 빨간불 또는 MA 클러스터 빨간불이면 원고 맨 위에 현금 전환
        ls = [PER.L('🔴 CTM 빨간불', f"S&P CTM {m.get('CTM_SPX')} (30 아래 {m.get('CTM_LOW_WEEKS')}주 연속)", '블록33 B01 CTM_RED')] if m.get('CTM_RED') == 1 else []
        ls += [PER.L('🔴 MA 클러스터 빨간불', f"S&P 주봉이 50~75주선 맨 아래 {m.get('MA_CLUSTER_BOT')} 밑 + 가운데 4주 기울기 {m.get('MA_CLUSTER_SLOPE')}%", '블록33 B01 MA_CLUSTER_RED')] if m.get('MA_CLUSTER_RED') == 1 else []
        sec.insert(0, ('0 현금 전환', '블록33 B01', '시장', ls + [PER.L('결론', '모든 분석을 멈추고 현금 전환', '11/22 의장 1순위 규칙')], [], ''))   # 11/24: 줄은 L(제목·사실·근거) — 글자 줄이면 원고 만들기가 멈춤
    elif m.get('CTM_GREEN') == 1:   # 11/22 의장: CTM이 내려왔다가 다시 오르기 시작하면 초록불
        # 11/26 의장 "초록불이라고 쓰지 말고, 칸을 나눠서 초록색 원이 나오도록" → 할 일 + 신호 칸 초록 원
        sec.insert(0, ('0 지수 매수 신호', '블록33 B01', '시장', [PER.L('지수 매수 신호 (CTM 반등 시작)', f"지수 적극 매수 — {m.get('CTM_GREEN_STAGE')}단계/3",
                                                               val=f"지수 적극 매수 — {m.get('CTM_GREEN_STAGE')}단계/3", chg=f"S&P CTM {m.get('CTM_SPX')}",
                                                               crit='CTM 최저 뒤 처음 오른 주부터 3주 동안 1/3씩', why='블록33 B01 CTM_GREEN(뜻은 4 엔진 블록 센터 1번)', sig='green')], [], ''))
    PFX = f'{today}_' if a.session == '국장전' else f'{today}_미장전_'
    if a.session == '미장전':
        try:   # 저녁 8시 수집(supplement.py 저녁)이 날짜 폴더에 둔 미장전 시세
            Q = pd.read_csv(f'{IN}/미장전시세.csv', encoding='utf-8-sig')
        except Exception:   # noqa: BLE001
            Q = pd.DataFrame(columns=['이름', '티커', '값', '전일대비(%)', '시각']); log('[미장전 시세] 날짜 폴더에 없음')
        # 11/20 23:39 의장: 미스터 마켓은 1번(0번 칸 없앰) — 미장전 시세를 '1 시장' 칸 맨 앞에 붙인다
        pm = PER.premarket(c, Q, tday)
        i1 = next((i for i, x in enumerate(sec) if x[0] == '1 시장'), None)
        if i1 is None:
            sec.insert(0, ('1 시장', '미스터 마켓', '마켓 센터장 · 시장', pm, [], ''))
        else:
            t, w, r, ls, g, tb = sec[i1]
            sec[i1] = (t, w, r, pm + ls, g, tb)
        note.insert(0, '미장전 회의 — 저녁 8시 수집까지 쌓인 데이터베이스로 엔진 다시 실행')
    # 11/20 의장 블록 1~5 재편: 블록 2 phase(국면.csv) · 블록 3 Analysis(종목점수.csv) 출력 — 다음 블록은 이 파일만 읽는다
    BLK = {}
    try:
        import market.run as PH
        G2, ex2 = PH.build(IN, W, B, m, M, c)
        BLK['2_phase/국면.csv'] = G2
        BLK.update({f'2_phase/{k}': v for k, v in ex2.items()})
        log(f"[블록2] 국면: " + ' / '.join(f"{r['시장']} {r['결론(2-16)'] or r['방어 국면(2-14)']}" for _, r in G2.iterrows()))
    except Exception as e:   # noqa: BLE001
        log(f'[블록2] 실패: {str(e)[:160]}')
    try:
        from block33 import b3_scores as B3
        BLK['3_analysis/종목점수.csv'] = B3.build(S, B)
        log(f"[블록3] 종목점수 {len(BLK['3_analysis/종목점수.csv'])}종목")
    except Exception as e:   # noqa: BLE001
        log(f'[블록3] 실패: {str(e)[:160]}')
    if '3-30' not in B.get('_꺼짐', []):   # 11/20 의장 '따로 집계': 바닥 기법은 종목점수에 섞지 않고 갈래별 한 표 집계만
        try:
            from block33 import b3_30_votes as B330
            T30 = B330.today(pd.read_csv(f'{IN}/유니버스.csv', dtype=str, encoding='utf-8-sig'))
            if T30 is not None and len(T30):
                BLK['3_analysis/바닥신호집계.csv'] = T30
                log(f"[3-30] 바닥 신호 집계 {len(T30)}종목, 최다 표 {T30['바닥 신호(표)'].max()}")
        except Exception as e:   # noqa: BLE001
            log(f'[3-30] 실패: {str(e)[:160]}')
    log('[원고 만든 자료] ' + ' | '.join(note))   # 11/20 23:39 의장: 원고 첫 줄 자료 메모는 회의에 필요 없음 → 로그에만
    head = ''
    txt = PER.render_txt(sec, tday, c.picks, head)
    js = PER.render_json(sec, tday, head, getattr(c, 'state', None))
    md = PER.render_md(sec, tday, c.picks, head)
    pk = PER.picks_csv(c.picks)
    outs = {f'{PFX}회의원고.txt': txt.encode('utf-8'), f'{PFX}회의원고.md': md.encode('utf-8'), f'{PFX}발표.json': js.encode('utf-8'),
            f'{PFX}오늘의한종목.csv': pk.to_csv(index=False).encode('utf-8-sig'),
            f'{PFX}판정표.csv': S.to_csv(index=False).encode('utf-8-sig'),
            f'{PFX}가격대.csv': BAND.to_csv(index=False).encode('utf-8-sig'),
            f'{PFX}시장블록.csv': M.to_csv(index=False).encode('utf-8-sig'),
            f'{PFX}이평상태.csv': pd.DataFrame([dict(선=f'{n}주선', 상태=m.get(f'SPX_W{n}_STATE'), 선값=m.get(f'SPX_W{n}_MA'), 차이=m.get(f'SPX_W{n}_GAP')) for n in (64, 109)]).to_csv(index=False).encode('utf-8-sig'),   # 11/22 의장: 64·109주선 상태 4가지
            f'{PFX}사건상태.csv': EV.to_csv(index=False).encode('utf-8-sig'),
            f'{PFX}변수달력.csv': CAL.to_csv(index=False).encode('utf-8-sig'),
            f'{PFX}종목색인.csv': PER.ask_index(c).to_csv(index=False).encode('utf-8-sig')}
    outs.update({f'{PFX}{k}': v for k, v in BTO.items()})
    try:   # 11/22 의장 '변곡점 판': 의장이 고른 그림 9개를 원본 그대로 매일 다시 그림(스트림릿 맨 위). 조건에는 안 넣음.
        import tempfile
        from block33 import turning as TURN
        _td = tempfile.mkdtemp(); _r = TURN.draw(pd.read_csv(f'{IN}/시장위험.csv', index_col=0, parse_dates=True, encoding='utf-8-sig'), _td)
        for _n in range(1, 10):
            if os.path.exists(f'{_td}/turn_{_n}.png'):
                outs[f'{PFX}변곡점_{_n}.png'] = open(f'{_td}/turn_{_n}.png', 'rb').read()
        if os.path.exists(f'{_td}/turn_lines.csv'):   # 11/23 의장: 그림마다 대상 값·기준선 값·닿음/돌파 표
            outs[f'{PFX}변곡점_선.csv'] = open(f'{_td}/turn_lines.csv', 'rb').read()
        log('[변곡점 판] ' + ' '.join(f'{k}:{v}' for k, v in _r.items()))
    except Exception as e:   # noqa: BLE001
        log(f'[변곡점 판] 실패: {str(e)[:160]}')
    try:   # 11/26 의장 "미스 차트는 그래프로, 선도 지지선·저항선도, 큼지막하게": SPYM·QQQM·TIGER 200 그림(스트림릿 5 기술적 분석 칸)
        import tempfile
        import miss_chart as MC
        _md = tempfile.mkdtemp()
        for _i, _nm, _p in MC.draw_all(IN, R['미스 차트 지표'], _md):
            outs[f'{PFX}미스차트_{_i}.png'] = open(_p, 'rb').read()
            log(f'[미스 차트 그림] {_i} {_nm}')
    except Exception as e:   # noqa: BLE001
        log(f'[미스 차트 그림] 실패: {str(e)[:160]}')
    try:   # 11/23 의장: 시장기록 장부 — 지수 기록(올해 상승분 반납 등)을 날마다 쌓아 몇 달 뒤에도 '언제였지?'에 답함
        import records as REC
        px = {k: v for k, v in PER.LAST_PX.items() if k != '_gap'}
        if px and use_drive:
            import drive, io
            b = drive.get(f'{D_DATA}/시장기록_장부.csv')
            L0 = pd.read_csv(io.BytesIO(b), encoding='utf-8-sig') if b else None
            new = []
            for k, x in px.items():
                last = None if L0 is None or not len(L0[L0['지수'] == k]) else L0.loc[L0['지수'] == k, '날짜'].max()
                new += REC.rows_for(x, k, PER.LAST_PX.get('_gap', 20), start=None if last is None else pd.Timestamp(last) + pd.Timedelta(days=1))
            L1 = REC.merge(L0, new)
            drive.put(f'{D_DATA}/시장기록_장부.csv', L1.to_csv(index=False).encode('utf-8-sig'))
            log(f'[시장기록] 장부 {len(L1)}줄(새 {len(new)}줄)')
    except Exception as e:   # noqa: BLE001
        log(f'[시장기록] 실패: {str(e)[:160]}')
    for k, v in outs.items():
        open(f'{OUT}/{k}', 'wb').write(v)
    log(f'[원고] {len(sec)}칸, 오늘의 한 종목 {c.picks.get("센터", {}).get("종목") or "해당 없음"}')

    # 5) 드라이브
    if use_drive:
        import drive
        fail = []
        for k, v in outs.items():
            try:
                drive.put(f'{D_DATA}/{today}/{k}', v)
            except Exception as e:
                fail.append(f'{k}({e})')
        if a.session == '국장전':
            for k, v in BLK.items():   # 블록 2·3 출력: 날짜 폴더와 '최신'(블록 폴더 바로 아래) 둘 다
                b = v.to_csv(index=False).encode('utf-8-sig')
                d0, nm = k.split('/')
                for dst in (f'{D_DATA}/{d0}/{today}_{nm}', f'{D_DATA}/{d0}/{nm}'):
                    try:
                        drive.put(dst, b)
                    except Exception as e:   # noqa: BLE001
                        fail.append(f'{dst}({e})')
        try:
            drive.put(f'{D_DATA}/최신_' + ('' if a.session == '국장전' else '미장전_') + '회의원고.txt', txt.encode('utf-8'))
        except Exception as e:
            fail.append(f'최신_회의원고.txt({e})')
        for name in sorted(set(carry_up)) + ['00_사건로그.csv']:
            p = f'{W}/{name}' if name == '00_사건로그.csv' else f'{IN}/{name}'
            if os.path.exists(p):
                try:
                    drive.put(f'{CARRY}/{name}', open(p, 'rb').read())
                except Exception as e:
                    fail.append(f'{name}({e})')
        log(f'[올리기] 실패: {", ".join(fail) or "없음"}')
        try:
            drive.put(f'{D_DATA}/{today}/{PFX}회의원고_점검.txt', '\n'.join(LOG).encode('utf-8'))
        except Exception:
            pass
        if fail:
            sys.exit(1)


if __name__ == '__main__':
    main()
