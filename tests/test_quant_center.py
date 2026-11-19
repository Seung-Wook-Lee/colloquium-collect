"""퀀트센터 엔진 시험: 합산(분산 승수), 메타라벨링, 단계 순서, 완성도 점검표, blocks.yaml 형식."""
import os
import sys

import numpy as np
import pandas as pd
import pytest
import yaml

QC = os.path.join(os.path.dirname(__file__), '..', 'quant_center')
sys.path.insert(0, QC)

import audit  # noqa: E402
import combine  # noqa: E402
import engine  # noqa: E402
import meta  # noqa: E402

B = yaml.safe_load(open(os.path.join(QC, 'blocks.yaml'), encoding='utf-8'))


# ---- 합산(Carver)
def test_same_blocks_get_no_diversification_bonus():
    x = np.linspace(0, 1, 50)
    R, _ = combine.combine(pd.DataFrame({'A': x, 'B': x}), {}, {})
    assert R['분산승수'].between(0.99, 1.01).all()


def test_independent_blocks_get_bonus_capped():
    rng = np.random.default_rng(0)
    SC = pd.DataFrame(rng.random((400, 4)), columns=list('ABCD'))
    R, _ = combine.combine(SC, {}, {'분산승수_상한': 2.5})
    assert R['분산승수'].median() > 1.7          # 상관 0 이면 sqrt(4) = 2
    assert R['분산승수'].max() <= 2.5
    assert R['종합점수'].abs().max() <= 20


def test_missing_block_uses_only_available_blocks():
    SC = pd.DataFrame({'A': [1.0, 0.0] * 15, 'B': [np.nan] * 30})
    R, _ = combine.combine(SC, {}, {})
    assert (R['합산블록수'] == 1).all() and (R['분산승수'] == 1).all()


def test_weight_counts():
    SC = pd.DataFrame({'A': [1.0] * 30, 'B': [0.0] * 30})
    R1, _ = combine.combine(SC, {'A': 2, 'B': 1}, {})
    R2, _ = combine.combine(SC, {'A': 1, 'B': 1}, {})
    assert R1['종합점수'].iloc[0] > R2['종합점수'].iloc[0]


# ---- 메타라벨링
def test_bet_size():
    assert meta.size(0.5) == 0 and meta.size(0.3) == 0
    assert 0 < meta.size(0.6) < meta.size(0.9) <= 1


def _px(path):
    idx = pd.bdate_range('2026-01-01', periods=len(path))
    return pd.DataFrame({'X': path}, index=idx)


def test_triple_barrier():
    up = _px(100 * np.cumprod([1] + [1.01] * 30))
    dn = _px(100 * np.cumprod([1] + [0.99] * 30))
    L = pd.DataFrame({'ticker': ['X'], '기준일': [up.index[0].strftime('%Y-%m-%d')], 'vol60': [20.0]})
    assert meta.label(L, up, 20, 1.0).iloc[0] == 1
    assert meta.label(L, dn, 20, 1.0).iloc[0] == 0
    short = _px([100, 101, 102])
    assert np.isnan(meta.label(L.assign(기준일=short.index[0].strftime('%Y-%m-%d')), short, 20, 1.0).iloc[0])


def test_meta_waits_until_enough_labels():
    P = _px(np.linspace(100, 110, 30))
    S = pd.DataFrame({'번호': ['A'], '종목': ['a'], '시장': ['미국'], '추천': ['추천'], '종합점수': [5.0]})
    f = pd.DataFrame({'번호': ['A'], 'ticker': ['X'], 'vol60': [20.0], 'beta': [1.0], 'dd52': [-5.0]})
    out, info = meta.run(S, f, P, {}, {'최소표본': 200}, None)
    assert out['메타배수'].iloc[0] == 1.0 and not info['학습']
    assert '학습 대기' in out['메타상태'].iloc[0]


# ---- 단계 순서
def _ctx(order, key='종합점수'):
    return dict(B={'순서': order, '추천': {'기준': key}}, info={})


def test_unknown_stage_rejected():
    with pytest.raises(ValueError, match='모르는 단계'):
        engine.run_stages(pd.DataFrame(), _ctx(['거르기', '없는단계']))


def test_judge_needs_combine_first_when_using_composite():
    with pytest.raises(ValueError, match='합산'):
        engine.run_stages(pd.DataFrame(), _ctx(['거르기', '판정', '합산']))


def test_yaml_order_is_valid():
    order = B['순서']
    assert set(order) <= set(engine.STAGES)
    assert order.index('합산') < order.index('판정') < order.index('메타')


# ---- 완성도 점검표
def test_korean_flow_not_missing_for_us():
    f = pd.DataFrame({'시장': ['한국', '미국'], '구분': ['개별주', '개별주'], 'layer': ['S1', 'S1'], 'ticker': ['a', 'b']})
    sc = B['완성도']['칸범위']
    assert list(audit.scope_mask('f5', f, sc)) == [True, False]
    assert list(audit.scope_mask('rsi_d', f, sc)) == [True, True]


def test_financials_exempt_from_ebitda():
    f = pd.DataFrame({'시장': ['한국', '한국'], '구분': ['개별주', '개별주'], 'layer': ['S5', 'S1'], 'ticker': ['a', 'b']})
    assert list(audit.scope_mask('debt_ebitda', f, B['완성도']['칸범위'])) == [False, True]


def test_every_formula_variable_has_history_class():
    known = set().union(*map(set, B['완성도']['칸과거'].values()))
    for sec in ('시장', '종목'):
        for bid, b in B[sec].items():
            for x in b['공식']:
                for v in compile(x[1], '<f>', 'eval').co_names:
                    assert v in known, f'{bid} {x[0]}: {v} 과거 등급 없음'


def test_meta_learns_from_ledger(tmp_path):
    n = 260
    idx = pd.bdate_range('2025-01-01', periods=n)
    P = pd.DataFrame({'X': 100 * np.cumprod([1.004] * n), 'Y': 100 * np.cumprod([0.996] * n)}, index=idx)
    rows = []
    for d in idx[:200]:
        for t, sc in (('X', 8.0), ('Y', -2.0)):
            rows.append(dict(기준일=d.strftime('%Y-%m-%d'), 번호=t, ticker=t, 시장='미국', 추천='관찰', 종합점수=sc,
                             분산승수=1.5, 블록예비율=0.6, vol60=20.0, beta=1.0, dd52=-5.0, 방어=0, 한국=0, 시장부담=1, 시장기회=0))
    led = tmp_path / '신호장부.csv'
    pd.DataFrame(rows).to_csv(led, index=False, encoding='utf-8-sig')
    S = pd.DataFrame({'번호': ['X', 'Y'], '종목': ['x', 'y'], '시장': ['미국'] * 2, '추천': ['추천'] * 2,
                      '종합점수': [8.0, -2.0], '분산승수': [1.5] * 2, '블록예비율': [0.6] * 2})
    f = pd.DataFrame({'번호': ['X', 'Y'], 'ticker': ['X', 'Y'], 'vol60': [20.0] * 2, 'beta': [1.0] * 2, 'dd52': [-5.0] * 2})
    out, info = meta.run(S, f, P, {'시장부담': 1, '시장기회': 0}, {'최소표본': 100}, str(led))
    assert info['학습']
    assert out['메타확률'].iloc[0] > 0.5 > out['메타확률'].iloc[1]
    assert out['메타배수'].iloc[0] > 0 and out['메타배수'].iloc[1] == 0


# ---- 장기 펀드 13F(B23)
import fetch_13f  # noqa: E402
import grade_13f  # noqa: E402


def test_issuer_name_normalize():
    assert fetch_13f.norm('NVIDIA CORPORATION') == fetch_13f.norm('NVIDIA Corp') == 'NVIDIA'
    assert fetch_13f.norm('Johnson & Johnson') == fetch_13f.norm('JOHNSON AND JOHNSON')


def test_b36_is_bonus_only_when_increased():
    b = B['종목']['B23']
    assert b['조건'] == 'lt_net > 0' and b.get('대상') == '개별주'
    assert engine._ev(b['조건'], {'lt_net': -3.0}) is False
    assert engine._ev(b['조건'], {'lt_net': None}) is None      # 한국 종목: 해당 없음


def test_grade_13f_uses_day_after_filing():
    idx = pd.bdate_range('2020-01-01', periods=400)
    P = pd.DataFrame({'X': np.linspace(100, 200, 400)}, index=idx)
    R = pd.DataFrame({'ticker': ['X'], '분기': ['2019-12-31'], '공시일': [idx[10].strftime('%Y-%m-%d')],
                      'lt_net': [5.0], 'lt_up': [3], 'lt_dn': [1], 'lt_net_prev': [2.0]})
    G, E = grade_13f.grade(R, P)
    assert str(E['출발'].iloc[0]) == str(idx[11].date())
    assert G[(G['구분'] == '늘림') & (G['기간'] == '4주')]['승률'].iloc[0] == 100.0
