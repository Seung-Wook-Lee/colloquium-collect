"""판정 엔진: 날짜(자료 폴더)를 넣으면 시장 블록 + 종목 블록 전부를 계산.
종목 하나든 전 종목이든 같은 계산. 블록·공식은 blocks.yaml만 고친다."""
import math
import os
import sys

import numpy as np
import pandas as pd
import yaml

import combine as C
import features as F
import meta as MT
import orders as O

LBL = {True: '통과', False: '불통과', None: '자료 없음'}



def _ev(expr, row):
    env = {k: (None if (isinstance(v, float) and math.isnan(v)) else v) for k, v in row.items()}
    names = compile(expr, '<f>', 'eval').co_names
    if any(env.get(n) is None for n in names):
        return None            # 쓰는 칸 중 하나라도 자료 없음이면 '자료 없음'
    try:
        v = eval(expr, {'__builtins__': {}}, env)
        return None if v is None else bool(v)
    except (TypeError, NameError):
        return None


# ---- 단계(blocks.yaml '순서'대로 실행). 블록 계산(공식 → 블록 점수)은 항상 맨 앞, 그 뒤 단계는 yaml 순서를 따른다.
def st_filter(S, c):
    """거르기: 역할 '거르기' 블록(이익·사건·크기) → 후보 / 참고만 / 걸러짐 / 자료 부족"""
    K_EARN, K_EVENT, K_SIZE = c['K_EARN'], c['K_EVENT'], c['K_SIZE']
    filt = S[K_EARN].isin(['통과', '해당 없음']) & (S[K_EVENT] == '통과')   # B12 거르기 폐지 → 갈래(주도·눌림)
    S['판정'] = np.where(filt, np.where(S[K_SIZE].isin(['통과', '해당 없음']), '후보', '참고만'),
                        np.where(S[K_EARN] == '자료 없음', '자료 부족', '걸러짐'))
    S.loc[S['층'] == 'S0', '판정'] = '기준층(지수·현금·금, 추천 대상 아님)'
    return S


def st_combine(S, c):
    """합산: 블록 점수를 같은 눈금으로 맞춰 가중 평균 × 분산 승수(Carver)"""
    sc = [k for k in S.columns if k.startswith('_sc_')]
    SC = S[sc].apply(pd.to_numeric, errors='coerce'); SC.columns = [k[4:] for k in sc]
    W = {k: c['SB'][k].get('가중', 1) for k in SC.columns}
    R, k = C.combine(SC, W, c['B'].get('합산', {}))
    S[R.columns] = R
    c['info']['눈금'] = {b: round(v, 2) for b, v in k.items()}
    return S


def st_judge(S, c):
    """판정: 후보 중 추천·관찰·대기. 기준(추천.기준) = 종합점수(합산 단계) 또는 블록예비율"""
    R = c['B'].get('추천', {})
    cut, cut2 = R.get('추천선', 2 / 3), R.get('관찰선', 0.5)
    key = R.get('기준', '블록예비율')
    if key == '종합점수':   # 같은 뜻의 문턱: 예 비율 x ↔ 평균 점수 (2x − 1) × 10
        cut, cut2 = R.get('추천선_점수', (2 * cut - 1) * 10), R.get('관찰선_점수', (2 * cut2 - 1) * 10)
    dfr = S['국면'].astype(str).str.startswith('방어')
    minb = np.where(dfr, np.where(S['구분'] == '개별주', R.get('최소블록_방어', 6), R.get('최소블록_ETF_방어', 6)),
                    np.where(S['구분'] == '개별주', R.get('최소블록', 8), R.get('최소블록_ETF', 6)))
    enough = (S['블록수'] >= minb) & (S['핵심관측'] >= R.get('핵심관측', 3))
    v = pd.to_numeric(S[key], errors='coerce')
    S['추천'] = np.where(S['판정'] != '후보', S['판정'], np.where(~enough, '자료 부족(블록 수 모자람)',
                np.where(v >= cut, '추천', np.where(v >= cut2, '관찰', '대기'))))
    # 제이미 B29: 눌림 갈래는 가짜 바닥이 아닐 때만 추천(아니면 관찰까지)
    fake = (S['갈래'] == '눌림') & (S['가짜바닥아님'] == 0) & (S['추천'] == '추천')
    S.loc[fake, '추천'] = '관찰'
    c['info']['판정기준'] = f'{key} 추천 ≥ {cut:.2f}, 관찰 ≥ {cut2:.2f}'
    return S


def st_meta(S, c):
    """메타: 1차 신호(추천·관찰)를 믿을 확률 → 비중 배수(로페즈 데 프라도 메타라벨링)"""
    cfg = c['B'].get('메타', {})
    led = cfg.get('장부')
    led = None if (not led or os.environ.get('QC_NO_LEDGER')) else os.path.join(c['d'], '..', led)
    # 시장 블록(B01~B08)은 메타의 입력: 오늘 '부담'·'기회' 공식이 몇 개 켜졌나(2차 판정이 과거 신호로 그 영향을 배움)
    mb = [(side, _ev(e, c['m'])) for bid, b in c['B']['시장'].items() if bid != 'B00' for n, e, side in b['공식']]
    c['m']['시장부담'] = sum(1 for sd, r in mb if sd == '부담' and r)
    c['m']['시장기회'] = sum(1 for sd, r in mb if sd == '기회' and r)
    S, info = MT.run(S, c['f'], c['P'], c['m'], cfg, led)
    c['info']['메타'] = info
    return S


STAGES = {'거르기': st_filter, '합산': st_combine, '판정': st_judge, '메타': st_meta}
NEED = {'판정': ['거르기'], '메타': ['판정']}


def run_stages(S, c):
    order = c['B'].get('순서', ['거르기', '판정'])
    for x in order:
        if x not in STAGES:
            raise ValueError(f"blocks.yaml 순서에 모르는 단계 '{x}'. 쓸 수 있는 단계: {list(STAGES)}")
    need = dict(NEED)
    if c['B'].get('추천', {}).get('기준') == '종합점수':
        need['판정'] = need['판정'] + ['합산']
    for i, x in enumerate(order):
        miss = [y for y in need.get(x, []) if y not in order[:i]]
        if miss:
            raise ValueError(f"blocks.yaml 순서: '{x}' 앞에 {miss} 단계가 있어야 합니다")
    for x in order:
        S = STAGES[x](S, c)
    return S.drop(columns=[k for k in S.columns if k.startswith('_sc_')])


def run(d, cfg='blocks.yaml'):
    B = yaml.safe_load(open(cfg, encoding='utf-8'))
    f = F.stocks(d)
    f = f[f['시장'].isin(['한국', '미국'])].reset_index(drop=True)
    m = F.market(d)
    P = F._px(d)
    # B00 시장별 방어 국면(챗지 식: 5일 중 3일 + 당일, 해제도 같은 방식, 그 사이 유지)
    RG = O.regime(d, P, B['국면']) if len(P) else {}
    for mk, v in RG.items():
        m[f'DEF_{mk}'] = v['DEF']; m[f'ROT_G_{mk}'] = v['G']; m[f'ROT_M_{mk}'] = v['M']
    if m.get('DEF_미국'): m['DEF_한국'] = 1   # 11/17 의장: 미국이 방어 국면이면 한국도 방어
    m['ROT_DEF'] = int(any(v['DEF'] for v in RG.values()))
    m.update(O.record(m))                      # 제이미 C_rate·C_techvol·C_breadth: 기록만
    IR = O.index_regime(d)                     # 지수 252·21일 4국면: 기록만
    for mk, v in IR.items(): m[f'IDX_{mk}'] = v
    OC = B.get('주문', {})
    LR = O.layer_rs(d, P) if len(P) else {}
    f['lay_rs_rank'] = [LR.get((mk, l), (np.nan, 0))[0] for mk, l in zip(f['시장'], f['layer'])]
    f['lay_rs_top'] = [int(LR[(mk, l)][0] <= max(1, LR[(mk, l)][1] // 3)) if (mk, l) in LR else np.nan for mk, l in zip(f['시장'], f['layer'])]
    # 11/17 의장: 방어 국면 기준은 절대값이 아니라 시장 안 상대 순위(한국은 한국끼리, 미국은 미국끼리)
    f = O.relative(d, P, f)
    ADV, ADV_W, ADV_F = O.advisors(d, B.get('자문사_이름', {}))   # 외부자문사 MP(S·C, 파일 생기면 자동)
    f['adv_hold'] = [ADV.get(t, (0, 0))[0] for t in f['ticker']]
    f['adv_new'] = [ADV.get(t, (0, 0))[1] for t in f['ticker']]
    m['_d'] = d; m['ADV_W'] = ADV_W; m['ADV_FILES'] = ', '.join(ADV_F)
    MULT, WHY, FLOW = O.limits(d, P, f, OC) if len(P) else ({}, {}, {})
    CRW = O.crowding(d, P, f, m, OC) if len(P) else {}
    FLIP = O.cta_flip(d)
    for mk, v in FLIP.items(): m[f'CTA_FLIP_{mk}'] = v
    M = pd.DataFrame([dict(블록=bid, 질문=b['질문'], 공식=n, 결과=LBL[_ev(e, m)], 방향=side)
                      for bid, b in B['시장'].items() for n, e, side in b['공식']])
    SB = B['종목']
    Q = {b['질문']: k for k, b in SB.items()}   # 질문으로 블록 찾기(번호가 바뀌어도 됨)
    K_EARN, K_EVENT, K_SIZE, K_HOT = Q['이익이 늘고 있나?'], Q['사건 역풍이 있나?'], [k for q, k in Q.items() if q.startswith('추천할 만큼')][0], Q['너무 많이 올랐나?']
    K_HIGH = Q['고점 부근이 아닌가?']; K_CHEAP = Q['싼가? (줄 세우기 뼈대)']
    last = int(list(SB)[-1][1:])
    K_SPLIT, K_CAP, K_SELL = f'B{last+1:02d}_분할', f'B{last+2:02d}_비중상한(%)', f'B{last+3:02d}_매도신호'
    # 1) 공식별 결과
    rows = [s.to_dict() for _, s in f.iterrows()]
    R = {}   # (i, bid, k) -> 결과
    for i, row in enumerate(rows):
        for bid, b in SB.items():
            if b.get('대상') == '개별주' and row['구분'] != '개별주':
                continue
            for k, (n, e, st, src) in enumerate(b['공식']):
                R[(i, bid, k)] = _ev(e, row)
    # 2) 변별력: 전 종목 통과율
    rate = {}
    for bid, b in SB.items():
        for k in range(len(b['공식'])):
            v = [R[key] for key in R if key[1] == bid and key[2] == k and R[key] is not None]
            rate[(bid, k)] = (sum(v) / len(v)) if v else None
    detail, out_rows = [], []
    for i, row in enumerate(rows):
        out = {'번호': row['번호'], '종목': row['종목'], '시장': row['시장'], '구분': row['구분'], '층': row.get('layer')}
        scores, why, allp, alln = [], [], 0, 0
        yes_blocks = []
        DEF = bool(m.get(f"DEF_{row['시장']}"))
        for bid, b in SB.items():
            if b.get('대상') == '개별주' and row['구분'] != '개별주':
                out[bid] = '해당 없음'; continue
            if '조건' in b and not _ev(b['조건'], row):   # 보너스 블록: 조건이 맞을 때만 셈
                out[bid] = '해당 없음'; continue
            reg = b.get('국면')   # 강세 = 방어 국면이면 쉼, 방어 = 방어 국면에서만 셈
            if reg and ((reg == '강세') == DEF):
                out[bid] = '국면 제외'; continue
            ok = []
            for k, (n, e, st, src) in enumerate(b['공식']):
                r = R[(i, bid, k)]; rt = rate[(bid, k)]
                detail.append(dict(번호=row['번호'], 종목=row['종목'], 블록=bid, 질문=b['질문'], 공식=n, 상태=st, 출처=src,
                                   결과=LBL[r], 전종목_통과율=None if rt is None else round(rt, 2)))
                if r is None:
                    continue
                ok.append(r)
                if r and b['역할'] in ('핵심', '점수', '타이밍'):
                    why.append((rt, n))
            if b['역할'] in ('점수', '타이밍', '핵심'):
                allp += sum(ok); alln += len(ok)
            # 자료 없는 공식이 절반을 넘으면 이 블록은 점수 없음(자료 한 개로 만점 방지)
            sc = (sum(ok) / len(ok)) if ok and len(ok) * 2 >= len(b['공식']) else None
            if b['역할'] == '점수' and sc is not None:
                scores.append(sc)
            if b['역할'] in ('핵심', '점수', '타이밍') and sc is not None:
                yes_blocks.append((bid, b['질문'], sc >= 0.5, b.get('가중', 1)))
            if b['역할'] in ('핵심', '점수', '타이밍'):
                out[f'_sc_{bid}'] = sc   # 합산 단계(분산 승수)에 쓰는 블록 점수 0~1
            if '통과식' in b:
                out[bid] = {True: '통과', False: '탈락', None: '자료 없음'}[_ev(b['통과식'], row)]
            else:
                out[bid] = None if sc is None else round(sc, 2)
        out['통과'] = allp; out['자료있는공식'] = alln
        out['점수'] = round(float(np.mean(scores)), 3) if scores else None
        why.sort()   # 드문 공식(통과율 낮은 것) 먼저 = 이 종목만의 이유
        out['왜'] = ' / '.join(n for _, n in why[:4])
        # B21 위험 값
        out['변동성60(%)'] = None if pd.isna(row.get('vol60')) else round(row['vol60'], 1)
        out['꼬리손실(%)'] = None if pd.isna(row.get('es5')) else round(row['es5'], 1)
        # B22 분할 차수
        four = all(_ev(e, row) for e in ['rsi_d <= 30', 'gap50 <= 90', 'close < m5', 'osc_w > osc_w1'])
        out[K_SPLIT] = '3차' if four else ('2차' if _ev('osc_w > osc_w1', row) else '1차')
        # B23 비중 상한(BLOCK20 반켈리)
        out[K_CAP] = None if pd.isna(row.get('cap')) else round(row['cap'] * 100, 1)
        # B24 팔 때인가
        sell = []
        if out.get(K_EARN) == '탈락': sell.append('이익 꺾임')
        if out.get(K_EVENT) == '탈락': sell.append('사건 역풍 ' + row.get('event_words', ''))
        if out.get(K_HIGH) == '탈락': sell.append(f"고점 부근(52주 고점 대비 {row.get('dd52')}%)")
        if isinstance(out.get(K_HOT), float) and out[K_HOT] > 0: sell.append('너무 많이 오름')
        if _ev('f5 < 0 and f20 < 0', row): sell.append('외국인 5·20일 순매도')
        out[K_SELL] = ', '.join(sell)
        # 빠지는 이유(20일 하락일 때)
        why_dn = []
        if _ev('ret20 < 0', row):
            if _ev('f20 < 0', row): why_dn.append('외국인 20일 순매도')
            if _ev('sec_flow5 < 0', row): why_dn.append('업종 ETF 자금 이탈')
            if _ev('rs20 < 0', row): why_dn.append('시장보다 약함')
            if _ev('peer20 < 0', row): why_dn.append('동료보다 약함')
            if _ev('est30 < 0', row): why_dn.append('이익 추정치 하향')
            if not why_dn: why_dn.append('시장 따라 하락(종목 고유 이유 없음)')
        out['20일(%)'] = None if pd.isna(row.get('ret20')) else round(row['ret20'], 1)
        out['5일(%)'] = None if pd.isna(row.get('ret5')) else round(row['ret5'], 1)
        out['빠지는 이유'] = ', '.join(why_dn)
        out['변수'] = row.get('변수', '')
        ny = sum(w for _, _, y, w in yes_blocks if y); nb = sum(w for *_, w in yes_blocks)
        out['국면'] = ('방어' if DEF else '평상') + (f" · 지수 {IR[row['시장']]}" if row['시장'] in IR else '')
        out['갈래'] = '주도' if _ev('dd52 >= -10', row) else '눌림'
        out['가짜바닥아님'] = row.get('survive')
        out['핵심관측'] = sum(1 for k in ('이익 전망이 오르나?', '회사가 튼튼한가?', '싼가? (줄 세우기 뼈대)', '퀀트 모델(BLOCK20)은 어떻게 보나?')
                           if any(q == k for _, q, *_ in yes_blocks))
        # 주문 한도(B27·B28·B29·쏠림·CTA 전환): 가장 엄격한 승수 하나
        lay = row.get('layer'); mu, al = MULT.get(lay, 1.0), [WHY[lay]] if lay in WHY else []
        if lay in CRW: mu = min(mu, OC.get('승수', 0.5)); al.append(CRW[lay])
        fl = FLIP.get(row['시장'])
        if fl is not None and fl > -OC.get('CTA_전환_%', 2) and _ev(f"beta > {OC.get('고베타', 1.2)}", row):
            mu = min(mu, OC.get('승수', 0.5)); al.append(f'CTA 매도 전환까지 {fl}%(고베타)')
        out['주문승수'] = mu; out['경보'] = ' / '.join(al)
        out['블록예'] = ny; out['블록수'] = nb; out['블록예비율'] = round(ny / nb, 2) if nb else None
        out['블록 예'] = ' / '.join(f'{k} {q}' for k, q, y, _ in yes_blocks if y)
        out['블록 아니오'] = ' / '.join(f'{k} {q}' for k, q, y, _ in yes_blocks if not y)
        out['Sigma Check'] = row.get('sigma_note')
        out_rows.append(out)
    S = pd.DataFrame(out_rows)
    # ETF: 실제 보유 종목(상위 10, 비중)으로 이익·전망·튼튼·싼가 블록을 비중 가중 평균(ETF보유.csv, ETF멤버.csv)
    S['구성종목'] = ''
    try:
        H = pd.read_csv(f'{d}/ETF보유.csv', encoding='utf-8-sig'); MI = pd.read_csv(f'{d}/ETF멤버.csv', encoding='utf-8-sig').set_index('멤버')
    except FileNotFoundError:
        H, MI = pd.DataFrame(columns=['번호', '멤버', '이름', '비중']), pd.DataFrame()
    K15 = Q['이익 전망이 오르나?']; K16 = Q['회사가 튼튼한가?']
    t2i = dict(zip(f['ticker'], S.index[S['번호'].isin(f['번호'])])) if False else {}
    num2row = {n: i for i, n in zip(S.index, S['번호'])}
    tk2num = dict(zip(f['ticker'], f['번호']))
    def nz(x):
        return x is not None and not (isinstance(x, float) and math.isnan(x))
    def mscore(t):
        if t in tk2num and tk2num[t] in num2row:
            r = S.loc[num2row[tk2num[t]]]
            e = {'통과': 1.0, '탈락': 0.0}.get(r[K_EARN])
            g = lambda k: pd.to_numeric(r[k], errors='coerce')
            return e, g(K15), g(K16), g(K_CHEAP)
        if t not in MI.index:
            return None, None, None, None
        m = MI.loc[t]
        eq = m['eqg'] if nz(m['eqg']) else m['eg']
        e = None if not nz(eq) else float(eq > 0)
        o = None if not (nz(m['feps']) and nz(m['teps'])) else float(m['feps'] > m['teps'])
        st = [float(m['roe'] >= 0.10) if nz(m['roe']) else None, float(m['fcf'] > 0) if nz(m['fcf']) else None,
              float(m['debt'] / m['ebitda'] <= 3) if nz(m['debt']) and nz(m['ebitda']) and m['ebitda'] > 0 else None]
        st = [x for x in st if x is not None]
        c = None if not (nz(m['fpe']) and nz(m['tpe'])) else float(m['fpe'] < m['tpe'])
        return e, o, (sum(st) / len(st) if st else None), c
    for n, g in H.groupby('번호'):
        if n not in num2row: continue
        i = num2row[n]
        sc = [(w, mscore(t)) for t, w in zip(g['멤버'], g['비중'])]
        S.at[i, '구성종목'] = ','.join(g['이름'].astype(str).head(10))
        def wavg(j):
            v = [(w, s[j]) for w, s in sc if s[j] is not None and not pd.isna(s[j])]
            tw = sum(w for w, _ in v)
            return (sum(w * x for w, x in v) / tw, len(v)) if tw else (None, 0)
        e, ne = wavg(0)
        if e is not None:
            S.at[i, K_EARN] = '통과' if e > 0.5 else '탈락'
            S.at[i, '구성_이익통과'] = f"보유 비중 {e*100:.0f}% 이익 증가({ne}종목)"
        for j, k in ((1, K15), (2, K16), (3, K_CHEAP)):
            v, _ = wavg(j)
            if v is not None: S.at[i, k] = round(v, 2); S.at[i, f'_sc_{k}'] = v
        # 블록 예/아니오 다시 세기
        ys = str(S.at[i, '블록 예']).split(' / ') if isinstance(S.at[i, '블록 예'], str) and S.at[i, '블록 예'] else []
        ns = str(S.at[i, '블록 아니오']).split(' / ') if isinstance(S.at[i, '블록 아니오'], str) and S.at[i, '블록 아니오'] else []
        for k in (K15, K16, K_CHEAP):
            v = pd.to_numeric(S.at[i, k], errors='coerce')
            if pd.isna(v): continue
            lab = f"{k} {SB[k]['질문']}"
            ys = [x for x in ys if x != lab]; ns = [x for x in ns if x != lab]
            (ys if v >= 0.5 else ns).append(lab)
        S.at[i, '블록 예'] = ' / '.join(ys); S.at[i, '블록 아니오'] = ' / '.join(ns)
        wt = lambda L: sum(SB.get(x.split(' ')[0], {}).get('가중', 1) for x in L)
        S.at[i, '블록예'] = wt(ys); S.at[i, '블록수'] = wt(ys) + wt(ns)
        S.at[i, '블록예비율'] = round(wt(ys) / (wt(ys) + wt(ns)), 2) if ys or ns else None
    S = S.rename(columns={K_SPLIT: '분할', K_CAP: '비중상한(%)', K_SELL: '매도신호'})
    S['싼가'] = pd.to_numeric(S[K_CHEAP], errors='coerce')
    ctx = dict(B=B, d=d, f=f, P=P, m=m, SB=SB, K_EARN=K_EARN, K_EVENT=K_EVENT, K_SIZE=K_SIZE, info={})
    S = run_stages(S, ctx)
    m['_단계'] = ctx['info']
    S = S.sort_values(['판정', '싼가', '점수'], ascending=[True, False, False])
    run.last_f = f
    return S, pd.DataFrame(detail), M, m


if __name__ == '__main__':
    d = sys.argv[1]
    S, D, M, m = run(d)
    S.to_csv(f'{d}/../out_판정표.csv', index=False, encoding='utf-8-sig')
    D.to_csv(f'{d}/../out_공식별결과.csv', index=False, encoding='utf-8-sig')
    M.to_csv(f'{d}/../out_시장블록.csv', index=False, encoding='utf-8-sig')
    print(M.to_string(index=False))
    print(S['판정'].value_counts().to_dict())
    cols = ['종목', '구분', '층', '점수', '5일(%)', '20일(%)', '분할', '매도신호', '빠지는 이유']
    print(S[(S['판정'] == '후보') & (S['구분'] == '개별주')][cols].head(25).to_string(index=False))
