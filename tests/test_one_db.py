"""11/26 의장 "따로 받는 코드는 전부 싹 다 지워", "2년치 자료도 전부 삭제하고, 딱 하나. 10년 치 자료만 남겨놔. 거기서 다 찾아서 읽을 수 있게 해."
1. 회의 코드(app/meeting)·블록33(app/block33)·시장 블록(app/market)은 아무것도 받지 않는다(야후·requests 금지). 받기는 아침 8시·저녁 8시 수집뿐.
2. 가격 사본 파일 이름(가격2년·지수2년·고가2년·00_가격이력 등)을 읽거나 만드는 코드가 없다. 가격은 px_store.frame/stocks/index/long으로만.
3. 지운 받기 코드(fetch_px·fetch_long·fetch_per3·한투 창고)가 다시 생기지 않는다."""
import re
from pathlib import Path

R = Path(__file__).resolve().parents[1]
NO_FETCH = [R / 'app' / 'meeting', R / 'app' / 'block33', R / 'app' / 'market']
NO_FETCH_OK = {'study.py', 'ask.py', 'dbmf_test.py', 'dbmf_report.py'}   # 위원 공부(의장 승인 자료 모으기)·질문 답(의장이 검색 허락할 때)·11/23 DBMF 1회 검증은 회의 준비가 아님
DL = re.compile(r'\bimport yfinance\b|\byf\.(download|Ticker)\(|\brequests\.(get|post)\(|urllib\.request\.urlopen')
COPY = re.compile(r"(가격|시가|고가|저가|거래량|지수)[25]년(\.csv)?['\"/]|00_가격이력|지수2년|PER3년\.csv")


def _py(dirs):
    for d in dirs:
        for p in d.rglob('*.py'):
            if '__pycache__' not in p.parts:
                yield p


def test_meeting_and_blocks_do_not_download():
    bad = []
    for p in _py(NO_FETCH):
        if p.name in NO_FETCH_OK:
            continue
        for i, ln in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
            if DL.search(ln) and not ln.lstrip().startswith('#'):
                bad.append(f'{p.relative_to(R)}:{i}')
    assert not bad, f'회의·블록 코드에서 직접 받는 줄(수집으로 옮길 것): {bad}'


def test_no_price_copies():
    bad = []
    for p in _py([R / 'app', R / 'collect' / 'blocks', R / 'collect' / 'data']):
        if p.name in ('rename_citadel_1125.py', 'trash_old_1126.py'):   # 옛 사본을 지우는 일회용 코드
            continue
        for i, ln in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
            if COPY.search(ln) and not ln.lstrip().startswith('#'):
                bad.append(f'{p.relative_to(R)}:{i}')
    assert not bad, f'10년치 데이터베이스 말고 가격 사본을 읽거나 만드는 줄: {bad}'


def test_removed_fetchers_stay_removed():
    for f in ('collect/data/fetch_px.py', 'collect/data/fetch_long.py', 'collect/data/fetch_per3.py', 'collect/blocks/b09_kisstore.py', 'collect/blocks/b09_heatmap.py', 'collect/heatmap.py', 'app/meeting/store_first.py'):
        assert not (R / f).exists(), f
    d = (R / 'app' / 'meeting' / 'daily.py').read_text(encoding='utf-8')
    assert 'FETCH = [' not in d and 'def fetch(' not in d and 'TEAMQ_DIR' not in d
    for w in ('meeting.yml', 'start.yml'):
        y = (R / '.github' / 'workflows' / w).read_text(encoding='utf-8')
        assert 'research/daily' not in y and 'TEAMQ_DIR' not in y and 'KIS_APP_KEY' not in y
