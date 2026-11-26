"""11/26 의장 에이피알: DART 정기보고서 원문의 지역별 매출 표를 10년치 데이터베이스 칸(지역매출)으로."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'collect' / 'data'))


def test_region_table_parse():
    import dart_q as Q
    x = ('<P>지역별 매출 (단위: 백만원)</P><TABLE><TR><TH>구분</TH><TH>당기</TH><TH>전기</TH></TR>'
         '<TR><TD>국내</TD><TD>1,234</TD><TD>(500)</TD></TR><TR><TD>미 국</TD><TD>2,000</TD><TD>800</TD></TR>'
         '<TR><TD>합계</TD><TD>3,234</TD><TD>300</TD></TR></TABLE><TABLE><TR><TD>매출</TD></TR></TABLE>')
    T = Q.region_tables(x)
    assert len(T) == 1 and T[0][2] == '백만원'
    assert T[0][4][1] == ('미국', 2000.0, 800.0, None) and T[0][4][0][2] == -500.0
    assert Q._qend('분기보고서 (2026.09)') == '2026-09-30' and Q._qend('사업보고서 (2025.12)') == '2025-12-31'


def test_region_in_runner_and_evening():
    R = pathlib.Path(__file__).resolve().parents[1]
    assert "'1-11': 'dart_q'" in (R / 'collect' / 'data' / 'run.py').read_text(encoding='utf-8')
    assert '--only 1-11' in (R / '.github' / 'workflows' / 'kr_evening.yml').read_text(encoding='utf-8')


def test_universe_out_list():
    """11/26 의장 "sol 조선 .. 유니버스에서 지워", "새 파일 만들지 말라니까": 편출은 layers.OUT 한 곳."""
    import pandas as pd
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'collect'))
    import layers
    u = pd.DataFrame({'번호': ['K2-1', 'K2-2'], 'yfinance 티커': ['466920.KS', '463250.KS']})
    assert list(layers.apply(u)['yfinance 티커']) == ['463250.KS']


def test_universe_manage_apply():
    import pandas as pd
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'collect'))
    import universe_manage as UM
    u = pd.DataFrame({'번호': ['K2-1', 'K2-2'], 'yfinance 티커': ['466920.KS', '463250.KS']})
    v, gone, new = UM.apply(u, out={'466920.KS'}, add=[{'번호': 'K2-9', 'yfinance 티커': 'NEW.KS'}, {'번호': 'K2-2', 'yfinance 티커': '463250.KS'}])
    assert gone == ['466920.KS'] and new == ['NEW.KS'] and list(v['yfinance 티커']) == ['463250.KS', 'NEW.KS']
