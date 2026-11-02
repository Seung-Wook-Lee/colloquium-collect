# ======================================================================
# 팀 Q — 재무제표(fundamentals)와 공시 이벤트(corporate_actions)
#   미국 : SEC companyfacts 전체 숫자(raw, 종목별) → 표준 항목 분기·연간 표(processed)
#          각 숫자에 '실제 공시일(filed)'이 붙어 있어 그 날짜 이후에만 쓰면 미래정보 누수가 없다.
#          SEC submissions → 공시 목록(8-K 2.02항 = 실적 발표, 접수 시각 포함)
#   한국 : DART 전체 재무제표(2015~, 연결 우선) raw → 표준 항목. 공시일 = 접수번호 앞 8자리
#          DART 주식총수·배당 사항, 공시 목록(유무상증자·자사주·배당 결정·잠정실적 등 분류)
#   일본 : EDINET은 키(EDINET_KEY)가 있어야 함. 이번에는 야후 재무(최근 4~5년, 공시일 없음)만 '참고용'으로
# ======================================================================
import io, re, time, zipfile, xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import yfinance as yf
from common import *

# 표준 항목 ← 후보 태그(앞쪽 우선)
STD_US = {
    'revenue': ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet',
                'RevenueFromContractWithCustomerIncludingAssessedTax', 'RevenuesNetOfInterestExpense', 'Revenue'],
    'cost_of_revenue': ['CostOfRevenue', 'CostOfGoodsAndServicesSold', 'CostOfGoodsSold', 'CostOfSales'],
    'gross_profit': ['GrossProfit'],
    'operating_income': ['OperatingIncomeLoss', 'ProfitLossFromOperatingActivities'],
    'pretax_income': ['IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
                      'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
                      'ProfitLossBeforeTax'],
    'income_tax': ['IncomeTaxExpenseBenefit', 'IncomeTaxExpenseContinuingOperations'],
    'net_income': ['NetIncomeLoss', 'ProfitLossAttributableToOwnersOfParent', 'ProfitLoss'],
    'eps_basic': ['EarningsPerShareBasic', 'BasicEarningsLossPerShare'],
    'eps_diluted': ['EarningsPerShareDiluted', 'DilutedEarningsLossPerShare'],
    'total_assets': ['Assets'],
    'total_liabilities': ['Liabilities'],
    'equity': ['StockholdersEquity', 'EquityAttributableToOwnersOfParent'],
    'cash': ['CashAndCashEquivalentsAtCarryingValue', 'CashAndCashEquivalents',
             'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'],
    'short_term_debt': ['ShortTermBorrowings', 'DebtCurrent', 'LongTermDebtCurrent', 'CurrentBorrowings'],
    'long_term_debt': ['LongTermDebtNoncurrent', 'LongTermDebt', 'NoncurrentBorrowings'],
    'cfo': ['NetCashProvidedByUsedInOperatingActivities', 'CashFlowsFromUsedInOperatingActivities'],
    'cfi': ['NetCashProvidedByUsedInInvestingActivities', 'CashFlowsFromUsedInInvestingActivities'],
    'cff': ['NetCashProvidedByUsedInFinancingActivities', 'CashFlowsFromUsedInFinancingActivities'],
    'capex': ['PaymentsToAcquirePropertyPlantAndEquipment', 'PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities'],
    'dep_amort': ['DepreciationDepletionAndAmortization', 'DepreciationAndAmortization', 'DepreciationAmortizationAndAccretionNet'],
    'dividends_paid': ['PaymentsOfDividendsCommonStock', 'PaymentsOfDividends', 'DividendsPaidClassifiedAsFinancingActivities'],
    'dps_declared': ['CommonStockDividendsPerShareDeclared', 'CommonStockDividendsPerShareCashPaid'],
    'buyback': ['PaymentsForRepurchaseOfCommonStock'],
    'shares_diluted_wavg': ['WeightedAverageNumberOfDilutedSharesOutstanding'],
    'shares_outstanding': ['EntityCommonStockSharesOutstanding'],   # dei, 표지 기준일
    'liab_and_equity': ['LiabilitiesAndStockholdersEquity'],
    'equity_incl_nci': ['StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest', 'Equity'],
}
FLOW = {'revenue', 'cost_of_revenue', 'gross_profit', 'operating_income', 'pretax_income', 'income_tax', 'net_income',
        'eps_basic', 'eps_diluted', 'cfo', 'cfi', 'cff', 'capex', 'dep_amort', 'dividends_paid', 'dps_declared', 'buyback',
        'shares_diluted_wavg'}


def sec_get(url):
    r = get(url, headers={'User-Agent': f'Colloquium TeamQ research {KEY["SEC_EMAIL"]}', 'Accept-Encoding': 'gzip, deflate'}, pause=0.15)
    return r.json() if r is not None and r.ok else None


def to_quarters(f):
    """같은 항목의 기간 숫자(start,end,val,filed) → 3개월 값. 누적(반기·9개월·연간)은 차이로 분기를 만든다.
    값은 '처음 공시된 값'만 쓴다(나중 정정값은 raw에 있음). 분기 값의 공시일 = 그 분기를 계산하는 데 쓴 숫자 중 가장 늦은 공시일."""
    f = f.dropna(subset=['start', 'end']).copy()
    f['days'] = (f['end'] - f['start']).dt.days
    f = f.sort_values('filed').drop_duplicates(['start', 'end'], keep='first')
    out = {}
    for _, r in f[(f['days'] >= 80) & (f['days'] <= 100)].iterrows():
        out[r['end']] = (r['val'], r['filed'], 'direct')
    for st, g in f.groupby('start'):
        g = g.sort_values('end')
        prev = None
        for _, r in g.iterrows():
            if prev is not None and 80 <= (r['end'] - prev['end']).days <= 100 and r['end'] not in out:
                out[r['end']] = (r['val'] - prev['val'], max(r['filed'], prev['filed']), 'derived_from_ytd')
            prev = r
    q = pd.DataFrame([{'period_end': k, 'value': v[0], 'filed': v[1], 'method': v[2]} for k, v in out.items()])
    return q.sort_values('period_end') if len(q) else q


def std_long(raw, std_map, ticker, src):
    """raw(concept,unit,start,end,val,filed,form) → 표준 항목 긴 표: 분기(Q)·연간(FY)·시점(I)"""
    rows = []
    for item, tags in std_map.items():
        sub = None
        for t in tags:
            s = raw[raw['concept'] == t]
            if len(s):
                sub, tag = s, t
                break
        if sub is None:
            continue
        unit = sub['unit'].value_counts().index[0]
        sub = sub[sub['unit'] == unit]
        if item in FLOW:
            q = to_quarters(sub)
            for _, r in q.iterrows():
                rows.append({'ticker': ticker, 'item': item, 'period_type': 'Q', 'period_start': None, 'period_end': r['period_end'],
                             'value': r['value'], 'unit': unit, 'filed': r['filed'], 'method': r['method'], 'tag': tag, 'source': src})
            fy = sub.dropna(subset=['start'])
            fy = fy[((fy['end'] - fy['start']).dt.days.between(350, 380))].sort_values('filed').drop_duplicates(['start', 'end'])
            for _, r in fy.iterrows():
                rows.append({'ticker': ticker, 'item': item, 'period_type': 'FY', 'period_start': r['start'], 'period_end': r['end'],
                             'value': r['val'], 'unit': unit, 'filed': r['filed'], 'method': 'direct', 'tag': tag, 'source': src})
        else:
            ins = sub.sort_values('filed').drop_duplicates(['end'], keep='first')
            for _, r in ins.iterrows():
                rows.append({'ticker': ticker, 'item': item, 'period_type': 'I', 'period_start': None, 'period_end': r['end'],
                             'value': r['val'], 'unit': unit, 'filed': r['filed'], 'method': 'direct', 'tag': tag, 'source': src})
    return pd.DataFrame(rows)


def part_fund_us():
    us = U[(U['country'] == '미국') & (U['kind'] == 'stock')]
    j = sec_get('https://www.sec.gov/files/company_tickers.json')
    cik = {v['ticker']: str(v['cik_str']).zfill(10) for v in (j or {}).values()}
    std_all, subs = [], []
    for t in us['yticker']:
        c = cik.get(t)
        if not c:
            status('fundamentals', f'SEC {t}', False, note='CIK 없음(SEC 미등록 또는 신규상장)')
            continue
        cf = sec_get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{c}.json')
        rows = []
        for tax, concepts in ((cf or {}).get('facts') or {}).items():
            for con, body in concepts.items():
                for unit, arr in (body.get('units') or {}).items():
                    for x in arr:
                        rows.append({'taxonomy': tax, 'concept': con, 'unit': unit, 'start': x.get('start'), 'end': x.get('end'),
                                     'val': x.get('val'), 'fy': x.get('fy'), 'fp': x.get('fp'), 'form': x.get('form'),
                                     'filed': x.get('filed'), 'frame': x.get('frame'), 'accn': x.get('accn')})
        raw = pd.DataFrame(rows)
        if len(raw):
            raw['start'] = pd.to_datetime(raw['start'], errors='coerce')
            raw['end'] = pd.to_datetime(raw['end'], errors='coerce')
            raw['filed'] = pd.to_datetime(raw['filed'], errors='coerce')
            raw['val'] = pd.to_numeric(raw['val'], errors='coerce')
            raw.insert(0, 'ticker', t)
            save(raw, f'raw/fundamentals/sec_companyfacts/{t}.parquet')
            s = std_long(raw[raw['end'] >= '2013-01-01'], STD_US, t, 'SEC companyfacts')
            std_all.append(s)
            status('fundamentals', f'SEC {t}', True, len(raw), note=f'표준항목 {s["item"].nunique() if len(s) else 0}개')
        else:
            status('fundamentals', f'SEC {t}', False, note='companyfacts 없음')
        # 공시 목록
        sb = sec_get(f'https://data.sec.gov/submissions/CIK{c}.json')
        if sb:
            parts = [sb.get('filings', {}).get('recent', {})]
            for fobj in sb.get('filings', {}).get('files', []):
                more = sec_get(f'https://data.sec.gov/submissions/{fobj["name"]}')
                if more:
                    parts.append(more)
            for p in parts:
                if p and p.get('form'):
                    d = pd.DataFrame({k: p.get(k) for k in ['accessionNumber', 'filingDate', 'acceptanceDateTime', 'reportDate',
                                                            'form', 'items', 'primaryDocDescription'] if k in p})
                    d.insert(0, 'ticker', t)
                    subs.append(d)
    if std_all:
        save(pd.concat(std_all), 'processed/fundamentals/us_standardized_pit.parquet')
    if subs:
        s = pd.concat(subs)
        s['filingDate'] = pd.to_datetime(s['filingDate'])
        s = s[s['filingDate'] >= START]
        s['event'] = np.where(s['form'].str.startswith('8-K') & s['items'].fillna('').str.contains('2.02'), '실적 발표(8-K 2.02)',
                     np.where(s['form'].isin(['10-K', '10-Q', '20-F', '6-K', '40-F']), '정기보고서', s['form']))
        s['source'] = 'SEC submissions'
        save(s, 'raw/corporate_actions/sec_filings.parquet')


# ---------------- DART ----------------
DART = 'https://opendart.fss.or.kr/api'
STD_KR = {
    'revenue': ['ifrs-full_Revenue', 'ifrs_Revenue'], 'cost_of_revenue': ['ifrs-full_CostOfSales', 'ifrs_CostOfSales'],
    'gross_profit': ['ifrs-full_GrossProfit', 'ifrs_GrossProfit'], 'operating_income': ['dart_OperatingIncomeLoss'],
    'pretax_income': ['ifrs-full_ProfitLossBeforeTax', 'ifrs_ProfitLossBeforeTax'],
    'income_tax': ['ifrs-full_IncomeTaxExpenseContinuingOperations', 'ifrs_IncomeTaxExpenseContinuingOperations'],
    'net_income': ['ifrs-full_ProfitLossAttributableToOwnersOfParent', 'ifrs_ProfitLossAttributableToOwnersOfParent',
                   'ifrs-full_ProfitLoss', 'ifrs_ProfitLoss'],
    'eps_basic': ['ifrs-full_BasicEarningsLossPerShare', 'ifrs_BasicEarningsLossPerShare'],
    'eps_diluted': ['ifrs-full_DilutedEarningsLossPerShare', 'ifrs_DilutedEarningsLossPerShare'],
    'total_assets': ['ifrs-full_Assets', 'ifrs_Assets'], 'total_liabilities': ['ifrs-full_Liabilities', 'ifrs_Liabilities'],
    'equity': ['ifrs-full_EquityAttributableToOwnersOfParent', 'ifrs_EquityAttributableToOwnersOfParent', 'ifrs-full_Equity', 'ifrs_Equity'],
    'cash': ['ifrs-full_CashAndCashEquivalents', 'ifrs_CashAndCashEquivalents'],
    'short_term_debt': ['ifrs-full_ShortTermBorrowings', 'ifrs_ShortTermBorrowings'],
    'long_term_debt': ['dart_LongTermBorrowingsGross', 'ifrs-full_LongtermBorrowings', 'ifrs-full_NoncurrentPortionOfNoncurrentBorrowings'],
    'cfo': ['ifrs-full_CashFlowsFromUsedInOperatingActivities', 'ifrs_CashFlowsFromUsedInOperatingActivities'],
    'cfi': ['ifrs-full_CashFlowsFromUsedInInvestingActivities', 'ifrs_CashFlowsFromUsedInInvestingActivities'],
    'cff': ['ifrs-full_CashFlowsFromUsedInFinancingActivities', 'ifrs_CashFlowsFromUsedInFinancingActivities'],
    'capex': ['ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities', 'ifrs_PurchaseOfPropertyPlantAndEquipment'],
    'dividends_paid': ['ifrs-full_DividendsPaidClassifiedAsFinancingActivities', 'ifrs_DividendsPaidClassifiedAsFinancingActivities'],
}
REPRT = {'11013': ('Q1', 3), '11012': ('H1', 6), '11014': ('Q3', 9), '11011': ('FY', 12)}


def dart(api, **p):
    r = get(f'{DART}/{api}', params={'crtfc_key': KEY['DART_KEY'], **p}, pause=0.25)
    if r is None:
        return None
    try:
        return r.json() if api.endswith('.json') else r
    except Exception:
        return None


def amt(v):
    if v is None:
        return np.nan
    s = str(v).replace(',', '').strip()
    if s in ('', '-'):
        return np.nan
    neg = s.startswith('(') and s.endswith(')')
    try:
        x = float(s.strip('()'))
        return -x if neg else x
    except ValueError:
        return np.nan


def dart_std(raw, code):
    """DART 원본 → 표준 항목. 손익은 분기 3개월 값(thstrm_amount, 연간은 연간−3분기 누적), 현금흐름은 누적의 차이, 재무상태는 시점."""
    rows = []
    raw = raw[raw['sj_div'] != 'SCE']
    for item, ids in STD_KR.items():
        sub = None
        for i in ids:
            s = raw[raw['account_id'] == i]
            if len(s):
                sub, tag = s, i
                break
        if sub is None:
            continue
        sub = sub.sort_values('sj_div', key=lambda c: c.map({'BS': 0, 'IS': 0, 'CF': 0, 'CIS': 1})).drop_duplicates(['bsns_year', 'reprt_code'])
        for _, r in sub.iterrows():
            yr, (lab, months) = int(r['bsns_year']), REPRT[r['reprt_code']]
            pe = pd.Timestamp(year=yr, month=12, day=31) if months == 12 else pd.Timestamp(year=yr, month=months, day=1) + pd.offsets.MonthEnd(0)
            base = {'ticker': code, 'item': item, 'period_end': pe, 'unit': r.get('currency') or 'KRW', 'filed': r['filed'],
                    'tag': tag, 'source': f'DART fnlttSinglAcntAll {r["fs_div"]}', 'fiscal_label': f'{yr}{lab}'}
            if r['sj_div'] == 'BS':
                rows.append({**base, 'period_type': 'I', 'value': amt(r['thstrm_amount']), 'method': 'direct'})
            elif r['sj_div'] in ('IS', 'CIS'):
                if months == 12:
                    rows.append({**base, 'period_type': 'FY', 'value': amt(r['thstrm_amount']), 'method': 'direct'})
                else:
                    rows.append({**base, 'period_type': 'Q', 'value': amt(r['thstrm_amount']), 'method': 'direct'})
                    rows.append({**base, 'period_type': f'YTD{months}', 'value': amt(r.get('thstrm_add_amount')) if months > 3 else amt(r['thstrm_amount']), 'method': 'direct'})
            else:  # CF 누적
                rows.append({**base, 'period_type': 'FY' if months == 12 else f'YTD{months}', 'value': amt(r['thstrm_amount']), 'method': 'direct'})
    d = pd.DataFrame(rows)
    if not len(d):
        return d
    # 분기 값 만들기: 손익 4분기 = 연간 − 3분기 누적, 현금흐름 분기 = 누적 차이
    add = []
    for (item, yr), g in d.assign(yr=d['period_end'].dt.year).groupby(['item', 'yr']):
        cum = {}
        for _, r in g.iterrows():
            if r['period_type'] in ('YTD6', 'YTD9', 'FY'):
                cum[{'YTD6': 6, 'YTD9': 9, 'FY': 12}[r['period_type']]] = r
            if r['period_type'] == 'Q' and r['period_end'].month == 3:
                cum.setdefault(3, r)
            if r['period_type'] == 'YTD3':
                cum[3] = r
        is_cf = not (g['period_type'] == 'Q').any()
        for m in ([3, 6, 9, 12] if is_cf else [12]):
            if m in cum and (m == 3 or m - 3 in cum):
                prev = cum.get(m - 3)
                v = cum[m]['value'] - (prev['value'] if prev is not None else 0)
                if item.startswith('eps') and m == 12:
                    v = cum[12]['value'] - cum[9]['value'] if 9 in cum else np.nan   # EPS 4분기는 근사(주식수 변화 무시)
                filed = max(cum[m]['filed'], prev['filed']) if prev is not None else cum[m]['filed']
                add.append({**cum[m].to_dict(), 'period_type': 'Q', 'value': v, 'filed': filed,
                            'method': 'derived_from_ytd' if m > 3 else 'direct'})
    d = pd.concat([d, pd.DataFrame(add)]) if add else d
    d = d[~d['period_type'].isin(['YTD3'])].drop(columns=['yr'], errors='ignore')
    return d.sort_values(['item', 'period_type', 'period_end', 'filed']).drop_duplicates(['item', 'period_type', 'period_end'], keep='first')


def part_fund_kr():
    if not KEY['DART_KEY']:
        status('fundamentals', 'DART', False, note='DART_KEY 없음')
        return
    r = dart('corpCode.xml')
    z = zipfile.ZipFile(io.BytesIO(r.content))
    root = ET.fromstring(z.read(z.namelist()[0]))
    cc = {(e.findtext('stock_code') or '').strip(): e.findtext('corp_code') for e in root.iter('list')}
    kr = U[(U['country'] == '한국') & (U['kind'] == 'stock')]
    years = range(int(START[:4]), int(TODAY[:4]) + 1)
    raws, stds, shares, divs, disc = [], [], [], [], []
    for code in kr['code']:
        corp = cc.get(code)
        if not corp:
            status('fundamentals', f'DART {code}', False, note='고유번호 없음')
            continue
        got = []
        for y in years:
            for rc in REPRT:
                for fs in ('CFS', 'OFS'):
                    j = dart('fnlttSinglAcntAll.json', corp_code=corp, bsns_year=str(y), reprt_code=rc, fs_div=fs)
                    if j and j.get('status') == '000' and j.get('list'):
                        d = pd.DataFrame(j['list'])
                        d['fs_div'] = fs
                        got.append(d)
                        break
                sh = dart('stockTotqySttus.json', corp_code=corp, bsns_year=str(y), reprt_code=rc)
                if sh and sh.get('status') == '000':
                    for x in sh.get('list', []):
                        shares.append({'ticker': code, 'bsns_year': y, 'reprt_code': rc, **x})
                if rc == '11011':
                    dv = dart('alotMatter.json', corp_code=corp, bsns_year=str(y), reprt_code=rc)
                    if dv and dv.get('status') == '000':
                        for x in dv.get('list', []):
                            divs.append({'ticker': code, 'bsns_year': y, **x})
        if got:
            raw = pd.concat(got)
            raw['filed'] = pd.to_datetime(raw['rcept_no'].str[:8], errors='coerce')
            raw.insert(0, 'ticker', code)
            raws.append(raw)
            s = dart_std(raw, code)
            stds.append(s)
            status('fundamentals', f'DART {code}', True, len(raw), note=f'보고서 {raw["rcept_no"].nunique()}건, 표준항목 {s["item"].nunique() if len(s) else 0}개')
        else:
            status('fundamentals', f'DART {code}', False, note='재무제표 없음')
        # 공시 목록 (10년 전체)
        page = 1
        while True:
            j = dart('list.json', corp_code=corp, bgn_de=START.replace('-', ''), end_de=TODAY.replace('-', ''), page_no=page, page_count=100)
            if not j or j.get('status') != '000':
                break
            for x in j.get('list', []):
                disc.append({'ticker': code, **x})
            if page >= int(j.get('total_page', 1)):
                break
            page += 1
    if raws:
        save(pd.concat(raws), 'raw/fundamentals/dart_fnltt_all.parquet')
        save(pd.concat(stds), 'processed/fundamentals/kr_standardized_pit.parquet')
    if shares:
        sh = pd.DataFrame(shares)
        sh['filed'] = pd.to_datetime(sh['rcept_no'].str[:8], errors='coerce')
        save(sh, 'raw/fundamentals/dart_shares_outstanding.parquet')
    if divs:
        dv = pd.DataFrame(divs)
        dv['filed'] = pd.to_datetime(dv['rcept_no'].str[:8], errors='coerce')
        save(dv, 'raw/corporate_actions/dart_dividend_matters.parquet')
    if disc:
        d = pd.DataFrame(disc)
        d['rcept_dt'] = pd.to_datetime(d['rcept_dt'])
        rules = [('유상증자', '유상증자'), ('무상증자', '무상증자'), ('자기주식.*소각|주식소각', '자사주 소각'),
                 ('자기주식취득|자기주식 취득|자기주식취득신탁', '자사주 매입'), ('현금ㆍ현물배당|현금·현물배당|배당결정|분기배당|중간배당', '배당 결정'),
                 ('주식분할|액면분할', '주식분할'), ('주식병합|액면병합', '주식병합'), ('영업\\(잠정\\)실적|잠정실적', '실적 발표(잠정)'),
                 ('사업보고서|반기보고서|분기보고서', '정기보고서'), ('매매거래정지|거래정지', '거래정지'), ('합병|분할합병|회사분할', '합병·분할')]
        d['event'] = None
        for pat, lab in rules:
            hit = d['event'].isna() & d['report_nm'].str.contains(pat, regex=True, na=False)
            d.loc[hit, 'event'] = lab
        d['event'] = d['event'].fillna('기타 공시')
        d['url'] = 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=' + d['rcept_no']
        d['source'] = 'DART list.json'
        save(d, 'raw/corporate_actions/dart_disclosures.parquet')
        status('corporate_actions', 'DART 공시 목록', True, len(d))


def part_fund_jp():
    """일본: EDINET 키가 없으면 야후 재무(최근 4~5년)만, 공시일이 없어 백테스트용 아님(참고)."""
    rows = []
    for t in U.loc[(U['country'] == '일본') & (U['kind'] == 'stock'), 'yticker']:
        try:
            tk = yf.Ticker(t)
            for nm, df in [('income_annual', tk.income_stmt), ('income_quarterly', tk.quarterly_income_stmt),
                           ('balance_annual', tk.balance_sheet), ('balance_quarterly', tk.quarterly_balance_sheet),
                           ('cashflow_annual', tk.cashflow), ('cashflow_quarterly', tk.quarterly_cashflow)]:
                if df is not None and not df.empty:
                    x = df.stack().reset_index()
                    x.columns = ['line_item', 'period_end', 'value']
                    x.insert(0, 'statement', nm)
                    x.insert(0, 'yticker', t)
                    rows.append(x)
            status('fundamentals', f'야후 일본 {t}', True)
        except Exception as e:
            status('fundamentals', f'야후 일본 {t}', False, note=e)
        time.sleep(1.5)
    if rows:
        d = pd.concat(rows, ignore_index=True)
        d['warning'] = '야후 재무: 최근 4~5년, 공시일 없음 → 미래정보 누수 위험, 백테스트에 그대로 쓰지 말 것'
        save(d, 'raw/fundamentals/yahoo_japan_financials_reference.parquet')
    status('fundamentals', 'EDINET 일본 공식 재무', False,
           note='EDINET_KEY 없음' if not KEY['EDINET_KEY'] else '다음 단계에서 수집(XBRL 해석 필요)')


def part_earnings_dates():
    """모든 개별주의 야후 실적 발표일(시각 포함, 최근 약 10~15년 중 야후가 가진 범위)"""
    out = []
    for t in U.loc[U['kind'] == 'stock', 'yticker']:
        try:
            ed = yf.Ticker(t).get_earnings_dates(limit=60)
            if ed is not None and not ed.empty:
                e = ed.reset_index()
                e.columns = ['earnings_datetime'] + list(e.columns[1:])
                e.insert(0, 'yticker', t)
                out.append(e)
            status('corporate_actions', f'야후 실적일 {t}', ed is not None and not ed.empty, 0 if ed is None else len(ed))
        except Exception as e:
            status('corporate_actions', f'야후 실적일 {t}', False, note=e)
        time.sleep(1.5)
    if out:
        d = pd.concat(out)
        d['earnings_datetime'] = d['earnings_datetime'].astype(str)
        d['source'] = 'yahoo get_earnings_dates'
        save(d, 'raw/corporate_actions/yahoo_earnings_dates.parquet')
