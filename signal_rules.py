"""스트림릿 '오늘 시장' 표의 '신호' 칸 (2026-11-10 의장: "신호 칸을 다 채워주고, 내가 채운 것 제외하고는 니가 채우고,
뒤에 하나씩 고칠텐데, 바닥을 찾는 우리의 목표에 맞게").

- 의장 기준(수집 블록 MACRO_RULES·RISK_RULES가 적은 '신호'·'표시')이 있으면 그것을 그대로 쓴다. 이 파일은 손대지 않는다.
- 의장 기준이 없는 칸은 아래 PROPOSE(클로드 제안)로 채우고 화면에 '(제안)'을 붙인다. 위원 발언·회의 자료에는 쓰지 않는다.
- 색 뜻(바닥 찾기 기준): 🟢 바닥 쪽 신호(공포·과매도·완화) / 🟠 주의 / 🔴 위험(아직 바닥 아님·침체·긴축) / ⚪ 평상.
- 조건에 걸리지 않아도 '⚪ 평상 (기준: …)'으로 기준을 보여 준다. 의장이 고치면 이 파일의 해당 줄만 바꾼다.
"""
import math

CHAIR_TEXT = {   # 의장 기준(수집 블록과 같은 글) — 조건에 안 걸렸을 때 '⚪ 평상 (의장 기준: …)'으로 보여 줄 글
    '미국 10년': '4.8 돌파 주식비중 축소(11/13 의장, 4.5에서 상향), 5.0 돌파 Derisking',
    '미국 30년': '5.0 돌파 현금비중 확대, 5.25~5.5 돌파 Derisking',
    '일본 10년': '3.0 위 엔캐리 되감기 경계',
    '달러지수': '103~106 달러 초강세',
    '엔/달러': '153 아래 엔캐리 회수 우려',
    '원/달러': '1400 회귀',
    '100엔당 원': '950원 = 일본 이익금 일부 회수',
    'WTI': '55~65달러 = 쉐브론 구입 구간',
    '코스피 50일 이격도': '70~80 단기 저점권, 125 과열주의, 130 과열',
    'VIX': '15.5 이하 과열 조짐, 현금↑',
    'MOVE': '55~60 고점권, 100~110 저점권, 70~90 Normal',
    '하이일드 스프레드': '3~4% 주의, 5% 이상 위기 징후',
    '10년−2년': '마이너스 = 경기침체 가능성↑',
    'SOFR−IORB': '−0.5~0.5 Normal',
}


def _ok(x):
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def _dd(cut_green, cut_orange):
    """지수·종목형: 고점 대비 하락폭(hi_gap, %)으로 바닥 쪽 신호"""
    def f(v, c):
        g = c.get('hi_gap')
        if not _ok(g):
            return '⚪', f'평상 (기준: 고점 −{cut_orange}% 조정, −{cut_green}% 바닥 탐색)'
        if g <= -cut_green:
            return '🟢', f'고점 {g:.0f}% — 바닥 탐색 구간(−{cut_green}% 이하)'
        if g <= -cut_orange:
            return '🟠', f'고점 {g:.0f}% — 조정 구간(−{cut_orange}% 이하)'
        return '⚪', f'고점 {g:.0f}% — 평상 (기준: −{cut_orange}% 조정, −{cut_green}% 바닥 탐색)'
    return f


def _band(cuts, unit=''):
    """cuts = [(조건함수, 색, 글), ...] 위에서부터 먼저 맞는 것, 없으면 마지막 ('⚪', 글)"""
    def f(v, c):
        for test, col, txt in cuts[:-1]:
            if test(v):
                return col, txt
        return cuts[-1][1], cuts[-1][2]
    return f


def _fed_rate(v, c):
    mo = c.get('mo')
    if _ok(mo) and mo < 0:
        return '🟢', '한 달 새 인하 — 완화 국면'
    if _ok(mo) and mo > 0:
        return '🔴', '한 달 새 인상 — 긴축 국면'
    return '⚪', '동결 (기준: 인하 🟢, 인상 🔴)'


def _us2y(v, c):
    fed = c.get('vals', {}).get('기준금리(범위)')
    if not _ok(fed):
        return '⚪', '평상 (기준: 기준금리 상단보다 −0.5%p 이하 🟢 인하 기대, +0.25%p 이상 🔴 인상 우려)'
    gap = v - fed
    if gap <= -0.5:
        return '🟢', f'기준금리보다 {gap:+.2f}%p — 시장이 인하를 더 반영'
    if gap >= 0.25:
        return '🔴', f'기준금리보다 {gap:+.2f}%p — 인상 우려'
    return '⚪', f'기준금리보다 {gap:+.2f}%p (기준: −0.5%p 이하 🟢, +0.25%p 이상 🔴)'


def _unrate(v, c):
    d = c.get('d1')
    if _ok(d) and d >= 0.3:
        return '🔴', f'직전 발표보다 {d:+.1f}%p — 빠르게 오름(침체 쪽)'
    if _ok(d) and d >= 0.2:
        return '🟠', f'직전 발표보다 {d:+.1f}%p — 오름'
    return '⚪', '평상 (기준: 직전 대비 +0.2%p 🟠, +0.3%p 🔴)'


def _copper(v, c):
    mo = c.get('mo')
    if _ok(mo) and mo <= -10:
        return '🔴', f'한 달 {mo:.0f}% — 경기 둔화 경고'
    col, txt = _dd(25, 15)(v, c)
    return col, txt.replace(' (기준: ', ' (기준: 한 달 −10% 🔴, ') if ' (기준: ' in txt else txt


def _netliq(v, c):
    if v <= -0.1:
        return '🟠', '4주 새 0.1조$ 넘게 줄어듦 — 유동성 부담'
    if v >= 0.1:
        return '🟢', '4주 새 0.1조$ 넘게 늘어남 — 유동성 우호'
    return '⚪', '평상 (기준: ±0.1조$)'


PROPOSE = {   # 의장 기준이 없는 항목의 클로드 제안 (항목 → (값, 문맥) → (아이콘, 글))
    # 지수: 고점 대비 하락폭
    'S&P500': _dd(20, 10), '나스닥': _dd(20, 10), '다우': _dd(20, 10), '코스피': _dd(20, 10), '코스닥': _dd(25, 15),
    '니케이225': _dd(20, 10), '대만 가권': _dd(20, 10), '유로스톡스50': _dd(20, 10), '필라델피아 반도체(SOX)': _dd(30, 15),
    # 금리
    '기준금리(범위)': _fed_rate, '미국 2년': _us2y,
    # 연준 참고(댈러스·클리블랜드·애틀랜타)
    '절사평균 PCE(댈러스)': _band([(lambda v: v >= 3.0, '🔴', '3% 이상 — 인하 어려움'),
                                (lambda v: v <= 2.5, '🟢', '2.5% 이하 — 인하 여지'),
                                (None, '⚪', '평상 (기준: 2.5% 이하 🟢, 3% 이상 🔴)')]),
    '기대인플레 1년(클리블랜드)': _band([(lambda v: v >= 3.0, '🔴', '3% 이상 — 인하 어려움'),
                                    (lambda v: v <= 2.5, '🟢', '2.5% 이하 — 인하 여지'),
                                    (None, '⚪', '평상 (기준: 2.5% 이하 🟢, 3% 이상 🔴)')]),
    '기대인플레 10년(클리블랜드)': _band([(lambda v: v >= 2.75, '🟠', '2.75% 이상 — 장기 기대 들썩'),
                                     (None, '⚪', '평상 (기준: 2.75% 이상 🟠)')]),
    'GDPNow': _band([(lambda v: v < 0, '🔴', '역성장 추정'), (lambda v: v < 1, '🟠', '1% 아래 — 둔화'),
                     (None, '⚪', '평상 (기준: 1% 아래 🟠, 0 아래 🔴)')]),
    # 고용
    '실업률': _unrate,
    '비농업 고용 증감': _band([(lambda v: v < 0, '🔴', '일자리 감소'), (lambda v: v < 50, '🟠', '5만 명 아래 — 약함'),
                          (None, '⚪', '평상 (기준: 5만 아래 🟠, 감소 🔴)')]),
    '실업수당 4주 평균': _band([(lambda v: v >= 300000, '🔴', '30만 건 이상 — 경기 둔화 경고'),
                           (lambda v: v >= 250000, '🟠', '25만 건 이상 — 둔화 조짐'),
                           (None, '⚪', '평상 (기준: 25만 🟠, 30만 🔴)')]),
    '샴 룰': _band([(lambda v: v >= 0.5, '🔴', '0.5 이상 — 침체 진입 신호'), (lambda v: v >= 0.3, '🟠', '0.3 이상 — 가까워짐'),
                   (None, '⚪', '평상 (기준: 0.3 🟠, 0.5 🔴)')]),
    '경기침체 확률': _band([(lambda v: v >= 30, '🔴', '30% 이상'), (lambda v: v >= 10, '🟠', '10% 이상'),
                       (None, '⚪', '평상 (기준: 10% 🟠, 30% 🔴)')]),
    # 원자재
    '구리': _copper, '금': _dd(20, 10),
    # 변동성: 공포가 클수록 바닥 쪽
    'VIX3M': _band([(lambda v: v >= 30, '🟢', '30 이상 — 공포 극단(과거 바닥 근처)'),
                    (lambda v: v >= 25, '🟠', '25 이상 — 불안'), (None, '⚪', '평상 (기준: 25 🟠, 30 🟢)')]),
    # 신용·스트레스
    '투자등급 스프레드': _band([(lambda v: v >= 2.0, '🔴', '2% 이상 — 우량 회사채도 위기'),
                           (lambda v: v >= 1.5, '🟠', '1.5% 이상 — 긴장'), (None, '⚪', '평상 (기준: 1.5% 🟠, 2% 🔴)')]),
    '세인트루이스': _band([(lambda v: v >= 1, '🔴', '1 이상 — 스트레스 높음'), (lambda v: v >= 0, '🟠', '0 위 — 평균보다 긴장'),
                       (None, '⚪', '평상 (기준: 0 🟠, 1 🔴)')]),
    '캔자스시티': _band([(lambda v: v >= 1, '🔴', '1 이상 — 스트레스 높음'), (lambda v: v >= 0, '🟠', '0 위 — 평균보다 긴장'),
                      (None, '⚪', '평상 (기준: 0 🟠, 1 🔴)')]),
    '시카고 NFCI': _band([(lambda v: v >= 0.5, '🔴', '0.5 이상 — 금융 긴축 뚜렷'), (lambda v: v >= 0, '🟠', '0 위 — 긴축 쪽'),
                        (None, '⚪', '평상 (기준: 0 🟠, 0.5 🔴)')]),
    '시카고 조정 NFCI': _band([(lambda v: v >= 0.5, '🔴', '0.5 이상 — 금융 긴축 뚜렷'), (lambda v: v >= 0, '🟠', '0 위 — 긴축 쪽'),
                           (None, '⚪', '평상 (기준: 0 🟠, 0.5 🔴)')]),
    '10년−3개월': _band([(lambda v: v < 0, '🟠', '역전 — 침체 경고'), (None, '⚪', '평상 (기준: 마이너스 🟠)')]),
    '순유동성 4주 변화': _netliq,
    'VIX − VIX3M': _band([(lambda v: v > 0, '🟢', '역전 — 단기 공포 극단(투매 쪽, 바닥 후보)'),
                          (None, '⚪', '정상 구조 (기준: 플러스 = 역전 🟢)')]),
}
# VIX: 의장 기준(15.5 이하 과열)에 걸리지 않을 때 쓰는 바닥 쪽 제안
VIX_BOTTOM = _band([(lambda v: v >= 40, '🟢', '40 이상 — 패닉(과거 바닥 근처)'), (lambda v: v >= 30, '🟢', '30 이상 — 공포 극단'),
                    (lambda v: v >= 25, '🟠', '25 이상 — 불안'), (None, '⚪', '평상 (기준: 25 🟠, 30 🟢)')])
PROPOSE['VIX'] = VIX_BOTTOM

ICON = {'빨강': '🔴', '주황': '🟠', '초록': '🟢'}
NOT_CHAIR = {'VIX − VIX3M'}   # 수집 블록이 색을 적지만 의장 기준이 아닌 항목 → 제안으로 바꿔 보여 줌


def _split(txt):
    """'평상 (기준: …)' → ('평상', '…')"""
    i = txt.find(' (기준: ')
    return (txt[:i], txt[i + 6:].rstrip(')')) if i >= 0 else (txt, '')


def criteria(name):
    """그 항목의 기준 글: (출처, 글). 제안 함수가 '평상' 때 적는 '(기준: …)'을 꺼내 쓴다."""
    if name in PROPOSE:
        for probe in (0.0, 2.7, -1e9, 1e9):   # 평상 글이 나오는 값을 찾는다
            try:
                _, t = PROPOSE[name](probe, {})
            except Exception:
                continue
            short, crit = _split(t)
            if crit:
                return '제안', crit
    return ('의장', CHAIR_TEXT[name]) if name in CHAIR_TEXT else ('', '')


def signal2(name, v, chair_color='', chair_text='', **ctx):
    """화면용: (아이콘, 짧은 글, 출처, 기준 글). 기준 글은 표 맨 뒤 '해석' 칸 앞머리에 쓴다."""
    icon, txt, who = signal(name, v, chair_color, chair_text, **ctx)
    short, crit = _split(txt.split(' · 의장 기준:')[0])
    if '(의장 기준: ' in short:
        short = short.split(' (의장 기준: ')[0]
    parts = []
    src, c = criteria(name)
    if src == '제안' and c:
        parts.append(f'제안 기준: {c}')
    if name in CHAIR_TEXT:
        parts.append(f'의장 기준: {CHAIR_TEXT[name]}')
    if not parts and crit:
        parts.append(f'기준: {crit}')
    return icon, short, who, ' / '.join(parts)


def signal(name, v, chair_color='', chair_text='', **ctx):
    """(아이콘, 글, 출처) — 출처는 '의장' 또는 '제안'. 의장 신호가 있으면 그것, 없으면 제안, 둘 다 없으면 ⚪ 평상."""
    chair_color = '' if chair_color is None or str(chair_color) == 'nan' else str(chair_color)
    chair_text = '' if chair_text is None or str(chair_text) == 'nan' else str(chair_text)
    if chair_color and name not in NOT_CHAIR:
        return ICON.get(chair_color, '⚪'), chair_text, '의장'
    if not _ok(v):
        return '', '', ''
    if name in PROPOSE:
        col, txt = PROPOSE[name](v, ctx)
        if name in CHAIR_TEXT:   # 의장 기준이 있는데 안 걸린 항목(VIX 등)은 의장 기준을 함께 보여 준다
            txt += f' · 의장 기준: {CHAIR_TEXT[name]}'
        return col, txt, '제안'
    if name in CHAIR_TEXT:
        return '⚪', f'해당 없음 (의장 기준: {CHAIR_TEXT[name]})', '의장'
    return '⚪', '기준 없음', '제안'
