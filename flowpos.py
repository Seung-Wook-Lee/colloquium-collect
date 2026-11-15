# 수급·포지셔닝 계산 — 시타델 GMI 자료(2026-11-03, 의장 제공)를 무료 자료로 따라 하는 근사 모형
#   쓰는 곳: blocks/b09_flowpos.py(매일 07시), 스트림릿 '수급·포지셔닝' 칸
#   정리 문서: /mnt/project-files/위원공부/수급포지셔닝/시타델_수급기법_배울점_Ver.20261115_2230.txt
#
#   1) CTA 포지셔닝 근사(σ) — 시타델의 실제 값은 비공개(블룸버그 기반, 고객용). 가격만으로 흉내 낸 근사.
#      시타델 그림(2025-11~2026-11, 눈으로 읽은 27점)에 맞춤(2026-11-15): 상관 0.88, 평균 오차 1.0σ.
#      맞는 곳: 3~4월 바닥(−3.7 대 −4.2), 5~6월 고점(+3.8 대 +3.5), 10~11월 하락. 다른 곳: 8~9월(시타델 +2, 근사 0), 11/3(−3.3 대 −2.2).
#      식: S&P 20%·나스닥100 60%·러셀 20%, [2·4·8개월 추세(선형, 20일 평활, 60일 변동성 조정) 80% + 1·2·3개월 추세(tanh, 40일 변동성) 20%],
#          2018년 이후 기준 σ × 3.04.
#      기준(2002~, 그날 알 수 있는 날): 처음 −4σ 아래 17번 → S&P 3달 +6.6%(76%)·6달 +10.1%. +4σ 찍고 1.5σ 꺾인 날 16번 → 6달 +1.5%, 3달 안 −5%↓ 44%.
#      평소 3달 +3.3%(70%)·6달 +6.0%.
#   2) 변동성 타기팅 노출 근사 = 10% ÷ 실현변동성(21·63일 섞음), 상한 1.5배.
#   3) 동일가중 S&P500 ÷ 나스닥100 (^SPXEW/^NDX): 비율, 1년 백분위, 상대 RSI(14일, 와일더).
#      11/2 계산 72.2·82% = 시타델 그림 72.2·82%와 같음.
#   4) 내재변동성 1년 백분위(VIX·VXN)와 내재−실현 차이.
import numpy as np
import pandas as pd

TICKERS = {'GSPC': '^GSPC', 'NDX': '^NDX', 'RUT': '^RUT', 'SPXEW': '^SPXEW', 'VIX': '^VIX', 'VXN': '^VXN', 'VIX3M': '^VIX3M'}
WEIGHTS = {'GSPC': 0.2, 'NDX': 0.6, 'RUT': 0.2}
TV = 0.10          # 목표 변동성
CAL_K = 3.04       # 시타델 눈금 배율(그림 27점에 맞춤, 2026-11-15)


def _trend(px, looks, kind, smooth, volwin):
    e = 0
    for c, w in WEIGHTS.items():
        p = px[c]
        r = np.log(p).diff()
        lp = np.log(p)
        sd = r.rolling(250).std()
        s = 0
        for L in looks:
            t = (lp - lp.shift(L)) / (sd * np.sqrt(L))
            s = s + (np.tanh(t) if kind == 'tanh' else t.clip(-2, 2) / 2)
        s = s / len(looks)
        if smooth > 1:
            s = s.ewm(span=smooth).mean()
        s = s * (TV / (r.ewm(span=volwin).std() * np.sqrt(252))).clip(upper=3)
        e = e + w * s
    return (e - e['2018':].mean()) / e['2018':].std()


def cta_sigma(px):
    slow = _trend(px, (40, 80, 160), 'lin', 20, 60)
    fast = _trend(px, (20, 40, 60), 'tanh', 1, 40)
    return CAL_K * (0.8 * slow + 0.2 * fast)


def rsi(x, n=14):
    d = x.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def pct_1y(s):
    return s.rolling(252, min_periods=200).apply(lambda a: (a <= a[-1]).mean(), raw=True)


def compute(close):
    """close: {키: 종가 Series(날짜 인덱스)} → 일별 표(DataFrame)"""
    px = pd.DataFrame({k: close[k] for k in WEIGHTS}).dropna()
    cta = cta_sigma(px)
    r = np.log(px['GSPC']).diff()
    rv = np.sqrt(0.5 * r.ewm(span=21).std() ** 2 + 0.5 * r.ewm(span=63).std() ** 2) * np.sqrt(252)
    out = pd.DataFrame({'S&P500': px['GSPC'], '나스닥100': px['NDX'],
                        'CTA σ(근사)': cta,
                        '변동성타기팅 노출(배)': (TV / rv).clip(upper=1.5), 'S&P 실현변동성(%)': rv * 100})
    if 'SPXEW' in close and close['SPXEW'] is not None:
        ratio = (close['SPXEW'] / close['NDX']).dropna()
        out['동일가중÷나스닥100'] = ratio
        out['비율 1년 백분위(%)'] = pct_1y(ratio) * 100
        out['상대 RSI(14일)'] = rsi(ratio)
    for k, nm in (('VIX', 'VIX'), ('VXN', 'VXN')):
        if k in close and close[k] is not None:
            out[nm] = close[k]
            out[f'{nm} 1년 백분위(%)'] = pct_1y(close[k].dropna()) * 100
    if 'VIX' in out:
        out['VIX−실현변동성(%p)'] = out['VIX'] - out['S&P 실현변동성(%)']
    return out['2018':].round(3)


# 이름 → (설명, 읽는 법). 판정 문턱은 의장 승인 전이라 '룰 미정'(아래 읽는 법은 시타델 자료·백테스트 근거의 참고 글)
NOTES = {
    'CTA σ(근사)': ('추세추종 펀드(CTA)가 미국 주식을 얼마나 들고 있나(가격으로 흉내 낸 근사, 시타델 눈금)',
                  '처음 -4σ 아래 = 수급 바닥(과거 17번, 3달 뒤 +6.6%·76%). +4σ 찍고 1.5σ 꺾이면 수급 고점(16번, 6달 +1.5%)'),
    '변동성타기팅 노출(배)': ('변동성 목표 펀드의 주식 노출(10% ÷ 실현변동성)',
                       '낮을수록 이미 줄인 상태. 변동성이 내려가면 공식대로 다시 산다'),
    'S&P 실현변동성(%)': ('S&P500이 실제로 움직인 폭(연율)', '내재변동성(VIX)과 비교'),
    '동일가중÷나스닥100': ('동일가중 S&P500 ÷ 나스닥100', '오르면 대형 기술주에서 나머지로 돈이 옮겨 가는 중'),
    '비율 1년 백분위(%)': ('위 비율이 지난 1년 범위에서 어디인가', '시타델 11/2: 82%'),
    '상대 RSI(14일)': ('위 비율의 RSI', '70 위 = 순환매 과매수(나스닥 상대 과매도), 30 아래 = 반대. 시타델 11/2: 72.2'),
    'VIX 1년 백분위(%)': ('S&P 내재변동성이 1년 범위에서 어디인가', '높을수록 옵션에 공포 보험료가 붙음'),
    'VXN 1년 백분위(%)': ('나스닥100 내재변동성의 1년 백분위', '시타델 11/2: 나스닥100 96%'),
    'VIX−실현변동성(%p)': ('내재 − 실현', '크게 플러스 = 사건 보험료. 사건이 지나면 빠지며 변동성 타기팅 매수로 이어지기 쉬움'),
}


def today_table(df):
    """마지막 날 값 + 전일·1주·1달 전 → 표"""
    rows = []
    last = df.index[-1]
    for col in [c for c in NOTES if c in df]:
        s = df[col].dropna()
        if not len(s):
            continue

        def at(off):
            x = s[s.index <= last - off]
            return round(float(x.iloc[-1]), 3) if len(x) else None
        d, how = NOTES[col]
        rows.append({'항목': col, '값': round(float(s.iloc[-1]), 3), '기준일': s.index[-1].strftime('%Y-%m-%d'),
                     '전일': round(float(s.iloc[-2]), 3) if len(s) > 1 else None,
                     '1주 전': at(pd.Timedelta(days=7)), '1달 전': at(pd.DateOffset(months=1)),
                     '판정': '룰 미정', '무엇': d, '읽는 법(참고)': how})
    return pd.DataFrame(rows)


def election_cycle(today):
    """대통령 임기 주기 달력 한 줄 (S&P500 1950~2025 우리 계산: 중간선거 뒤 12달 19번 모두 상승, 중앙값 +14.5%)"""
    y = today.year
    kind = {2: '중간선거 해', 0: '대선 해', 1: '임기 1년차', 3: '임기 3년차'}[y % 4]
    d = pd.Timestamp(f'{y}-11-02')
    while d.weekday() != 1:
        d += pd.Timedelta(days=1)
    return {'올해': kind, '선거일': d.strftime('%Y-%m-%d') if y % 2 == 0 else '',
            '선거 뒤 날수': (pd.Timestamp(today) - d).days if y % 2 == 0 and pd.Timestamp(today) >= d else None}


def buyback_window(today):
    """자사주 블랙아웃 어림: 분기 끝 2주 전 닫힘 → 분기 끝 뒤 약 5주(대부분 실적 발표 뒤 48시간) 열림"""
    t = pd.Timestamp(today)
    qe = [pd.Timestamp(f'{y}-{m}-01') + pd.offsets.MonthEnd(0) for y in (t.year - 1, t.year, t.year + 1) for m in (3, 6, 9, 12)]
    for q in qe:
        close_, open_ = q - pd.Timedelta(days=14), q + pd.Timedelta(days=35)
        if close_ <= t < open_:
            return {'자사주 창(어림)': '닫힘(블랙아웃)', '다음 변화': open_.strftime('%Y-%m-%d') + ' 무렵 열림'}
    nxt = min(q - pd.Timedelta(days=14) for q in qe if q - pd.Timedelta(days=14) > t)
    return {'자사주 창(어림)': '열림', '다음 변화': nxt.strftime('%Y-%m-%d') + ' 무렵 닫힘'}
