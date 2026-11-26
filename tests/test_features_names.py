"""11/26: features.stocks 안에서 _r(파일 읽기)를 다른 값으로 덮어써 원고가 UnboundLocalError로 멈춘 일 — 모듈 함수 이름을 지역 변수로 쓰지 않는다."""
import ast
import pathlib

R = pathlib.Path(__file__).resolve().parents[1]


def test_no_local_shadow_of_module_functions():
    src = (R / 'app' / 'block33' / 'features.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    top = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    bad = []
    for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id in top:
                bad.append(f'{fn.name}: {node.id} (줄 {node.lineno})')
    assert not bad, bad
