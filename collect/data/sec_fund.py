"""SEC 공시 재무 이력 (11/20 의장: "SEC 공시로 10년치 재무 이력, 최대한 모아서, 최대한 Quant로").

SEC XBRL companyfacts(무료, 키 없음)에서 미국 종목의 분기 재무를 받아, '공시가 나온 날' 기준(point-in-time)으로 쌓는다.
- 대상: 스튜디오 톰앤수 유니버스 미국 개별주 + S&P500 구성 종목(오늘 기준, 생존 편향 있음).
- 흐름 항목(매출·이익·현금흐름)은 분기 값으로 맞춘다: 3달짜리 값을 쓰고, 없는 4분기는 1년 값 − 앞 세 분기.
- 같은 분기를 나중에 고쳐 다시 낸 값은 쓰지 않는다(처음 공시한 값과 그날 = 그때 알 수 있던 것).
- 잔액 항목(자산·부채·자본)은 분기 말 값, 처음 공시일.
출력: 가격10년_SEC재무.csv.gz(10년치 저장본 칸, ticker, cik, 항목, 분기말, 공시일, 값) — 원본 json은 버린다.
"""
import json
import os
import sys
import time
import urllib.request

import numpy as np
import pandas as pd

UA = {'User-Agent': 'colloquium-research research-bot'}
FLOW = {   # 항목: 후보 태그(앞쪽 우선)
    '매출': ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues', 'SalesRevenueNet',
           'RevenueFromContractWithCustomerIncludingAssessedTax', 'RevenuesNetOfInterestExpense', 'SalesRevenueGoodsNet'],
    '매출총이익': ['GrossProfit'],
    '영업이익': ['OperatingIncomeLoss'],
    '세전이익': ['IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
             'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments'],
    '순이익': ['NetIncomeLoss', 'ProfitLoss', 'NetIncomeLossAvailableToCommonStockholdersBasic'],
    '이자비용': ['InterestExpense', 'InterestExpenseNonoperating', 'InterestExpenseDebt'],
    '감가상각': ['DepreciationDepletionAndAmortization', 'DepreciationAndAmortization', 'DepreciationAmortizationAndAccretionNet', 'Depreciation'],
    '영업현금흐름': ['NetCashProvidedByUsedInOperatingActivities', 'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'],
    '설비투자': ['PaymentsToAcquirePropertyPlantAndEquipment', 'PaymentsToAcquireProductiveAssets'],
    '희석EPS': ['EarningsPerShareDiluted', 'EarningsPerShareBasicAndDiluted'],
}
STOCK = {
    '자산': ['Assets'],
    '유동자산': ['AssetsCurrent'],
    '유동부채': ['LiabilitiesCurrent'],
    '부채': ['Liabilities'],
    '자본': ['StockholdersEquity', 'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'],
    '이익잉여금': ['RetainedEarningsAccumulatedDeficit'],
    '장기부채': ['LongTermDebtNoncurrent', 'LongTermDebt'],
    '단기부채': ['LongTermDebtCurrent', 'DebtCurrent', 'ShortTermBorrowings', 'CommercialPaper'],
    '현금': ['CashAndCashEquivalentsAtCarryingValue', 'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'],
    '주식수': ['dei:EntityCommonStockSharesOutstanding', 'CommonStockSharesOutstanding'],
}
FORMS = ('10-K', '10-Q', '10-K/A', '10-Q/A', '20-F', '40-F', '6-K')


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.loads(r.read())
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def cik_map():
    d = get('https://www.sec.gov/files/company_tickers.json')
    return {v['ticker'].upper(): int(v['cik_str']) for v in d.values()}


def _facts(F, tag, unit_pref=('USD', 'USD/shares', 'shares')):
    ns, t = tag.split(':') if ':' in tag else ('us-gaap', tag)
    node = F.get('facts', {}).get(ns, {}).get(t)
    if not node:
        return None
    for u in unit_pref:
        if u in node['units']:
            x = pd.DataFrame(node['units'][u])
            x = x[x['form'].isin(FORMS)] if 'form' in x else x
            return x if len(x) else None
    return None


def _quarters(x):
    """흐름 항목 → 분기 값(처음 공시값). 3달 값을 쓰고, 없으면 누적값 사다리(3·6·9·12달, 같은 시작일)의 차이로 만든다.
    현금흐름표는 10-Q에 연초부터 누적(6달·9달)으로만 나오므로 이 사다리가 필요하다."""
    x = x.copy()
    x['start'] = pd.to_datetime(x['start']); x['end'] = pd.to_datetime(x['end']); x['filed'] = pd.to_datetime(x['filed'])
    x['days'] = (x['end'] - x['start']).dt.days
    x = x.sort_values('filed').drop_duplicates(['start', 'end'], keep='first')
    q = x[x['days'].between(80, 100)][['end', 'filed', 'val']].drop_duplicates('end', keep='first')
    lad = x[x['days'].between(80, 100) | x['days'].between(170, 200) | x['days'].between(260, 290) | x['days'].between(350, 380)]
    add = []
    for _, g in lad.groupby('start'):
        g = g.sort_values('end')
        for i in range(1, len(g)):
            a, b = g.iloc[i - 1], g.iloc[i]
            if 80 <= (b['end'] - a['end']).days <= 100:
                add.append(dict(end=b['end'], filed=max(a['filed'], b['filed']), val=b['val'] - a['val']))
    if add:
        A = pd.DataFrame(add)
        A = A[~A['end'].apply(lambda e: (abs((q['end'] - e).dt.days) <= 7).any())]
        q = pd.concat([q, A], ignore_index=True)
    return q.sort_values('end').drop_duplicates('end', keep='first')


def _stock(x):
    x = x.copy()
    x['end'] = pd.to_datetime(x['end']); x['filed'] = pd.to_datetime(x['filed'])
    return x.sort_values('filed').drop_duplicates('end', keep='first')[['end', 'filed', 'val']]


def one(tk, cik):
    F = get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json')
    rows = []
    for name, tags, fn in [(k, v, _quarters) for k, v in FLOW.items()] + [(k, v, _stock) for k, v in STOCK.items()]:
        parts = []
        for tag in tags:   # 태그를 바꾼 회사(예: Revenues → RevenueFromContract...)는 이어 붙인다, 앞 태그 우선
            x = _facts(F, tag)
            if x is None or not {'end', 'val', 'filed'} <= set(x.columns):
                continue
            if fn is _quarters and 'start' not in x:
                continue
            y = fn(x)
            if len(y):
                parts.append(y)
        if not parts:
            continue
        y = pd.concat(parts).drop_duplicates('end', keep='first').sort_values('end')
        y = y.assign(ticker=tk, cik=cik, 항목=name)
        rows.append(y)
    return pd.concat(rows) if rows else pd.DataFrame()


def tickers(univ_csv=None, sp500=True):
    t = []
    if univ_csv:
        U = pd.read_csv(univ_csv, encoding='utf-8-sig')
        t += U[(U['시장'] == '미국') & (U['구분'] == '개별주')]['yfinance 티커'].dropna().astype(str).tolist()
    sector = {}
    if sp500:
        S = pd.read_csv('https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv')
        t += S['Symbol'].astype(str).tolist()
        sector = dict(zip(S['Symbol'], S['GICS Sector']))
    return sorted(set(x.upper() for x in t)), sector


def run(out, univ_csv=None, sp500=True):
    os.makedirs(out, exist_ok=True)
    tk, sector = tickers(univ_csv, sp500)
    cm = cik_map()
    from concurrent.futures import ThreadPoolExecutor
    res, miss = [], []

    def job(t):
        c = cm.get(t) or cm.get(t.replace('-', '.')) or cm.get(t.replace('.', '-'))
        if c is None:
            return t, None
        time.sleep(0.5)   # 일꾼 4명 × 초당 2번 미만 = SEC 초당 10번 제한 안
        try:
            return t, one(t, c)
        except Exception as e:
            return f'{t}({type(e).__name__})', None

    with ThreadPoolExecutor(4) as ex:
        for i, (t, d) in enumerate(ex.map(job, tk)):
            if d is None or d.empty:
                miss.append(t)
            else:
                res.append(d)
            if i % 50 == 0:
                print(f'[SEC] {i}/{len(tk)}', flush=True)
    D = pd.concat(res, ignore_index=True)
    D = D.rename(columns={'end': '분기말', 'filed': '공시일', 'val': '값'})[['ticker', 'cik', '항목', '분기말', '공시일', '값']]
    D.to_csv(f'{out}/가격10년_SEC재무.csv.gz', index=False, encoding='utf-8-sig', compression='gzip')
    pd.DataFrame({'ticker': list(sector), '섹터': list(sector.values())}).to_csv(f'{out}/SEC_섹터.csv', index=False, encoding='utf-8-sig')
    cov = D.groupby('항목')['ticker'].nunique()
    print(f'[SEC] 종목 {D["ticker"].nunique()}/{len(tk)}, 못 받음 {len(miss)}: {miss[:20]}')
    print(f'[SEC] 기간 {D["분기말"].min()}~{D["분기말"].max()}, 항목별 종목 수:\n{cov.to_string()}')
    return D


if __name__ == '__main__':
    # python sec_fund.py <출력폴더> [유니버스.csv]
    run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
