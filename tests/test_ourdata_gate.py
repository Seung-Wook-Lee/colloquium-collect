"""app/market 분석 스크립트가 우리 자료(ourdata)를 건너뛰고 외부에서 직접 받지 못하게 막는다(11/23 의장).
외부 다운로드(yfinance·urllib·requests)가 있는 파일은 app/market/외부자료_허락.yaml에 있어야 한다. '허락 대기'는 경고만."""
import re
from pathlib import Path

import yaml

M = Path(__file__).resolve().parents[1] / 'app' / 'market'
EXT = re.compile(r'import yfinance|yf\.download|yf\.Ticker|urllib\.request|requests\.get')
SKIP = {'ourdata.py', 'run.py', 'canary.py', 'stored.py'}   # stored.py = 저장본에 칸이 없을 때만 받는 단일 입구(11/25)


def test_external_download_needs_permission():
    allow = yaml.safe_load((M / '외부자료_허락.yaml').read_text(encoding='utf-8')) or {}
    bad, wait = [], []
    for p in sorted(M.glob('*.py')):
        if p.name in SKIP or not EXT.search(p.read_text(encoding='utf-8')):
            continue
        st = (allow.get(p.name) or {}).get('상태')
        if st == '허락':
            continue
        (wait if st == '허락 대기' else bad).append(p.name)
    if wait:
        print('[허락 대기] 외부 자료를 받는 스크립트:', ', '.join(wait))
    assert not bad, f'의장 허락 없이 외부에서 받는 스크립트: {bad} → ourdata.get()으로 바꾸거나 외부자료_허락.yaml에 허락을 적을 것'


def test_blocks_read_stored_only():
    """11/25 의장 "블록과 회의프로그램 모두 저장된 것을 쓰도록, 회의프로그램이 하루 2번 업데이트하면 블록은 그걸 가지고 계산":
    바닥 확률·분할 판정·조정 단계·시황 한 줄·베타는 지수·가격을 저장본(stored.py·가격2년)에서만 읽는다."""
    R = M.parents[1]
    bad = []
    for p in (M / 'lt_bottom.py', M / 'buy_plan.py', M / 'correction.py', R / 'app' / 'meeting' / 'personas.py'):
        for i, ln in enumerate(p.read_text(encoding='utf-8').splitlines()):
            if re.search(r'yf\.download|yf\.Ticker|import yfinance', ln) and not ln.lstrip().startswith('#'):
                bad.append(f'{p.name}:{i + 1}')
    assert not bad, f'블록이 저장본을 건너뛰고 직접 받는 줄: {bad} → stored.close()로'
