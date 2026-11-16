# ======================================================================
# [블록 8] 체크리스트 1~32 — 리오팀 체크리스트를 예전 모양 그대로 채운다
#   하는 일  : 블록 3~5가 받은 값으로 체크리스트 32항목(+ 참고 VIX3M)을 한 표로 만든다.
#              1~22는 의장 기준 문구, 23~32는 일반 기준 문구를 참고로 붙인다. 판정은 하지 않는다.
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_시장지표.csv (예전과 같은 칸)
#   쓰는 위원: 포보스·엘피스·뉴스보이·리오 (회의 체크리스트)
#   고칠 곳  : 항목·기준 문구가 바뀌면 CHECK 표 (같은 항목의 색 기준은 블록 4 MACRO_RULES·블록 5 RISK_RULES)
# ======================================================================
def _v(s, src):
    v, d = last(s)
    return (round(v, 3), d, src) if v is not None else None


V = {}   # 항목 → (값, 기준일, 출처[, 비고])
for k, name in [('S&P500', 'S&P500'), ('Nasdaq', '나스닥'), ('Nikkei 225', '니케이225'), ('Kospi', '코스피'),
                ('VIX', 'VIX'), ('미국 10년', '미국 10년'), ('미국 30년', '미국 30년'), ('WTI', 'WTI'), ('금', '금'),
                ('달러인덱스', '달러지수'), ('엔/달러', '엔/달러'), ('원/달러', '원/달러'), ('엔/원(100엔)', '100엔당 원'),
                ('MOVE', 'MOVE'), ('VIX3M', 'VIX3M')]:
    if name in YS:
        V[k] = _v(YS[name], f'야후 {YF_SERIES.get(name, "계산")}')
if '코스피' in YS and len(YS['코스피']) >= 50:
    ks = YS['코스피']
    V['Kospi 50일 이격도'] = (round(float(ks.iloc[-1] / ks.iloc[-50:].mean() * 100), 2), ks.index[-1].strftime('%Y-%m-%d'), '야후 ^KS11 계산')
if JP10 is not None:
    V['일본 10년'] = _v(JP10, '일본 재무성 CSV')
if FG:
    V['Fear and Greed'] = (round(FG['score'], 1), TODAY, 'CNN')
    if FG.get('putcall'):
        V['Put/Call Ratio'] = (round(FG['putcall'], 3), TODAY, 'CNN 풋/콜 5일 평균 (체크리스트 원본과 정의 다를 수 있음)')
sofr = SOFR_NY if SOFR_NY[0] is not None else last(FS.get('SOFR'))
if sofr[0] is not None:
    V['SOFR'] = (sofr[0], sofr[1], '뉴욕연준' if SOFR_NY[0] is not None else 'FRED SOFR')
    if 'IORB' in FS:
        V['SOFR-IORB'] = (round(sofr[0] - at_or_before(FS['IORB'], sofr[1]), 3), sofr[1], 'SOFR − IORB 계산')
for k, sid in [('하이일드 스프레드', 'BAMLH0A0HYM2'), ('장단기 금리차', 'T10Y2Y'), ('10년-3개월 금리차', 'T10Y3M'),
               ('미국 10년 실질금리', 'DFII10'), ('5년 기대인플레(BEI)', 'T5YIE'), ('금융스트레스(세인트루이스)', 'STLFSI4'),
               ('금융여건(시카고 NFCI)', 'NFCI'), ('샴 룰 침체 지표', 'SAHMREALTIME'), ('GDPNow', 'GDPNOW')]:
    if sid in FS:
        V[k] = _v(FS[sid], f'FRED {sid}')
if NETLIQ is not None and len(NETLIQ) > 4:
    V['순유동성(조$)'] = (round(NETLIQ.iloc[-1], 3), NETLIQ.index[-1].strftime('%Y-%m-%d'), 'FRED WALCL − WTREGEN − RRPONTSYD 계산',
                       f'4주 전({NETLIQ.index[-5]:%Y-%m-%d}) {NETLIQ.iloc[-5]:.3f} → 변화 {NETLIQ.iloc[-1] - NETLIQ.iloc[-5]:+.3f}')
if 'PCEPILFE' in FS:
    V['근원 PCE 전년비(%)'] = (yoy(FS['PCEPILFE']), last(FS['PCEPILFE'])[1], 'FRED PCEPILFE 계산')
if 'ICSA' in FS and len(FS['ICSA']) >= 4:
    w = FS['ICSA'].iloc[-4:]
    V['신규 실업수당 4주 평균'] = (round(w.mean()), w.index[-1].strftime('%Y-%m-%d'), 'FRED ICSA 계산', f'최신 주 {w.iloc[-1]:,.0f}건')
if 'GDPNow' in V:
    V['GDPNow'] = V['GDPNow'][:3] + ('기준일은 분기 시작일(예: 07-01 = 3분기 추정치)',)

CHECK = [  # (번호, 항목, 담당, 의장 기준(참고), 일반 기준(참고))
    (1, 'S&P500', '포보스', '시트리니 보고서 8000 즈음이 과열', ''),
    (2, 'Nasdaq', '포보스', '前 고점 27,190', ''),
    (3, 'Nikkei 225', '포보스', '前 고점 72,831', ''),
    (4, 'Kospi', '포보스', '前 고점 9,385 / 1차고점 7500~7800', ''),
    (5, 'Fear and Greed', '포보스', 'Event-Driven 하락의 바닥 측정 vs Over 70이면 현금 ↑', ''),
    (6, 'VIX', '포보스', '15.5 이하 과열 조짐, 현금↑', ''),
    (7, '미국 10년', '포보스', '4.8 돌파 = ERP 감소, 주식비중 축소 / 5.0 돌파 = Derisking', ''),
    (8, '미국 30년', '포보스', '5.0 돌파 = 현금비중 확대 / 5.25~5.5 돌파 = Derisking', ''),
    (9, '일본 10년', '포보스', '3.0 넘어가면 엔캐리 트레이드 되감길 수 있음', ''),
    (10, 'WTI', '엘피스', '55~65달러 수준되면 배당용 쉐브론 구입', ''),
    (11, '금', '엘피스', '연준 금리인하 방향 = 금가격 상승', ''),
    (12, '달러인덱스', '포보스', '103~106 달러 초강세 = 안전자산 선호', ''),
    (13, '엔/달러', '포보스', '153 엔캐리트레이드 회수 우려', ''),
    (14, '원/달러', '엘피스', '1400 회귀', ''),
    (15, '엔/원(100엔)', '엘피스', '950원, 일본 이익금 일부 회수', ''),
    (16, 'SOFR', '포보스', '급등하면 단기유동성 문제', ''),
    (17, 'SOFR-IORB', '포보스', 'Normal -0.5~0.5, 플러스 폭 커지면 유동성 문제', ''),
    (18, '하이일드 스프레드', '포보스', '3~4% 주의, 5% 이상 위기 징후', ''),
    (19, 'Kospi 50일 이격도', '포보스', '70~80 단기 저점, 125 이상 과열 주의, 130 근처 고점', ''),
    (20, '장단기 금리차', '포보스', '마이너스일 경우 경기침체 가능성↑', ''),
    (21, 'MOVE', '포보스', '55~60 고점, 100~110 저점, 70~90 Normal', ''),
    (22, 'Put/Call Ratio', '포보스', '고점 0.6~0.7, 저점 1.1~1.2, Average 0.94', ''),
    (23, '순유동성(조$)', '포보스', '', '수준보다 방향: 4주 증가 = 유동성 우호, 감소 = 부담'),
    (24, '10년-3개월 금리차', '포보스', '', '마이너스 = 침체 경고, 역전 뒤 플러스 복귀 구간을 더 경계하는 시각도 있음'),
    (25, '미국 10년 실질금리', '엘피스', '', '2% 위면 금·성장주 부담, 내려가면 금 우호'),
    (26, '5년 기대인플레(BEI)', '엘피스', '', '2~2.5% 연준 목표권, 3% 위면 인플레 재점화 경계'),
    (27, '근원 PCE 전년비(%)', '뉴스보이', '', '연준 목표 2%, 3% 위면 금리인하 어려움'),
    (28, '금융스트레스(세인트루이스)', '포보스', '', '0 = 평균, 0 위 스트레스, 1 위 높은 스트레스'),
    (29, '금융여건(시카고 NFCI)', '포보스', '', '0 = 평균, 0 위면 긴축(돈 빌리기 어려움)'),
    (30, '신규 실업수당 4주 평균', '뉴스보이', '', '25만 건 아래 양호, 30만 건 위면 경기 둔화 경고'),
    (31, '샴 룰 침체 지표', '뉴스보이', '', '0.5 이상이면 침체 진입 신호'),
    (32, 'GDPNow', '뉴스보이', '', '0% 아래면 역성장 경고'),
]
rows = []
for no, k, who, rule, gen in CHECK + [(None, 'VIX3M', '포보스', '참고', '')]:
    v = V.get(k)
    if v is None and no is None:
        continue
    rows.append({'번호': no, '항목': k, '값': v[0] if v else '데이터 없음', '기준일': v[1] if v else None,
                 '출처': v[2] if v else None, '담당': who, '의장 기준(참고)': rule or None,
                 '일반 기준(참고)': gen or None, '비고': v[3] if v and len(v) > 3 else None})
mk = pd.DataFrame(rows)
mk['번호'] = mk['번호'].astype('Int64')
mk['수집시각(KST)'] = stamp()
mk.to_csv(f'{DAY}/{TODAY}_시장지표.csv', index=False, encoding='utf-8-sig')
none = mk.loc[(mk['값'] == '데이터 없음') & mk['번호'].notna(), '항목'].tolist()
log(f'[8 체크리스트] {len(CHECK) - len(none)}/{len(CHECK)} | 데이터 없음: {", ".join(none) or "없음"}')
