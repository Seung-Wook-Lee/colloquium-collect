"""추천 포트폴리오(자문사 MP 형식: 시장 / 종목 / 비중%, 합계 100%). 엔진 판정표 + blocks.yaml '포트' 규칙으로만 만든다.
실행: (in/ 와 out_판정표.csv 가 있는 폴더에서) python qblocks/gen_port.py"""
import sys
sys.path.insert(0, 'qblocks')
import numpy as np, pandas as pd, yaml
import features as F, orders as O

B = yaml.safe_load(open('qblocks/blocks.yaml', encoding='utf-8'))
PC, CC, OC = B['포트'], B['국가'], B.get('주문', {})
S = pd.read_csv('out_판정표.csv'); f = F.stocks('in'); P = F._px('in')
f = O.relative('in', P, f).set_index('번호')
m = F.market('in'); RG = O.regime('in', P, B['국면'])
for mk, v in RG.items(): m[f'DEF_{mk}'] = v['DEF']
if m.get('DEF_미국'): m['DEF_한국'] = 1
m['_d'] = 'in'
ADV, ADV_W, _ = O.advisors('in', B.get('자문사_이름', {}))
CW, cwhy = O.country(m, f.reset_index(), P, ADV_W, CC)
dd = O.basket_dd('in', P)
lines, rows = [], []
for mk in ('미국', '한국'):
    dfm = bool(m.get(f'DEF_{mk}')); g = RG.get(mk, {})
    lines.append(f"{mk}: {'약세(방어 국면)' if dfm else '강세·평상'} — AI÷금융·방어 비율 50일 이격 {g.get('G')}%·20일 변화 {g.get('M')}% → "
                 + (PC['문장_방어'] if dfm else PC['문장_평상']))
    C = S[(S['시장'] == mk) & (S['판정'] == '후보')].copy()
    pool = C[C['추천'] == '추천'].sort_values(['블록예비율', '싼가'], ascending=False)
    if len(pool) < PC['종목수'][mk]:      # 추천 등급이 모자라면 관찰 등급으로 채우고 표시(나라 몫을 비우지 않음)
        pool = pd.concat([pool, C[C['추천'] == '관찰'].sort_values(['블록예비율', '싼가'], ascending=False)])
    pick, nlay = [], {}
    for _, r in pool.iterrows():
        rf = f.loc[r['번호']] if r['번호'] in f.index else None
        if rf is None or (not pd.isna(rf.get('vol60')) and rf['vol60'] > PC['변동성상한']): continue
        if mk == '한국' and (rf.get('f5') or 0) < 0 and (rf.get('f20') or 0) < 0: continue
        if nlay.get(r['층'], 0) >= PC['층당최대']: continue
        nlay[r['층']] = nlay.get(r['층'], 0) + 1; pick.append((r, rf))
        if len(pick) >= PC['종목수'][mk]: break
    if not pick: continue
    raw = []
    for r, rf in pick:
        beta = max(float(rf.get('beta') or 1), 0.1); vol = max(float(rf.get('vol60') or 30), 5)
        tilt = (1 / beta) * (1 / vol) * 30 if dfm else beta * (1 + abs(min(float(rf.get('dd52') or 0), 0)) / 100)
        raw.append(r['블록예비율'] * tilt)
    raw = np.array(raw) / sum(raw) * CW[mk]
    cap = PC['종목상한']          # 한 종목 상한, 넘는 몫은 같은 나라 나머지에 비례 재분배(모두 상한이면 현금)
    for _ in range(10):
        over = raw > cap
        if not over.any(): break
        ex = (raw[over] - cap).sum(); raw[over] = cap
        room = ~over & (raw < cap)
        if not room.any(): break
        raw[room] += ex * raw[room] / raw[room].sum()
    for (r, rf), w in zip(pick, raw):
        w0 = w; w *= r.get('주문승수', 1) if not pd.isna(r.get('주문승수', 1)) else 1
        rows.append(dict(시장=mk, 종목=r['종목'], 층=r['층'], **{'비중(%)': w}, 등급=r['추천'], 블록=f"{r['블록예']:.0f}/{r['블록수']:.0f}",
                         베타=round(float(rf.get('beta') or np.nan), 2), 주문승수=r.get('주문승수'), 경보=r.get('경보') if isinstance(r.get('경보'), str) else '',
                         자문사='신규' if rf.get('adv_new') else ('보유' if rf.get('adv_hold') else '')))
T = pd.DataFrame(rows)
if len(T):
    ai = T['층'].isin(['S1', 'S2', 'S3'])
    if any(m.get(f'DEF_{k}') for k in ('미국', '한국')) and T.loc[ai, '비중(%)'].sum() > PC['AI한도_방어']:
        T.loc[ai, '비중(%)'] *= PC['AI한도_방어'] / T.loc[ai, '비중(%)'].sum()
        lines.append(f"방어 국면 AI(S1~S3) 합산 {PC['AI한도_방어']}% 상한 적용")
    if dd is not None and dd <= PC['낙폭한도']:
        T['비중(%)'] *= PC['낙폭승수']; lines.append(f"직전 추천 바구니 {dd}% → 이번 비중 {PC['낙폭승수']}배(Millennium)")
    T['비중(%)'] = T['비중(%)'].round(1)
cash = round(100 - T['비중(%)'].sum(), 1) if len(T) else 100.0
T = pd.concat([pd.DataFrame([dict(시장='공통', 종목='현금(주문 한도·AI 상한·낙폭 한도)', **{'비중(%)': cash})]), T], ignore_index=True)
tot = T.groupby('시장')['비중(%)'].sum()
day = pd.Timestamp.now(tz='Asia/Seoul').strftime('%Y%m%d_%H%M')
T.to_csv(f'추천포트폴리오_Ver.{day}.csv', index=False, encoding='utf-8-sig')
head = ['추천 포트폴리오 (엔진 출력, 클로드 판단 없음)', '[국면]'] + lines + ['[국가] ' + cwhy,
        f"[합계] 미국 {tot.get('미국', 0):.0f}% / 한국 {tot.get('한국', 0):.0f}% / 현금 {cash:.0f}%", '']
body = T[['시장', '종목', '비중(%)', '등급', '블록', '베타', '주문승수', '자문사', '경보']].fillna('').to_string(index=False)
open(f'추천포트폴리오_Ver.{day}.txt', 'w', encoding='utf-8').write('\n'.join(head) + body)
print('\n'.join(head) + body)
