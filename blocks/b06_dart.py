# ======================================================================
# [블록 6] DART 실적 — 한국 개별주 최근 4분기(TTM) 실적과 PER·PBR·ROE 재계산
#   하는 일  : 금융감독원 DART에서 한국 개별주 20종목의 최신 정기보고서(분기·반기·사업보고서)와
#              직전 사업보고서를 받아 최근 4분기 합계를 낸다.
#              최근 4분기 = 직전 연간 + 올해 누적 − 작년 같은 기간 누적
#              매출·영업이익·지배주주 순이익·EPS(기본)와 최신 지배주주 자본을 뽑고,
#              한투 현재가·시가총액으로 PER(최근 4분기)·PBR·ROE를 다시 계산한다.
#              한투 PER(직전 연간 EPS 기준)과 나란히 적어 차이를 볼 수 있게 한다. 판정은 하지 않는다.
#              PER은 세 칸: TTM(최근 4분기) / 연환산(가장 최근 한 분기 순이익 × 4) / 선행(블록 2의 야후 값, 참고)
#              실적은 분기마다 바뀌므로 받은 실적을 드라이브에 저장해 두고 7일마다만 DART에서 새로 받는다.
#              그 사이 날에는 저장된 실적에 오늘 한투 가격만 넣어 다시 계산하므로 몇 초면 끝난다.
#              단, 받은 날 뒤에 새 정기보고서가 공시된 종목은 7일을 기다리지 않고 그날 바로 새로 받는다.
#              잠정실적: 최근 PRELIM_DAYS일 안의 '영업(잠정)실적' 공정공시 본문에서 당해 분기 매출·영업이익·순이익을 읽는다.
#              그 분기가 최근 정기보고서보다 새것이면 'PER 연환산(잠정×4)'을 따로 계산한다(정기보고서는 한 달쯤 늦게 나옴).
#              2026-10-29 의장 지시: 어제 나온 잠정실적(삼성전기·SK하이닉스)이 오늘 회의에 빠지지 않게.
#   소스     : DART OpenAPI (키 DART_KEY, 하루 2만 회 제한 → 간격 0.3초, 연결재무제표 우선·없으면 별도)
#   읽는 것  : 블록 2의 한투 현재가·시가총액·야후 선행 PER (블록 2를 건너뛰었으면 오늘 밸류에이션.csv)
#              수집데이터/00_누적/00_DART_고유번호.csv (종목코드 → DART 고유번호, 30일마다 새로 받음)
#              수집데이터/00_누적/00_DART_실적저장.csv (종목별 최근 4분기 실적, 7일마다 새로 받음)
#              수집데이터/00_누적/00_DART_잠정저장.csv (읽은 잠정실적 공시, 접수번호별)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_DART실적.csv (금액은 억원, EPS는 원)
#   쓰는 위원: 피터·섹터 위원(밸류에이션·실적), 닉스 3여신(실적 추세 참고)
#   주의     : 보고서가 나온 직후가 아니면 최근 4분기는 최대 한 분기 늦다(3분기 보고서는 11월 중순 공시)
#   고칠 곳  : 계정 이름이 달라 빈칸이 나오는 종목은 ACCT 표에 계정 ID나 이름을 더한다
#              새 분기 보고서를 바로 반영하려면 DART_REFRESH_DAYS를 0으로 바꿔 한 번 돌린다
#   실패하면 : 종목별로 '실패'와 사유를 남기고 다음 블록은 계속 실행
# ======================================================================
import html, re, zipfile, xml.etree.ElementTree as ET

DART = 'https://opendart.fss.or.kr/api'
DART_PAUSE = 0.3
DART_REFRESH_DAYS = 7     # 저장된 실적을 며칠 동안 다시 쓸지 (0이면 매번 새로 받음)
PRELIM_DAYS = 45          # 잠정실적 공시를 며칠 전까지 찾을지
DART_CALC_VER = 2         # 계산 방식을 고치면 올린다 → 저장본을 버리고 다시 받음
DART_FATAL = {'010', '011', '012', '020', '021', '100', '101', '800', '900', '901'}   # 키·한도 오류는 바로 멈춤
REPRT = {'11013': '1분기', '11012': '반기', '11014': '3분기', '11011': '사업보고서'}
ACCT = {  # 항목 → (재무제표 구분, 계정 ID 후보, 계정 이름 후보)
    '매출': (('IS', 'CIS'), ['ifrs-full_Revenue'], ['매출액', '영업수익', '수익(매출액)', '매출']),
    '영업이익': (('IS', 'CIS'), ['dart_OperatingIncomeLoss'], ['영업이익', '영업이익(손실)']),
    '지배순이익': (('IS', 'CIS'), ['ifrs-full_ProfitLossAttributableToOwnersOfParent', 'ifrs-full_ProfitLoss'],
                   ['지배기업의 소유주에게 귀속되는 당기순이익', '지배기업 소유주지분', '당기순이익', '당기순이익(손실)']),
    'EPS': (('IS', 'CIS'), ['ifrs-full_BasicEarningsLossPerShare', 'ifrs-full_BasicAndDilutedEarningsLossPerShare'],
            ['기본주당이익', '기본주당순이익', '기본주당이익(손실)', '기본주당순이익(손실)', '보통주기본주당이익',
             '보통주 기본주당이익', '기본 및 희석주당이익', '기본및희석주당이익(손실)']),
    '지배자본': (('BS',), ['ifrs-full_EquityAttributableToOwnersOfParent', 'ifrs-full_Equity'],
                 ['지배기업의 소유주에게 귀속되는 자본', '지배기업 소유주지분', '자본총계']),
}

def dart_get(api, params, retry=2):
    for n in range(retry + 1):
        try:
            time.sleep(DART_PAUSE)
            j = requests.get(f'{DART}/{api}', params={'crtfc_key': SEC['DART_KEY'], **params}, timeout=20).json()
            if j.get('status') == '000':
                return j.get('list') or []
            if j.get('status') == '013':     # 조회된 데이터 없음 (아직 공시 전 등)
                return None
            if j.get('status') in DART_FATAL:
                raise PermissionError(f"DART {j.get('status')} {j.get('message')}")
            raise ValueError(f"{j.get('status')} {j.get('message')}")
        except PermissionError:
            raise
        except Exception as e:
            if n == retry:
                print(f'  DART 실패 {params}: {e}')
                return None
            time.sleep(2 + 2 * n)

def corp_codes():
    """종목코드 → DART 고유번호. 드라이브에 저장해 두고 30일마다 새로 받는다."""
    path = f'{KEEP}/00_DART_고유번호.csv'
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 30 * 86400:
        return pd.read_csv(path, dtype=str)
    r = requests.get(f'{DART}/corpCode.xml', params={'crtfc_key': SEC['DART_KEY']}, timeout=60)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    root = ET.fromstring(z.read(z.namelist()[0]))
    cc = pd.DataFrame([{'corp_code': e.findtext('corp_code'), 'stock_code': (e.findtext('stock_code') or '').strip(),
                        'corp_name': e.findtext('corp_name')} for e in root.iter('list')])
    cc = cc[cc['stock_code'] != '']
    cc.to_csv(path, index=False, encoding='utf-8-sig')
    return cc

def amt(v):
    try:
        return float(str(v).replace(',', '').strip())
    except Exception:
        return None

def pick(rows, key):
    sj, ids, names = ACCT[key]
    rows = [x for x in rows if x.get('sj_div') in sj]
    for i in ids:                       # 계정 ID가 먼저, 없으면 계정 이름
        for x in rows:
            if x.get('account_id') == i:
                return x
    for nm in names:
        for x in rows:
            if x.get('account_nm', '').replace(' ', '') == nm.replace(' ', ''):
                return x
    return None

def statements(corp, year, code):
    """연결 우선, 없으면 별도. (목록, 'CFS'/'OFS')"""
    for fs in ['CFS', 'OFS']:
        rows = dart_get('fnlttSinglAcntAll.json', {'corp_code': corp, 'bsns_year': str(year),
                                                   'reprt_code': code, 'fs_div': fs})
        if rows:
            return rows, fs
    return None, None

def ttm_one(corp):
    y = NOW.year
    tries = [(y, '11014'), (y, '11012'), (y, '11013'), (y - 1, '11011'), (y - 1, '11014'), (y - 1, '11012')]
    for year, code in tries:                       # 가장 최근 정기보고서 찾기
        cur, fs = statements(corp, year, code)
        if cur:
            break
    else:
        raise RuntimeError('정기보고서 없음')
    out = {'최근 보고서': f'{year} {REPRT[code]}', '재무제표': '연결' if fs == 'CFS' else '별도'}
    if code == '11011':
        ann = None
    else:
        ann, _ = statements(corp, year - 1, '11011')
        if not ann:
            raise RuntimeError(f'{year - 1} 사업보고서 없음')
    for key in ['매출', '영업이익', '지배순이익', 'EPS']:
        x = pick(cur, key)
        if x is None:
            out[key] = None
            continue
        if code == '11011':
            out[key] = amt(x.get('thstrm_amount'))
            continue
        if key == '지배순이익':          # 분기·반기 보고서의 당기 금액 = 가장 최근 3개월
            out['최근분기 순이익'] = amt(x.get('thstrm_amount'))
        a = pick(ann, key)
        now_cum = amt(x.get('thstrm_add_amount')) if amt(x.get('thstrm_add_amount')) is not None else amt(x.get('thstrm_amount'))
        prev_cum = amt(x.get('frmtrm_add_amount')) if amt(x.get('frmtrm_add_amount')) is not None else amt(x.get('frmtrm_q_amount'))
        a_val = amt(a.get('thstrm_amount')) if a else None
        out[key] = a_val + now_cum - prev_cum if None not in (a_val, now_cum, prev_cum) else None
    e = pick(cur, '지배자본')
    out['지배자본'] = amt(e.get('thstrm_amount')) if e else None
    out.setdefault('최근분기 순이익', None)   # 사업보고서가 최신이면 4분기만 따로 나오지 않아 비움
    out['계산버전'] = DART_CALC_VER
    return out

def _plain(b):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', b.decode('utf-8', 'ignore')))).strip()

def doc_text(rcept_no):
    time.sleep(DART_PAUSE)
    r = requests.get(f'{DART}/document.xml', params={'crtfc_key': SEC['DART_KEY'], 'rcept_no': rcept_no}, timeout=30)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    return ' '.join(_plain(z.read(n)) for n in z.namelist())

PRELIM_UNIT = {'조원': 1e4, '억원': 1, '백만원': 1e-2, '천원': 1e-5, '원': 1e-8}
PRELIM_ITEM = {'잠정 매출(억원)': ['매출액', '영업수익', '매출'], '잠정 영업이익(억원)': ['영업이익'],
               '잠정 순이익(억원)': ['지배기업 소유주지분 순이익', '당기순이익']}

def prelim_parse(text, rdate):
    """잠정실적 공시 본문에서 당해 분기 매출·영업이익·순이익(억원)과 분기. 표 줄은 '항목 당해실적 숫자 ...' 모양"""
    m = re.search(r'단위\s*[:：]?\s*(조원|억원|백만원|천원|원)', text)
    mult = PRELIM_UNIT[m.group(1)] if m else 1e-2
    out = {}
    for col, names in PRELIM_ITEM.items():
        for nm in names:
            pat = (r'\s*'.join(map(re.escape, nm.replace(' ', '')))
                   + r'\s*(?:\(손실\))?\s*당해\s*실적\s*(\(?-?[\d,]+(?:\.\d+)?\)?)')
            g = re.search(pat, text)
            if g:
                v = g.group(1)
                neg = v.startswith('(') or v.startswith('-')
                v = float(v.strip('()-').replace(',', ''))
                out[col] = round((-v if neg else v) * mult)
                break
    q = re.search(r'당기\s*실적\s*\(?\s*[’\'‘]?\s*(\d{2})\s*[.년]\s*([1-4])\s*(?:Q|분기)', text)
    if q:
        out['잠정 분기'] = f'20{q.group(1)} {q.group(2)}Q'
    else:                       # 공시 달로 짐작: 1~3월 = 작년 4Q, 4~6월 = 1Q, 7~9월 = 2Q, 10~12월 = 3Q
        qq = (rdate.month - 1) // 3
        out['잠정 분기'] = f'{rdate.year - (qq == 0)} {qq or 4}Q'
    return out

def report_q(name):
    """'2026 반기' 또는 '2026 3Q' -> (2026, 분기 번호). 사업보고서는 4"""
    y, k = str(name).split(' ', 1)
    return int(y), {'1분기': 1, '반기': 2, '3분기': 3, '사업보고서': 4, '1Q': 1, '2Q': 2, '3Q': 3, '4Q': 4}.get(k, 0)

def prelim_latest(corp, store_p):
    """최근 PRELIM_DAYS일 안의 가장 새 잠정실적 공시. 읽은 공시는 접수번호로 저장해 다시 읽지 않는다"""
    bgn = (NOW - dt.timedelta(days=PRELIM_DAYS)).strftime('%Y%m%d')
    lst = dart_get('list.json', {'corp_code': corp, 'bgn_de': bgn, 'end_de': TODAY, 'pblntf_ty': 'I', 'page_count': 100}) or []
    lst = [x for x in lst if '잠정' in x.get('report_nm', '') and '실적' in x.get('report_nm', '')
           and '자회사' not in x.get('report_nm', '')]
    if not lst:
        return None
    x = max(lst, key=lambda x: x['rcept_no'])
    if x['rcept_no'] in store_p:
        return store_p[x['rcept_no']]
    rdate = dt.datetime.strptime(x['rcept_dt'], '%Y%m%d').date()
    t = prelim_parse(doc_text(x['rcept_no']), rdate)
    t.update({'잠정 공시일': rdate.isoformat(), '잠정 공시': x['report_nm'].strip(), 'corp_code': corp})
    store_p[x['rcept_no']] = t
    return t

def new_regular(corp, since):
    """since(YYYY-MM-DD) 뒤에 정기보고서(분기·반기·사업)가 공시됐는지"""
    lst = dart_get('list.json', {'corp_code': corp, 'bgn_de': since.replace('-', ''), 'end_de': TODAY,
                                 'pblntf_ty': 'A', 'page_count': 10}) or []
    return any(x.get('rcept_dt', '') > since.replace('-', '') for x in lst)

try:
    if not SEC.get('DART_KEY'):
        raise RuntimeError('DART_KEY 없음 (opendart.fss.or.kr에서 받아 GitHub Secrets 또는 코랩 Secrets에 넣기)')
    cc = corp_codes().set_index('stock_code')['corp_code']
    # 한투 현재가·시총: 블록 2 결과가 메모리에 없으면 오늘 파일에서 읽는다
    kis = val if 'val' in globals() else pd.read_csv(f'{DAY}/{TODAY}_밸류에이션.csv', dtype={'코드': str})
    kis = kis.set_index('코드')
    kr = u[(u['시장'] == '한국') & (u['구분'] == '개별주')]
    # 저장된 실적: 7일 안에 받은 것은 그대로 쓰고, 오래됐거나 없는 종목만 DART에서 받는다
    STORE = f'{KEEP}/00_DART_실적저장.csv'
    store = pd.read_csv(STORE, dtype={'코드': str}).set_index('코드') if os.path.exists(STORE) else pd.DataFrame()
    fresh_cut = (NOW - dt.timedelta(days=DART_REFRESH_DAYS)).strftime('%Y-%m-%d')
    PSTORE = f'{KEEP}/00_DART_잠정저장.csv'
    store_p = (pd.read_csv(PSTORE, dtype={'rcept_no': str}).set_index('rcept_no').astype(object)
               .where(lambda d: d.notna(), None).to_dict('index') if os.path.exists(PSTORE) else {})
    n_store_p = len(store_p)
    fetched, n_new_reg, n_prelim = 0, 0, 0
    rows = []
    for _, s in kr.iterrows():
        r = {'번호': s['번호'], '정식 종목명': s['정식 종목명'], '코드': s['코드']}
        try:
            corp = cc.get(s['코드'])
            if not corp:
                raise RuntimeError('DART 고유번호 없음')
            keep = (s['코드'] in store.index and str(store.loc[s['코드'], '받은날']) > fresh_cut
                    and str(store.get('계산버전', pd.Series(dtype=str)).get(s['코드'])) in (str(DART_CALC_VER), f'{DART_CALC_VER}.0'))
            if keep and str(store.loc[s['코드'], '받은날']) < NOW.strftime('%Y-%m-%d') \
                    and new_regular(corp, str(store.loc[s['코드'], '받은날'])):
                keep = False                 # 받은 뒤 새 정기보고서가 나왔으면 7일을 기다리지 않는다
                n_new_reg += 1
            if keep:
                t = store.loc[s['코드']].to_dict()
                t = {k: (None if pd.isna(v) else v) for k, v in t.items()}
            else:
                t = ttm_one(corp)
                t['받은날'] = NOW.strftime('%Y-%m-%d')
                store = pd.concat([store.drop(index=s['코드'], errors='ignore'),
                                   pd.DataFrame([t], index=pd.Index([s['코드']], name='코드'))])
                fetched += 1
            price = kis['현재가'].get(s['코드']) if '현재가' in kis else None
            mcap = kis['시가총액(억원)'].get(s['코드']) if '시가총액(억원)' in kis else None
            ni, eq, eps = t['지배순이익'], t['지배자본'], t['EPS']
            qni = t.get('최근분기 순이익')
            fwd = kis['선행 PER(야후)'].get(s['코드']) if '선행 PER(야후)' in kis else None
            pr = {}
            try:
                pr = prelim_latest(corp, store_p) or {}
            except PermissionError:
                raise
            except Exception as e:
                print(f'  잠정실적 실패 {s["정식 종목명"]}: {e}')
            pr_new = bool(pr.get('잠정 분기')) and report_q(pr['잠정 분기']) > report_q(t['최근 보고서'])
            pni = pr.get('잠정 순이익(억원)') if pr_new else None
            n_prelim += pr_new
            r.update({'최근 보고서': t['최근 보고서'], '재무제표': t['재무제표'],
                      '매출 TTM(억원)': round(t['매출'] / 1e8) if t['매출'] else None,
                      '영업이익 TTM(억원)': round(t['영업이익'] / 1e8) if t['영업이익'] else None,
                      '지배순이익 TTM(억원)': round(ni / 1e8) if ni else None,
                      'EPS TTM(원)': round(eps) if eps else None,
                      '지배자본(억원)': round(eq / 1e8) if eq else None,
                      '현재가(한투)': price, '시가총액(억원, 한투)': mcap,
                      'PER TTM(주가÷EPS)': round(price / eps, 2) if price and eps and eps > 0 else None,
                      'PER TTM(시총÷순이익)': round(mcap / (ni / 1e8), 2) if mcap and ni and ni > 0 else None,
                      'PER 연환산(최근분기×4)': round(mcap / (qni * 4 / 1e8), 2) if mcap and qni and qni > 0 else None,
                      '선행 PER(야후, 참고)': fwd,
                      '최근분기 순이익(억원)': round(qni / 1e8) if qni else None,
                      'PBR(시총÷지배자본)': round(mcap / (eq / 1e8), 2) if mcap and eq and eq > 0 else None,
                      'ROE TTM(%)': round(ni / eq * 100, 1) if ni and eq else None,
                      '한투 PER(직전 연간)': kis['PER'].get(s['코드']) if 'PER' in kis else None,
                      '잠정 분기': pr.get('잠정 분기'), '잠정 공시일': pr.get('잠정 공시일'),
                      '잠정 매출(억원)': pr.get('잠정 매출(억원)'), '잠정 영업이익(억원)': pr.get('잠정 영업이익(억원)'),
                      '잠정 순이익(억원)': pr.get('잠정 순이익(억원)'),
                      '잠정이 더 새것': ('예' if pr_new else '아니오') if pr else None,
                      'PER 연환산(잠정×4)': round(mcap / (pni * 4), 2) if mcap and pni and pni > 0 else None,
                      '실적 받은날': t['받은날'], '수신': '성공'})
        except PermissionError:
            raise
        except Exception as e:
            r.update({'수신': '실패', '비고': f'{type(e).__name__} {e}'})
        rows.append(r)
    if fetched:
        store.reset_index().to_csv(STORE, index=False, encoding='utf-8-sig')
    if len(store_p) > n_store_p:
        pd.DataFrame.from_dict(store_p, orient='index').rename_axis('rcept_no').reset_index().to_csv(
            PSTORE, index=False, encoding='utf-8-sig')
    dart = pd.DataFrame(rows)
    dart['출처'] = 'DART OpenAPI 단일회사 전체 재무제표'
    dart['수집시각(KST)'] = dt.datetime.now(KST).strftime('%Y-%m-%d %H:%M')
    dart.to_csv(f'{DAY}/{TODAY}_DART실적.csv', index=False, encoding='utf-8-sig')

    ok = dart[dart['수신'] == '성공']
    fail = dart.loc[dart['수신'] == '실패', '정식 종목명'].tolist()
    log(f'[6 DART 실적] {len(ok)}/{len(dart)}종목 | 최근 보고서: '
        f'{", ".join(f"{k} {v}" for k, v in ok["최근 보고서"].value_counts().items()) or "없음"} | '
        f'PER TTM 있음 {ok["PER TTM(주가÷EPS)"].notna().sum()} | DART에서 새로 받은 종목 {fetched}(새 정기보고서 {n_new_reg}) | 잠정실적이 더 새것 {n_prelim} | 실패: {", ".join(fail) or "없음"}')
except Exception as e:
    traceback.print_exc()
    log(f'[6 DART 실적] 실패: {type(e).__name__} {e}')
