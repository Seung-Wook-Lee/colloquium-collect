# ======================================================================
# [블록 9-닉스] 닉스 팀 기술적 계산 — 콜로키움 100 일봉·주봉 7개 기준과 차트 패턴
#   하는 일  : 블록 1이 쌓은 가격 이력으로 종목마다 아래를 계산한다(계산식은 nyx.py).
#              지지·저항선(띠·터치 수·거리·상태), 볼린저(20,2), RSI(14)·시그널(6), CCI(20)·시그널(10),
#              스토캐스틱 슬로우(14,3,3), 이격도(20·50·60·120일 / 20·50·60주), 일목균형표(9,26,52),
#              주봉 MACD 오실레이터(이번·지난·2주 전), 월봉 5개월선,
#              패턴(이중·삼중 바닥/천장, 헤드앤숄더, 역헤드앤숄더)
#   소스     : 수집데이터/00_누적/00_가격이력.csv (블록 1)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_닉스.csv (종목 한 줄, 일_·주_·월_ 머리말로 봉 구분)
#   쓰는 위원: 클로토·라케시스·아트로포스 (2026-10-28 의장: 이 7개 기준을 놓고 매번 말한다)
#   고칠 곳  : 띠 폭·패턴 기준은 nyx.py 맨 위 CFG (룰 변경은 의장 승인 뒤)
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
import nyx

try:
    px = pd.read_csv(f'{KEEP}/00_가격이력.csv', parse_dates=['날짜'], dtype={'티커': str})
    rows, bad = [], []
    for t, g in px.groupby('티커'):
        try:
            r = nyx.analyze(g.set_index('날짜').sort_index())
            if r:
                rows.append({'yfinance 티커': t, **r})
        except Exception as e:
            bad.append(f'{t}({type(e).__name__})')
    nx = u[['번호', '정식 종목명', '시장', '구분', '보유/관심', 'yfinance 티커']].merge(
        pd.DataFrame(rows), on='yfinance 티커', how='left')
    nx['계산시각(KST)'] = NOW.strftime('%Y-%m-%d %H:%M')
    nx.to_csv(f'{DAY}/{TODAY}_닉스.csv', index=False, encoding='utf-8-sig')

    cnt = lambda col, word: int(nx[col].fillna('').str.startswith(word).sum()) if col in nx else 0
    pat = lambda col: int(nx[col].fillna('').ne('').sum()) if col in nx else 0
    log(f'[9 닉스] {nx["종가"].notna().sum()}/{len(nx)}종목 | 주봉 지지 반등 {cnt("주_지지상태", "반등")} · '
        f'이탈 {cnt("주_지지상태", "이탈")} · 저항 돌파 {cnt("주_저항상태", "돌파")} | '
        f'패턴 일봉 {pat("일_패턴")} · 주봉 {pat("주_패턴")} | 계산 실패: {", ".join(bad) or "없음"}')
except Exception as e:
    traceback.print_exc()
    log(f'[9 닉스] 실패: {type(e).__name__} {e}')
