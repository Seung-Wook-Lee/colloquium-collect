"""11/26 의장: 미스 차트는 SPYM·QQQM·TIGER 200 세 개만, 데이터베이스만 읽어 보조지표·그림. 종목 추천 없음."""
import pathlib
import sys

import numpy as np
import pandas as pd
import yaml

R = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(R / 'app' / 'meeting'), str(R / 'collect'), str(R / 'collect' / 'data')]


def _db(d):
    import px_store as PS
    rng = np.random.default_rng(3); n = 700; idx = pd.bdate_range('2023-06-01', periods=n)
    F = {k: {} for k in ('Open', 'High', 'Low', 'Close', 'Volume')}
    for tk, base in (('SPYM', 70), ('QQQM', 200), ('102110.KS', 40000)):
        c = base * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n))); o = c * (1 + rng.normal(0, 0.006, n))
        F['Close'][tk] = c; F['Open'][tk] = o; F['High'][tk] = np.maximum(o, c) * 1.006; F['Low'][tk] = np.minimum(o, c) * 0.994; F['Volume'][tk] = rng.integers(1e5, 1e6, n)
    for k, v in F.items():
        pd.DataFrame(v, idx).to_csv(d / PS.name(k), encoding='utf-8-sig')


def test_three_etfs_table_and_pictures(tmp_path):
    import miss_chart as MC
    _db(tmp_path)
    Rm = yaml.safe_load(open(R / 'app' / 'meeting' / 'rules.yaml', encoding='utf-8'))['미스 차트 지표']
    assert [nm for nm, _ in Rm['대상']] == ['SPYM', 'QQQM', 'TIGER 200']
    res = MC.run(str(tmp_path), Rm)
    assert all(res.values())
    cols, rows = MC.table(res)
    assert cols == ['지표', 'SPYM', 'QQQM', 'TIGER 200']
    assert {'일봉 지지', '주봉 지지', '일봉 저항', '주봉 저항', '일목 삼역'} <= {r[0] for r in rows}
    pics = MC.draw_all(str(tmp_path), Rm, str(tmp_path))
    assert len(pics) == 3 and all(pathlib.Path(p).stat().st_size > 50_000 for *_, p in pics)


def test_no_pattern_or_neckline_words():
    src = (R / 'app' / 'meeting' / 'miss_chart.py').read_text(encoding='utf-8')
    body = src.split('"""', 2)[2]   # 머리 설명 뒤 코드
    assert '넥라인' not in body and 'multi_extreme' not in body and 'head_shoulders' not in body
