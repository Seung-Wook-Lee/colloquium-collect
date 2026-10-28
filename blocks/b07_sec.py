# ======================================================================
# [블록 7] SEC 실적 — 미국 개별주 최근 4분기(TTM) 실적과 PER·PBR·ROE 재계산
#   하는 일  : 미국 증권거래위원회(SEC)의 기업 재무 데이터(XBRL companyfacts)에서 미국 개별주 30종목의
#              매출·영업이익·순이익·희석 EPS·자본·발행주식수를 받아 최근 4분기 합계를 낸다.
#              최근 4분기 = 직전 연간(10-K) + 올해 누적(10-Q) − 작년 같은 기간 누적
#              (안 되면 3개월 값 4개 합, 그것도 안 되면 한 분기 앞으로 물러나 다시 시도)
#              (회계연도가 달라도 된다: 애플 9월, 월마트 1월 결산 등)
#              한투 현재가로 PER(최근 4분기)·PBR·ROE를 다시 계산하고 한투 PER과 나란히 적는다. 판정은 하지 않는다.
#              PER은 세 칸: TTM(최근 4분기) / 연환산(가장 최근 한 분기 순이익 × 4) / 선행(블록 2의 야후 값)
#              실적은 드라이브에 저장해 두고 7일마다만 SEC에서 새로 받는다(그 사이에는 몇 초).
#   소스     : SEC EDGAR data.sec.gov (키 없음. 대신 연락용 이메일을 User-Agent로 보내야 함 → Secrets SEC_EMAIL)
#              초당 10회 제한 → 간격 0.2초
#   읽는 것  : 블록 2의 한투 현재가 (블록 2를 건너뛰었으면 오늘 밸류에이션.csv)
#              수집데이터/00_누적/00_SEC_CIK.csv (티커 → SEC 회사번호 CIK, 30일마다 새로 받음)
#              수집데이터/00_누적/00_SEC_실적저장.csv (종목별 최근 4분기 실적, 7일마다 새로 받음)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_SEC실적.csv (금액은 백만 달러, EPS는 달러)
#   쓰는 위원: 피터·섹터 위원(밸류에이션·실적)
#   주의     : TSMC·ASML처럼 미국 회계(US GAAP)가 아닌 외국 회사(20-F, IFRS)는 여기서 빼고 '해외 회계'로 남긴다
#              (한투 PER을 그대로 쓴다). 상장 직후라 10-Q·10-K가 없는 종목도 빈칸으로 남는다.
#   고칠 곳  : 계정 이름이 달라 빈칸이 나오는 종목은 SEC_TAGS 표에 태그를 더한다
#              새 분기 보고서를 바로 반영하려면 SEC_REFRESH_DAYS를 0으로 바꿔 한 번 돌린다
#   실패하면 : 종목별로 '실패'와 사유를 남기고 다음 블록은 계속 실행
# ======================================================================
SEC_PAUSE = 0.2
SEC_REFRESH_DAYS = 7
SEC_CALC_VER = 3   # 계산 방식을 고치면 올린다 → 저장본을 버리고 SEC에서 다시 받음
SEC_TAGS = {  # 항목 → (단위, 태그 후보). 후보 중 가장 최근 기간까지 있는 태그를 쓴다
    '매출': ('USD', ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'RevenuesNetOfInterestExpense',
                    'RevenueFromContractWithCustomerIncludingAssessedTax', 'SalesRevenueNet']),
    '영업이익': ('USD', ['OperatingIncomeLoss']),
    '순이익': ('USD', ['NetIncomeLoss', 'NetIncomeLossAvailableToCommonStockholdersBasic', 'ProfitLoss']),
    'EPS': ('USD/shares', ['EarningsPerShareDiluted', 'EarningsPerShareBasicAndDiluted', 'EarningsPerShareBasic']),
}
EQUITY_TAGS = ['StockholdersEquity', 'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest']
FORMS = {'10-K', '10-Q', '10-K/A', '10-Q/A', '20-F', '20-F/A', '40-F'}   # 20-F·40-F는 연간만 있음

def sec_get(url, retry=2):
    h = {'User-Agent': f'Colloquium research {SEC["SEC_EMAIL"]}', 'Accept-Encoding': 'gzip, deflate'}
    for n in range(retry + 1):
        try:
            time.sleep(SEC_PAUSE)
            r = requests.get(url, headers=h, timeout=60)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if n == retry:
                print(f'  SEC 실패 {url[-40:]}: {e}')
                return None
            time.sleep(3 + 3 * n)

def sec_ciks():
    path = f'{KEEP}/00_SEC_CIK.csv'
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 30 * 86400:
        return pd.read_csv(path, dtype=str)
    j = sec_get('https://www.sec.gov/files/company_tickers.json')
    if not j:
        raise RuntimeError('SEC 티커 목록을 받지 못함 (SEC_EMAIL 확인)')
    cik = pd.DataFrame(j.values())[['ticker', 'cik_str', 'title']].astype(str)
    cik.to_csv(path, index=False, encoding='utf-8-sig')
    return cik

def _d(s):
    return dt.date.fromisoformat(s)

def ttm_tag(facts, tag, unit):
    """태그 하나의 최근 4분기 값. (값, 기준일, 근거) 또는 None
    가장 최근 분기부터 거꾸로 시도한다. 분기마다 ① 연간 그대로 ② 연간 + 올해 누적 − 작년 누적 ③ 3개월 값 4개 합"""
    rows = facts.get('us-gaap', {}).get(tag, {}).get('units', {}).get(unit, [])
    rows = [x for x in rows if x.get('form') in FORMS and x.get('start') and x.get('end')]
    if not rows:
        return None
    per = {}
    for x in sorted(rows, key=lambda x: x.get('filed', '')):      # 같은 기간이 여러 번 나오면 가장 나중 공시
        per[(x['start'], x['end'])] = x
    rows = list(per.values())
    dur = lambda x: (_d(x['end']) - _d(x['start'])).days
    near = lambda a, b, tol=10: abs((_d(a) - _d(b)).days) <= tol
    mon = lambda x: round(dur(x) / 30.4)
    q3 = [x for x in rows if 80 <= dur(x) <= 100]
    for E in sorted({x['end'] for x in rows}, reverse=True)[:6]:
        at_e = [x for x in rows if x['end'] == E]
        ann_e = [x for x in at_e if 350 <= dur(x) <= 380]
        if ann_e:
            return ann_e[0]['val'], E, '연간(10-K)'
        ytd = max(at_e, key=dur)
        want = (_d(E) - dt.timedelta(days=365)).isoformat()
        prev = [x for x in rows if near(x['end'], want) and abs(dur(x) - dur(ytd)) <= 10]
        ann = [x for x in rows if 350 <= dur(x) <= 380 and prev and prev[0]['end'] < x['end'] < E]
        if prev and ann:
            ann = max(ann, key=lambda x: x['end'])
            return ann['val'] + ytd['val'] - prev[0]['val'], E, f'연간 {ann["end"]} + 누적 {mon(ytd)}개월'
        qs, e = [], E                     # ③ 3개월 값을 거꾸로 4개 이어 붙인다
        for _ in range(4):
            q = [x for x in q3 if near(x['end'], e)]
            if q:
                qs.append(q[0]['val'])
                e = (_d(q[0]['start']) - dt.timedelta(days=1)).isoformat()
                continue
            a = [x for x in rows if near(x['end'], e) and 350 <= dur(x) <= 380]       # 4분기 = 연간 − 9개월 누적
            n = [x for x in rows if a and x['start'] == a[0]['start'] and 260 <= dur(x) <= 290]
            if not n:
                break
            qs.append(a[0]['val'] - n[0]['val'])
            e = n[0]['end']
        if len(qs) == 4:
            return sum(qs), E, '3개월 4개 합'
    return None

def quarter_tag(facts, tag, unit, E):
    """기간 끝이 E인 한 분기(3개월) 값. 없으면 4분기 = 연간 − 9개월 누적"""
    rows = [x for x in facts.get('us-gaap', {}).get(tag, {}).get('units', {}).get(unit, [])
            if x.get('form') in FORMS and x.get('start') and x.get('end') == E]
    dur = lambda x: (_d(x['end']) - _d(x['start'])).days
    q = sorted([x for x in rows if 80 <= dur(x) <= 100], key=lambda x: x.get('filed', ''))
    if q:
        return q[-1]['val']
    a = [x for x in rows if 350 <= dur(x) <= 380]
    if a:
        allr = facts['us-gaap'][tag]['units'][unit]
        n = [x for x in allr if x.get('start') == a[0]['start'] and x.get('end') and 260 <= dur(x) <= 290]
        if n:
            return a[0]['val'] - max(n, key=lambda x: x.get('filed', ''))['val']
    return None


def sec_one(cik):
    j = sec_get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json')
    if not j:
        raise RuntimeError('SEC 재무 데이터 없음 (상장 직후일 수 있음)')
    facts = j.get('facts', {})
    if 'us-gaap' not in facts:
        raise RuntimeError('해외 회계(IFRS·20-F) → 한투 PER 사용')
    out = {}
    for key, (unit, tags) in SEC_TAGS.items():
        best = None
        for tag in tags:
            v = ttm_tag(facts, tag, unit)
            if v and (best is None or v[1] > best[1]):
                best = v
        out[key] = best[0] if best else None
        if key == '순이익':
            out['기준일'], out['계산 근거'] = (best[1], best[2]) if best else (None, None)
            out['최근분기 순이익'] = None
            for tag in tags:   # TTM과 같은 기간 끝의 한 분기 순이익
                if best and out['최근분기 순이익'] is None:
                    out['최근분기 순이익'] = quarter_tag(facts, tag, unit, best[1])
    if out['순이익'] is None:
        raise RuntimeError('달러 순이익 항목을 찾지 못함 (외화 보고 회사일 수 있음 → 한투 PER 사용)')
    eq = None
    for tag in EQUITY_TAGS:
        xs = [x for x in facts['us-gaap'].get(tag, {}).get('units', {}).get('USD', [])
              if x.get('form') in FORMS and not x.get('start')]
        if xs:
            x = max(xs, key=lambda x: (x['end'], x.get('filed', '')))
            if eq is None or x['end'] > eq[1]:
                eq = (x['val'], x['end'])
    out['자본'] = eq[0] if eq else None
    sh = facts.get('dei', {}).get('EntityCommonStockSharesOutstanding', {}).get('units', {}).get('shares', [])
    out['주식수 출처'] = None
    if sh:   # 주식 종류가 여럿이면(예: 알파벳 A·B·C) 같은 공시의 값을 더한다
        last = max(sh, key=lambda x: (x['end'], x.get('filed', '')))
        out['발행주식수'] = sum(x['val'] for x in sh if x.get('accn') == last.get('accn') and x['end'] == last['end'])
    else:    # 표지 주식수가 없으면(종류가 여럿인 회사에서 흔함) 최근 분기 희석 가중평균 주식수
        w = [x for x in facts['us-gaap'].get('WeightedAverageNumberOfDilutedSharesOutstanding', {})
             .get('units', {}).get('shares', []) if x.get('form') in FORMS]
        out['발행주식수'] = max(w, key=lambda x: (x['end'], x.get('filed', '')))['val'] if w else None
        out['주식수 출처'] = '주식수는 희석 가중평균' if w else '주식수 없음'
    # 진단용: 이 회사가 SEC에 낸 가장 최근 정기보고서와, 순이익 태그별 가장 최근 기간 끝
    allf = [x for t_ in facts['us-gaap'].values() for u_ in t_.get('units', {}).values() for x in u_
            if x.get('form') in FORMS and x.get('filed')]
    if allf:
        z = max(allf, key=lambda x: (x['filed'], x['end']))
        out['최신 공시'] = f"{z['form']} {z['filed']} 제출(기간 끝 {z['end']})"
    out['순이익 태그 최신'] = ', '.join(
        f"{tg} {max(x['end'] for x in facts['us-gaap'][tg]['units'].get('USD', []) or [{'end': '-'}])}"
        for tg in SEC_TAGS['순이익'][1] if tg in facts['us-gaap'])
    out['계산버전'] = SEC_CALC_VER
    return out

try:
    if not SEC.get('SEC_EMAIL'):
        raise RuntimeError('SEC_EMAIL 없음 (GitHub Secrets 또는 코랩 Secrets에 연락용 이메일)')
    cik = sec_ciks().set_index('ticker')['cik_str']
    kis = val if 'val' in globals() else pd.read_csv(f'{DAY}/{TODAY}_밸류에이션.csv', dtype={'코드': str})
    kis = kis.set_index('코드')
    us = u[(u['시장'] == '미국') & (u['구분'] == '개별주')]
    STORE_S = f'{KEEP}/00_SEC_실적저장.csv'
    store_s = pd.read_csv(STORE_S, dtype={'코드': str}).set_index('코드') if os.path.exists(STORE_S) else pd.DataFrame()
    cut_s = (NOW - dt.timedelta(days=SEC_REFRESH_DAYS)).strftime('%Y-%m-%d')
    got_s = 0
    rows = []
    for _, s in us.iterrows():
        tk = s['코드']
        r = {'번호': s['번호'], '정식 종목명': s['정식 종목명'], '티커': tk}
        try:
            if (tk in store_s.index and str(store_s.loc[tk, '받은날']) > cut_s and pd.notna(store_s.loc[tk, '기준일'])
                    and (NOW.date() - _d(str(store_s.loc[tk, '기준일']))).days <= 150   # 옛 분기에 멈춘 종목은 매번 다시 받음
                    and str(store_s.get('계산버전', pd.Series(dtype=str)).get(tk)) in (str(SEC_CALC_VER), f'{SEC_CALC_VER}.0')):
                t = {k: (None if pd.isna(v) else v) for k, v in store_s.loc[tk].to_dict().items()}
            else:
                c = cik.get(tk.replace('.', '-'))
                if not c:
                    raise RuntimeError('SEC 회사번호(CIK) 없음')
                t = sec_one(c)
                t['받은날'] = NOW.strftime('%Y-%m-%d')
                store_s = pd.concat([store_s.drop(index=tk, errors='ignore'),
                                     pd.DataFrame([t], index=pd.Index([tk], name='코드'))])
                got_s += 1
            price = kis['현재가'].get(tk) if '현재가' in kis else None
            ni, eq, eps, sh = t['순이익'], t['자본'], t['EPS'], t['발행주식수']
            qni = t.get('최근분기 순이익')
            fwd = kis['선행 PER(야후)'].get(tk) if '선행 PER(야후)' in kis else None
            mcap = price * sh if price and sh else None
            m = lambda v: round(v / 1e6) if v else None
            r.update({'기준일(최근 분기 끝)': t['기준일'], '계산 근거': t['계산 근거'],
                      '매출 TTM(백만$)': m(t['매출']), '영업이익 TTM(백만$)': m(t['영업이익']),
                      '순이익 TTM(백만$)': m(ni), '희석 EPS TTM($)': round(eps, 2) if eps else None,
                      '자본(백만$)': m(eq), '발행주식수(백만주)': round(sh / 1e6, 1) if sh else None,
                      '현재가(한투, $)': price, '시가총액(백만$)': m(mcap),
                      'PER TTM(주가÷EPS)': round(price / eps, 2) if price and eps and eps > 0 else None,
                      'PER TTM(시총÷순이익)': round(mcap / ni, 2) if mcap and ni and ni > 0 else None,
                      'PER 연환산(최근분기×4)': round(mcap / (qni * 4), 2) if mcap and qni and qni > 0 else None,
                      '선행 PER(야후)': fwd,
                      '최근분기 순이익(백만$)': m(qni),
                      'PBR(시총÷자본)': round(mcap / eq, 2) if mcap and eq and eq > 0 else None,
                      'ROE TTM(%)': round(ni / eq * 100, 1) if ni and eq and eq > 0 else None,
                      '한투 PER': kis['PER'].get(tk) if 'PER' in kis else None,
                      '실적 받은날': t['받은날'], '수신': '성공'})
            note = [t.get('주식수 출처')]
            if t['기준일'] and (NOW.date() - _d(str(t['기준일']))).days > 150:
                note.append(f"기준일이 오래됨 — SEC 최신 공시: {t.get('최신 공시')} / 순이익 태그: {t.get('순이익 태그 최신')}")
            if ni and ni < 0:
                note.append('최근 4분기 적자 → PER 없음')
            r['비고'] = ' / '.join(x for x in note if x and not (isinstance(x, float) and pd.isna(x))) or None
        except Exception as e:
            r.update({'수신': '실패', '비고': f'{e}'})
        rows.append(r)
    if got_s:
        store_s.reset_index().to_csv(STORE_S, index=False, encoding='utf-8-sig')
    secdf = pd.DataFrame(rows)
    secdf['출처'] = 'SEC EDGAR XBRL companyfacts'
    secdf['수집시각(KST)'] = dt.datetime.now(KST).strftime('%Y-%m-%d %H:%M')
    secdf.to_csv(f'{DAY}/{TODAY}_SEC실적.csv', index=False, encoding='utf-8-sig')

    ok = secdf[secdf['수신'] == '성공']
    fail = [f'{a}({b})' for a, b in secdf.loc[secdf['수신'] == '실패', ['티커', '비고']].values]
    log(f'[7 SEC 실적] {len(ok)}/{len(secdf)}종목 | PER TTM 있음 {ok["PER TTM(주가÷EPS)"].notna().sum()} | '
        f'SEC에서 새로 받은 종목 {got_s} | 실패: {", ".join(fail) or "없음"}')
except Exception as e:
    traceback.print_exc()
    log(f'[7 SEC 실적] 실패: {type(e).__name__} {e}')
