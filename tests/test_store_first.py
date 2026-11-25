"""11/25 의장 "구글 드라이브에 있는 것으로 계산한다, 라는 걸 코딩으로 심어 놓으라고. 거기 없을 때에만 뭘 받으라고."
이 시험이 그 규칙을 지킨다(app/meeting/store_first.py).
1. 회의 보조 자료(daily.FETCH)는 SLOW(저장본 우선, 없는 것만) 이거나 저장본에 새 날짜만 덧붙이는 스크립트여야 한다.
2. 가격 받는 코드에서 긴 기간(2y·3y·max) 받기는 '저장본에 없을 때' 갈래 안에만 있어야 한다.
3. why_fetch는 저장본에 없는 것이 있을 때만 이유를 낸다."""
import datetime as dt
import json
import re
import sys
from pathlib import Path

import pandas as pd

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'app' / 'meeting'))
import store_first as SF  # noqa: E402

INCREMENTAL = {None, 'fetch_px.py', 'fetch_risk_daily.py'}   # 저장본 마지막 날 뒤만 덧붙이는 스크립트(None = daily.py 안 지수)
LONG = re.compile(r"period\s*=\s*['\"](2y|3y|5y|10y|max)['\"]")


def _fetch_list():
    src = (R / 'app' / 'meeting' / 'daily.py').read_text(encoding='utf-8')
    body = src[src.index('FETCH = ['):src.index(']\n', src.index('FETCH = ['))]
    return re.findall(r"\((None|'[^']+'),\s*'([^']+)'\)", body)


def test_every_fetch_is_store_first():
    bad = []
    for script, out in _fetch_list():
        sc = None if script == 'None' else script.strip("'")
        if out not in SF.SLOW and sc not in INCREMENTAL:
            bad.append(f'{sc}→{out}')
    assert not bad, f'드라이브 저장본을 건너뛰고 매번 다시 받는 자료: {bad} → store_first.SLOW에 넣거나 저장본 뒤 날짜만 받게 고칠 것'


def test_long_downloads_only_when_missing():
    bad = []
    for p in (R / 'collect' / 'data' / 'fetch_px.py', R / 'collect' / 'data' / 'fetch_risk_daily.py', R / 'app' / 'meeting' / 'daily.py'):
        L = p.read_text(encoding='utf-8').splitlines()
        for i, ln in enumerate(L):
            if not LONG.search(ln) or ln.lstrip().startswith('#'):
                continue
            prev = next((x.strip() for x in reversed(L[:i]) if x.strip()), '')
            if not (re.search(r'\bNEW\b|\bif\b|\belse\b', ln) or prev.endswith('else:')):
                bad.append(f'{p.name}:{i + 1}')
    assert not bad, f'저장본이 있어도 긴 기간을 받는 줄: {bad}'


def _mk_in(tmp, today, filing=None, extra_uni=()):
    pd.DataFrame({'번호': ['G01', 'K01', *extra_uni], '구분': '개별주', '시장': '미국', 'yfinance 티커': ['NVDA', '005930.KS', *extra_uni]}).to_csv(tmp / '닉스.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame({'번호': ['G01', 'K01'], '매출': [1, 2]}).to_csv(tmp / '분기원자료.csv', index=False, encoding='utf-8-sig')
    if filing:
        pd.DataFrame({'번호': ['K01'], '잠정 공시일': [filing]}).to_csv(tmp / 'DART.csv', index=False, encoding='utf-8-sig')
    mk = {'분기원자료.csv': today.isoformat()}
    (tmp / SF.MARK).write_text(json.dumps(mk), encoding='utf-8')
    return mk


def test_why_fetch(tmp_path):
    today = dt.date(2026, 11, 25)
    mk = _mk_in(tmp_path, today)
    assert SF.why_fetch('분기원자료.csv', tmp_path, mk, today) is None                     # 다 있음 → 저장본 그대로
    assert SF.why_fetch('연매출.csv', tmp_path, mk, today) == '저장본 없음'
    mk = _mk_in(tmp_path, today, extra_uni=('G99',))
    assert SF.why_fetch('분기원자료.csv', tmp_path, mk, today).startswith('새 종목')
    mk = _mk_in(tmp_path, today - dt.timedelta(days=3), filing='2026-11-24')
    assert SF.why_fetch('분기원자료.csv', tmp_path, mk, today).startswith('새 실적 공시')
    mk = _mk_in(tmp_path, today, filing='2026-11-20')                                      # 받은 뒤 새 공시 없음
    assert SF.why_fetch('분기원자료.csv', tmp_path, mk, today) is None
