"""11/26 의장: 아침 회의 발표 순서대로 코드 편성 — 칸 번호는 1부터 차례대로, 뚜지(엔진 블록 센터) 포함, 6 기타(국장)·반대 의견·종목 추천 칸은 없음."""
import ast
import pathlib
import sys

import yaml

R = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(R / 'app' / 'meeting'), str(R / 'app' / 'block33'), str(R / 'collect')]


def test_order_numbers_run_1_to_9():
    import personas as P
    nums = [int(sec.split(' ')[0]) for sec, _, _ in P.ORDER]
    assert nums == sorted(nums) and sorted(set(nums)) == list(range(1, 10))
    assert ('4 엔진 블록 센터', '뚜지(센터장)', '블록33 엔진 결과가 좋은 기업 5개') in P.ORDER


def test_rules_order_matches_code():
    import personas as P
    rules = yaml.safe_load(open(R / 'app' / 'meeting' / 'rules.yaml', encoding='utf-8'))['회의순서']
    assert [r.split(' · ')[0] for r in rules] == list(dict.fromkeys(sec for sec, _, _ in P.ORDER))


def test_removed_sections_stay_removed():
    names = {n.name for n in ast.parse((R / 'app' / 'meeting' / 'personas.py').read_text(encoding='utf-8')).body if isinstance(n, ast.FunctionDef)}
    assert not names & {'gukjang', 'objections'}


def test_functions_sit_in_presentation_order():
    src = (R / 'app' / 'meeting' / 'personas.py').read_text(encoding='utf-8')
    line = {n.name: n.lineno for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)}
    seq = ['mr_market', 'miss_citadel', 'rio', 'ttuji', 'miss_chart', 'nyx', 'miss_value', 'desks', 'elpis', 'build']
    assert [line[k] for k in seq] == sorted(line[k] for k in seq)
