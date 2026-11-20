"""공포탐욕·VIX를 판정과 말로(블록 2-5 공포 극단, 2-2 바닥 즈음). 회의 결론과 종목 진단이 같이 쓴다.

11/21 의장: "공탐지수가 바닥을 제일 잘 찾는다 — 꼭 반영되게 몇 개 중 하나로", "회의 결론에 공포와 탐욕, 빅스에 대해 말이 있어야지".
숫자 구간 → 판정 → 말. 문턱은 비공개 blocks.yaml '진단_공포탐욕'.
입력 = 07시 수집 YYYYMMDD_공포탐욕.csv(collect/blocks/b05_risk.py) 또는 CNN 응답.
"""
import re

import pandas as pd

KEY = {  # CNN 키 → 한글
    'market_momentum_sp500': '모멘텀(S&P 125일선)', 'stock_price_strength': '신고가 강도', 'stock_price_breadth': '거래량 폭',
    'put_call_options': '풋콜 비율', 'market_volatility_vix': '변동성(VIX)', 'safe_haven_demand': '안전자산 선호',
    'junk_bond_demand': '정크본드(신용)'}
CSVN = dict(zip(['1. Market Momentum', '2. Stock Price Strength', '3. Stock Price Breadth', '4. Put and Call Options',
                 '5. Market Volatility', '6. Safe Haven Demand', '7. Junk Bond Demand'], KEY.values()))


def from_csv(G):
    """07시 공포탐욕.csv(DataFrame) → dict(종합, 전일, 주전, 지표{이름: 점수}, VIX, VIX50)"""
    if G is None or not len(G):
        return {}
    tot = G[G['구분'] == '종합'].iloc[0]
    I = G[G['구분'] == '지표']
    out = dict(종합=float(tot['점수']), 전일=float(tot['전일']), 주전=float(tot['1주 전']),
               지표={CSVN.get(n, n): float(v) for n, v in zip(I['지표'], I['점수'])})
    v = I[I['지표'].astype(str).str.startswith('5.')]
    if len(v) and '원천값' in v:
        out['VIX'] = pd.to_numeric(v['원천값'], errors='coerce').iloc[0]
        m = re.search(r'비교선 ([\d.]+)', str(v['원천값 설명'].iloc[0]))
        out['VIX50'] = float(m.group(1)) if m else None
    return out


def from_cnn(j):
    f = j['fear_and_greed']
    out = dict(종합=float(f['score']), 전일=float(f['previous_close']), 주전=float(f['previous_1_week']),
               지표={v: float(j[k]['score']) for k, v in KEY.items() if k in j})
    try:
        out['VIX'] = float(j['market_volatility_vix']['data'][-1]['y'])
        out['VIX50'] = float(j['market_volatility_vix_50']['data'][-1]['y'])
    except Exception:   # noqa: BLE001
        pass
    return out


def say(fg, F, term=None):
    """→ dict(가까움, 구간, 말, VIX말). F = blocks.yaml '진단_공포탐욕'. term = VIX − VIX3M(있으면)."""
    if not fg or not F:
        return dict(가까움=False, 구간='', 말='공포탐욕 자료를 못 읽었습니다(판정에서 빠짐).', VIX말='')
    v = fg['종합']
    if v <= F['극단공포']:
        zone, judge = '극단 공포', '살 때가 가까워졌습니다'
    elif v <= F['공포']:
        zone, judge = '공포', '살 준비를 할 때입니다'
    elif v >= F['탐욕']:
        zone, judge = '탐욕', '사람들이 들떠 있어 사기에 부담스러운 때입니다'
    else:
        zone, judge = '보통', '공포탐욕으로는 특별한 신호가 없습니다'
    t = f"공포탐욕 {v:.0f}(전날 {fg['전일']:.0f}, 1주 전 {fg['주전']:.0f}) — {zone}. {judge}."
    low = sorted([(n, x) for n, x in fg['지표'].items() if x <= F['지표_바닥']], key=lambda q: q[1])
    if low:
        t += ' 이번 공포를 만든 건 ' + ', '.join(f'{n} {x:.0f}' for n, x in low) + '입니다.'
    junk = fg['지표'].get('정크본드(신용)')
    credit_bad = junk is not None and junk <= F['신용_버팀']
    if junk is not None and v <= F['공포']:
        t += (f" 정크본드(신용)도 {junk:.0f}로 무너졌습니다. 돈줄이 막히는 공포라 바닥이 더 멀 수 있습니다." if credit_bad else
              f" 정크본드(신용)는 {junk:.0f}로 아직 버팁니다. 가격과 심리가 무너진 공포이고, 돈줄이 막힌 공포는 아닙니다.")
    vt = ''
    vix, v50 = fg.get('VIX'), fg.get('VIX50')
    if vix is not None and pd.notna(vix):
        vt = f"VIX {vix:.1f}" + (f"(50일 평균 {v50:.1f}의 {vix / v50:.1f}배)" if v50 else '')
        vt += ' — 공포가 큰 구간입니다.' if vix >= F['VIX_높음'] else (' — 평소보다 불안합니다.' if v50 and vix > v50 else ' — 차분합니다.')
        if term is not None and pd.notna(term):
            vt += (f" 1달 VIX가 3달 VIX보다 {term:+.1f} 높아 뒤집혔습니다(당장의 공포가 극단, 블록 2-2 기회 신호)." if term > 0 else
                   f" 1달 VIX가 3달 VIX보다 낮습니다(아직 뒤집히지 않음).")
    return dict(가까움=v <= F['극단공포'] and not credit_bad, 구간=zone, 말=t, VIX말=vt, 종합=v)


HIST_URL = 'https://raw.githubusercontent.com/whit3rabbit/fear-greed-data/main/fear-greed.csv'   # CNN 공포탐욕 일별 2011~ (공개 저장)


def history():
    """CNN 공포탐욕 일별 이력(2011~) Series. 실패하면 빈 Series."""
    try:
        H = pd.read_csv(HIST_URL, parse_dates=['Date'])
        return H.set_index('Date')['Fear Greed'].astype(float).sort_index()
    except Exception as e:   # noqa: BLE001
        print('공포탐욕 이력 실패:', e)
        return pd.Series(dtype=float)
