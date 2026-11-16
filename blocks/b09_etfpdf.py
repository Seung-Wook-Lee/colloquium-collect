# ======================================================================
# [블록 9-ETF구성] 한국 상장 ETF 보유 종목 상위 10 (2026-11-16 의장 "ETF는 왜 안 채우지")
#   하는 일  : 콜로키움 유니버스의 한국 상장 ETF마다 구성 종목과 비중을 받아 상위 10개를 남긴다.
#              퀀트센터 엔진이 이 표로 ETF의 이익·전망·재무·밸류 블록을 보유 비중 가중 평균한다.
#   소스     : 한투 ETF 구성종목시세(FHKST121600C0, inquire-component-stock-price)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_ETF구성.csv (번호, ETF, 순위, 코드, 이름, 비중)
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
#   주의     : 블록들은 한 공간(G)을 같이 쓴다. 맨 위에 변수를 두면 뒤 블록의 u·s 등을 덮어쓸 수 있어
#              (11/16 수급 블록 사고) 본문을 함수 안에 넣었다.
#              이 API는 구성 종목을 output2로 돌려줘서 kis_get(output만 받음) 대신 직접 부른다.
# ======================================================================
def _b09_etfpdf():
    if 'TOKEN' not in globals():
        raise RuntimeError('블록 2(한투) 없음')
    h = {'content-type': 'application/json; charset=utf-8', 'authorization': f'Bearer {TOKEN}',
         'appkey': SEC['KIS_APP_KEY'], 'appsecret': SEC['KIS_APP_SECRET'], 'tr_id': 'FHKST121600C0', 'custtype': 'P'}

    def call(code):
        for n in range(3):
            try:
                time.sleep(0.3)
                j = requests.get('https://openapi.koreainvestment.com:9443/uapi/etfetn/v1/quotations/inquire-component-stock-price',
                                 headers=h, params={'FID_COND_MRKT_DIV_CODE': 'J', 'FID_INPUT_ISCD': code,
                                                    'FID_COND_SCR_DIV_CODE': '11216'}, timeout=15).json()
                if j.get('rt_cd') == '0':
                    return j.get('output2') or j.get('output') or []
                err = f"{j.get('msg_cd')} {j.get('msg1')}"
            except Exception as e:
                err = f'{type(e).__name__} {e}'
            time.sleep(1 + 2 * n)
        print(f'  ETF구성 {code} 실패: {err}')
        return None

    ke = u[(u['시장'] == '한국') & (u['구분'] != '개별주')]
    rows, fails = [], []
    for _, s in ke.iterrows():
        out = call(str(s['코드']))
        d = pd.DataFrame(out or [])
        if d.empty or 'etf_cnfg_issu_rlim' not in d or 'stck_shrn_iscd' not in d:
            fails.append(s['정식 종목명'])
            continue
        d['비중'] = pd.to_numeric(d['etf_cnfg_issu_rlim'], errors='coerce')
        d = d[d['stck_shrn_iscd'].astype(str).str.strip() != ''].sort_values('비중', ascending=False).head(10)
        for i, (_, r) in enumerate(d.iterrows(), 1):
            rows.append({'번호': s['번호'], 'ETF': s['정식 종목명'], '순위': i, '코드': str(r['stck_shrn_iscd']).strip(),
                         '이름': r.get('hts_kor_isnm', ''), '비중': r['비중']})
    if not rows:
        raise RuntimeError(f'받은 ETF 없음(대상 {len(ke)}, 실패 {len(fails)})')
    ep = pd.DataFrame(rows)
    ep.to_csv(f'{DAY}/{TODAY}_ETF구성.csv', index=False, encoding='utf-8-sig')
    log(f'[9 ETF구성] {ep["번호"].nunique()}/{len(ke)}개 ETF, 구성 종목 {len(ep)}줄 | 실패: {", ".join(fails) or "없음"}')


try:
    _b09_etfpdf()
except Exception as e:
    import traceback
    traceback.print_exc()
    log(f'[9 ETF구성] 실패: {type(e).__name__} {e}')
