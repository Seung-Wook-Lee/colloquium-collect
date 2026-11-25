# ======================================================================
# [블록 9-한투창고] 한투 시세 창고 — 스튜디오 톰앤수 100 일봉·주봉·월봉을 드라이브에 쌓기 (2026-11-09 의장)
#   하는 일  : 한국투자증권 API로 유니버스 100종목의 일봉·주봉·월봉(수정주가)을 받아 00_누적 창고에 이어 쓴다.
#              매일: 종목·주기마다 최근 100줄을 받아 덮어 넣는다(진행 중인 주·월은 매일 갱신).
#              과거 채우기: 창고에 목표 기간(일봉 10년, 주봉·월봉 20년)이 없으면 한 번에 BACKFILL_CALLS번까지
#              더 과거 페이지를 받는다. 며칠에 걸쳐 다 채워지면 그 종목·주기는 '완료'로 적고 다시 받지 않는다.
#              그날 밸류에이션(블록 2)도 00_한투_밸류이력.csv에 하루 한 줄씩 쌓는다.
#   목적     : 클로드·챗지·제이미가 드라이브에서 바로 찾아 쓰게(야후를 매번 받지 않게) 한투 원자료를 한곳에.
#   소스     : 한투 국내 FHKST03010100(기간별 시세), 해외 HHDFS76240000(기간별 시세). 블록 2 토큰을 같이 쓴다. 조회만.
#   만드는 것: 수집데이터/00_누적/00_한투_일봉.csv · 00_한투_주봉.csv · 00_한투_월봉.csv
#                (긴 표: 번호,코드,종목명,시장,날짜,시가,고가,저가,종가,거래량. 날짜는 그 봉의 마지막 거래일)
#              수집데이터/00_누적/00_한투_밸류이력.csv (날짜별 PER·PBR·EPS·BPS·외국인 소진율 등)
#              수집데이터/00_누적/00_한투_창고상태.csv (종목·주기별 첫날·끝날·줄 수·과거 채우기 완료)
#              수집데이터/00_누적/00_한투_창고_안내.txt (AI가 읽는 설명서)
#   쓰는 위원: 직접 쓰는 위원 없음(자료 창고). 기존 계산(블록 1 야후 가격이력)은 그대로 둔다.
#   주의     : 수정주가는 받은 날 기준. 분할·배당으로 과거가 바뀌면 그 종목을 상태 파일에서 지우면 다시 받는다.
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
KS_FILES = {'D': f'{KEEP}/00_한투_일봉.csv', 'W': f'{KEEP}/00_한투_주봉.csv', 'M': f'{KEEP}/00_한투_월봉.csv'}
KS_YEARS = {'D': 10, 'W': 20, 'M': 20}          # 과거 채우기 목표
KS_STATE = f'{KEEP}/00_한투_창고상태.csv'
KS_VAL = f'{KEEP}/00_한투_밸류이력.csv'
KS_COLS = ['번호', '코드', '종목명', '시장', '날짜', '시가', '고가', '저가', '종가', '거래량']
BACKFILL_CALLS = 1000                           # 과거 채우기 호출 한도
# 과거 채우기 시간 한도: 07시 정기 실행은 4분(전체 45분 제한 안, 11/10 시험에서 한투 1회 약 1.2초),
# 손으로 블록만 돌릴 때(BLOCKS 입력 있음)는 25분
BACKFILL_SEC = 1500 if os.environ.get('BLOCKS', '').strip() else 240
KS_T0 = time.time()
KS_EXCD = {'NASDAQ': 'NAS', 'NYSE': 'NYS', 'NYSE American': 'AMS', 'NYSE Arca': 'AMS', 'Cboe BZX': 'AMS', 'TSE 프라임': 'TSE'}
KS_GUBN = {'D': '0', 'W': '1', 'M': '2'}


def _ks_call(path, tr_id, params):
    """한투 GET 한 번(재시도 2회). 성공이면 output2 목록, 실패면 None."""
    h = {'content-type': 'application/json; charset=utf-8', 'authorization': f'Bearer {TOKEN}',
         'appkey': SEC['KIS_APP_KEY'], 'appsecret': SEC['KIS_APP_SECRET'], 'tr_id': tr_id, 'custtype': 'P'}
    for n in range(3):
        try:
            time.sleep(0.3)
            j = requests.get(f'https://openapi.koreainvestment.com:9443{path}', headers=h, params=params, timeout=15).json()
            if j.get('rt_cd') == '0':
                return j.get('output2') or []
        except Exception:
            pass
        time.sleep(1 + 2 * n)
    return None


def ks_page(s, per, end):
    """종목 s(유니버스 한 줄), 주기 per(D/W/M), end(YYYYMMDD) 이전 최대 100줄 → DataFrame(KS_COLS) 또는 None."""
    if s['시장'] == '한국':
        start = (pd.Timestamp(end) - pd.DateOffset(years={'D': 1, 'W': 3, 'M': 10}[per])).strftime('%Y%m%d')
        rows = _ks_call('/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice', 'FHKST03010100',
                        {'FID_COND_MRKT_DIV_CODE': 'J', 'FID_INPUT_ISCD': s['코드'], 'FID_INPUT_DATE_1': start,
                         'FID_INPUT_DATE_2': end, 'FID_PERIOD_DIV_CODE': per, 'FID_ORG_ADJ_PRC': '0'})
        if rows is None:
            return None
        f = dict(d='stck_bsop_date', o='stck_oprc', h='stck_hgpr', l='stck_lwpr', c='stck_clpr', v='acml_vol')
    else:
        rows = _ks_call('/uapi/overseas-price/v1/quotations/dailyprice', 'HHDFS76240000',
                        {'AUTH': '', 'EXCD': s['_excd'], 'SYMB': str(s['코드']).replace('-', '/'), 'GUBN': KS_GUBN[per], 'BYMD': end, 'MODP': '1'})
        if rows is None:
            return None
        f = dict(d='xymd', o='open', h='high', l='low', c='clos', v='tvol')
    rows = [r for r in rows if r.get(f['d'])]
    if not rows:
        return pd.DataFrame(columns=KS_COLS)
    d = pd.DataFrame(rows)
    out = pd.DataFrame({'번호': s['번호'], '코드': s['코드'], '종목명': s['정식 종목명'], '시장': s['시장'],
                        '날짜': pd.to_datetime(d[f['d']], format='%Y%m%d', errors='coerce'),
                        '시가': pd.to_numeric(d[f['o']], errors='coerce'), '고가': pd.to_numeric(d[f['h']], errors='coerce'),
                        '저가': pd.to_numeric(d[f['l']], errors='coerce'), '종가': pd.to_numeric(d[f['c']], errors='coerce'),
                        '거래량': pd.to_numeric(d[f['v']], errors='coerce')})
    return out[(out['종가'] > 0) & out['날짜'].notna()].drop_duplicates('날짜')


def ks_excd(s):
    """해외 종목의 한투 거래소 코드. 첫 후보에서 안 나오면 NAS·NYS·AMS 차례로."""
    first = KS_EXCD.get(s['거래소'], 'NAS')
    for ex in [first] + ([] if first == 'TSE' else [e for e in ('NAS', 'NYS', 'AMS') if e != first]):
        x = ks_page(dict(s, _excd=ex), 'D', TODAY)
        if x is not None and len(x):
            return ex
    return None


def ks_merge(store, new):
    if store is None or store.empty:
        return new.reset_index(drop=True)
    x = pd.concat([store, new]).drop_duplicates(['번호', '날짜'], keep='last')
    return x.sort_values(['번호', '날짜']).reset_index(drop=True)


KS_GUIDE = """한투 시세 창고 안내 (스튜디오 톰앤수 07시 수집 블록 9-한투창고가 매일 갱신)
- 00_한투_일봉.csv / 00_한투_주봉.csv / 00_한투_월봉.csv
  스튜디오 톰앤수 100 유니버스 종목의 한국투자증권 시세(수정주가). 긴 표 한 줄 = 한 종목의 한 봉.
  칸: 번호(유니버스 번호 K1-9·U1-4…), 코드(국내 6자리·해외 티커·일본 4자리), 종목명, 시장(한국/미국/일본), 날짜(그 봉의 마지막 거래일),
      시가, 고가, 저가, 종가(현지 통화: 한국 원, 미국 달러, 일본 엔), 거래량
  목표 기간: 일봉 10년, 주봉·월봉 20년(상장이 늦은 종목은 상장일부터). 진행 중인 주·월 봉은 매일 바뀐다.
- 00_한투_밸류이력.csv: 날짜별 한투 현재가·PER·PBR·EPS·BPS·외국인 소진율·시가총액(블록 2의 그날 값을 쌓음, 2026-11-10부터)
- 00_한투_창고상태.csv: 종목·주기별 첫날·끝날·줄 수·과거 채우기 완료 여부
- 찾는 법 예: 종목명 또는 코드로 거르고 날짜로 정렬. 유니버스 목록은 드라이브 포트폴리오 폴더 콜로키움100_유니버스_최신 날짜.csv
- 숫자는 한투가 준 그대로다. 계산값(이동평균·RSI 등)은 넣지 않는다.
"""

try:
    if not (SEC.get('KIS_APP_KEY') and SEC.get('KIS_APP_SECRET')):
        raise RuntimeError('한투 키 없음')
    if 'TOKEN' not in globals() or not TOKEN:
        TOKEN = kis_token()
    uu = u[['번호', '정식 종목명', '시장', '거래소', '코드']].copy()
    uu['코드'] = uu['코드'].astype(str).str.strip()
    uu.loc[uu['시장'] == '한국', '코드'] = uu.loc[uu['시장'] == '한국', '코드'].str.zfill(6)
    state = pd.read_csv(KS_STATE, dtype=str, keep_default_na=False) if os.path.exists(KS_STATE) else \
        pd.DataFrame(columns=['번호', '코드', '주기', '거래소코드', '첫날', '끝날', '줄수', '과거완료'])
    st = {(r['번호'], r['코드'], r['주기']): dict(r) for _, r in state.iterrows()}
    stores = {p: (pd.read_csv(f, dtype={'번호': str, '코드': str}, parse_dates=['날짜']) if os.path.exists(f)
                  else pd.DataFrame(columns=KS_COLS)) for p, f in KS_FILES.items()}
    budget, bad, n_new = BACKFILL_CALLS, [], {p: 0 for p in KS_FILES}
    for _, s in uu.iterrows():
        s = dict(s)
        if s['시장'] != '한국':
            ex = next((v['거래소코드'] for k, v in st.items() if k[:2] == (s['번호'], s['코드']) and v.get('거래소코드')), None)
            s['_excd'] = ex or ks_excd(s)
            if not s['_excd']:
                bad.append(s['코드']); continue
        for per in ('D', 'W', 'M'):
            key = (s['번호'], s['코드'], per)
            rec = st.get(key, {'번호': s['번호'], '코드': s['코드'], '주기': per, '과거완료': ''})
            got = []
            x = ks_page(s, per, TODAY)                       # 매일: 최근 100줄
            if x is None:
                bad.append(f"{s['코드']}/{per}"); continue
            got.append(x)
            have = pd.to_datetime(stores[per].loc[stores[per]['번호'] == s['번호'], '날짜'])
            cands = [t for t in (have.min() if len(have) else None, x['날짜'].min() if len(x) else None)
                     if t is not None and not pd.isna(t)]
            oldest = min(cands) if cands else None
            target = pd.Timestamp(TODAY) - pd.DateOffset(years=KS_YEARS[per])
            while rec.get('과거완료') != '예' and budget > 0 and time.time() - KS_T0 < BACKFILL_SEC \
                    and oldest is not None and oldest > target:
                y = ks_page(s, per, (oldest - pd.Timedelta(days=1)).strftime('%Y%m%d'))
                budget -= 1
                if y is None:
                    break
                y = y[y['날짜'] < oldest]
                if y.empty:                                   # 더 과거가 없음(상장일 도달)
                    rec['과거완료'] = '예'; break
                got.append(y); oldest = y["날짜"].min()
            if oldest is not None and oldest <= target:
                rec['과거완료'] = '예'
            new = pd.concat(got)
            if len(new):
                n_new[per] += len(new)
                stores[per] = ks_merge(stores[per], new)
            mine = stores[per][stores[per]['번호'] == s['번호']]['날짜']
            rec.update({'거래소코드': s.get('_excd', ''), '첫날': str(mine.min().date()) if len(mine) else '',
                        '끝날': str(mine.max().date()) if len(mine) else '', '줄수': str(len(mine))})
            st[key] = rec
    keep_ids = set(uu['번호'])
    for per, f in KS_FILES.items():
        x = stores[per]
        x = x[x['번호'].isin(keep_ids)] if len(x) else x               # 편출 종목은 창고에서 뺀다
        if len(x):
            x.assign(날짜=pd.to_datetime(x['날짜']).dt.strftime('%Y-%m-%d'))[KS_COLS].to_csv(f, index=False, encoding='utf-8-sig')
    S = pd.DataFrame(st.values())
    S = S[S['번호'].isin(keep_ids)] if len(S) else S
    S.to_csv(KS_STATE, index=False, encoding='utf-8-sig')
    # 밸류 이력: 블록 2의 오늘 파일을 하루 한 묶음으로 쌓는다
    vf = f'{DAY}/{TODAY}_밸류에이션.csv'
    if os.path.exists(vf):
        v = pd.read_csv(vf, dtype={'번호': str, '코드': str})
        v.insert(0, '날짜', f'{TODAY[:4]}-{TODAY[4:6]}-{TODAY[6:]}')
        old = pd.read_csv(KS_VAL, dtype={'번호': str, '코드': str, '날짜': str}) if os.path.exists(KS_VAL) else None
        V = v if old is None else pd.concat([old[old['날짜'] != v['날짜'].iloc[0]], v], ignore_index=True)
        V.to_csv(KS_VAL, index=False, encoding='utf-8-sig')
    with open(f'{KEEP}/00_한투_창고_안내.txt', 'w', encoding='utf-8') as g:
        g.write(KS_GUIDE)
    done = int((S['과거완료'] == '예').sum()) if len(S) else 0
    log(f'[9 한투창고] 일봉 {len(stores["D"]):,}줄·주봉 {len(stores["W"]):,}줄·월봉 {len(stores["M"]):,}줄 | '
        f'과거 채우기 완료 {done}/{len(S)} (오늘 과거 호출 {BACKFILL_CALLS - budget}) | 못 받음: {", ".join(bad[:10]) or "없음"}')
except Exception as e:
    traceback.print_exc()
    log(f'[9 한투창고] 실패: {type(e).__name__} {e}')
