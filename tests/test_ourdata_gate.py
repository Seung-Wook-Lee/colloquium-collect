"""app/market 분석 스크립트가 우리 자료(ourdata)를 건너뛰고 외부에서 직접 받지 못하게 막는다(11/23 의장).
외부 다운로드(yfinance·urllib·requests)가 있는 파일은 app/market/외부자료_허락.yaml에 있어야 한다. '허락 대기'는 경고만."""
import re
from pathlib import Path

import yaml

M = Path(__file__).resolve().parents[1] / 'app' / 'market'
EXT = re.compile(r'import yfinance|yf\.download|yf\.Ticker|urllib\.request|requests\.get')
SKIP = {'ourdata.py', 'buy_plan.py', 'run.py', 'canary.py', 'correction.py', 'lt_bottom.py'}   # 매일 원고·수집 흐름에서 그날 받는 모듈(분석 스크립트 아님)


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
