"""추천 포트폴리오(자문사 MP 형식: 시장 / 종목 / 비중%, 합계 100%). 엔진 판정표 + blocks.yaml '자산배분'·'포트' 규칙으로만 만든다.
자산 배분(11/17 의장): 지수 30 + 주식·ETF 70. MMF는 의장 판단(엔진 밖). 층마다 업종 1등(시총 1위) 코어를 항상 담고,
돈이 들어오는 주도 층(B32 + 층 ETF 자금 유입)은 코어 외 몫을 그 층 ETF로 담는다.
실행: (in/ 와 out_판정표.csv 가 있는 폴더에서) python qblocks/gen_port.py"""
import sys
sys.path.insert(0, 'qblocks')
import numpy as np, pandas as pd, yaml
import features as F, orders as O

B = yaml.safe_load(open('qblocks/blocks.yaml', encoding='utf-8'))
PC, CC, AA = B['포트'], B['국가'], B['자산배분']
S = pd.read_csv('out_판정표.csv'); f = F.stocks('in'); P = F._px('in')
f = O.relative('in', P, f).set_index('번호')
m = F.market('in'); RG = O.regime('in', P, B['국면'])
for mk, v in RG.items(): m[f'DEF_{mk}'] = v['DEF']
if m.get('DEF_미국'): m['DEF_한국'] = 1
m['_d'] = 'in'
ADV, ADV_W, _ = O.advisors('in', B.get('자문사_이름', {}))
CW, cwhy = O.country(m, f.reset_index(), P, ADV_W, CC)
dd = O.basket_dd('in', P)
anydef = any(m.get(f'DEF_{k}') for k in ('미국', '한국'))
SL = AA['주식'] * (B['바구니']['낙폭승수'] if dd is not None and dd <= B['바구니']['낙폭한도'] else 1)
LR = O.layer_rs('in', P)
LT = {}   # 시장·층별 목표 몫(%)
lines, rows, OUT = [], [], []


def _cap(n, mk):
    if n not in f.index: return np.nan
    v = f.loc[n].get('mcap' if mk == '미국' else 'mcap_kr')
    return np.nan if v is None or pd.isna(v) else float(v)


def _vm(r):
    """기존 블록 연결(국면 무관): B17 싼가 아니오 → ×밸류_승수, B19 너무 많이 올랐나 예 → ×과열_승수"""
    vm, why = 1.0, []
    b17, b19 = pd.to_numeric(r.get(PC['밸류블록']), errors='coerce'), pd.to_numeric(r.get(PC['과열블록']), errors='coerce')
    if not pd.isna(b17) and b17 < 0.5: vm *= PC['밸류_승수']; why.append(f"{PC['밸류블록']} 싼가 아니오({b17:.2f})")
    if not pd.isna(b19) and b19 > 0: vm *= PC['과열_승수']; why.append(f"{PC['과열블록']} 과열 예({b19:.2f})")
    return vm, ' / '.join(why)


def add(mk, r, rf, lay, w, kind, why):
    mu = r.get('주문승수', 1); mu = 1 if pd.isna(mu) else mu   # 주문 한도로 깎인 몫은 미배정
    rows.append(dict(시장=mk, 종목=r['종목'], 층=lay, **{'비중(%)': w * mu}, 구분=kind, 등급=r['추천'],
                     블록=f"{r['블록예']:.0f}/{r['블록수']:.0f}" if not pd.isna(r.get('블록수')) else '',
                     베타=round(float(rf.get('beta') or np.nan), 2) if len(rf) else np.nan, 주문승수=mu, 밸류과열=why,
                     경보=r.get('경보') if isinstance(r.get('경보'), str) else '',
                     자문사='신규' if len(rf) and rf.get('adv_new') else ('보유' if len(rf) and rf.get('adv_hold') else '')))

for mk in ('미국', '한국'):
    dfm = bool(m.get(f'DEF_{mk}')); g = RG.get(mk, {})
    lines.append(f"{mk}: {'약세(방어 국면)' if dfm else '강세·평상'} — AI÷금융·방어 비율 50일 이격 {g.get('G')}%·20일 변화 {g.get('M')}% → "
                 + (PC['문장_방어'] if dfm else PC['문장_평상']))
    LW = dict(B['바구니']['층비중_방어' if dfm else '층비중_평상']); t = sum(LW.values()); LW = {k: v / t for k, v in LW.items()}
    if dfm:
        ai = sum(LW[k] for k in ('S1', 'S2', 'S3'))
        cap = PC['AI한도_방어'] / 100
        if ai > cap:
            for k in ('S1', 'S2', 'S3'): LW[k] *= cap / ai
            rest = [k for k in LW if k not in ('S1', 'S2', 'S3')]; rs = sum(LW[k] for k in rest)
            for k in rest: LW[k] *= (1 - cap) / rs
    sleeve = SL * CW[mk] / 100
    lr = {k[1]: v for k, v in LR.items() if k[0] == mk}
    for lay, lw in LW.items():
        L = sleeve * lw; LT[(mk, lay)] = L; Sm = S[(S['시장'] == mk) & (S['층'] == lay)]
        # 1) 코어: 시장·층별 개별주 시총 1위(판정 무관)
        st = Sm[Sm['구분'] == '개별주'].copy()
        st['cap_'] = [_cap(n, mk) for n in st['번호']]
        st = st.dropna(subset=['cap_']).sort_values('cap_', ascending=False)
        core = st.iloc[0] if len(st) else None
        cw = min(L, PC['코어비중']['방어' if dfm else '평상']) if core is not None else 0
        if core is not None:
            vm, why = _vm(core)
            rf = f.loc[core['번호']] if core['번호'] in f.index else {}
            add(mk, core, rf, lay, cw * vm, '코어(업종 1등)', why)
        rest = L - cw
        if rest <= 0: continue
        # 2) 돈이 들어오는 주도 층 → 층 ETF
        rk = lr.get(lay)
        top = rk is not None and rk[0] <= np.ceil(rk[1] / 3)
        E = Sm[Sm['구분'] == 'ETF'].copy()
        E['f5'] = [f.loc[n].get('etf_flow5') if n in f.index else np.nan for n in E['번호']]
        E['f20'] = [f.loc[n].get('etf_flow20') if n in f.index else np.nan for n in E['번호']]
        E = E[(E['f5'] > PC['유입ETF_5일하한']) & (E['f20'].isna() | (E['f20'] > PC['유입ETF_20일하한']))].sort_values('f5', ascending=False)
        if top and len(E):
            e = E.iloc[0]; rf = f.loc[e['번호']] if e['번호'] in f.index else {}
            add(mk, e, rf, lay, rest, f"유입 섹터 ETF(업종RS {rk[0]}/{rk[1]}위, 5일 자금 {e['f5']:+.0f})", '')
            continue
        # 3) 나머지: 블록 점수 순 개별주
        C = Sm[(Sm['판정'] == '후보') & (Sm['구분'] == '개별주')].sort_values(['블록예비율', '싼가'], ascending=False)
        pick = []
        for _, r in C.iterrows():
            if core is not None and r['번호'] == core['번호']: continue
            rf = f.loc[r['번호']] if r['번호'] in f.index else None
            if rf is None or (not pd.isna(rf.get('vol60')) and rf['vol60'] > PC['변동성상한']): continue
            if mk == '한국' and (rf.get('f5') or 0) < 0 and (rf.get('f20') or 0) < 0: continue
            if r['추천'] not in PC['등급']: continue
            vm, why = _vm(r)
            if vm <= PC['제외_승수이하']:
                OUT.append(f"{r['종목']}({why})"); continue
            beta = max(float(rf.get('beta') or 1), 0.1); vol = max(float(rf.get('vol60') or 30), 5)
            tilt = (1 / beta) * (30 / vol) if dfm else beta * (1 + abs(min(float(rf.get('dd52') or 0), 0)) / 100)
            pick.append((r, rf, r['블록예비율'] * tilt, vm, why))
            if len(pick) >= PC['층당최대'] - (core is not None): break
        if not pick:
            if core is not None:   # 다른 후보가 없으면 층 몫 전부 코어
                vm, why = _vm(core); rows[-1]['비중(%)'] += rest * vm
            continue
        tot = sum(p[2] for p in pick)
        for r, rf, sc, vm, why in pick:
            add(mk, r, rf, lay, rest * sc / tot * vm, '블록 점수', why)
T = pd.DataFrame(rows)
cap = PC['종목상한']
if len(T):   # 승수(밸류·과열·주문 한도)는 층 안 상대 비중으로 쓰고, 층 몫(국가·층 비중·AI 한도)에 맞춰 다시 채운다
    for (mk, lay), L in LT.items():
        i = (T['시장'] == mk) & (T['층'] == lay); s_ = T.loc[i, '비중(%)'].sum()
        if s_ > 0: T.loc[i, '비중(%)'] *= L / s_
    st_ = ~T['구분'].str.startswith('유입')   # 종목상한은 개별주에만(ETF는 분산 상품)
    T.loc[st_, '비중(%)'] = T.loc[st_, '비중(%)'].clip(upper=cap)
    # 넘친 몫(포트.넘침): 같은 시장·층 ETF 중 5일 자금 1위로, 층 ETF가 없으면 지수로
    extra, IDX = [], 0.0
    for (mk, lay), L in LT.items():
        i = (T['시장'] == mk) & (T['층'] == lay); over = L - T.loc[i, '비중(%)'].sum()
        if T.loc[i].empty or over <= 0.05: continue
        E = S[(S['시장'] == mk) & (S['층'] == lay) & (S['구분'] == 'ETF')].copy()
        E['f5'] = [f.loc[n].get('etf_flow5') if n in f.index else np.nan for n in E['번호']]
        E = E.sort_values('f5', ascending=False, na_position='last')
        if len(E):
            e = E.iloc[0]; j = T['종목'] == e['종목']
            if j.any(): T.loc[j, '비중(%)'] += over
            else: extra.append(dict(시장=mk, 종목=e['종목'], 층=lay, **{'비중(%)': over}, 구분='층 ETF(종목상한 넘친 몫)', 등급=e['추천']))
        else: IDX += over
    if extra: T = pd.concat([T, pd.DataFrame(extra)], ignore_index=True)
    T['비중(%)'] = T['비중(%)'].round(1)
IDX = IDX if len(T) else 0.0
fixed = [dict(시장='공통', 종목=n, **{'비중(%)': round(float(w) + IDX * w / sum(AA['지수'].values()), 1)},
              구분='자산배분(지수)' + (f' + 층 ETF 없는 넘친 몫 {IDX:.1f}%' if IDX > 0.05 else '')) for n, w in AA['지수'].items()]
stock = T['비중(%)'].sum() if len(T) else 0.0
left = round(100 - stock - sum(x['비중(%)'] for x in fixed), 1)
if left > 0: fixed.append(dict(시장='공통', 종목='미배정(현금·MMF는 의장 판단)', **{'비중(%)': left}, 구분='빈 층·하락 한도로 못 채운 몫'))
T = pd.concat([pd.DataFrame(fixed), T], ignore_index=True)
if OUT: lines.append('밸류·과열로 신규 편입 제외: ' + ', '.join(OUT[:10]))
tot = T.groupby('시장')['비중(%)'].sum()
day = pd.Timestamp.now(tz='Asia/Seoul').strftime('%Y%m%d_%H%M')
T.to_csv(f'추천포트폴리오_Ver.{day}.csv', index=False, encoding='utf-8-sig')
head = ['추천 포트폴리오 (엔진 출력, 클로드 판단 없음)',
        f"[자산배분] 지수 {sum(AA['지수'].values())}% / 주식·ETF {AA['주식']}% (MMF는 의장 판단)" + (f" (직전 바구니 {dd}% → 주식 몫 {SL}%)" if SL != AA['주식'] else ''),
        '[국면]'] + lines + ['[국가(주식 몫 안)] ' + cwhy,
        f"[합계] 공통 {tot.get('공통', 0):.0f}% / 미국 {tot.get('미국', 0):.0f}% / 한국 {tot.get('한국', 0):.0f}%", '']
body = T[['시장', '종목', '비중(%)', '구분', '등급', '블록', '베타', '주문승수', '밸류과열', '자문사', '경보']].fillna('').to_string(index=False)
open(f'추천포트폴리오_Ver.{day}.txt', 'w', encoding='utf-8').write('\n'.join(head) + body)
print('\n'.join(head) + body)
