"""적정 매수 가격대 (11/20 의장: "어느 정도 가격이 적당한가 — 블록 조합으로 안 되나").

추천 원칙 조합(떨어짐 → 우량 → 비쌈 아님 → 순위 블록 평균 ≥ 추천선)이 '추천'·'관찰'로 바뀌는 가장 높은 가격을 찾는다.
- 가격을 오늘 종가에서 1%씩 내리며, 가격으로 바로 정해지는 칸만 다시 계산하고 블록 공식(blocks.yaml 그대로)을 다시 돌린다.
  52주 고점 대비, PER(TTM·선행·오늘)·PBR(× 가격 비율), FCF 수익률(÷), 층 안 PER·PBR 순위(동료는 그대로), 자기 3년·52주 PER 위치, 50일 이격.
- 우량(이익·돈 잘 버나·빚)은 가격과 무관 → 우량에서 떨어지면 '가격과 무관하게 추천 안 됨'.
- RSI·CCI·%B·스토캐스틱·Sigma Check·이익 전망은 오늘 값 그대로 둔다(가격이 빠지면 보통 더 '예'가 되므로, 여기 나온 가격은 보수적 = 실제보다 낮게 나올 수 있음).
새 숫자를 정하지 않는다: 문턱은 모두 blocks.yaml(원칙·블록 공식).
출력: 가격대.csv (번호, 종목, 현재가, 추천가격, 추천_현재대비%, 관찰가격, 관찰_현재대비%, 막는 것)
"""
import numpy as np
import pandas as pd

STEPS = 60   # 최대 −60%까지


def _ev(expr, row):
    import math
    env = {k: (None if (isinstance(v, float) and math.isnan(v)) else v) for k, v in row.items()}
    names = compile(expr, '<f>', 'eval').co_names
    if any(env.get(n) is None for n in names):
        return None
    try:
        v = eval(expr, {'__builtins__': {}}, env)
        return None if v is None else bool(v)
    except (TypeError, NameError):
        return None


def _num(v):
    try:
        v = float(v)
        return None if np.isnan(v) else v
    except (TypeError, ValueError):
        return None


def shift(row, x, peers):
    """가격이 오늘의 x배일 때 가격으로 바로 정해지는 칸."""
    r = dict(row)
    dd = _num(row.get('dd52'))
    if dd is not None:
        r['dd52'] = ((1 + dd / 100) * x - 1) * 100
    for k in ('per_ttm', 'per_now', 'fper', 'pbr'):
        v = _num(row.get(k))
        if v is not None:
            r[k] = v * x
    v = _num(row.get('fcf_yield'))
    if v is not None:
        r['fcf_yield'] = v / x
    v = _num(row.get('gap50'))
    if v is not None:
        r['gap50'] = v * x
    for k, med in (('per_pct3', 'per_med3'), ('per_pct1', 'per_med1')):
        now, m = _num(r.get('per_now')), _num(row.get(med))
        if now is not None and m is not None and _num(row.get(k)) is not None:
            r[k] = min(_num(row.get(k)), 0.49) if now < m else max(_num(row.get(k)), 0.5)
    for k, col in (('per_rank', 'per_ttm'), ('pbr_rank', 'pbr')):
        v, P = _num(r.get(col)), peers.get(col)
        if v is not None and P is not None and len(P):
            r[k] = (np.sum(P <= v) + 1) / (len(P) + 1)
    return r


def block_score(b, row):
    v = [_ev(e, row) for _, e, _, _ in b['공식']]
    v = [z for z in v if z is not None]
    return (sum(v) / len(v)) if v else None


def judge_at(row, x, B, peers):
    P = B['원칙']; SB = B['종목']
    r = shift(row, x, peers)
    for k in P.get('떨어짐', []):
        t = SB[k].get('통과식')
        if t and _ev(t, r) is not True:
            return '대기(고점 부근)', None
    if P.get('비쌈') and _ev(P['비쌈'], r) is True:
        return '대기(비쌈)', None
    sc = [block_score(SB[k], r) for k in P.get('순위', [])]
    sc = [s for s in sc if s is not None]
    if len(sc) < P.get('순위_최소관측', 2):
        return '자료 부족', None
    m = float(np.mean(sc))
    return ('추천' if m >= P.get('추천선', 0.5) else '관찰'), round(m, 3)


def run(S, f, B):
    if not B.get('원칙'):
        return pd.DataFrame()
    F = f.drop_duplicates('번호').set_index('번호')
    lay = 'layer' if 'layer' in F else ('층' if '층' in F else None)
    px_col = next((c for c in ('close', '종가', 'px') if c in F), None)
    rows = []
    for _, s in S[(S['판정'] == '후보') & (S['구분'] == '개별주')].iterrows():
        b = s['번호']
        if b not in F.index:
            continue
        row = F.loc[b].to_dict()
        px = _num(row.get(px_col)) if px_col else None
        out = dict(번호=b, 종목=s['종목'], 시장=s['시장'], 오늘판정=s.get('추천'), 현재가=px)
        if s.get('원칙') == '떨어짐 자료 없음':
            out.update(추천가격=None, 관찰가격=None, **{'막는 것': '52주 고점 자료 없음(상장 1년 안)'})
            rows.append(out); continue
        if s.get('원칙') in ('우량 아님',) or str(s.get('추천')).startswith('대기(우량'):
            out.update(추천가격=None, 관찰가격=None, **{'막는 것': '우량 아님 → 가격과 무관하게 추천 안 됨'})
            rows.append(out); continue
        peers = {}
        if lay:
            same = F[F[lay] == row.get(lay)]
            for col in ('per_ttm', 'pbr'):
                if col in same:
                    peers[col] = pd.to_numeric(same.drop(index=b, errors='ignore')[col], errors='coerce').dropna().values
        rec = obs = None; last = None
        for k in range(0, STEPS + 1):
            x = 1 - k / 100
            j, m = judge_at(row, x, B, peers)
            last = j
            if obs is None and j in ('관찰', '추천'):
                obs = x
            if j == '추천':
                rec = x
                break
        pr = lambda x: None if (x is None or px is None) else round(px * x, 2)
        out.update(추천가격=pr(rec), 추천_현재대비=None if rec is None else round((rec - 1) * 100),
                   관찰가격=pr(obs), 관찰_현재대비=None if obs is None else round((obs - 1) * 100),
                   **{'막는 것': '' if rec is not None else f'−{STEPS}%까지 내려도 추천 안 됨(마지막 판정 {last})'})
        rows.append(out)
    T = pd.DataFrame(rows)
    if len(T):
        T = T.rename(columns={'추천_현재대비': '추천_현재대비%', '관찰_현재대비': '관찰_현재대비%'})
    return T
