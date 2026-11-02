# ======================================================================
# [블록 4] 매크로 — 시장이 어디에 있나 (지수·환율·금리·물가·성장·원자재)
#   하는 일  : 블록 3이 받은 시계열로 표 하나를 만든다.
#              지수 : S&P500, 나스닥, 코스피, 니케이225, SOX, 대만 가권, 유로스톡스50
#                     → 종가, YTD(작년 말 대비 %), 1달(%), 사상 최고 대비(%), 최고면 '신고점'
#                     → 코스피 줄 아래 50일 이격도(코스피 ÷ 50일 평균 × 100), 125 이상 '과열 주의', 130 이상 '과열'
#              환율 : 원/달러, 엔/달러, 100엔당 원, 달러지수 → YTD·1달(%)
#              금리 : 기준금리(범위), 실효 연방기금금리, 미국 3개월·2년·10년·30년·10년 실질, 일본 10년 → YTD·1달(%p)
#              물가 : CPI·근원 CPI·근원 PCE 전년비, 절사평균 PCE, 5년 BEI, 기대인플레 1·10년 → 직전 발표 대비(%p)
#              성장·고용 : GDPNow, 실업률, 비농업 고용 증감(천명)과 3개월 평균
#              원자재 : WTI, 구리, 금 → YTD·1달(%), 사상 최고 대비
#              '신호' 칸은 의장 기준이 있는 항목에만 빨강·주황·초록을 적는다(그 밖에는 비움).
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_매크로.csv
#              수집데이터/YYYYMMDD/YYYYMMDD_추이.csv (항목별 최근 1달 값, 화면의 작은 선 그래프용. 블록 5가 리스크 항목을 덧붙임)
#   쓰는 위원: 포보스(지수·금리), 엘피스(환율·원자재), 뉴스보이(물가·성장·고용)
#   고칠 곳  : 의장 기준이 바뀌면 MACRO_RULES, 항목을 더하려면 블록 3 표에 넣고 아래 해당 묶음에 한 줄
# ======================================================================
MACRO_RULES = {   # 항목 → 값을 받아 (신호, 문구)를 돌려주는 의장 기준
    '미국 10년': lambda v: ('빨강', '5.0 돌파 = Derisking') if v >= 5.0 else ('주황', '4.5 돌파 = 주식비중 축소') if v >= 4.5 else ('', ''),
    '미국 30년': lambda v: ('빨강', '5.25~5.5 돌파 = Derisking') if v >= 5.25 else ('주황', '5.0 돌파 = 현금비중 확대') if v >= 5.0 else ('', ''),
    '일본 10년': lambda v: ('빨강', '3.0 위 = 엔캐리 되감기 경계') if v >= 3.0 else ('', ''),
    '달러지수': lambda v: ('주황', '103~106 = 달러 초강세, 안전자산 선호') if v >= 103 else ('', ''),
    '엔/달러': lambda v: ('주황', '153 아래 = 엔캐리 회수 우려') if v <= 153 else ('', ''),
    '원/달러': lambda v: ('주황', '1400 회귀') if v >= 1400 else ('', ''),
    '100엔당 원': lambda v: ('초록', '950원 = 일본 이익금 일부 회수') if v >= 950 else ('', ''),
    'WTI': lambda v: ('초록', '55~65달러 = 배당용 쉐브론 구입 구간') if v <= 65 else ('', ''),
    '코스피 50일 이격도': lambda v: ('빨강', '130 이상 = 과열') if v >= 130 else ('주황', '125 이상 = 과열 주의') if v >= 125
                         else ('초록', '70~80 = 단기 저점권') if v <= 80 else ('', ''),
}
CHAIR_NOTE = {   # 의장 기준 문구(참고) — 체크리스트와 같은 글
    'S&P500': '시트리니 보고서 8000 즈음이 과열', '나스닥': '前 고점 27,190', '니케이225': '前 고점 72,831',
    '코스피': '前 고점 9,385 / 1차고점 7500~7800', '금': '연준 금리인하 방향 = 금가격 상승',
}
MACRO = []
TREND = []   # (구분, 항목, 날짜, 값) — 화면의 작은 선 그래프용


def trend(kind, name, s):
    """최근 1달 값을 TREND에 담는다. 1달 안에 점이 6개보다 적으면(주간·월간 지표) 최근 13개를 담는다."""
    if s is None:
        return
    s = s.dropna()
    if len(s) < 2:
        return
    w = s[s.index >= s.index[-1] - pd.DateOffset(months=1)]
    if len(w) < 6:
        w = s.iloc[-13:]
    TREND.extend((kind, name, d.strftime('%Y-%m-%d'), round(float(v), 4)) for d, v in w.items())


def save_trend():
    pd.DataFrame(TREND, columns=['구분', '항목', '날짜', '값']).to_csv(f'{DAY}/{TODAY}_추이.csv', index=False, encoding='utf-8-sig')


def mrow(grp, name, s, unit='', pct=True, high=False, src='', value=None, date=None, note='', line=None):
    v, d = last(s) if value is None else (value, date)
    trend('매크로', name, s if line is None else line)
    r = {'구분': grp, '항목': name, '값': round(v, 3) if v is not None else '데이터 없음', '단위': unit, '기준일': d,
         'YTD': ytd(s, pct) if s is not None else None, '1달': m1(s, pct) if s is not None else None,
         '변화 단위': '%' if pct else '%p', '사상 최고': None, '최고일': None, '최고 대비(%)': None,
         '신호': '', '표시': '', '의장 기준(참고)': CHAIR_NOTE.get(name, ''), '비고': note, '출처': src,
         '전일 값': None, '1주 전 값': None, '1달 전 값': None}
    if s is not None and len(s) > 1 and value is None:   # 의장 11/2 "어제·1주 전·1달 전 값을 그냥 보여줘"
        d0 = s.index[-1]
        r['전일 값'] = round(float(s.iloc[-2]), 3)
        w, mo = at_or_before(s, d0 - pd.Timedelta(days=7)), at_or_before(s, d0 - pd.DateOffset(months=1))
        r['1주 전 값'] = None if w is None else round(w, 3)
        r['1달 전 값'] = None if mo is None else round(mo, 3)
    if high and s is not None and len(s):
        mx, mxd = float(s.max()), s.idxmax().strftime('%Y-%m-%d')
        r.update({'사상 최고': round(mx, 3), '최고일': mxd, '최고 대비(%)': round((v / mx - 1) * 100, 2)})
        if v >= mx * 0.9999:
            r['표시'] = '신고점'
    if v is not None and name in MACRO_RULES:
        r['신호'], r['표시'] = MACRO_RULES[name](v)[0], (r['표시'] + ' ' + MACRO_RULES[name](v)[1]).strip()
    MACRO.append(r)
    return r


try:
    # 지수
    for k in ['S&P500', '나스닥', '다우', '코스피', '코스닥', '니케이225', '필라델피아 반도체(SOX)', '대만 가권', '유로스톡스50']:
        if k not in YS and k not in YF_SERIES:
            continue
        mrow('지수', k, YS.get(k), high=True, src=YSRC.get(k, ''))
        if k == '코스피' and '코스피' in YS and len(YS['코스피']) >= 50:
            ks = YS['코스피']
            disp = ks / ks.rolling(50).mean() * 100
            mrow('지수', '코스피 50일 이격도', None, value=float(disp.iloc[-1]), date=ks.index[-1].strftime('%Y-%m-%d'),
                 src='야후 ^KS11 계산', line=disp, note=f'1년 최고 {disp.iloc[-250:].max():.1f} / 최저 {disp.iloc[-250:].min():.1f}')
    # 환율
    for k in ['원/달러', '엔/달러', '100엔당 원', '달러지수']:
        mrow('환율', k, YS.get(k), src='야후 원/달러 ÷ 엔/달러 계산' if k == '100엔당 원' else f'야후 {YF_SERIES[k]}')
    # 금리
    lo, hi = last(FS.get('DFEDTARL')), last(FS.get('DFEDTARU'))
    if hi[0] is not None:
        mrow('금리', '기준금리(범위)', FS.get('DFEDTARU'), unit='%', pct=False, src='FRED DFEDTARL·DFEDTARU',
             note=f'{lo[0]:.2f}~{hi[0]:.2f}%' if lo[0] is not None else '')
    mrow('금리', '실효 연방기금금리', FS.get('EFFR'), unit='%', pct=False, src='FRED EFFR')
    mrow('금리', '미국 3개월', FS.get('DGS3MO'), unit='%', pct=False, src='FRED DGS3MO')
    mrow('금리', '미국 2년', FS.get('DGS2'), unit='%', pct=False, src='FRED DGS2')
    mrow('금리', '미국 10년', YS.get('미국 10년'), unit='%', pct=False, src='야후 ^TNX (FRED보다 하루 빠름)')
    mrow('금리', '미국 30년', YS.get('미국 30년'), unit='%', pct=False, src='야후 ^TYX')
    mrow('금리', '미국 10년 실질', FS.get('DFII10'), unit='%', pct=False, src='FRED DFII10')
    mrow('금리', '일본 10년', JP10, unit='%', pct=False, src='일본 재무성 CSV')
    # 물가 (월간: '1달' 칸 = 직전 발표 대비 %p)
    for k, sid in [('CPI 전년비', 'CPIAUCSL'), ('근원 CPI 전년비', 'CPILFESL'), ('근원 PCE 전년비', 'PCEPILFE')]:
        s = FS.get(sid)
        if s is not None and len(s) > 13:
            now_, before = yoy(s), yoy(s.iloc[:-1])
            r = mrow('물가', k, None, unit='%', pct=False, value=now_, date=last(s)[1], src=f'FRED {sid} 계산',
                     note='1달 칸 = 직전 발표 대비', line=(s / s.shift(12) - 1) * 100)
            r['1달'] = round(now_ - before, 2) if now_ is not None and before is not None else None
        else:
            mrow('물가', k, None, unit='%', src=f'FRED {sid}')
    for k, sid in [('절사평균 PCE(댈러스)', 'PCETRIM12M159SFRBDAL'), ('5년 BEI', 'T5YIE'),
                   ('기대인플레 1년(클리블랜드)', 'EXPINF1YR'), ('기대인플레 10년(클리블랜드)', 'EXPINF10YR')]:
        s = FS.get(sid)
        r = mrow('물가', k, s, unit='%', pct=False, src=f'FRED {sid}')
        if sid != 'T5YIE' and s is not None and len(s) > 1:   # 월간 시리즈는 직전 발표 대비
            r['YTD'], r['1달'], r['비고'] = None, round(s.iloc[-1] - s.iloc[-2], 3), '1달 칸 = 직전 발표 대비'
    # 성장·고용
    g = FS.get('GDPNOW')
    r = mrow('성장·고용', 'GDPNow', g, unit='%', pct=False, src='FRED GDPNOW',
             note='기준일은 분기 시작일(예: 07-01 = 3분기 추정치)')
    r['YTD'], r['1달'] = None, round(g.iloc[-1] - g.iloc[-2], 2) if g is not None and len(g) > 1 else None
    s = FS.get('UNRATE')
    r = mrow('성장·고용', '실업률', s, unit='%', pct=False, src='FRED UNRATE', note='1달 칸 = 직전 발표 대비')
    r['YTD'], r['1달'] = None, round(s.iloc[-1] - s.iloc[-2], 2) if s is not None and len(s) > 1 else None
    s = FS.get('PAYEMS')
    if s is not None and len(s) > 3:
        dif = s.diff().dropna()
        mrow('성장·고용', '비농업 고용 증감', None, unit='천명', pct=False, value=float(dif.iloc[-1]),
             date=last(s)[1], src='FRED PAYEMS 계산', line=dif, note=f'3개월 평균 {dif.iloc[-3:].mean():+,.0f}천명')
    # 원자재
    for k in ['WTI', '구리', '금']:
        mrow('원자재', k, YS.get(k), unit='$', high=True, src=f'야후 {YF_SERIES[k]}')

    mac = pd.DataFrame(MACRO)
    mac['수집시각(KST)'] = stamp()
    mac.to_csv(f'{DAY}/{TODAY}_매크로.csv', index=False, encoding='utf-8-sig')
    save_trend()
    none = mac.loc[mac['값'] == '데이터 없음', '항목'].tolist()
    newhigh = mac.loc[mac['표시'].str.contains('신고점', na=False), '항목'].tolist()
    log(f'[4 매크로] {len(mac) - len(none)}/{len(mac)}항목 | 신고점: {", ".join(newhigh) or "없음"} | '
        f'신호: {", ".join(f"{a}({b})" for a, b in mac.loc[mac["신호"] != "", ["항목", "신호"]].values) or "없음"} | '
        f'데이터 없음: {", ".join(none) or "없음"}')
except Exception as e:
    traceback.print_exc()
    log(f'[4 매크로] 실패: {type(e).__name__} {e}')
