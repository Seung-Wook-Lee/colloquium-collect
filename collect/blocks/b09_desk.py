# ======================================================================
# [블록 9-데스크] 섹터 데스크 수급 — 데스크 5곳의 돈 흐름 (2026-10-31 의장)
#   하는 일  : 데스크마다 담당 종목·테마 ETF와 업종 대표 ETF(유니버스 밖, 미국)의
#              1·4·12주 초과수익, 섹터 로테이션 사분면(RRG), 거래대금 배율(5일/60일), 20주선 위·아래를 계산하고
#              데스크별 한 줄 요약(중앙값, 거래대금 늘며 오른 것·빠진 것)을 만든다. 계산식은 desk.py
#   소스     : 10년치 데이터베이스 1_data/가격10년_*(블록 1, PS.long) + 야후(업종 대표 ETF·닛케이225, 2년 일봉)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_데스크수급.csv (데스크 요약)
#              수집데이터/YYYYMMDD/YYYYMMDD_데스크수급상세.csv (종목·ETF 한 줄씩)
#   쓰는 위원: 섹터 데스크 5명(미스 세마이·미스터 빅스·미스 파이낸스·일라이 존슨·미스터 로보), 피터
#   고칠 곳  : 데스크 담당·업종 ETF는 desk.py DESKS
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
import desk

try:
    hist = PS.long(PXD, days=5 * 366)   # 10년치 데이터베이스(블록 1)
    ext = _yf(desk.extra_tickers(), '2y')          # 블록 1의 야후 함수
    allp = pd.concat([hist, ext]) if len(ext) else hist
    px = {t: g.set_index('날짜').sort_index() for t, g in allp.groupby('티커')}
    det, summ = desk.analyze(px, u)
    det.to_csv(f'{DAY}/{TODAY}_데스크수급상세.csv', index=False, encoding='utf-8-sig')
    summ.to_csv(f'{DAY}/{TODAY}_데스크수급.csv', index=False, encoding='utf-8-sig')
    log(f'[9 데스크] {len(summ)}곳 · {len(det)}줄 | ' +
        ' | '.join(f"{r['데스크'].split('(')[0]} 4주 {r['담당 종목 초과_4주 중앙값(%p)']:+.1f}%p" for _, r in summ.iterrows()))
except Exception as e:
    traceback.print_exc()
    log(f'[9 데스크] 실패: {type(e).__name__} {e}')
