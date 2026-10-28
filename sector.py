# 닉스 팀 섹터 순환 계산 — 블록 09_sector가 부른다 (2026-10-28 의장 요청, 2026-10-29 의장 승인 룰 v1)
#   한국 섹터 ETF를 TIGER 200과 비교한다.
#   상대: 1·3·6·12개월 초과수익, 모멘텀 순위, 섹터 로테이션 사분면(RRG, 주봉 근사)
#   절대: 20주선 위·기울기, 52주 고점 대비, 닉스 7개 기준(nyx.py)
#   룰 원문: 드라이브 페르소나 스토리/닉스_공통 6장 (로컬 /mnt/project-files/페르소나/닉스_공통.txt)
#   기준값(-20%, 상위 1/3, 26주·4주)은 v1 가정치. 성적이 쌓이면 월 성적 회의에서 의장이 조정한다.
import numpy as np
import pandas as pd

import nyx

PERIODS = (('1개월', 20), ('3개월', 60), ('6개월', 120), ('12개월', 250))
RS_AVG, RS_MOM, TRAIL = 26, 4, 8        # RS-Ratio 평균 주 수, RS-Momentum 비교 주 수, 궤적 주 수
NYX_COLS = ['일_RSI', '일_RSI_단순평균식', '주_RSI', '주_RSI_단순평균식', '주_CCI', '주_STO_K', '주_STO_D', '주_STO_교차',
            '주_볼린저_%B', '일_50일_이격도', '주_20주_이격도', '주_일목_구름위치', '주_일목_전환기준',
            '주_MACD오실레이터', '주_MACD오실레이터_1봉전', '주_MACD오실레이터_2봉전',
            '주_지지상태', '주_저항상태', '주_패턴', '일_지지상태', '일_저항상태', '일_패턴']


def weekly(c):
    return c.groupby(c.index.to_period('W-FRI')).last()


def quad(r, m):
    """RRG 네 칸: 선도(Ratio·Momentum 둘 다 100 위) → 약화 → 침체 → 개선"""
    if pd.isna(r) or pd.isna(m):
        return ''
    return ('선도' if m >= 100 else '약화') if r >= 100 else ('개선' if m >= 100 else '침체')


def rrg(c, bw):
    """주봉 RS = ETF ÷ 벤치마크, RS-Ratio = RS ÷ RS 26주 평균 × 100, RS-Momentum = RS-Ratio ÷ 4주 전 × 100 (원조 JdK 근사)"""
    cw = weekly(c)
    rs = (cw / bw.reindex(cw.index)).dropna()
    ratio = 100 * rs / rs.rolling(RS_AVG, min_periods=20).mean()
    return ratio, 100 * ratio / ratio.shift(RS_MOM)


def judge(r, n):
    """룰 v1 (2026-10-29 의장 승인, 원문 닉스_공통.txt 6장). 판정은 충족 여부와 근거만, 비중 결정은 의장."""
    out = []
    f = lambda k: pd.to_numeric(r.get(k), errors='coerce')
    o0, o1, o2 = f('주_MACD오실레이터'), f('주_MACD오실레이터_1봉전'), f('주_MACD오실레이터_2봉전')
    q, q4 = r['RRG_사분면'], r['RRG_4주전']
    # 라케시스: 상대(선도 + 모멘텀 상위 1/3)와 절대(20주선 위·상승) 둘 다 → 추세 강함, 선도만 → 관찰
    above = r['20주선_위'] == '위' and r['20주선_기울기'] == '상승'
    if q == '선도' and r['모멘텀순위'] <= n // 3 + 1 and above:
        out.append('라케시스 추세 강함')
    elif q == '선도':
        out.append('라케시스 관찰(시장보다 강하나 20주선 아래)' if not above else '라케시스 관찰(모멘텀 상위 1/3 밖)')
    # 클로토: 52주 고점 대비 -20% 이하에서 반전 증거 3개 중 2개 이상 → 반전 후보, 1개 → 관찰
    if f('52주고점대비(%)') <= -20:
        ev = []
        if q == '개선' or (q4 in ('침체', '개선') and q == '선도'):
            ev.append('상대강도 반전')
        if o0 < 0 and o0 > o1 and o1 <= o2:
            ev.append('주봉 MACD 음수권 상승 전환')
        if any(k in str(r.get('주_패턴', '')) for k in ('바닥 넥라인 돌파', '역헤드앤숄더 넥라인 돌파')) \
                or str(r.get('주_지지상태', '')).startswith('반등'):
            ev.append('주봉 바닥 패턴 돌파·지지 반등')
        if len(ev) >= 2:
            out.append('클로토 반전 후보(' + '+'.join(ev) + ')')
        elif ev:
            out.append('클로토 관찰(' + ev[0] + ')')
    # 아트로포스: 과열 또는 꺾임 (경고와 근거만, 매도 가격 없음)
    if f('주_RSI') >= 70 or f('주_20주_이격도') >= 120 or f('주_볼린저_%B') > 1:
        out.append('아트로포스 과열')
    bend = []
    if q4 == '선도' and q in ('약화', '침체'):
        bend.append('선도→' + q)
    if o0 > 0 and o0 < o1 <= o2:
        bend.append('주봉 MACD 양수권 하락 전환')
    if '천장 넥라인 이탈' in str(r.get('주_패턴', '')):
        bend.append('주봉 천장 넥라인 이탈')
    if bend:
        out.append('아트로포스 꺾임 주의(' + '+'.join(bend) + ')')
    return ' / '.join(out) or '해당 없음'


def analyze(px, members, bench):
    """px: {티커: 일봉 DataFrame(시가·고가·저가·종가·거래량)}, members: [(번호, 이름, 티커)], bench: 벤치마크 티커
    반환: (섹터 표, RRG 궤적 표)"""
    b = px[bench]['종가']
    bw = weekly(b)
    rows, trail = [], []
    for no, nm, t in members:
        if t not in px:
            continue
        d = px[t]
        c = d['종가']
        r = {'번호': no, '종목': nm, '종가': c.iloc[-1], '기준일': c.index[-1].date()}
        for lab, k in PERIODS:
            if len(c) > k and len(b) > k:
                mine, mkt = (c.iloc[-1] / c.iloc[-1 - k] - 1) * 100, (b.iloc[-1] / b.iloc[-1 - k] - 1) * 100
                r[f'수익률_{lab}(%)'], r[f'초과_{lab}(%p)'] = round(mine, 1), round(mine - mkt, 1)
            else:
                r[f'수익률_{lab}(%)'] = r[f'초과_{lab}(%p)'] = np.nan
        ratio, mom = rrg(c, bw)
        r['RS_Ratio'], r['RS_Momentum'] = round(ratio.iloc[-1], 1), round(mom.iloc[-1], 1)
        r['RRG_사분면'] = quad(ratio.iloc[-1], mom.iloc[-1])
        r['RRG_4주전'] = quad(ratio.iloc[-5], mom.iloc[-5]) if len(ratio) > 5 else ''
        for i in range(min(TRAIL, len(ratio)), 0, -1):
            if pd.notna(ratio.iloc[-i]) and pd.notna(mom.iloc[-i]):
                trail.append({'번호': no, '종목': nm, '주': min(ratio.index[-i].end_time.date(), c.index[-1].date()), '몇주전': i - 1,
                              'RS_Ratio': round(ratio.iloc[-i], 2), 'RS_Momentum': round(mom.iloc[-i], 2)})
        cw = weekly(c)
        ma20 = cw.rolling(20).mean()
        r['20주선_위'] = '' if pd.isna(ma20.iloc[-1]) else ('위' if cw.iloc[-1] > ma20.iloc[-1] else '아래')
        r['20주선_기울기'] = '' if pd.isna(ma20.iloc[-5]) else ('상승' if ma20.iloc[-1] > ma20.iloc[-5] else '하락')
        r['52주고점대비(%)'] = round((c.iloc[-1] / d['고가'].iloc[-250:].max() - 1) * 100, 1)
        r['3개월저점대비반등(%)'] = round((c.iloc[-1] / d['저가'].iloc[-60:].min() - 1) * 100, 1)
        a = nyx.analyze(d.copy())
        for k in NYX_COLS:
            r[k] = a.get(k, np.nan)
        rows.append(r)
    df = pd.DataFrame(rows)
    if not len(df):
        return df, pd.DataFrame(trail)
    # 모멘텀 순위: 1·3·6개월 초과수익 순위의 평균 (12개월은 상장 1년 안 된 ETF가 있어 뺀다)
    rk = pd.concat([df[f'초과_{lab}(%p)'].rank(ascending=False) for lab in ('1개월', '3개월', '6개월')], axis=1)
    df.insert(2, '모멘텀순위', rk.mean(axis=1).rank(method='min').astype(int))
    df.insert(3, '판정', df.apply(lambda r: judge(r, len(df)), axis=1))
    return df.sort_values('모멘텀순위'), pd.DataFrame(trail)
