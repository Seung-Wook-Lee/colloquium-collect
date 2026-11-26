"""11/26 의장: 뚜지(엔진 블록 센터)는 엔진 계산 순서대로 시장 스위치 → 시장 블록·현금 집행 여건 → 층 상대강도 →
판정·비중 한도 → 상위 5개 기업 → 블록 정확도 → 하위 블록. 시장 블록 표는 미스 리스크에서 옮김(두 번 나오지 않음)."""
import inspect
import pathlib
import sys
from types import SimpleNamespace

import pandas as pd
import yaml

R = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(R / 'app' / 'meeting'), str(R / 'app' / 'block33'), str(R / 'collect')]


def _ctx(d):
    import personas as P
    T = pd.DataFrame([dict(번호=f'U1-{i}', 종목=f'회사{i}', ticker=f'T{i}', 시장='미국' if i < 5 else '한국', 구분='개별주', 층='S1' if i % 2 else 'S4',
                           층순위=1 if i % 2 else 2, 추천='추천' if i < 3 else '관찰', 판정='후보', 순위점수=10 - i, 블록예=8, 블록수=12, 블록예비율=0.67,
                           원칙='떨어진 우량주', dd52=-0.12, PER=20, 왜='', 주문승수=0.5 if i == 1 else 1.0, 경보='쏠림(S1)' if i == 1 else '') for i in range(8)])
    M = pd.DataFrame([dict(블록='B02', 질문='바닥 즈음인가?', 공식='VIX 33.5 이상', 영문='VIX', 식='VIX >= 33.5', 값='35', 결과='통과', 방향='기회'),
                      dict(블록='B04', 질문='금리가 부담인가?', 공식='10년물 5.0% 이상(부담)', 영문='UST 10Y yield', 식='UST10 >= 5', 값='4.1', 결과='탈락', 방향='부담')])
    pd.DataFrame([dict(블록='B15', 질문='그래서, 지금 싼가?', 국면='전체', 기간='26주', 날짜수=300, 예_승률=60, 아니오_승률=50, IC평균=0.05, IC_t=3.1),
                  dict(블록='B28', 질문='너무 많이 올랐나?', 국면='전체', 기간='26주', 날짜수=300, 예_승률=45, 아니오_승률=55, IC평균=-0.02, IC_t=-1.0)]
                 ).to_csv(d / '블록성적.csv', index=False, encoding='utf-8-sig')
    Rr = yaml.safe_load(open(R / 'app' / 'meeting' / 'rules.yaml', encoding='utf-8'))
    c = SimpleNamespace(d=str(d), T=T, M=M, m={'CTM_SPX': 55.0, 'CTM_RED': 0, 'MA_CLUSTER_RED': 0, 'CTM_GREEN': 0}, R=Rr,
                        regime=lambda mk: ('평상', 0.01, 0.0, '상승'), burden_opp=lambda: (['b'], ['o', 'o2']))
    return P, c


def test_ttuji_engine_order(tmp_path):
    P, c = _ctx(tmp_path)
    lines, G, md = P.ttuji(c)
    t = [x.title for x in lines]
    order = ['지수 매수 신호 (CTM 반등 시작)', '현금 집행 여건', '미국 층 상대강도', '엔진 판정', '비중 한도(사는 금액 줄이기)', '1위 T0', '블록 정확도 상위 3개']
    assert all(k in t for k in order), t
    assert [t.index(k) for k in order] == sorted(t.index(k) for k in order)
    assert '**시장 블록' in md   # 스트림릿 신호 칩이 이 제목을 봄
    assert any(g.get('title', '').startswith('층 상대강도') for g in G)
    assert lines[0].fact == '아직 아님' and '꺼' not in ' '.join(str(x.fact) for x in lines)
    assert not any('빨간불' in x.title or '초록불' in x.title or '경고' in x.title for x in lines)   # 11/26 의장: 신호 안 나온 현금 전환 경고는 원고에서 뺌


def test_switch_green_first_and_red_only_when_fired(tmp_path):
    P, c = _ctx(tmp_path)
    c.m.update(CTM_GREEN=1, CTM_GREEN_STAGE=1)
    t = P._switch(c)
    assert t[0].title == '지수 매수 신호 (CTM 반등 시작)' and '적극 매수' in t[0].fact and 'Chande Trend Meter' in t[0].why
    assert t[0].row()['신호'] == 'green' and '초록불' not in str(t[0].row())
    c.m.update(CTM_RED=1, MA_CLUSTER_RED=1)
    tt = [x.title for x in P._switch(c)]
    assert '현금 전환 경고 (CTM)' in tt and '현금 전환 경고 (MA 클러스터)' in tt


def test_market_block_moved_out_of_miss_risk():
    import personas as P
    assert 'market_block_md' not in inspect.getsource(P.macro_table)
    assert 'burden_opp' not in inspect.getsource(P.rio)
    b = inspect.getsource(P.build)
    assert "_safe(ttuji, 3, c)" in b
