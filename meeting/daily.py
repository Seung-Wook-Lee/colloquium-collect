"""매일 07시 수집 뒤 자동 실행: 엔진 입력 받기 → 사건·변수달력(규칙) → 보조 자료 갱신 → 퀀트센터 엔진 → 위원 원고(코드) → 드라이브.
사람·AI가 손으로 옮기거나 쓰는 단계가 없다(2026-11-17 의장).

  python meeting/daily.py                  # GitHub Actions(meeting.yml): 드라이브에서 받고 드라이브에 올림
  python meeting/daily.py --local <폴더>   # 손 시험: 그 폴더(날짜 앞머리 없는 이름)를 입력으로, 결과는 <폴더>/../원고/
  --date YYYYMMDD                          # 그날 자료로 다시 만들기
  --skip-fetch                             # 야후 보조 자료 갱신 건너뛰기(전날 것 사용)

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
REPO = os.path.dirname(HERE)
DATA = os.path.join(REPO, 'data')      # 블록 1 데이터 수집
MKT = os.path.join(REPO, 'market')     # 블록 2 마켓 센터
QC = os.path.join(REPO, 'block33')     # 블록 3 블록33
PYPATH = os.pathsep.join([REPO, QC, MKT])
sys.path[:0] = [REPO, MKT, QC, HERE]
import qc_config as QCC  # noqa: E402  비공개 설정(blocks.yaml·종목 목록·판단 코드) 위치
import events as EVT      # noqa: E402
import personas as PER    # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
D_DATA = '콜로키움 수집데이터'
CARRY = f'{D_DATA}/00_퀀트입력'
RENAME = {'DART실적': 'DART', 'SEC실적': 'SEC'}
# 매일 갱신하는 보조 자료(야후): (스크립트, 만드는 파일)
FETCH = [('fetch_px.py', '가격2년.csv'), (None, '지수2년.csv'), ('fetch_q.py', '분기원자료.csv'), ('fetch_fund.py', '분기실적.csv'),
         ('fetch_bs.py', '재무건전성.csv'), ('fetch_rev.py', '연매출.csv'), ('fetch_fz.py', 'FZ점수.csv'), ('fetch_per3.py', 'PER3년.csv'),
         ('fetch_13f.py', '장기펀드13F.csv'), ('fetch_short.py', '공매도.csv')]   # 11/19 장기 펀드 13F(B21 보너스, SEC 무료), B22 공매도 잔고(미국, 야후)
# 전날 것을 이어 쓰는 자료(드라이브 00_퀀트입력 → 없으면 저장소 meeting/seed/)
CARRY_FILES = ['유니버스.csv', 'ETF보유.csv', 'ETF멤버.csv', '1달조합.csv', '블룸버그EPS.csv', '지수밸류.csv',
               '퀀트자료.csv', 'forward_log.csv', '아침보고.txt', '고가2년.csv', '저가2년.csv', '거래량2년.csv'] + [x for _, x in FETCH]
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
    log(f'[받기] 07시 파일 {got}개 ({day})')
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


def pull_univ(IN):
    """유니버스: 드라이브 콜로키움/포트폴리오 최신 csv(층 칸이 있을 때만), 없으면 이어 쓰는 사본."""
    import drive
    try:
        names = sorted(f['name'] for f in drive.ls('콜로키움/포트폴리오') if f['name'].startswith('콜로키움100_유니버스_') and f['name'].endswith('.csv'))
        if names:
            data = drive.get(f'콜로키움/포트폴리오/{names[-1]}')
            tmp = f'{IN}/_u.csv'
            open(tmp, 'wb').write(data)
            if '층' in pd.read_csv(tmp, encoding='utf-8-sig', nrows=1).columns:
                os.replace(tmp, f'{IN}/유니버스.csv'); log(f'[받기] 유니버스 {names[-1]}')
                return
            os.remove(tmp)
    except Exception as e:
        log(f'[받기] 유니버스 드라이브 실패: {e}')


def pull_teamq(IN):
    """팀Q BLOCK20 아침보고·퀀트자료·forward_log: 워크플로가 받아 둔 team_q 폴더(TEAMQ_DIR)에서 최신 파일."""
    root = os.environ.get('TEAMQ_DIR', '')
    if not root or not os.path.isdir(f'{root}/research/daily'):
        log('[받기] 팀Q 폴더 없음 → 전날 사본 사용')
        return []
    dd = f'{root}/research/daily'
    got = []
    for pat, name in (('*_팀Q_아침보고.txt', '아침보고.txt'), ('*_퀀트자료_종목.csv', '퀀트자료.csv'), ('forward_log.csv', 'forward_log.csv')):
        fs = sorted(glob.glob(f'{dd}/{pat}'))
        if fs:
            shutil.copy(fs[-1], f'{IN}/{name}'); got.append(f'{name}←{os.path.basename(fs[-1])}')
    log('[받기] 팀Q ' + ', '.join(got))
    return [g.split('←')[0] for g in got]


def fetch(W, IN):
    """야후 보조 자료. 실패하면 전날 사본(이미 IN에 있음)을 그대로 쓴다."""
    import yfinance as yf
    done = []
    for script, out in FETCH:
        try:
            if script is None:
                px = yf.download(['^GSPC', '^KQ11', '^KS11'], period='2y', auto_adjust=True, progress=False)['Close']
                px.to_csv(f'{IN}/{out}', encoding='utf-8-sig')
            else:
                bak = f'{IN}/{out}.bak'
                if os.path.exists(f'{IN}/{out}'):
                    shutil.copy(f'{IN}/{out}', bak)
                r = subprocess.run([sys.executable, f'{DATA}/{script}'], cwd=W, capture_output=True, text=True, timeout=900, env={**os.environ, 'PYTHONPATH': PYPATH})
                if r.returncode != 0:
                    if os.path.exists(bak):
                        shutil.move(bak, f'{IN}/{out}')
                    raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else f'코드 {r.returncode}')
                if os.path.exists(bak):
                    os.remove(bak)
            done.append(out)
        except Exception as e:
            log(f'[보조 자료] {out} 갱신 실패 → 전날 사본: {str(e)[:120]}')
    log(f'[보조 자료] 갱신 {len(done)}/{len(FETCH)}')
    return done


def premarket_quotes(R):
    """미장전 시세: rules.yaml 미장전.시세의 야후 티커 지금 값·전일 종가 대비."""
    import yfinance as yf
    rows = []
    for name, tk in R.get('미장전', {}).get('시세', []):
        try:
            h = yf.Ticker(tk).history(period='5d', interval='1d', auto_adjust=False)
            h = h['Close'].dropna()
            v, prev = float(h.iloc[-1]), (float(h.iloc[-2]) if len(h) > 1 else float('nan'))
            ts = h.index[-1]
            rows.append(dict(이름=name, 티커=tk, 값=v, **{'전일대비(%)': (v / prev - 1) * 100 if prev == prev and prev else float('nan')},
                             시각=f'{ts:%m-%d}'))
        except Exception as e:   # noqa: BLE001
            rows.append(dict(이름=name, 티커=tk, 값=float('nan'), **{'전일대비(%)': float('nan')}, 시각=''))
            log(f'[미장전 시세] {tk} 실패: {str(e)[:80]}')
    return pd.DataFrame(rows, columns=['이름', '티커', '값', '전일대비(%)', '시각'])


def judge(W, S):
    """11/19 의장: 콜로키움 판단 층. 엔진(블록33) 판정표 위에서 최종 포트폴리오를 정하는 코드는 비공개(colloquium_private/gen_port.py)."""
    try:
        p = os.path.join(QCC.private_dir(), 'gen_port.py')
    except FileNotFoundError:
        p = ''
    if not os.path.exists(p):
        log('[판단] 비공개 판단 코드 없음 → 건너뜀'); return {}
    S.to_csv(f'{W}/out_판정표.csv', index=False, encoding='utf-8-sig')
    for x in glob.glob(f'{W}/추천포트폴리오_Ver.*'):
        os.remove(x)
    r = subprocess.run([sys.executable, p], cwd=W, capture_output=True, text=True, timeout=600,
                       env={**os.environ, 'PYTHONPATH': PYPATH, 'QC_PRIVATE': QCC.private_dir()})
    if r.returncode != 0:
        log('[판단] 실패: ' + (r.stderr.strip().splitlines() or ['?'])[-1][:160]); return {}
    out = {os.path.basename(x): open(x, 'rb').read() for x in glob.glob(f'{W}/추천포트폴리오_Ver.*')}
    log(f'[판단] 추천 포트폴리오 {len(out)}개 파일')
    return out


def backtest(W, IN, use_drive, tday, B, S):
    """11/19 의장: 블록 성적표·조합 시험(block33/backtest.py). 금요일(성적표.요일)만. 지난 계산(블록점수이력.csv)은 드라이브에 이어 써서 새 날짜만 계산."""
    cache = f'{W}/블록점수이력.csv'
    S.to_csv(f'{W}/out_판정표.csv', index=False, encoding='utf-8-sig')   # 오늘 후보는 엔진 '후보'만
    try:
        if use_drive:
            import drive
            raw = drive.get(f'{CARRY}/블록점수이력.csv')
            if raw:
                open(cache, 'wb').write(raw)
        r = subprocess.run([sys.executable, f'{DATA}/fetch_long.py', IN], cwd=W, capture_output=True, text=True, timeout=900, env={**os.environ, 'PYTHONPATH': PYPATH})
        if r.returncode != 0:
            raise RuntimeError('긴 가격 실패: ' + (r.stderr.strip().splitlines() or ['?'])[-1])
        r = subprocess.run([sys.executable, '-W', 'ignore', f'{QC}/backtest.py', IN], cwd=W, capture_output=True, text=True, timeout=5400, env={**os.environ, 'PYTHONPATH': PYPATH})
        if r.returncode != 0:
            raise RuntimeError((r.stderr.strip().splitlines() or ['?'])[-1])
        log('[성적표] ' + ' | '.join(r.stdout.strip().splitlines()[:2]))
        out = {k: open(f'{W}/{k}', 'rb').read() for k in ('블록성적.csv', '조합시험.csv', '조합후보_오늘.csv') if os.path.exists(f'{W}/{k}')}
        if use_drive and os.path.exists(cache):
            import drive
            drive.put(f'{CARRY}/블록점수이력.csv', open(cache, 'rb').read())
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
        return {os.path.basename(k): open(k, 'rb').read() for k in glob.glob(f'{W}/바닥확률*.csv') + glob.glob(f'{W}/조정*.csv')}
    except Exception as e:
        log(f'[바닥] 실패 → 건너뜀: {str(e)[:160]}')
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date'); ap.add_argument('--local'); ap.add_argument('--skip-fetch', action='store_true')
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
    # fetch_*.py는 'in/'·'qblocks/'를 상대 경로로 쓴다
    for link, target in (('in', IN), ('qblocks', QC)):
        lp = os.path.join(W, link)
        if os.path.abspath(lp) != target and not os.path.exists(lp):
            os.symlink(target, lp)
    R = yaml.safe_load(open(f'{HERE}/rules.yaml', encoding='utf-8'))
    B = QCC.load_blocks()
    if B.get('결론'):   # 11/20 의장 결론 칸 규칙 숫자는 비공개 blocks.yaml에만(공개 저장소에 매수 규칙 숫자를 두지 않음)
        R['결론'] = B['결론']
    if B.get('의장 장기 후보') and R.get('결론'):   # 11/20 의장 장기 후보(번호 목록), 결론 칸에 매일 낙폭·PER 위치 표시
        R['결론'] = {**R['결론'], '장기후보': B['의장 장기 후보']}
    if B.get('반대'):   # 11/20 의장 반대 의견 규칙도 비공개 blocks.yaml
        R['반대'] = B['반대']
    if B.get('엘피스_200일선'):   # 11/20 의장: 200일선 근처(하단~상단)만 싼 눌림, 하단 아래 = 추세 무너짐. 문턱은 비공개
        R['엘피스_200일선'] = B['엘피스_200일선']
    carry_up = []
    if use_drive:
        if not pull_day(today, IN):
            sys.exit(f'{today} 07시 파일이 드라이브에 없습니다.')
        pull_univ(IN)
        carry_up += pull_teamq(IN)
    pull_carry(IN, use_drive)
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
        new, fail = EVT.fetch_rss(R) if use_drive or os.environ.get('MEETING_RSS') else (pd.DataFrame(columns=EVT.LOG_COLS), ['손 시험: RSS 건너뜀'])
        logdf = EVT.update_log(old, pd.concat([new, EVT.news_csv_rows(IN, R, tday)]), tday)
        EV = EVT.event_state(R, logdf, tday)
        CAL = EVT.calendar(R, IN, tday)
        EV.to_csv(f'{IN}/사건상태.csv', index=False, encoding='utf-8-sig')
        CAL.to_csv(f'{IN}/변수달력.csv', index=False, encoding='utf-8-sig')
        logdf.to_csv(f'{W}/00_사건로그.csv', index=False, encoding='utf-8-sig')
        log(f'[사건] RSS {len(new)}건(실패 {", ".join(fail) or "없음"}), 진행 중 사건 {EV["사건"].nunique() if len(EV) else 0}개, 변수 {len(CAL)}줄(확정 {int((CAL["확정"] == "예").sum()) if len(CAL) else 0})')
    except Exception as e:
        traceback.print_exc(); log(f'[사건] 실패 → 사건·변수 없이 진행: {e}')
        EV, CAL = pd.DataFrame(columns=['업종', '사건', '상태', '날짜', '출처']), pd.DataFrame()

    # 2) 보조 자료
    if not a.skip_fetch:
        carry_up += fetch(W, IN)

    # 3) 엔진
    import engine as ENG
    S, D, M, m = ENG.run(IN)
    import features as F
    f = F.stocks(IN)
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
    BTO = backtest(W, IN, use_drive, tday, B, S) if '5-1' not in B.get('_꺼짐', []) and a.session == '국장전' and (tday.weekday() == B.get('성적표', {}).get('요일', 4) or os.environ.get('BACKTEST')) else {}
    BTO.update(bottom(W, use_drive, B, S))

    # 4) 위원 원고
    if os.path.exists(f'{IN}/아침보고.txt'):
        first = open(f'{IN}/아침보고.txt', encoding='utf-8').read().splitlines()[1:2]
        note.append('팀Q 자료 ' + (first[0][:40] if first else ''))
    c, sec = PER.build(IN, S, M, m, f, R, B.get('추천', {}), tday, EV, CAL, session=a.session)
    PFX = f'{today}_' if a.session == '국장전' else f'{today}_미장전_'
    if a.session == '미장전':
        Q = premarket_quotes(R)
        # 11/20 23:39 의장: 미스터 마켓은 1번(0번 칸 없앰) — 미장전 시세를 '1 시장' 칸 맨 앞에 붙인다
        pm = PER.premarket(c, Q, tday)
        i1 = next((i for i, x in enumerate(sec) if x[0] == '1 시장'), None)
        if i1 is None:
            sec.insert(0, ('1 시장', '미스터 마켓', '시장', pm, [], ''))
        else:
            t, w, r, ls, g, tb = sec[i1]
            sec[i1] = (t, w, r, pm + ls, g, tb)
        note.insert(0, '미장전 회의(22:00) — 07시 파일 + 야후 가격(오늘 한국 종가까지)·RSS 다시 받아 엔진 다시 실행')
        Q.to_csv(f'{IN}/미장전시세.csv', index=False, encoding='utf-8-sig')
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
            f'{PFX}사건상태.csv': EV.to_csv(index=False).encode('utf-8-sig'),
            f'{PFX}변수달력.csv': CAL.to_csv(index=False).encode('utf-8-sig'),
            f'{PFX}종목색인.csv': PER.ask_index(c).to_csv(index=False).encode('utf-8-sig')}
    outs.update({f'{PFX}{k}': v for k, v in BTO.items()})
    outs.update({(k if a.session == '국장전' else f'미장전_{k}'): v for k, v in judge(W, S).items()})
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
