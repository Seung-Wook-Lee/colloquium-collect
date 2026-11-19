"""매일 07시 수집 뒤 자동 실행: 엔진 입력 받기 → 사건·변수달력(규칙) → 보조 자료 갱신 → 퀀트센터 엔진 → 위원 원고(코드) → 드라이브.
사람·AI가 손으로 옮기거나 쓰는 단계가 없다(2026-11-17 의장).

  python meeting/daily.py                  # GitHub Actions(meeting.yml): 드라이브에서 받고 드라이브에 올림
  python meeting/daily.py --local <폴더>   # 손 시험: 그 폴더(날짜 앞머리 없는 이름)를 입력으로, 결과는 <폴더>/../원고/
  --date YYYYMMDD                          # 그날 자료로 다시 만들기
  --skip-fetch                             # 야후 보조 자료 갱신 건너뛰기(전날 것 사용)

드라이브: 읽기 '콜로키움 수집데이터/YYYYMMDD/'(07시), '콜로키움 수집데이터/00_퀀트입력/'(전날까지의 보조 자료·사건 로그)
          쓰기 같은 날짜 폴더 YYYYMMDD_회의원고.txt·_발표.json·_오늘의한종목.csv·_판정표.csv·_시장블록.csv·_사건상태.csv·_변수달력.csv,
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
QC = os.path.join(REPO, 'quant_center')
sys.path[:0] = [REPO, QC, HERE]
import events as EVT      # noqa: E402
import personas as PER    # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
D_DATA = '콜로키움 수집데이터'
CARRY = f'{D_DATA}/00_퀀트입력'
RENAME = {'DART실적': 'DART', 'SEC실적': 'SEC'}
# 매일 갱신하는 보조 자료(야후): (스크립트, 만드는 파일)
FETCH = [('fetch_px.py', '가격2년.csv'), (None, '지수2년.csv'), ('fetch_q.py', '분기원자료.csv'), ('fetch_fund.py', '분기실적.csv'),
         ('fetch_bs.py', '재무건전성.csv'), ('fetch_rev.py', '연매출.csv'), ('fetch_fz.py', 'FZ점수.csv'), ('fetch_per3.py', 'PER3년.csv'),
         ('fetch_13f.py', '장기펀드13F.csv')]   # 11/19 장기 펀드 13F(B23 보너스), SEC 무료
# 전날 것을 이어 쓰는 자료(드라이브 00_퀀트입력 → 없으면 저장소 meeting/seed/)
CARRY_FILES = ['유니버스.csv', 'ETF보유.csv', 'ETF멤버.csv', '1달조합.csv', '블룸버그EPS.csv', '지수밸류.csv',
               '퀀트자료.csv', 'forward_log.csv', '아침보고.txt'] + [x for _, x in FETCH]
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
        if data is None and os.path.exists(f'{HERE}/seed/{name}'):
            data = open(f'{HERE}/seed/{name}', 'rb').read()
            log(f'[받기] {name}: 저장소 초기본(meeting/seed) 사용')
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
        for fp in glob.glob(f'{HERE}/seed/외부자문사/*_MP_*.csv'):
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
                r = subprocess.run([sys.executable, f'{QC}/{script}'], cwd=W, capture_output=True, text=True, timeout=900)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date'); ap.add_argument('--local'); ap.add_argument('--skip-fetch', action='store_true')
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
    B = yaml.safe_load(open(f'{QC}/blocks.yaml', encoding='utf-8'))
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
    S, D, M, m = ENG.run(IN, cfg=f'{QC}/blocks.yaml')
    import features as F
    f = F.stocks(IN)
    log(f"[엔진] {S['추천'].value_counts().to_dict()}")

    # 4) 위원 원고
    if os.path.exists(f'{IN}/아침보고.txt'):
        first = open(f'{IN}/아침보고.txt', encoding='utf-8').read().splitlines()[1:2]
        note.append('팀Q 자료 ' + (first[0][:40] if first else ''))
    c, sec = PER.build(IN, S, M, m, f, R, B.get('추천', {}), tday, EV, CAL)
    head = ' | '.join(note)
    txt = PER.render_txt(sec, tday, c.picks, head)
    js = PER.render_json(sec, tday, head)
    pk = PER.picks_csv(c.picks)
    outs = {f'{today}_회의원고.txt': txt.encode('utf-8'), f'{today}_발표.json': js.encode('utf-8'),
            f'{today}_오늘의한종목.csv': pk.to_csv(index=False).encode('utf-8-sig'),
            f'{today}_판정표.csv': S.to_csv(index=False).encode('utf-8-sig'),
            f'{today}_시장블록.csv': M.to_csv(index=False).encode('utf-8-sig'),
            f'{today}_사건상태.csv': EV.to_csv(index=False).encode('utf-8-sig'),
            f'{today}_변수달력.csv': CAL.to_csv(index=False).encode('utf-8-sig')}
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
        try:
            drive.put(f'{D_DATA}/최신_회의원고.txt', txt.encode('utf-8'))
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
            drive.put(f'{D_DATA}/{today}/{today}_회의원고_점검.txt', '\n'.join(LOG).encode('utf-8'))
        except Exception:
            pass
        if fail:
            sys.exit(1)


if __name__ == '__main__':
    main()
