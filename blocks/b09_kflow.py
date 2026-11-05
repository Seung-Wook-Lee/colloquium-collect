# ======================================================================
# [블록 9-국내수급] 한국 개별주 외국인·기관·개인 순매수 (2026-11-05 의장 "우리나라 수급도 외국인을 잘 봐야겠고")
#   하는 일  : 콜로키움 한국 개별주마다 최근 약 30영업일의 투자자별 순매수(거래대금)를 받아
#              외국인 연속 순매수·순매도 일수, 외국인·기관·개인 1·5·20일 누적(억원), 20일 주가 변화를 낸다.
#              표시만 한다(판정 없음): '주가↓·외국인↑' = 20일 주가는 내렸는데 외국인 20일 누적은 순매수,
#              '주가↑·외국인↓' = 반대, '외국인 방향 바뀜' = 최근 5일 누적과 그 앞 15일 누적의 부호가 다름.
#   소스     : 한투 주식현재가 투자자(FHKST01010900, inquire-investor). 07시에는 어제까지 확정 자료.
#              (일별 투자자 매매 FHPTJ04160001은 장 마감 15:40 뒤에만 되어 아침에 못 씀)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_국내수급.csv (종목 한 줄, 외국인 5일 누적 순)
#   쓰는 위원: 뉴스 국장(업종 수급), 라케시스·클로토(수급 확인), 데스크
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
KF_COLS = {'외국인': 'frgn_ntby_tr_pbmn', '기관': 'orgn_ntby_tr_pbmn', '개인': 'prsn_ntby_tr_pbmn'}   # 백만원
try:
    if 'kis_get' not in globals():
        raise RuntimeError('블록 2(한투) 없음')
    kr = u[(u['시장'] == '한국') & (u['구분'] == '개별주')]
    rows, n_fail, first_keys = [], 0, None
    for _, s in kr.iterrows():
        out = kis_get('/uapi/domestic-stock/v1/quotations/inquire-investor', 'FHKST01010900',
                      {'FID_COND_MRKT_DIV_CODE': 'J', 'FID_INPUT_ISCD': s['코드']})
        if not out:
            n_fail += 1
            continue
        first_keys = first_keys or list(out[0].keys())
        d = pd.DataFrame(out)
        d = d[(d['stck_bsop_date'] < TODAY) & (d[KF_COLS['외국인']].astype(str).str.strip() != '')]
        d = d.sort_values('stck_bsop_date', ascending=False).reset_index(drop=True)   # 0 = 가장 최근일
        if len(d) < 2:
            n_fail += 1
            continue
        v = {k: pd.to_numeric(d[c], errors='coerce').fillna(0) / 100 for k, c in KF_COLS.items()}   # 억원
        px = pd.to_numeric(d['stck_clpr'], errors='coerce')
        f = v['외국인']
        sgn = (f > 0).astype(int) - (f < 0).astype(int)
        streak = 0
        if sgn[0] != 0:
            for x in sgn:
                if x != sgn[0]:
                    break
                streak += 1
        row = {'번호': s['번호'], '종목': s['정식 종목명'], '코드': s['코드'], '기준일': d['stck_bsop_date'][0],
               '종가': px[0], '외국인 연속': (f'순매수 {streak}일' if sgn[0] > 0 else f'순매도 {streak}일' if sgn[0] < 0 else '0')}
        for k in KF_COLS:
            for n in (1, 5, 20):
                row[f'{k} {n}일(억원)'] = round(v[k][:n].sum(), 1) if len(d) >= n else None
        n20 = min(20, len(d) - 1)
        row['주가 20일(%)'] = round((px[0] / px[n20] - 1) * 100, 1) if px[n20] else None
        f20, f5, f15 = row['외국인 20일(억원)'], f[:5].sum(), f[5:20].sum()
        flag = []
        if f20 is not None and row['주가 20일(%)'] is not None:
            if row['주가 20일(%)'] < 0 < f20:
                flag.append('주가↓·외국인↑')
            elif row['주가 20일(%)'] > 0 > f20:
                flag.append('주가↑·외국인↓')
        if len(d) >= 20 and f5 * f15 < 0:
            flag.append('외국인 방향 바뀜(' + ('매수 전환' if f5 > 0 else '매도 전환') + ')')
        row['표시'] = ', '.join(flag)
        rows.append(row)
    if not rows:
        raise RuntimeError(f'받은 종목 없음(실패 {n_fail})')
    kf = pd.DataFrame(rows).sort_values('외국인 5일(억원)', ascending=False)
    kf.to_csv(f'{DAY}/{TODAY}_국내수급.csv', index=False, encoding='utf-8-sig')
    top = ', '.join(f'{r["종목"]} {r["외국인 5일(억원)"]:+,.0f}' for _, r in kf.head(3).iterrows())
    bot = ', '.join(f'{r["종목"]} {r["외국인 5일(억원)"]:+,.0f}' for _, r in kf.tail(3).iloc[::-1].iterrows())
    long_ = ', '.join(f'{r["종목"]} {r["외국인 연속"]}' for _, r in kf.iterrows()
                      if int(''.join(ch for ch in r['외국인 연속'] if ch.isdigit()) or 0) >= 5)
    log(f'[9 국내수급] {len(kf)}종목(실패 {n_fail}) 기준 {kf["기준일"].max()} | 외국인 5일 상위 {top} | 하위 {bot} | 5일 이상 연속: {long_ or "없음"}')
except Exception as e:
    import traceback
    traceback.print_exc()
    log(f'[9 국내수급] 실패: {type(e).__name__} {e}')
