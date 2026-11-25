"""11/26 의장 "이미 다 되어 있는 계산을 왜 다시 하는 거지", "10년치 하나에 넣으라니까", "왜 자꾸 CSV 파일을 추가하나":
블록 점수·N주 뒤 수익은 10년치 데이터베이스 칸(가격10년_블록점수)에만 두고, 이미 있는 칸은 다시 계산하지 않는다. 새 CSV 저장본을 만들지 않는다."""
import pathlib
import re
import sys

import numpy as np
import pandas as pd

R = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(R / 'app' / 'block33'), str(R / 'collect')]


def test_fast_ic_equals_slow():
    import backtest as BT
    rng = np.random.default_rng(1)
    Z = pd.DataFrame(dict(날짜=np.repeat(pd.bdate_range('2020-01-03', periods=40, freq='W-FRI').date, 25),
                          B15=rng.random(1000), **{'4주': rng.normal(size=1000)}))
    Z.loc[::7, 'B15'] = 0.5   # 같은 값(순위 동률)도
    slow = Z.groupby('날짜').apply(lambda g: g['B15'].rank().corr(g['4주'].rank()), include_groups=False).dropna()
    fast = BT._ic_by_date(Z, 'B15', '4주')
    assert np.allclose(slow.sort_index().values, fast.sort_index().values)


def test_backtest_uses_block33_hist_short():
    """collect/data/hist_short.py(FINRA 받기)가 블록33 hist_short.py를 가리면 성적표가 받기를 시작한다(회의 코드는 받지 않음)."""
    import backtest as BT
    assert BT.HSH.__file__.replace('\\', '/').endswith('app/block33/hist_short.py')


def test_scores_live_in_ten_year_db_no_new_csv():
    src = (R / 'app' / 'block33' / 'backtest.py').read_text(encoding='utf-8')
    assert "PS.name('블록점수')" in src and '블록점수이력.csv' not in src.split('"""', 2)[2]
    assert "need = Z[hk].isna().any(axis=1)" in src   # N주 뒤 수익은 빈 칸만
    dl = (R / 'app' / 'meeting' / 'daily.py').read_text(encoding='utf-8')
    assert "drive.put(f'{D_DATA}/1_data/{PS.name(\"블록점수\")}'" in dl
    assert not re.search(r"drive\.put\(f'\{CARRY\}/(블록점수이력|블록성적|블록IC이력|조합시험)\.csv'", dl)
