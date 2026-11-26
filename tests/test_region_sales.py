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


def test_universe_one_place():
    """11/26 의장 "하나로 통일해": 유니버스는 10년치 데이터베이스 칸(px_store.universe)만 읽는다. 옛 포트폴리오 CSV를 직접 읽는 코드 금지."""
    R = pathlib.Path(__file__).resolve().parents[1]
    bad = []
    for p in list((R / 'app').rglob('*.py')) + list((R / 'collect').rglob('*.py')):
        if p.name == 'px_store.py':
            continue
        t = p.read_text(encoding='utf-8', errors='ignore')
        if "ls('콜로키움/포트폴리오')" in t or "/포트폴리오')" in t and '콜로키움100_유니버스_' in t and 'ls(' in t:
            bad.append(str(p.relative_to(R)))
    assert not bad, bad


def test_meeting_drops_out_rows(tmp_path):
    """11/26 의장 "아직도 조선이 나오잖아": 회의가 받은 표에서 편출 종목 줄(티커·코드·이름)을 지움."""
    import pandas as pd
    R = pathlib.Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(R / "app" / "meeting"), str(R / "collect")]
    import daily
    pd.DataFrame({'ETF': ['SOL 조선TOP3플러스', 'TIGER 200'], 'v': [1, 2]}).to_csv(tmp_path / 'ETF자금.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame({'yfinance 티커': ['466920.KS', '005930.KS']}).to_csv(tmp_path / '닉스.csv', index=False, encoding='utf-8-sig')
    daily.drop_out_rows(str(tmp_path))
    assert list(pd.read_csv(tmp_path / 'ETF자금.csv', encoding='utf-8-sig')['ETF']) == ['TIGER 200']
    assert list(pd.read_csv(tmp_path / '닉스.csv', encoding='utf-8-sig')['yfinance 티커']) == ['005930.KS']
