# ======================================================================
# [블록 2] 한투 밸류에이션 — 스튜디오 톰앤수 100 PER·PBR·EPS·BPS
#   하는 일  : 한국투자증권 API로 토큰을 받고(24시간 유효, 파일 저장 안 함),
#              국내 50종목(국내 현재가 시세)과 미국·일본 50종목(해외 현재가 상세)을 조회한다.
#              국내는 외국인 소진율·시가총액·52주 고저도 받는다. 조회만 하고 주문은 하지 않는다.
#              개별주는 야후에서 선행 PER·선행 EPS(애널리스트 예상 1년 이익 기준)도 받아 옆 칸에 붙인다.
#              (한국 종목의 야후 선행 값은 근거가 불분명해 '참고'로만 쓴다)
#              한투 '종목 추정실적'(국내 컨센서스)은 시험 단계: 삼성전자 하나만 받아 진단 파일로 남긴다.
#   소스     : KIS Developers 실전 서버 (블록 0의 한투 키 2개 필요, 요청 간격 0.3초·재시도 2회), 야후(선행 PER)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_밸류에이션.csv
#              수집데이터/YYYYMMDD/YYYYMMDD_진단_한투추정실적.json (시험용, 형식 확인 뒤 없앨 예정)
#   쓰는 위원: 미스 밸류·섹터 위원(밸류에이션), 미스 차트 가점 ⑨(외국인 소진율)
#   주의     : 한투 PER은 직전 연간 EPS 기준 → 최근 4분기(TTM) PER은 블록 6(DART)·7(SEC)이 다시 계산
#   고칠 곳  : 미국 종목이 '실패'로 나오면 EXCD(거래소 코드표)
#   실패하면 : 한투가 막히면(해외 접속 차단 등) 같은 칸을 야후 값으로 채우고 출처에 '야후 (한투 실패로 대체)'라고 적는다
# ======================================================================
BASE = 'https://openapi.koreainvestment.com:9443'   # 실전 서버, 조회만
KIS_PAUSE = 0.3                                     # 실전 초당 20회 제한보다 넉넉히
EXCD = {'NASDAQ': 'NAS', 'NYSE': 'NYS', 'NYSE American': 'AMS', 'NYSE Arca': 'AMS',
        'Cboe BZX': 'AMS', 'TSE 프라임': 'TSE'}

def kis_token():
    # 토큰은 24시간 유효, 1분에 1회만 발급 가능. 11/25 의장 "07시 조회 때 0730 것까지 한꺼번에": 같은 실행 안 스크립트들이
    # 토큰 하나를 같이 쓰도록 러너 임시 파일(KIS_TOKEN_FILE)에만 둔다(실행이 끝나면 사라짐).
    import json as _j, time as _t
    _f = os.environ.get('KIS_TOKEN_FILE', '')
    if _f and os.path.exists(_f):
        try:
            _x = _j.load(open(_f))
            if _t.time() - _x['t'] < 20 * 3600:
                return _x['v']
        except Exception:
            pass
    r = requests.post(f'{BASE}/oauth2/tokenP', timeout=10, json={
        'grant_type': 'client_credentials', 'appkey': SEC['KIS_APP_KEY'], 'appsecret': SEC['KIS_APP_SECRET']})
    tok = r.json().get('access_token')
    if not tok:
        raise RuntimeError(f"토큰 발급 실패 {r.json().get('error_code')} {r.json().get('error_description')}")
    if _f:
        _j.dump({'v': tok, 't': _t.time()}, open(_f, 'w'))
        os.chmod(_f, 0o600)
    return tok

def kis_get(path, tr_id, params, retry=2):
    h = {'content-type': 'application/json; charset=utf-8', 'authorization': f'Bearer {TOKEN}',
         'appkey': SEC['KIS_APP_KEY'], 'appsecret': SEC['KIS_APP_SECRET'], 'tr_id': tr_id, 'custtype': 'P'}
    for n in range(retry + 1):
        try:
            time.sleep(KIS_PAUSE)
            out = requests.get(f'{BASE}{path}', headers=h, params=params, timeout=10).json()
            if out.get('rt_cd') == '0' and out.get('output'):
                return out['output']
            raise ValueError(f"{out.get('msg_cd')} {out.get('msg1')}")
        except Exception as e:
            if n == retry:
                return None
            time.sleep(1 + 2 * n)

def num(v):
    try:
        f = float(str(v).replace(',', ''))
        return f if f != 0 else None   # 한투는 값이 없으면 0을 준다 → 빈칸으로
    except Exception:
        return None


# 야후 보조 정보: 선행 PER(개별주)과, 한투가 막혔을 때 대신 쓸 현재가·PER·PBR·시가총액·52주 고저
def yahoo_info(rows_u):
    out = {}
    for _, s in rows_u.iterrows():
        try:
            out[s['번호']] = yf.Ticker(s['yfinance 티커']).info or {}
        except Exception as e:
            print('  야후 정보 실패', s['yfinance 티커'], e)
        time.sleep(0.4)
    return out


val, kis_err = None, None
def _evening_val():
    """11/25 의장 "아침 8시 미국, 저녁 8시 한국": 아침엔 한투에 접속하지 않고 전날 저녁 8시 수집의 한투 밸류에이션을 쓴다."""
    for _d in range(1, 6):
        _day = (NOW - dt.timedelta(days=_d)).strftime('%Y%m%d')
        try:
            _b = gdrive.get(f'{D_DATA}/{_day}/{_day}_밸류에이션.csv')
        except Exception:
            _b = None
        if _b:
            _v = pd.read_csv(io.BytesIO(_b), dtype={'코드': str}, encoding='utf-8-sig')
            if _v['출처'].astype(str).str.contains('한국투자증권').any():
                return _v, _day
    return None, None


KIS_OFF = os.environ.get('KIS_OFF') == '1'
try:
    if KIS_OFF:
        raise RuntimeError('아침 수집: 한투 접속 안 함(저녁 8시 수집이 받음)')
    if not (SEC.get('KIS_APP_KEY') and SEC.get('KIS_APP_SECRET')):
        raise RuntimeError('한투 키 없음')
    if 'TOKEN' not in globals() or not TOKEN:
        TOKEN = kis_token()
    rows = []
    for _, s in u.iterrows():
        r = {'번호': s['번호'], '정식 종목명': s['정식 종목명'], '시장': s['시장'], '구분': s['구분'], '코드': s['코드']}
        if s['시장'] == '한국':
            x = kis_get('/uapi/domestic-stock/v1/quotations/inquire-price', 'FHKST01010100',
                        {'FID_COND_MRKT_DIV_CODE': 'J', 'FID_INPUT_ISCD': s['코드']})
            if x:
                r.update({'현재가': num(x.get('stck_prpr')), '통화': 'KRW', 'PER': num(x.get('per')),
                          'PBR': num(x.get('pbr')), 'EPS': num(x.get('eps')), 'BPS': num(x.get('bps')),
                          '외국인 소진율(%)': num(x.get('hts_frgn_ehrt')), '시가총액(억원)': num(x.get('hts_avls')),
                          '52주 고가': num(x.get('w52_hgpr')), '52주 저가': num(x.get('w52_lwpr'))})
        else:
            first = EXCD.get(s['거래소'], 'NAS')
            for ex in [first] + [e for e in ['NAS', 'NYS', 'AMS'] if e != first and first != 'TSE']:
                x = kis_get('/uapi/overseas-price/v1/quotations/price-detail', 'HHDFS76200200',
                            {'AUTH': '', 'EXCD': ex, 'SYMB': str(s['코드']).replace('-', '/')})   # 한투 해외 기호는 BRK/B 식(11/16)
                if x and num(x.get('last')):
                    r.update({'현재가': num(x.get('last')), '통화': x.get('curr'), 'PER': num(x.get('perx')),
                              'PBR': num(x.get('pbrx')), 'EPS': num(x.get('epsx')), 'BPS': num(x.get('bpsx')),
                              '52주 고가': num(x.get('h52p')), '52주 저가': num(x.get('l52p')), '거래소코드': ex})
                    break
        r['수신'] = '성공' if r.get('현재가') else '실패'
        rows.append(r)
    val = pd.DataFrame(rows)
    val['출처'] = '한국투자증권 KIS'
    if (val['수신'] == '성공').sum() == 0:
        raise RuntimeError('한투에서 받은 종목이 하나도 없음 (해외 접속 차단일 수 있음)')
except Exception as e:
    traceback.print_exc()
    kis_err, val = f'{type(e).__name__} {e}', None

try:
    # 한투가 되면 개별주만, 안 되면 100종목 전부 야후에서
    info = yahoo_info(u[u['구분'] == '개별주'] if val is not None else u)
    if val is None:   # 한투 대신 야후 값으로 같은 칸을 채운다 (외국인 소진율은 비움)
        rows = []
        for _, s in u.iterrows():
            i = info.get(s['번호'], {})
            mc = i.get('marketCap')
            rows.append({'번호': s['번호'], '정식 종목명': s['정식 종목명'], '시장': s['시장'], '구분': s['구분'], '코드': s['코드'],
                         '현재가': i.get('currentPrice') or i.get('regularMarketPrice') or i.get('navPrice'),
                         '통화': i.get('currency'), 'PER': i.get('trailingPE'), 'PBR': i.get('priceToBook'),
                         'EPS': i.get('trailingEps'), 'BPS': i.get('bookValue'),
                         '시가총액(억원)': round(mc / 1e8) if mc and s['시장'] == '한국' else None,
                         '52주 고가': i.get('fiftyTwoWeekHigh'), '52주 저가': i.get('fiftyTwoWeekLow'),
                         '수신': '성공' if i else '실패'})
        val = pd.DataFrame(rows)
        val['출처'] = '야후 (한투 실패로 대체)'
        if KIS_OFF:   # 한국 종목은 전날 저녁 8시 한투 값(한국 장은 그 뒤로 열리지 않음), 미국은 야후 최신
            _ev, _evd = _evening_val()
            if _ev is not None:
                _ev = _ev[_ev['시장'] == '한국'].set_index('번호')
                _kr = val['번호'].isin(_ev.index)
                for _c in [c for c in _ev.columns if c in val.columns or c in ('외국인 소진율(%)',)]:
                    if _c in ('번호', '선행 PER(야후)', '선행 EPS(야후)', '수집시각(KST)'):
                        continue
                    val.loc[_kr, _c] = val.loc[_kr, '번호'].map(_ev[_c])
                val.loc[_kr, '출처'] = f'한국투자증권 KIS ({_evd} 저녁 8시)'
                kis_err = f'아침: 한투 접속 안 함, 한국 {int(_kr.sum())}종목은 {_evd} 저녁 한투 값'
    val['선행 PER(야후)'] = val['번호'].map(lambda n: round(info[n]['forwardPE'], 2)
                                           if info.get(n, {}).get('forwardPE') else None)
    val['선행 EPS(야후)'] = val['번호'].map(lambda n: info.get(n, {}).get('forwardEps'))
    val.loc[val['구분'] != '개별주', ['선행 PER(야후)', '선행 EPS(야후)']] = None
    val['수집시각(KST)'] = stamp()
    val.to_csv(f'{DAY}/{TODAY}_밸류에이션.csv', index=False, encoding='utf-8-sig')

    fail = val.loc[val['수신'] == '실패', '정식 종목명'].tolist()
    stocks = val[val['구분'] == '개별주']
    log(f'[2 밸류에이션] 출처 {val["출처"].iloc[0]} | {(val["수신"] == "성공").sum()}/{len(val)}종목 | '
        f'개별주 PER 있음 {stocks["PER"].notna().sum()}/{len(stocks)} | 선행 PER(야후) {stocks["선행 PER(야후)"].notna().sum()}/{len(stocks)} | '
        f'실패: {", ".join(fail) or "없음"}' + (f' | 한투 오류: {kis_err}' if kis_err else ''))
except Exception as e:
    traceback.print_exc()
    log(f'[2 밸류에이션] 실패: {type(e).__name__} {e}' + (f' | 한투 오류: {kis_err}' if kis_err else ''))

# 시험: 한투 종목 추정실적(국내 컨센서스) — 형식을 보려고 삼성전자 하나만 원문 저장
if not kis_err:
    try:
        import json
        h = {'content-type': 'application/json; charset=utf-8', 'authorization': f'Bearer {TOKEN}',
             'appkey': SEC['KIS_APP_KEY'], 'appsecret': SEC['KIS_APP_SECRET'], 'tr_id': 'HHKST668300C0', 'custtype': 'P'}
        j = requests.get(f'{BASE}/uapi/domestic-stock/v1/quotations/estimate-perform', headers=h,
                         params={'SHT_CD': '005930'}, timeout=15).json()
        with open(f'{DAY}/{TODAY}_진단_한투추정실적.json', 'w', encoding='utf-8') as f:
            json.dump(j, f, ensure_ascii=False, indent=1)
        log(f'[2 한투 추정실적 시험] 응답 {j.get("rt_cd")} {str(j.get("msg1", ""))[:40]} | 항목 {[k for k in j if k.startswith("output")]}')
    except Exception as e:
        log(f'[2 한투 추정실적 시험] 실패: {type(e).__name__} {e}')
