# ======================================================================
# [블록 9-섹터] 닉스 팀 섹터 순환 — 한국 섹터 ETF를 TIGER 200과 비교 (2026-10-29 의장 승인 룰 v1)
#   하는 일  : 섹터 ETF마다 아래를 계산한다(계산식은 sector.py).
#              1·3·6·12개월 수익률과 TIGER 200 대비 초과수익, 모멘텀 순위(1·3·6개월 초과수익 순위 평균),
#              섹터 로테이션 사분면(RRG 근사: 선도·약화·침체·개선, 4주 전과 비교), 20주선 위·기울기,
#              52주 고점 대비, 닉스 7개 기준(일봉·주봉), 판정(라케시스·미스 차트·아트로포스, 닉스_공통 6장)
#   소스     : 10년치 데이터베이스 1_data/가격10년_*(블록 1, PS.long)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_섹터.csv (섹터 한 줄, 모멘텀 순위 순)
#              수집데이터/YYYYMMDD/YYYYMMDD_섹터궤적.csv (최근 8주 RS-Ratio·RS-Momentum, 스트림릿 사분면 그림용)
#   쓰는 위원: 미스 차트(반전 섹터), 라케시스(추세 강한 섹터), 아트로포스(과열·꺾임 섹터)
#   고칠 곳  : 대상 섹터 ETF는 아래 SECTOR_NO, 벤치마크는 BENCH_NO. 판정 기준은 sector.py judge (룰 변경은 의장 승인 뒤)
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
import sector

SECTOR_NO = ['K1-1', 'K1-5', 'K1-2', 'K4-1', 'K4-2', 'K2-2', 'K2-1', 'K3-2', 'K5-1', 'K1-4', 'K2-3', 'K2-4']
BENCH_NO = 'K0-1'          # TIGER 200

try:
    hist = PS.long(PXD, days=5 * 366)   # 10년치 데이터베이스(블록 1)
    tick = u.set_index('번호')['yfinance 티커']
    names = u.set_index('번호')['정식 종목명']
    members = [(no, names[no], tick[no]) for no in SECTOR_NO if no in tick.index]
    need = {t for _, _, t in members} | {tick[BENCH_NO]}
    px = {t: g.set_index('날짜').sort_index() for t, g in hist[hist['티커'].isin(need)].groupby('티커')}
    sec, trail = sector.analyze(px, members, tick[BENCH_NO])
    sec['계산시각(KST)'] = NOW.strftime('%Y-%m-%d %H:%M')
    sec.to_csv(f'{DAY}/{TODAY}_섹터.csv', index=False, encoding='utf-8-sig')
    trail.to_csv(f'{DAY}/{TODAY}_섹터궤적.csv', index=False, encoding='utf-8-sig')

    pick = lambda w: ', '.join(sec.loc[sec['판정'].str.contains(w), '종목']) or '없음'
    log(f'[9 섹터] {len(sec)}/{len(SECTOR_NO)}개 | 20주선 위 {int((sec["20주선_위"] == "위").sum())}개 | '
        f'라케시스 추세 강함: {pick("라케시스 추세 강함")} | 미스 차트 반전 후보: {pick("미스 차트 반전 후보")} | '
        f'아트로포스: {pick("아트로포스")}')
except Exception as e:
    traceback.print_exc()
    log(f'[9 섹터] 실패: {type(e).__name__} {e}')
