import pandas as pd, numpy as np, sys, yfinance as yf
sys.path.insert(0,'qblocks'); import features as F
f=F.stocks('in'); S=pd.read_csv('out_판정표.csv'); M=pd.read_csv('out_시장블록.csv'); m=F.market('in')
R=pd.read_csv('in/연매출.csv',encoding='utf-8-sig')
S=S.merge(R[['번호','연매출(원)']],on='번호',how='left')
X=S.merge(f.drop(columns=['종목','시장','구분'],errors='ignore'),on='번호',how='left')
def n(v,fmt='{:.1f}',suf=''):
    return '자료 없음' if v is None or (isinstance(v,float) and np.isnan(v)) else fmt.format(v)+suf
big=X[(X['판정']=='후보')&(((X['구분']=='개별주')&(X['연매출(원)']>=1e13))|(X['구분']!='개별주'))]
kr=big[(big['구분']=='개별주')&(big['시장']=='한국')].sort_values(['싼가','점수'],ascending=False)
us=big[(big['구분']=='개별주')&(big['시장']=='미국')&(~big['종목'].str.contains('ADR\\)'))].sort_values(['싼가','점수'],ascending=False)
ee=big[big['구분']!='개별주'].sort_values(['싼가','점수'],ascending=False)
allc=pd.concat([kr,us,ee])
rec=allc[allc['추천']=='추천']; obs=allc[allc['추천']=='관찰'].sort_values(['싼가','점수'],ascending=False)
pick=rec   # 관찰 등급을 임의 개수로 끼워 넣지 않음(11/17 의장)
# 오늘 등락(한국 장중)
tk=[t for t in pick['ticker'] if str(t).endswith(('.KS','.KQ'))]
today={}
if tk:
    h=yf.download(tk+['^KS11'],period='5d',progress=False,auto_adjust=True)['Close']
    today={t:(h[t].dropna().iloc[-1]/h[t].dropna().iloc[-2]-1)*100 for t in h}
L=[]
L.append('퀀트센터 종목 추천 — 2026-11-16 14시 (블록 엔진 판정, 의장 확인 전)')
L.append('자료: 07시 수집(외국인 수급·Sigma Check는 11/13 금요일까지), 가격은 오늘 장중(15~20분 지연), 야후 재무·추정치. 미국은 11/13 종가.')
L.append('')
L.append('1. 시장 (리스크관리센터)')
for _,r in M.iterrows():
    if r['결과']=='통과': L.append(f"  - {r['방향']}: {r['공식']}")
L.append(f"  값: VIX {n(m.get('VIX'))}, MOVE {n(m.get('MOVE'))}, HY {n(m.get('HY'),'{:.2f}','%')}, 미국 10년물 {n(m.get('US10Y'),'{:.2f}','%')}, 공포탐욕 {n(m.get('FG'),'{:.0f}')}, CTA {n(m.get('CTA'),'{:.2f}','σ')}, Vol-target {n(m.get('VOLT'),'{:.2f}','배')}, 국내 지수·커버드콜·미국지수 ETF 5일 유입 {n(m.get('KR_SAFE_FLOW5'),'{:.0f}','억')}")
L.append(f"  S&P500 선행 PER {n(m.get('SPX_FPER'),'{:.1f}','배')}(11/13 블룸버그, 선행 EPS 1주 +0.3%·YTD +33.8%, PBR 5.5배, ROE 30.4%) — 10년 σ 위치는 이력 쌓인 뒤")
L.append(f"  코스피 오늘 {n(today.get('^KS11'),'{:+.1f}','%')}")
L.append('  → 부담 신호가 기회보다 많음. 투입 비율 규칙은 룰 미정, 분할 1/3 자리.')
L.append('')
L.append('2. 추천 기준')
L.append('  세 질문에 모두 예면 추천, 둘이면 관찰, 하나 이하면 대기. 점수 평균으로 자르지 않음.')
L.append('  싸다: 싼가 공식 5개(동료 대비 선행 PER·PBR 순위, 선행 PER < TTM PER, FCF 수익률 5% 이상 등) 중 과반 통과')
L.append('  돈이 들어온다: 한국 개별주는 외국인 5일 순매수이면서 20일 순매수 또는 3일 이상 연속. ETF는 그 ETF 5일 자금 유입. 미국 개별주는 업종 ETF 5일 자금 유입')
L.append('  돌아섰다: 주봉 MACD 오실레이터 2주 연속 상승 또는 주가가 50일선 위')
L.append('  그 앞에 거르기: 이익 증가(한 분기 꺾임은 앞 분기 증가와 추정치 상향이면 허용), 사건 역풍 없음, 52주 고점 대비 10% 이상 아래, 연매출 10조 원 이상')
L.append('  커트라인 근거: 과반(3/5)과 세 조건 동시 충족은 11/15 의장 기준(돈과 차트가 비면 추천 금지)을 옮긴 것. 백테스트는 아직 없음(시험 없음, 팀Q로)')
L.append('')
L.append(f"  결과: 추천 {len(rec)}개, 관찰 {len(obs)}개")
for _,r in rec.iterrows(): L.append(f"  추천: {r['종목']}")
L.append('  관찰(조건 2개): '+', '.join(f"{r['종목']}(빠진 조건: {', '.join(k for k in ['싸다','돈이 들어온다','돌아섰다'] if r[k]!='예')})" for _,r in obs.iterrows()))
L.append('')
L.append(f"3. 후보군: 200종목 중 거르기(이익 증가·사건 역풍·연매출 10조) 통과 개별주 {len(kr)+len(us)}개, ETF {len(ee)}개")
L.append('  싼가 = 동료 대비 선행 PER·PBR 순위·선행<TTM·FCF 수익률 통과 비율(0~1, 줄 세우기 뼈대). 나머지 점수 = 전망·재무·Sigma Check·수급·추세·업종·BLOCK20 블록 평균')
for name,d in (('한국',kr),('미국',us)):
    L.append(f"  [{name}] "+', '.join(f"{r['종목']} 싼가 {r['싼가']:.2f}·{r['점수']:.2f}" for _,r in d.iterrows()))
L.append("  [ETF] "+', '.join(f"{r['종목']} 싼가 {r['싼가']:.2f}·{r['점수']:.2f}" for _,r in ee.head(15).iterrows()))
L.append('')
L.append('4. 추천과 관찰 상위 상세 (손으로 빼거나 넣지 않음)')
for _,r in pick.iterrows():
    L.append('')
    L.append(f"■ {r['추천']} | {r['종목']} | {r['시장']} {r['층']}층 | 싸다 {r['싸다']} · 돈이 들어온다 {r['돈이 들어온다']} · 돌아섰다 {r['돌아섰다']} | 분할 {r['분할']}")
    if r['구분']!='개별주':
        L.append(f"  구성 종목(유니버스 안): {r['구성종목']} — 이익 증가 통과 {r['구성_이익통과']}")
    else:
        L.append(f"  이익: 최근 분기({r.get('last_q')}) {r.get('kind')} 전년비 {n(r.get('op_yoy'),'{:+.1f}','%')}, 이익률 {n(r.get('opm'),'{:.1f}','%')}(전년비 {n(r.get('opm_yoy'),'{:+.1f}','%p')}), 매출 전년비 {n(r.get('rev_yoy'),'{:+.1f}','%')}")
        L.append(f"  추정치: 내년 EPS 30일 {n(r.get('est30'),'{:+.1f}','%')}, 90일 {n(r.get('est90'),'{:+.1f}','%')}, 30일 상향 {n(r.get('up30'),'{:.0f}')}·하향 {n(r.get('dn30'),'{:.0f}')}, 같은 층 동료 중 상향 순위 백분위 {n(r.get('peer_est30'),'{:.2f}')}")
        L.append(f"  밸류: 선행 PER {n(r.get('fper'),'{:.1f}','배')}, TTM PER {n(r.get('per_ttm'),'{:.1f}','배')}, PBR {n(r.get('pbr'),'{:.2f}','배')}, 동료 중 선행 PER 저렴 백분위 {n(r.get('peer_fper'),'{:.2f}')}")
        L.append(f"  재무: Piotroski F-Score {n(r.get('fscore'),'{:.0f}')}/9, Altman Z {n(r.get('z'),'{:.2f}')}, 총부채/EBITDA {n(r.get('debt_ebitda'),'{:.2f}','배')}, ROE {n(r.get('roe'),'{:.1f}','%')}")
    if pd.notna(r.get('bb_fper')):
        L.append(f"  블룸버그(11/13): 12개월 선행 PER {r['bb_fper']:.1f}배, 선행 EPS 1주 {r['bb_eps1w']:+.1f}%·YTD {r['bb_epsytd']:+.1f}%, 주가 1주 {r['bb_ret1w']:+.1f}%·YTD {r['bb_ytd']:+.1f}%")
    L.append(f"  Sigma Check: 자기역사 하락 p-value 10년 {n(r.get('p10'),'{:.3f}')}, 5년 {n(r.get('p5'),'{:.3f}')}, 3년 {n(r.get('p3'),'{:.3f}')} / 베타 잔차 p-value 4주 {n(r.get('res4p'),'{:.3f}')}, 13주 {n(r.get('res13p'),'{:.3f}')} / 베타(주간 2년) {n(r.get('beta'),'{:.2f}')}")
    pmin=min([x for x in [r.get('p10'),r.get('p5'),r.get('p3')] if pd.notna(x)] or [np.nan]); rmin=min([x for x in [r.get('res4p'),r.get('res13p')] if pd.notna(x)] or [np.nan])
    if pd.isna(pmin): it='자료 없음'
    elif pmin<=0.05 and rmin<=0.05: it=f'3-sigma drop, beta-adjusted — 자기역사 p {pmin:.3f}, 베타 잔차 p {rmin:.3f} 둘 다 0.05 이하(시장 베타로 설명 안 되는 종목 고유 하락)'
    elif pmin<=0.05: it=f'3-sigma drop, beta-explained — 자기역사 p {pmin:.3f} ≤ 0.05이나 베타 잔차 p {rmin:.3f} > 0.05(시장 베타만큼 빠짐)'
    else: it=f'통계적으로 평소 범위(자기역사 최소 p {pmin:.3f} > 0.05)'
    L.append(f"    판정: {it}")
    L.append(f"  위치: 52주 고점 대비 {n(r.get('dd52'),'{:+.1f}','%')}, 20일 {n(r.get('ret20'),'{:+.1f}','%')}(시장 대비 {n(r.get('rs20'),'{:+.1f}','%p')}, 동료 대비 {n(r.get('peer20'),'{:+.1f}','%p')}), 5일 {n(r.get('ret5'),'{:+.1f}','%')}" + (f", 오늘 {today[r['ticker']]:+.1f}%" if r['ticker'] in today else ''))
    if r['시장']=='한국':
        L.append(f"  수급: 11/13까지 외국인 5일 {n(r.get('f5'),'{:+,.0f}','억')}, 20일 {n(r.get('f20'),'{:+,.0f}','억')}, 연속 {n(r.get('fstreak'),'{:+.0f}','일')}, 기관 5일 {n(r.get('inst5'),'{:+,.0f}','억')}")
    L.append(f"  차트: 일봉 RSI {n(r.get('rsi_d'),'{:.0f}')}, 50일 이격 {n(r.get('gap50'),'{:.0f}')}, 주봉 RSI {n(r.get('rsi_w'),'{:.0f}')}, 주봉 MACD 오실레이터 {'상승' if r.get('osc_w',0)>r.get('osc_w1',0) else '하락'}, 월봉 5개월선 {'아래' if r.get('close',0)<r.get('m5',0) else '위'}")
    L.append(f"  BLOCK20: 6달 +10% 확률 {n(r.get('p126'),'{:.0%}')} (층 평균 {n(r.get('n0_126'),'{:.0%}')}), 3달 +5% {n(r.get('p63'),'{:.0%}')} (층 평균 {n(r.get('n0_63'),'{:.0%}')})")
    L.append(f"  위험: 60일 변동성 연 {n(r.get('vol60'),'{:.0f}','%')}, 1년 하위 5% 일간 손실 평균(ES) {n(r.get('es5'),'{:.1f}','%')}")
    if isinstance(r.get('변수'),str) and r['변수']: L.append(f"  변수: {r['변수']}")
    bad=[x for x in [r.get('매도신호'),r.get('빠지는 이유')] if isinstance(x,str) and x]
    L.append(f"  주의: {' / '.join(bad) if bad else '없음'}")
L.append('')
L.append('5. 앞으로의 변수(변수달력.csv — 예정된 사건, 거르지 않고 표시)')
for _,c in pd.read_csv('in/변수달력.csv',encoding='utf-8-sig').iterrows():
    L.append(f"  - {c['시기']} {c['사건']} | 영향: {c['영향 업종 낱말'].replace('|',', ')} | {c['방향']} | 출처 {c['출처']}")
L.append('')
L.append('6. 걸러진 주요 종목')
for _,r in X[X['판정']=='걸러짐'].iterrows():
    if r['구분']=='개별주' and (r.get('연매출(원)') or 0)>=1e13:
        L.append(f"  - {r['종목']}: {r['매도신호']}" + (f" (이익 {n(r.get('op_yoy'),'{:+.1f}','%')}, 이익률 {n(r.get('opm_yoy'),'{:+.1f}','%p')})" if '이익' in str(r['매도신호']) else ''))
L.append('')
L.append('블록 구조: 퀀트센터/블록구조_Ver.20261116_1430.txt, 전 종목: 퀀트센터/판정표_20261116.csv')
open('/mnt/project-files/퀀트센터/종목추천_Ver.20261116_1430.txt','w',encoding='utf-8').write('\n'.join(L))
print('\n'.join(L))
