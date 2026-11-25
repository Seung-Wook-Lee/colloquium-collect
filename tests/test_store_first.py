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
    for p in (R / 'collect' / 'data' / 'fetch_px.py', R / 'collect' / 'data' / 'fetch_risk_daily.py', R / 'collect' / 'data' / 'b1_1_prices.py', R / 'app' / 'meeting' / 'daily.py'):
        L = p.read_text(encoding='utf-8').splitlines()
        for i, ln in enumerate(L):
            if not LONG.search(ln) or ln.lstrip().startswith('#'):
                continue
            prev = next((x.strip() for x in reversed(L[:i]) if x.strip()), '')
            if not (re.search(r'\bNEW\b|\bif\b|\belse\b', ln) or prev.endswith('else:')):
                bad.append(f'{p.name}:{i + 1}')
    assert not bad, f'저장본이 있어도 긴 기간을 받는 줄: {bad}'


def _mk_in(tmp, today, filing=None, extra_uni=()):
    pd.DataFrame({'번호': ['U1-4', 'K1-9', *extra_uni], '구분': '개별주', '시장': '미국', 'yfinance 티커': ['NVDA', '005930.KS', *extra_uni]}).to_csv(tmp / '닉스.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame({'번호': ['U1-4', 'K1-9'], '매출': [1, 2]}).to_csv(tmp / '분기원자료.csv', index=False, encoding='utf-8-sig')
    if filing:
        pd.DataFrame({'번호': ['K1-9'], '잠정 공시일': [filing]}).to_csv(tmp / 'DART.csv', index=False, encoding='utf-8-sig')
    mk = {'분기원자료.csv': today.isoformat()}
    (tmp / SF.MARK).write_text(json.dumps(mk), encoding='utf-8')
    return mk


def test_why_fetch(tmp_path):
    today = dt.date(2026, 11, 25)
    mk = _mk_in(tmp_path, today)
    assert SF.why_fetch('분기원자료.csv', tmp_path, mk, today) is None                     # 다 있음 → 저장본 그대로
    assert SF.why_fetch('연매출.csv', tmp_path, mk, today) == '저장본 없음'
    mk = _mk_in(tmp_path, today, extra_uni=('U9-9',))
    assert SF.why_fetch('분기원자료.csv', tmp_path, mk, today).startswith('새 종목')
    mk = _mk_in(tmp_path, today - dt.timedelta(days=3), filing='2026-11-24')
    assert SF.why_fetch('분기원자료.csv', tmp_path, mk, today).startswith('새 실적 공시')
    mk = _mk_in(tmp_path, today, filing='2026-11-20')                                      # 받은 뒤 새 공시 없음
    assert SF.why_fetch('분기원자료.csv', tmp_path, mk, today) is None


def test_px_store_appends_only(tmp_path):
    """11/25 의장 "매일매일 그날 자료만 받아오고, 구글 드라이브에 쌓고": 저장본 10년치에 새 날짜만 붙고, 과거치는 그대로."""
    sys.path.insert(0, str(R / 'collect' / 'data'))
    import px_store as PS
    idx = pd.bdate_range('2016-01-04', '2026-11-24')
    B = {k: pd.DataFrame({'NVDA': 100.0, 'OLD': 5.0}, index=idx) for k in ('Open', 'High', 'Low', 'Close', 'Volume')}
    PS.save(B, tmp_path)
    B = PS.load(tmp_path)
    assert PS.start(B) == dt.date(2026, 11, 21)                       # 마지막 날 3일 전부터만 받음
    assert PS.missing(B, ['NVDA', 'GEV']) == ['GEV']                  # 저장본에 없는 종목만 과거치
    nd = pd.bdate_range('2026-11-21', '2026-11-25')
    N = {k: pd.DataFrame({'NVDA': 100.0}, index=nd) for k in ('High', 'Low', 'Close', 'Volume')}
    N['Close'].loc['2026-11-25', 'NVDA'] = 110.0
    M = PS.merge(B, N)
    assert M['Close'].index.min() == idx.min() and M['Close'].index.max() == pd.Timestamp('2026-11-25')
    assert M['Close'].loc['2026-11-25', 'NVDA'] == 110.0 and M['Close'].loc['2020-01-02', 'NVDA'] == 100.0
    assert M['Close']['OLD'].dropna().index.max() == pd.Timestamp('2026-11-24')   # 빠진 종목 과거치는 지우지 않음
    assert M['Open'].loc['2026-11-24', 'NVDA'] == 100.0                # 새로 안 받은 칸은 저장본 그대로
    N2 = {'Close': pd.DataFrame({'NVDA': 50.0}, index=nd)}            # 2:1 분할 → 저장본 과거치를 같은 비율로
    M2 = PS.merge(PS.load(tmp_path), N2, log=lambda s: None)
    assert M2['Close'].loc['2020-01-02', 'NVDA'] == 50.0 and M2['Volume'].loc['2020-01-02', 'NVDA'] == 200.0
    two = PS.two_years(M, tmp_path, ['NVDA'])
    P2 = pd.read_csv(tmp_path / '가격2년.csv', index_col=0, parse_dates=True)
    assert '가격2년.csv' in two and P2.index.min() >= pd.Timestamp('2024-11-20') and list(P2.columns) == ['NVDA']


def test_no_full_redownload():
    """일요일 10년치 통째 받기 금지: 가격 받는 코드는 저장본(px_store)을 읽어야 한다."""
    for p in ('b1_1_prices.py', 'fetch_px.py'):
        src = (R / 'collect' / 'data' / p).read_text(encoding='utf-8')
        assert 'px_store' in src and 'PS.start(' in src and 'PS.missing(' in src, p
