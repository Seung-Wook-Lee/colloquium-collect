# ======================================================================
# [블록 5] 리스크 — 시장이 얼마나 불안한가
#   하는 일  : (가) CNN 공포탐욕 종합 점수와 7개 지표: 점수·판정·원천값과 한 줄 해석
#              (나) 리스크 표: 변동성(VIX·VIX3M·MOVE), 신용(하이일드·투자등급 스프레드),
#                   금융 스트레스(세인트루이스·캔자스시티·시카고 NFCI·조정 NFCI),
#                   침체 신호(10년−2년·10년−3개월·샴 룰·침체 확률·실업수당 4주 평균),
#                   자금 경색(SOFR−IORB·순유동성 4주 변화)
#                   값, 기준일, 1주 전·1달 전 값을 나란히 적는다.
#              '신호' 칸은 의장 기준이 있는 항목과 VIX 역전(VIX > VIX3M)에만 적는다. 나머지는 '일반 기준' 글만 붙인다.
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_공포탐욕.csv, YYYYMMDD_리스크.csv
#              (YYYYMMDD_추이.csv 에 공포탐욕 1년 이력, 7개 지표·리스크 항목의 최근 1년 값을 더함)
#   쓰는 위원: 포보스(회의 0번 공포탐욕, 변동성·신용·자금), 리오(침체 신호), 뉴스보이(고용)
#   고칠 곳  : 의장 기준이 정해지면 RISK 표의 의장 기준 칸과 RISK_RULES
# ======================================================================
def rating(r):
    return {'extreme fear': 'Extreme Fear', 'fear': 'Fear', 'neutral': 'Neutral',
            'greed': 'Greed', 'extreme greed': 'Extreme Greed'}.get(str(r).lower(), r)


FG_ITEMS = [  # (이름, CNN 키, 원천값 설명) — 회의 발표 순서
    ('1. Market Momentum', 'market_momentum_sp500', 'S&P500 종가'),
    ('2. Stock Price Strength', 'stock_price_strength', 'NYSE 52주 신고가−신저가 비율(%)'),
    ('3. Stock Price Breadth', 'stock_price_breadth', 'McClellan 거래량 합'),
    ('4. Put and Call Options', 'put_call_options', '풋/콜 5일 평균'),
    ('5. Market Volatility', 'market_volatility_vix', 'VIX'),
    ('6. Safe Haven Demand', 'safe_haven_demand', '20일 주식−채권 수익률 차(%p)'),
    ('7. Junk Bond Demand', 'junk_bond_demand', '정크본드−투자등급 금리차(%p)'),
]


def fg_explain(key, v, extra, score):
    """7개 지표 한 줄 해석 (숫자가 무엇을 뜻하는지까지만, 매수·매도 판단은 하지 않음)"""
    if v is None:
        return ''
    side = '탐욕 쪽' if score >= 55 else '공포 쪽' if score < 45 else '중립'
    if key == 'market_momentum_sp500' and extra:
        return f'S&P500이 125일 평균({extra:,.0f})보다 {(v / extra - 1) * 100:+.1f}% → 평균 위일수록 탐욕 ({side})'
    if key == 'stock_price_strength':
        return f'52주 신고가 종목이 신저가보다 {"많음" if v > 0 else "적음"}({v:+.1f}%) ({side})'
    if key == 'stock_price_breadth':
        return f'오르는 종목 거래량 쪽으로 기운 정도. 1년 범위 안에서 점수 {score:.0f} ({side})'
    if key == 'put_call_options':
        return f'풋/콜 {v:.2f}: 1보다 낮으면 상승 베팅(콜)이 많음, 높으면 하락 대비(풋)가 많음 ({side})'
    if key == 'market_volatility_vix' and extra:
        return f'VIX {v:.1f}가 50일 평균({extra:.1f})보다 {"높음 → 불안" if v > extra else "낮음 → 안정"} ({side})'
    if key == 'safe_haven_demand':
        return f'최근 20일 주식이 채권보다 {v:+.1f}%p → 마이너스면 채권(안전자산) 선호 ({side})'
    if key == 'junk_bond_demand':
        return f'정크본드 추가 금리 {v:.2f}%p → 좁을수록 위험 선호 ({side})'
    return ''


FG = {}
try:
    if not CNN:
        raise RuntimeError('CNN 응답 없음 (블록 3)')
    f = CNN['fear_and_greed']
    dif = f['score'] - f['previous_close']
    rows = [{'구분': '종합', '지표': 'Fear & Greed Index', '점수': round(f['score'], 1), '판정': rating(f['rating']),
             '원천값': None, '원천값 설명': None, '해석': f'전일 {f["previous_close"]:.1f}에서 {dif:+.1f}, '
             f'1주 전 {f["previous_1_week"]:.1f}, 1달 전 {f["previous_1_month"]:.1f}',
             '전일': round(f['previous_close'], 1), '1주 전': round(f['previous_1_week'], 1),
             '1개월 전': round(f['previous_1_month'], 1), '1년 전': round(f['previous_1_year'], 1),
             'CNN 갱신시각': f['timestamp']}]
    for name, key, desc in FG_ITEMS:
        x = CNN.get(key, {})
        v = (x.get('data') or [{}])[-1].get('y')
        extra = None
        if key == 'market_momentum_sp500':
            extra = (CNN.get('market_momentum_sp125', {}).get('data') or [{}])[-1].get('y')
        if key == 'market_volatility_vix':
            extra = (CNN.get('market_volatility_vix_50', {}).get('data') or [{}])[-1].get('y')
        sc = x.get('score', float('nan'))
        rows.append({'구분': '지표', '지표': name, '점수': round(sc, 1), '판정': rating(x.get('rating')),
                     '원천값': round(v, 3) if v is not None else None,
                     '원천값 설명': desc + (f' (비교선 {extra:.2f})' if extra else ''),
                     '해석': fg_explain(key, v, extra, sc),
                     'CNN 갱신시각': str(pd.to_datetime(x['timestamp'], unit='ms', utc=True)) if x.get('timestamp') else None})
    fg = pd.DataFrame(rows)
    fg['수집시각(KST)'] = stamp()
    # 화면 그래프용: 종합 점수 1년 이력 + 7개 지표 원천값 최근 1년
    hist = (CNN.get('fear_and_greed_historical') or {}).get('data') or []
    if hist:
        h = pd.Series({pd.to_datetime(p['x'], unit='ms').normalize(): p['y'] for p in hist}).sort_index()
        TREND.extend(('공포탐욕', 'Fear & Greed Index', d.strftime('%Y-%m-%d'), round(float(v), 1)) for d, v in h.items())
    for name, key, desc in FG_ITEMS:
        pts = CNN.get(key, {}).get('data') or []
        if pts:
            trend('공포탐욕', name, pd.Series({pd.to_datetime(p['x'], unit='ms').normalize(): p['y'] for p in pts}).sort_index())
    save_trend()
    fg.to_csv(f'{DAY}/{TODAY}_공포탐욕.csv', index=False, encoding='utf-8-sig')
    FG = {'score': f['score'], 'putcall': rows[4]['원천값']}
    log(f'[5 공포탐욕] 종합 {f["score"]:.1f} ({rating(f["rating"])}) | 전일 {f["previous_close"]:.1f} | '
        f'7개 지표 {fg["점수"].iloc[1:].notna().sum()}/7')
except Exception as e:
    traceback.print_exc()
    log(f'[5 공포탐욕] 실패: {type(e).__name__} {e}')

# (나) 리스크 표 -------------------------------------------------------------
RISK_RULES = {   # 의장 기준이 있는 항목만
    'VIX': lambda v: ('주황', '15.5 이하 = 과열 조짐, 현금↑') if v <= 15.5 else ('', ''),
    'MOVE': lambda v: ('초록', '70~90 = Normal') if 70 <= v <= 90 else ('주황', '100~110 = 저점권') if v >= 100
            else ('주황', '55~60 = 고점권') if v <= 60 else ('', ''),
    '하이일드 스프레드': lambda v: ('빨강', '5% 이상 = 위기 징후') if v >= 5 else ('주황', '3~4% = 주의') if v >= 3 else ('초록', '3% 아래'),
    '10년−2년': lambda v: ('빨강', '마이너스 = 경기침체 가능성↑') if v < 0 else ('', ''),
    'SOFR−IORB': lambda v: ('초록', '−0.5~0.5 = Normal') if -0.5 <= v <= 0.5 else ('빨강', '범위 밖 = 유동성 문제'),
}
RISK = []


def rk(grp, name, s, unit='', chair='', general='', src='', value=None, date=None, w1=None, mo1=None, note=''):
    v, d = last(s) if value is None else (value, date)
    trend('리스크', name, s)
    if s is not None and len(s) and d:
        w1 = at_or_before(s, pd.Timestamp(d) - pd.Timedelta(days=7)) if w1 is None else w1
        mo1 = at_or_before(s, pd.Timestamp(d) - pd.DateOffset(months=1)) if mo1 is None else mo1
    r = {'구분': grp, '항목': name, '값': round(v, 4) if v is not None else '데이터 없음', '단위': unit, '기준일': d,
         '1주 전': round(w1, 4) if w1 is not None else None, '1달 전': round(mo1, 4) if mo1 is not None else None,
         '신호': '', '표시': '', '의장 기준(참고)': chair, '일반 기준(참고)': general, '비고': note, '출처': src,
         '전일': None, '작년 말': None, '1년 전': None}
    if s is not None and len(s) > 1 and d and value is None:   # 11/3 의장: 전일·1달·YTD·1년 네 칸
        d0 = pd.Timestamp(d)
        ye, y1 = at_or_before(s, f'{d0.year - 1}-12-31'), at_or_before(s, d0 - pd.DateOffset(years=1))
        r['전일'] = round(float(s.iloc[-2]), 4)
        r['작년 말'] = None if ye is None else round(ye, 4)
        r['1년 전'] = None if y1 is None or s.index[0] > d0 - pd.DateOffset(years=1) - pd.Timedelta(days=10) else round(y1, 4)
    if v is not None and name in RISK_RULES:
        r['신호'], r['표시'] = RISK_RULES[name](v)
    RISK.append(r)
    return r


try:
    rk('변동성', 'VIX', YS.get('VIX'), chair='15.5 이하 과열 조짐, 현금↑', src='야후 ^VIX')
    r = rk('변동성', 'VIX3M', YS.get('VIX3M'), general='평소엔 VIX보다 높음. VIX가 VIX3M을 넘으면 단기 공포', src='야후 ^VIX3M')
    if 'VIX' in YS and 'VIX3M' in YS:
        x = pd.concat([YS['VIX'], YS['VIX3M']], axis=1, join='inner').dropna()
        gap = x.iloc[:, 0] - x.iloc[:, 1]
        r2 = rk('변동성', 'VIX − VIX3M', gap, unit='pt', general='플러스 = 단기 공포 역전', src='계산')
        r2['신호'], r2['표시'] = ('빨강', '역전: 단기 공포') if gap.iloc[-1] > 0 else ('초록', '정상 구조')
    rk('변동성', 'MOVE', YS.get('MOVE'), chair='55~60 고점, 100~110 저점, 70~90 Normal', general='채권시장 변동성', src='야후 ^MOVE')
    rk('신용', '하이일드 스프레드', FS.get('BAMLH0A0HYM2'), unit='%', chair='3~4% 주의, 5% 이상 위기 징후', src='FRED BAMLH0A0HYM2')
    rk('신용', '투자등급 스프레드', FS.get('BAMLC0A0CM'), unit='%', general='1.5% 위면 우량 회사채도 긴장', src='FRED BAMLC0A0CM')
    for k, sid in [('세인트루이스', 'STLFSI4'), ('캔자스시티', 'KCFSI'), ('시카고 NFCI', 'NFCI'), ('시카고 조정 NFCI', 'ANFCI')]:
        rk('금융 스트레스', k, FS.get(sid), general='0 = 평균, 0 위 = 스트레스·긴축, 1 위 = 높음', src=f'FRED {sid}')
    rk('침체 신호', '10년−2년', FS.get('T10Y2Y'), unit='%p', chair='마이너스일 경우 경기침체 가능성↑', src='FRED T10Y2Y')
    rk('침체 신호', '10년−3개월', FS.get('T10Y3M'), unit='%p', general='마이너스 = 침체 경고, 역전 뒤 플러스 복귀 구간을 더 경계하기도', src='FRED T10Y3M')
    rk('침체 신호', '샴 룰', FS.get('SAHMREALTIME'), general='0.5 이상 = 침체 진입 신호', src='FRED SAHMREALTIME')
    rk('침체 신호', '경기침체 확률', FS.get('RECPROUSM156N'), unit='%', general='평소 1% 안팎, 높아지면 경고', src='FRED RECPROUSM156N')
    ic = FS.get('ICSA')
    if ic is not None and len(ic) >= 4:
        ic4 = ic.rolling(4).mean().dropna()
        rk('침체 신호', '실업수당 4주 평균', ic4, unit='건', general='25만 아래 양호, 30만 위 경기 둔화 경고',
           src='FRED ICSA 계산', note=f'최신 주 {ic.iloc[-1]:,.0f}건')
    iorb = FS.get('IORB')
    sofr_v, sofr_d = SOFR_NY if SOFR_NY[0] is not None else last(FS.get('SOFR'))
    if sofr_v is not None and iorb is not None:
        fs_sofr = FS.get('SOFR')
        spread = (fs_sofr - iorb.reindex(fs_sofr.index, method='ffill')).dropna() if fs_sofr is not None else None
        rk('자금 경색', 'SOFR−IORB', spread, unit='%p', value=round(sofr_v - at_or_before(iorb, sofr_d), 3), date=sofr_d,
           chair='Normal −0.5~0.5, 플러스 폭 커지면 유동성 문제', src='뉴욕연준 SOFR − FRED IORB')
    if NETLIQ is not None and len(NETLIQ) > 4:
        d4 = NETLIQ.iloc[-1] - NETLIQ.iloc[-5]
        trend('리스크', '순유동성 4주 변화', (NETLIQ - NETLIQ.shift(4)).dropna())   # 화면 1년 그래프용
        r = rk('자금 경색', '순유동성 4주 변화', None, unit='조$', value=round(d4, 3), date=NETLIQ.index[-1].strftime('%Y-%m-%d'),
               general='증가 = 유동성 우호, 감소 = 부담', src='FRED WALCL − WTREGEN − RRPONTSYD 계산',
               note=f'순유동성 {NETLIQ.iloc[-1]:.3f}조$ (4주 전 {NETLIQ.iloc[-5]:.3f})')

    risk = pd.DataFrame(RISK)
    risk['수집시각(KST)'] = stamp()
    risk.to_csv(f'{DAY}/{TODAY}_리스크.csv', index=False, encoding='utf-8-sig')
    save_trend()   # 블록 4의 추이 파일에 리스크 항목을 더해 다시 저장
    none = risk.loc[risk['값'] == '데이터 없음', '항목'].tolist()
    log(f'[5 리스크] {len(risk) - len(none)}/{len(risk)}항목 | '
        f'신호: {", ".join(f"{a}({b})" for a, b in risk.loc[risk["신호"] != "", ["항목", "신호"]].values) or "없음"} | '
        f'데이터 없음: {", ".join(none) or "없음"}')
except Exception as e:
    traceback.print_exc()
    log(f'[5 리스크] 실패: {type(e).__name__} {e}')
