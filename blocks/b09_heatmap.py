# ======================================================================
# [블록 9-히트맵] 스트림릿 '오늘 시장' 맨 위 히트맵 자료 (2026-11-10 의장 "히트맵도 넣어야 할 것 같고, 제일 위에")
#   하는 일  : (가) S&P500: SPDR 섹터 ETF 11개의 상위 10종목(yeokdosan/holdings_top10.csv)을 섹터별로 묶어
#                   1일·1주(5거래일)·1달(21거래일) 등락률과 시가총액(칸 크기)을 적는다. 섹터 ETF 줄도 함께.
#              (가-2) 한국: heatmap_kr.csv의 코스피·코스닥 주요 약 70종목(섹터별, 칸 크기 시총)
#              (나) 콜로키움 100: 유니버스 종목을 층(S0~S6)별로 묶어 같은 세 기간 등락률(칸 크기는 같게).
#              판정은 하지 않는다. 숫자만.
#   소스     : 야후(키 없음, 최근 3달 일봉·시가총액), 수집데이터/00_누적/00_가격이력.csv(블록 1)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_히트맵.csv (시장, 묶음, 티커, 이름, 시총, 1일, 1주, 1달, 종가, 기준일)
#   쓰는 곳  : 스트림릿 '오늘 시장' 히트맵 (위원 발언에는 쓰지 않음)
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
import heatmap as hmmod   # 계산식(스트림릿과 같이 씀)

try:
    hold = pd.read_csv('yeokdosan/holdings_top10.csv')
    HM = hmmod.sp500(yf, hold)   # (가) S&P500 섹터 × 상위 10 + 섹터 ETF 줄
    HM += hmmod.korea(yf, pd.read_csv('heatmap_kr.csv'))   # (가-2) 한국: 코스피·코스닥 주요 약 70종목
    caps = {r['티커']: r['시총'] for r in HM if r['시장'] in ('S&P500', '한국')}
    # (나) 콜로키움 100 (블록 1 가격 이력)
    ph = pd.read_csv(f'{KEEP}/00_가격이력.csv', parse_dates=['날짜'], dtype={'티커': str},
                     usecols=['날짜', '티커', '수정종가', '종가'])
    ph = ph[ph['날짜'] >= ph['날짜'].max() - pd.Timedelta(days=60)]
    ph['가격'] = ph['수정종가'].fillna(ph['종가'])
    grpcol = '층 이름' if '층 이름' in u.columns else '섹터/테마'
    for _, r in u.iterrows():
        g = ph[ph['티커'] == r['yfinance 티커']].set_index('날짜')['가격'].sort_index()
        if not len(g):
            continue
        grp = r.get(grpcol)
        lay = r.get('층')
        label = f'{lay} {grp}' if isinstance(lay, str) and isinstance(grp, str) else (grp if isinstance(grp, str) else '기타')
        HM.append({'시장': '콜로키움 100', '묶음': label, '티커': r['yfinance 티커'], '이름': r['정식 종목명'],
                   '시총': None, **hmmod.returns(g)})
    hm = pd.DataFrame(HM, columns=hmmod.COLS)
    hm.to_csv(f'{DAY}/{TODAY}_히트맵.csv', index=False, encoding='utf-8-sig')
    log(f'[9 히트맵] S&P500 {int((hm.시장 == "S&P500").sum())}종목·한국 {int((hm.시장 == "한국").sum())}종목·섹터 ETF {int((hm.시장 == "S&P500 섹터 ETF").sum())} | '
        f'콜로키움 100 {int((hm.시장 == "콜로키움 100").sum())}종목 | 시총 {sum(v is not None for v in caps.values())}/{len(caps)}')
except Exception as e:
    traceback.print_exc()
    log(f'[9 히트맵] 실패: {type(e).__name__} {e}')
