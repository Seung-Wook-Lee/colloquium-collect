"""보조 자료 받기 — 아침 8시(collect.yml)·저녁 8시(kr_evening.yml) 수집 끝에서만 돈다(11/26 의장 "따로 받는 코드는 전부 싹 다 지워").
회의 코드(app/meeting/daily.py)·블록33은 여기서 드라이브에 쌓은 것만 읽고, 아무것도 받지 않는다.

  python collect/data/supplement.py 아침     # 재무·13F·공매도(SLOW, store_first 규칙) + 시장위험 + 사건 RSS
  python collect/data/supplement.py 저녁     # 시장위험 + 사건 RSS + 미장전 시세(회의 rules.yaml 미장전.시세)

드라이브: 읽기 '콜로키움 수집데이터/YYYYMMDD/'(닉스·DART·SEC), '콜로키움/포트폴리오' 최신 유니버스, 00_퀀트입력 저장본
          쓰기 00_퀀트입력/(SLOW·보조갱신일.json·시장위험.csv·00_사건로그.csv), 저녁은 YYYYMMDD/YYYYMMDD_미장전시세.csv"""
import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys

import pandas as pd
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
COLLECT = os.path.dirname(HERE)
ROOT = os.path.dirname(COLLECT)
MEET = os.path.join(ROOT, 'app', 'meeting')
sys.path[:0] = [HERE, COLLECT, MEET]
import drive  # noqa: E402
from store_first import SLOW, MARK, why_fetch  # noqa: E402

D_DATA = '콜로키움 수집데이터'
CARRY = f'{D_DATA}/00_퀀트입력'
KST = dt.timezone(dt.timedelta(hours=9))
SCRIPT = {'분기원자료.csv': 'fetch_q.py', '분기실적.csv': 'fetch_fund.py', '재무건전성.csv': 'fetch_bs.py', '연매출.csv': 'fetch_rev.py',
          'FZ점수.csv': 'fetch_fz.py', '장기펀드13F.csv': 'fetch_13f.py', '공매도.csv': 'fetch_short.py'}
assert set(SCRIPT) == SLOW, 'store_first.SLOW와 받는 스크립트 목록이 다름'
RENAME = {'DART실적': 'DART', 'SEC실적': 'SEC'}


def _get(src, dst):
    b = drive.get(src)
    if b:
        open(dst, 'wb').write(b)
    return bool(b)


def pull(IN, today):
    """오늘 날짜 폴더(닉스·DART·SEC) + 최신 유니버스 + 00_퀀트입력 저장본."""
    for f in drive.ls(f'{D_DATA}/{today}'):
        base, ext = os.path.splitext(f['name'][len(today) + 1:])
        if f['name'].startswith(f'{today}_') and RENAME.get(base, base) in ('닉스', 'DART', 'SEC'):
            _get(f'{D_DATA}/{today}/{f["name"]}', f'{IN}/{RENAME.get(base, base)}{ext}')
    names = sorted(f['name'] for f in drive.ls('콜로키움/포트폴리오') if f['name'].startswith('콜로키움100_유니버스_') and f['name'].endswith('.csv'))
    if names:
        _get(f'콜로키움/포트폴리오/{names[-1]}', f'{IN}/유니버스.csv')
    for nm in sorted(SLOW) + [MARK, '시장위험.csv', '00_사건로그.csv']:
        _get(f'{CARRY}/{nm}', f'{IN}/{nm}')


def slow(W, IN, tday):
    """재무·13F·공매도: 저장본에 없는 것이 생겼을 때만(store_first.why_fetch)."""
    try:
        mk = json.load(open(f'{IN}/{MARK}', encoding='utf-8'))
    except Exception:
        mk = {o: tday.isoformat() for o in SLOW if os.path.exists(f'{IN}/{o}')}
    up = []
    for out in sorted(SLOW):
        why = why_fetch(out, IN, mk, tday)
        if why is None:
            print(f'[보조] {out} 저장본 그대로'); continue
        bak = f'{IN}/{out}.bak'
        if os.path.exists(f'{IN}/{out}'):
            shutil.copy(f'{IN}/{out}', bak)
        r = subprocess.run([sys.executable, f'{HERE}/{SCRIPT[out]}'], cwd=W, capture_output=True, text=True, timeout=1800,
                           env={**os.environ, 'PYTHONPATH': os.pathsep.join([COLLECT, HERE])})
        if r.returncode != 0:
            if os.path.exists(bak):
                shutil.move(bak, f'{IN}/{out}')
            print(f'[보조] {out} 받기 실패({why}) → 저장본 그대로: {(r.stderr.strip().splitlines() or ["?"])[-1][:160]}')
            continue
        if os.path.exists(bak):
            os.remove(bak)
        mk[out] = tday.isoformat(); up.append(out)
        print(f'[보조] {out} 받음({why})')
    json.dump(mk, open(f'{IN}/{MARK}', 'w', encoding='utf-8'), ensure_ascii=False)
    return up + [MARK]


def risk(W):
    """시장위험.csv: 저장본 마지막 날 뒤만 덧붙임(fetch_risk_daily.py)."""
    r = subprocess.run([sys.executable, f'{HERE}/fetch_risk_daily.py'], cwd=W, capture_output=True, text=True, timeout=1800)
    print('[시장위험]', (r.stdout.strip().splitlines() or [''])[-1], (r.stderr.strip().splitlines() or [''])[-1][:160] if r.returncode else '')
    return ['시장위험.csv'] if r.returncode == 0 else []


def fetch_rss(R, timeout=20):
    """승인 매체 RSS 제목(rules.yaml RSS). 실패한 주소는 건너뛰고 이유를 돌려준다. 받기는 수집에서만(11/26 의장)."""
    import xml.etree.ElementTree as ET
    import requests
    from events import LOG_COLS, _date
    rows, fail = [], []
    for media, url in R.get('RSS', []):
        try:
            r = requests.get(url, timeout=timeout, headers={'User-Agent': 'Mozilla/5.0 (colloquium rss)'})
            r.raise_for_status()
            root = ET.fromstring(r.content)
            items = root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')
            for it in items:
                g = lambda k: (it.findtext(k) or it.findtext('{http://www.w3.org/2005/Atom}' + k) or '').strip()
                link = g('link') or (it.find('{http://www.w3.org/2005/Atom}link').get('href') if it.find('{http://www.w3.org/2005/Atom}link') is not None else '')
                day = _date(g('pubDate') or g('published') or g('updated') or g('{http://purl.org/dc/elements/1.1/}date'))
                if g('title') and day:
                    rows.append(dict(날짜=str(day), 매체=media, 제목=g('title'), 링크=link))
        except Exception as e:
            fail.append(f'{media}({type(e).__name__})')
    return pd.DataFrame(rows, columns=LOG_COLS), fail


def rss(IN, R, tday):
    """사건 RSS 제목 → 00_사건로그.csv에 덧붙임(회의는 이 로그만 읽음)."""
    import events as EVT
    try:
        old = pd.read_csv(f'{IN}/00_사건로그.csv', encoding='utf-8-sig')
    except Exception:
        old = pd.DataFrame(columns=EVT.LOG_COLS)
    new, fail = fetch_rss(R)
    EVT.update_log(old, new, tday).to_csv(f'{IN}/00_사건로그.csv', index=False, encoding='utf-8-sig')
    print(f'[사건] RSS {len(new)}건, 실패 {", ".join(fail) or "없음"}')
    return ['00_사건로그.csv']


def premarket(R):
    """미장전 시세(rules.yaml 미장전.시세): 지금 값·전일 종가 대비 → 날짜 폴더 YYYYMMDD_미장전시세.csv."""
    import yfinance as yf
    rows = []
    for name, tk in R.get('미장전', {}).get('시세', []):
        try:
            h = yf.Ticker(tk).history(period='5d', interval='1d', auto_adjust=False)['Close'].dropna()
            v, prev = float(h.iloc[-1]), (float(h.iloc[-2]) if len(h) > 1 else float('nan'))
            rows.append(dict(이름=name, 티커=tk, 값=v, **{'전일대비(%)': (v / prev - 1) * 100 if prev == prev and prev else float('nan')}, 시각=f'{h.index[-1]:%m-%d}'))
        except Exception as e:   # noqa: BLE001
            rows.append(dict(이름=name, 티커=tk, 값=float('nan'), **{'전일대비(%)': float('nan')}, 시각=''))
            print(f'[미장전 시세] {tk} 실패: {str(e)[:80]}')
    return pd.DataFrame(rows, columns=['이름', '티커', '값', '전일대비(%)', '시각'])


def main():
    when = (sys.argv[1:] or ['아침'])[0]
    if not drive.ready():
        sys.exit('DRIVE_URL·DRIVE_TOKEN 없음')
    now = dt.datetime.now(KST); today = now.strftime('%Y%m%d'); tday = now.date()
    W = os.path.join(ROOT, 'work_supplement'); IN = os.path.join(W, 'in')
    shutil.rmtree(W, ignore_errors=True); os.makedirs(IN)
    R = yaml.safe_load(open(f'{MEET}/rules.yaml', encoding='utf-8'))
    pull(IN, today)
    up = slow(W, IN, tday) if when == '아침' else []
    up += risk(W)
    up += rss(IN, R, tday)
    fail = []
    for nm in up:
        try:
            drive.put(f'{CARRY}/{nm}', open(f'{IN}/{nm}', 'rb').read())
        except Exception as e:   # noqa: BLE001
            fail.append(f'{nm}({e})')
    if when == '저녁':
        Q = premarket(R)
        drive.put(f'{D_DATA}/{today}/{today}_미장전시세.csv', Q.to_csv(index=False).encode('utf-8-sig'))
        print(f'[미장전 시세] {Q["값"].notna().sum()}/{len(Q)}')
    print(f'[올리기] {len(up)}개, 실패 {", ".join(fail) or "없음"}')
    if fail:
        sys.exit(1)


if __name__ == '__main__':
    main()
