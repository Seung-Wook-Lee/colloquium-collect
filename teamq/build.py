# ======================================================================
# 팀 Q — 가공: 밸류에이션(valuation), 시장 이벤트(market_events), 품질 검사·현황(metadata)
#   밸류에이션 원칙: 그날 주가 × '그날 이미 공시된' 재무만 사용. 공시일 다음 날부터 반영(장 마감 뒤 공시 대비).
#   주식수는 공시 당시 값에 그 뒤 분할만 곱해 맞춘다. 미국 외 회계(TSM·ASML 등, 단위가 USD가 아님)는 계산하지 않는다.
# ======================================================================
import numpy as np
import pandas as pd
from common import *

STALE_DAYS = 450   # 분기말로부터 450일(약 15개월)이 지나면 그 값은 결측 처리
ITEMS_TTM = ['revenue', 'operating_income', 'net_income', 'cfo', 'capex', 'dep_amort', 'income_tax', 'pretax_income', 'dividends_paid']
ITEMS_I = ['equity', 'total_assets', 'total_liabilities', 'cash', 'short_term_debt', 'long_term_debt', 'liab_and_equity', 'equity_incl_nci']


def ttm_table(std, ticker, cur):
    """종목 하나의 표준 표 → 분기마다 '그 시점 TTM·시점값'과 사용 가능일(available)"""
    s = std[std['ticker'] == ticker]
    s = s[s['unit'].astype(str).str.upper().str.startswith(cur)]
    rows = {}
    for it in ITEMS_TTM:
        q = s[(s['item'] == it) & (s['period_type'] == 'Q')].sort_values('period_end').drop_duplicates('period_end')
        q = q.reset_index(drop=True)
        for k in range(3, len(q)):
            w = q.iloc[k - 3:k + 1]
            if 250 <= (w['period_end'].iloc[-1] - w['period_end'].iloc[0]).days <= 290:
                rows.setdefault(w['period_end'].iloc[-1], {})[f'{it}_ttm'] = (w['value'].sum(), w['filed'].max())
    for it in ITEMS_I:
        q = s[(s['item'] == it) & (s['period_type'] == 'I')]
        for _, r in q.iterrows():
            rows.setdefault(r['period_end'], {})[it] = (r['value'], r['filed'])
    if not rows:
        return pd.DataFrame()
    # 항목별로 '공시일 기준' 시계열을 만든다(항목마다 공시일이 달라도 섞이지 않게)
    out = []
    for pe, d in rows.items():
        for k, (v, f) in d.items():
            out.append({'period_end': pe, 'field': k, 'value': v, 'filed': f})
    o = pd.DataFrame(out).dropna(subset=['filed'])
    o['available'] = o['filed'] + pd.Timedelta(days=1)
    o['ticker'] = ticker
    return o


def asof_fields(dates, o):
    """일별 날짜에 항목별로 '사용 가능일 ≤ 그날' 인 가장 최근 분기 값"""
    base = pd.DataFrame({'date': dates}).sort_values('date')
    for f, g in o.groupby('field'):
        g = g.sort_values(['available', 'period_end']).drop_duplicates('available', keep='last')
        # 같은 날 여러 분기가 나오면 가장 최근 분기, 이미 더 최근 분기가 나왔으면 옛 분기로 되돌아가지 않게
        g['pe_max'] = g['period_end'].cummax()
        g = g[g['period_end'] == g['pe_max']]
        base = pd.merge_asof(base, g[['available', 'value', 'period_end']].rename(
            columns={'available': 'date', 'value': f, 'period_end': f'{f}__pe'}), on='date', direction='backward')
        stale = (base['date'] - base[f'{f}__pe']).dt.days > STALE_DAYS     # 새 공시가 끊긴 옛 값은 이어 쓰지 않는다
        base.loc[stale, f] = np.nan
    return base


def shares_series(t, cur, us_std, kr_sh):
    if cur == 'USD':
        s = us_std[(us_std['ticker'] == t) & (us_std['item'] == 'shares_outstanding')]
        src = 'SEC dei 표지 발행주식수'
        if not len(s):
            s = us_std[(us_std['ticker'] == t) & (us_std['item'] == 'shares_diluted_wavg') & (us_std['period_type'] == 'Q')]
            src = 'SEC 희석 가중평균 주식수(대체)'
        return s[['period_end', 'value', 'filed']].assign(src=src)
    k = kr_sh[(kr_sh['ticker'] == t) & kr_sh['se'].astype(str).str.contains('합계')].copy()
    if not len(k):
        return pd.DataFrame()
    num = lambda c: pd.to_numeric(k[c].astype(str).str.replace(',', ''), errors='coerce') if c in k else np.nan
    k['value'] = num('distb_stock_co')
    k['value'] = k['value'].fillna(num('istc_totqy'))
    m = {'11013': 3, '11012': 6, '11014': 9, '11011': 12}
    k['period_end'] = [pd.Timestamp(year=int(y), month=m[str(r)], day=1) + pd.offsets.MonthEnd(0) for y, r in zip(k['bsns_year'], k['reprt_code'])]
    return k[['period_end', 'value', 'filed']].assign(src='DART 유통주식수(없으면 발행주식총수)')


def part_valuation():
    px = load('processed/prices/daily_prices_10y.parquet')
    us = load('processed/fundamentals/us_standardized_pit.parquet')
    kr = load('processed/fundamentals/kr_standardized_pit.parquet')
    krsh = load('raw/fundamentals/dart_shares_outstanding.parquet')
    if px is None:
        raise RuntimeError('가격 가공본이 없음 (prices 먼저)')
    std = pd.concat([x for x in [us, kr] if x is not None])
    for c in ['period_end', 'filed']:
        std[c] = pd.to_datetime(std[c])
    if krsh is not None:
        krsh['filed'] = pd.to_datetime(krsh['filed'])
    all_v, ttm_all = [], []
    for _, u in U[U['kind'] == 'stock'].iterrows():
        key = u['yticker'] if u['country'] == '미국' else u['code']
        if u['country'] == '일본':
            status('valuation', u['yticker'], False, note='일본 공식 재무(EDINET) 미확보 → 계산 안 함')
            continue
        p = px[px['yticker'] == u['yticker']].sort_values('date')
        o = ttm_table(std, key, u['currency'])
        if p.empty or o.empty:
            status('valuation', u['yticker'], False, note='가격 또는 재무 없음(단위가 현지통화가 아니면 제외: TSM·ASML 등)')
            continue
        ttm_all.append(o)
        v = asof_fields(p['date'], o).merge(p[['date', 'close', 'close_raw', 'split', 'dividend']], on='date')
        # 주식수(분할 보정)
        sh = shares_series(key, u['currency'], std, krsh if krsh is not None else pd.DataFrame(columns=['ticker', 'se']))
        if len(sh):
            sh = sh.dropna().assign(available=lambda d: pd.to_datetime(d['filed']) + pd.Timedelta(days=1)).sort_values('available')
            v = pd.merge_asof(v.sort_values('date'), sh[['available', 'value', 'period_end', 'src']].rename(
                columns={'available': 'date', 'value': 'shares_reported', 'period_end': 'shares_asof', 'src': 'shares_src'}),
                on='date', direction='backward')
            sp = p[['date', 'split']].copy()
            sp['cum'] = sp['split'].fillna(0).replace(0, 1.0).astype(float).cumprod()
            cum = sp.set_index('date')['cum']
            ref = cum.reindex(pd.to_datetime(v['shares_asof']), method='ffill').values
            v['shares_adj'] = v['shares_reported'] * v['date'].map(cum).values / np.where(np.isnan(ref), 1.0, ref)
        else:
            v['shares_adj'] = np.nan
            v['shares_src'] = '없음'
        v['market_cap'] = v['close_raw'] * v['shares_adj']
        g = lambda c: v[c] if c in v else pd.Series(np.nan, index=v.index)
        debt = pd.concat([g('short_term_debt'), g('long_term_debt')], axis=1).sum(axis=1, min_count=1)
        if 'liab_and_equity' in v:   # 부채 총계를 따로 안 내는 회사: 부채와자본총계 − 자본총계
            alt = v['liab_and_equity'] - g('equity_incl_nci').fillna(g('equity'))
            v['total_liabilities'] = g('total_liabilities').fillna(alt)
        v['PER'] = v['market_cap'] / g('net_income_ttm')
        v['PBR'] = v['market_cap'] / g('equity')
        v['PSR'] = v['market_cap'] / g('revenue_ttm')
        v['PCR'] = v['market_cap'] / g('cfo_ttm')
        v['EV'] = v['market_cap'] + debt - g('cash').fillna(0)
        v['EBITDA_ttm'] = g('operating_income_ttm') + g('dep_amort_ttm')
        v['EV_EBITDA'] = v['EV'] / v['EBITDA_ttm']
        v['ROE'] = g('net_income_ttm') / g('equity')
        v['ROA'] = g('net_income_ttm') / g('total_assets')
        tax = (g('income_tax_ttm') / g('pretax_income_ttm')).clip(0, 0.5)
        v['ROIC'] = g('operating_income_ttm') * (1 - tax) / (g('equity') + debt - g('cash').fillna(0))
        v['op_margin'] = g('operating_income_ttm') / g('revenue_ttm')
        v['net_margin'] = g('net_income_ttm') / g('revenue_ttm')
        v['debt_ratio'] = g('total_liabilities') / g('equity')
        v['BPS'] = g('equity') / v['shares_adj']
        v['FCF_ttm'] = g('cfo_ttm') - g('capex_ttm').abs()
        v['FCF_yield'] = v['FCF_ttm'] / v['market_cap']
        dv = v.set_index('date')['dividend'].fillna(0).rolling('365D').sum()
        v['dividend_yield'] = dv.values / v['close'].values      # 야후 배당·종가 모두 분할 보정 단위라 비율은 맞다
        v.insert(0, 'yticker', u['yticker'])
        v['currency'] = u['currency']
        v['method'] = '공시일+1일부터 반영한 TTM(최근 4분기) / 시점값은 최근 공시 분기말'
        all_v.append(v)
        status('valuation', u['yticker'], True, len(v), note=f'PER 첫날 {v.loc[v["PER"].notna(), "date"].min()}')
    if ttm_all:
        save(pd.concat(ttm_all), 'processed/fundamentals/ttm_and_instant_pit.parquet')
    if all_v:
        save(pd.concat(all_v), 'processed/valuation/daily_valuation_pit.parquet')


# ---------------- 시장 이벤트 ----------------
def part_events():
    ym = load('raw/macro/yahoo_index_fx_vol.parquet')
    fr = load('raw/macro/fred_latest_values.parquet')
    ev = []
    def add(d, scope, ticker, typ, val, detail, src):
        ev.append({'date': pd.Timestamp(d), 'scope': scope, 'ticker': ticker, 'event_type': typ, 'value': val, 'detail': detail, 'source': src})
    if ym is not None and len(ym):
        for t in ['^GSPC', '^IXIC', '^NDX', '^KS11', '^KQ11', '^N225', '^SOX']:
            s = ym[ym['yticker'] == t].set_index('date')['close'].sort_index().dropna()
            if s.empty:
                continue
            r = s.pct_change()
            for d, x in r[r <= -0.03].items():
                add(d, 'market', t, '지수 하루 -3% 이상 급락', round(x * 100, 2), '', 'yahoo')
            dd = s / s.cummax() - 1
            for lvl in (-0.10, -0.20, -0.30):
                cross = (dd <= lvl) & (dd.shift(1) > lvl)
                for d in dd.index[cross]:
                    add(d, 'market', t, f'고점 대비 {int(lvl*100)}% 진입', round(dd[d] * 100, 2), '', 'yahoo')
            newhigh = dd == 0
            for d in dd.index[newhigh & (dd.shift(1) < -0.10)]:
                add(d, 'market', t, '-10% 이상 하락 뒤 신고가 회복', 0, '', 'yahoo')
        vix = ym[ym['yticker'] == '^VIX'].set_index('date')['close'].sort_index()
        for d in vix.index[(vix >= 30) & (vix.shift(1) < 30)]:
            add(d, 'market', '^VIX', 'VIX 30 돌파', vix[d], '', 'yahoo')
        ch5 = vix / vix.shift(5) - 1
        for d in ch5.index[(ch5 >= 0.5) & (ch5.shift(1) < 0.5)]:
            add(d, 'market', '^VIX', 'VIX 5일 +50% 급등', round(ch5[d] * 100, 1), '', 'yahoo')
        for t, th in [('KRW=X', 0.015), ('JPY=X', 0.015)]:
            s = ym[ym['yticker'] == t].set_index('date')['close'].sort_index().pct_change()
            for d, x in s[s.abs() >= th].items():
                add(d, 'market', t, '환율 하루 1.5% 이상 변동', round(x * 100, 2), '', 'yahoo')
    if fr is not None and len(fr):
        for sid, th in [('DGS10', 0.15), ('DGS2', 0.20)]:
            s = fr[fr['series_id'] == sid].set_index('date')['value'].sort_index().dropna().diff()
            for d, x in s[s.abs() >= th].items():
                add(d, 'market', sid, f'금리 하루 {int(th*100)}bp 이상 변동', round(x * 100, 1), 'bp', 'FRED')
        s = fr[fr['series_id'] == 'DFEDTARU'].set_index('date')['value'].sort_index().dropna()
        for d, x in s.diff()[s.diff().abs() > 0].items():
            add(d, 'market', 'DFEDTARU', '미국 기준금리 변경', x, f'상단 {s[d]}%', 'FRED')
    rel = load('raw/market_events/fred_release_dates.parquet')
    if rel is not None:
        for _, r in rel.iterrows():
            add(r['date'], 'market', 'US', f'지표 발표일: {r["label"]}', None, r.get('fred_release_name'), 'FRED release dates')
    fo = load('raw/market_events/fomc_meetings.parquet')
    if fo is not None:
        for _, r in fo.iterrows():
            add(r['date'], 'market', 'FOMC', 'FOMC 회의(성명 발표일)', None, r['label'], 'federalreserve.gov')
    ec = load('raw/macro/ecos_korea.parquet')
    if ec is not None and len(ec):
        b = ec[ec['name'] == '한국은행 기준금리'].copy()
        b['date'] = pd.to_datetime(b['time'], format='%Y%m%d', errors='coerce')
        s = b.set_index('date')['value'].sort_index()
        for d, x in s.diff()[s.diff().abs() > 0].items():
            add(d, 'market', 'BOK', '한국 기준금리 변경', x, f'{s[d]}%', 'ECOS')
    # 기업 이벤트
    sec = load('raw/corporate_actions/sec_filings.parquet')
    if sec is not None:
        for _, r in sec[sec['event'] == '실적 발표(8-K 2.02)'].iterrows():
            add(r['filingDate'], 'company', r['ticker'], '실적 발표', None, f'접수 {r.get("acceptanceDateTime")}', 'SEC 8-K 2.02')
    dd_ = load('raw/corporate_actions/dart_disclosures.parquet')
    if dd_ is not None:
        for _, r in dd_[dd_['event'] != '기타 공시'].iterrows():
            add(r['rcept_dt'], 'company', r['ticker'], r['event'], None, r['report_nm'], r['url'])
    ca = load('raw/corporate_actions/yahoo_dividends_splits.parquet')
    if ca is not None:
        for _, r in ca.iterrows():
            add(r['date'], 'company', r['yticker'], r['event'], r['split'] if r['event'] != '배당락' else r['dividend'], '', 'yahoo')
    e = pd.DataFrame(ev)
    if len(e):
        e = e[e['date'] >= '2005-01-01'].sort_values(['date', 'scope'])
        e['note'] = '날짜는 각 시장 현지 날짜. 미국 공시는 장 마감 뒤일 수 있어 다음 거래일부터 반응을 볼 것'
    save(e, 'processed/market_events/events.parquet')
    status('market_events', '이벤트 표', len(e) > 0, len(e))
    status('market_events', '거래정지 이력(한국 외)', False, note='무료 과거 출처 없음 → 한국은 DART 거래정지 공시만')
    status('market_events', '과거 뉴스 원문', False, note='이번 범위 밖(GDELT 등은 다음 단계 후보)')


# ---------------- 품질 검사·현황 ----------------
def part_quality():
    px = load('processed/prices/daily_prices_10y.parquet')
    kis = load('raw/prices/kis_kr_daily_10y.parquet')
    rows = []
    if px is not None:
        idx = load('raw/macro/yahoo_index_fx_vol.parquet')
        cal = {}
        if idx is not None:
            for c, t in [('한국', '^KS11'), ('미국', '^GSPC'), ('일본', '^N225')]:
                cal[c] = set(idx.loc[idx['yticker'] == t, 'date'])
        for t, g in px.groupby('yticker'):
            c = g['country'].iloc[0]
            d = set(g['date'])
            exp = {x for x in cal.get(c, set()) if g['date'].min() <= x <= g['date'].max()}
            r = g.sort_values('date')['adj_close'].pct_change()
            rows.append({'yticker': t, 'name': g['name'].iloc[0], 'country': c, 'kind': g['kind'].iloc[0],
                         'first_date': g['date'].min().date(), 'last_date': g['date'].max().date(), 'rows': len(g),
                         'years': round((g['date'].max() - g['date'].min()).days / 365.25, 1),
                         'full_10y': g['date'].min() <= pd.Timestamp(START) + pd.Timedelta(days=10),
                         'missing_vs_index_cal': len(exp - d) if exp else None, 'extra_vs_index_cal': len(d - exp) if exp else None,
                         'dup_dates': int(g['date'].duplicated().sum()), 'zero_volume_days': int((g['volume'] == 0).sum()),
                         'nonpositive_price': int((g['close'] <= 0).sum()), 'abs_ret_over_40pct': int((r.abs() > 0.4).sum()),
                         'splits': int((g['split'].fillna(0) != 0).sum()), 'dividends': int((g['dividend'].fillna(0) != 0).sum()),
                         'kis_raw_close_median_diff_pct': round(g['raw_close_diff_pct'].abs().median(), 3) if 'raw_close_diff_pct' in g and g['raw_close_diff_pct'].notna().any() else None})
    q = pd.DataFrame(rows)
    # 기존 매일 수집 가격과 겹치는 기간 대조(읽기만)
    b = read_existing('콜로키움 수집데이터/00_누적/00_가격이력.csv')
    if b is not None and len(q):
        old = pd.read_csv(io.BytesIO(b), parse_dates=['날짜'], dtype={'티커': str})
        m = old.rename(columns={'날짜': 'date', '티커': 'yticker', '수정종가': 'old_adj', '종가': 'old_close'}).merge(
            px[['yticker', 'date', 'close', 'adj_close']], on=['yticker', 'date'])
        m['diff_close_pct'] = (m['close'] / m['old_close'] - 1).abs() * 100
        agg = m.groupby('yticker').agg(overlap_days=('date', 'size'), existing_close_median_diff_pct=('diff_close_pct', 'median')).reset_index()
        q = q.merge(agg, on='yticker', how='left')
        status('metadata', '기존 00_가격이력 대조', True, len(m))
    else:
        status('metadata', '기존 00_가격이력 대조', False, note='기존 창구 없음 또는 파일 없음')
    save(q, 'metadata/quality_prices.parquet')
    q.to_csv(os.path.join(OUT, 'metadata/quality_prices.csv'), index=False, encoding='utf-8-sig')

    # 재무 확보 기간
    fr = []
    for f, src in [('processed/fundamentals/us_standardized_pit.parquet', 'SEC'), ('processed/fundamentals/kr_standardized_pit.parquet', 'DART')]:
        s = load(f)
        if s is None:
            continue
        s['period_end'] = pd.to_datetime(s['period_end'])
        for t, g in s.groupby('ticker'):
            qq = g[(g['period_type'] == 'Q') & (g['item'].isin(['revenue', 'net_income']))]
            fr.append({'ticker': t, 'source': src, 'first_quarter': qq['period_end'].min(), 'last_quarter': qq['period_end'].max(),
                       'quarters_net_income': int((qq['item'] == 'net_income').sum()), 'quarters_revenue': int((qq['item'] == 'revenue').sum()),
                       'items_found': g['item'].nunique(), 'items_missing': ','.join(sorted(set(['revenue', 'cost_of_revenue', 'gross_profit', 'operating_income', 'net_income', 'eps_basic', 'total_assets', 'total_liabilities', 'equity', 'cash', 'short_term_debt', 'long_term_debt', 'cfo', 'cfi', 'cff', 'capex']) - set(g['item'])))})
    f = pd.DataFrame(fr)
    save(f, 'metadata/coverage_fundamentals.parquet')
    f.to_csv(os.path.join(OUT, 'metadata/coverage_fundamentals.csv'), index=False, encoding='utf-8-sig')

    st = pd.DataFrame(STATUS)
    prev = load('metadata/run_status.parquet')          # 앞 실행의 결과는 남기고, 이번에 다시 돈 단계만 바꾼다
    if prev is not None and len(prev):
        st = pd.concat([prev[~prev['part'].isin(set(st['part']) if len(st) else set())], st])
    save(st, 'metadata/run_status.parquet')
    st.to_csv(os.path.join(OUT, 'metadata/run_status.csv'), index=False, encoding='utf-8-sig')
    src = pd.DataFrame([
        ('prices', 'Yahoo Finance(yfinance)', '없음', '일봉 OHLC·수정종가·거래량·배당·분할, 상장 이후 전체'),
        ('prices', '한국투자증권 국내주식기간별시세', 'KIS_APP_KEY', '한국 49종목 원주가·수정주가·거래대금'),
        ('fundamentals', 'SEC EDGAR companyfacts·submissions', 'SEC_EMAIL(User-Agent)', '미국 재무 전 기간, 공시일·접수시각'),
        ('fundamentals', 'DART OpenAPI fnlttSinglAcntAll·stockTotqySttus·alotMatter·list', 'DART_KEY', '한국 재무 2015~, 공시일=접수번호'),
        ('fundamentals', 'EDINET API v2', 'EDINET_KEY', '일본 공식 재무(키 있을 때 다음 단계)'),
        ('etf', 'KRX(pykrx)', 'KRX_ID·KRX_PW', '한국 ETF NAV·기초지수·과거 구성'),
        ('macro', 'FRED / ALFRED', 'FRED_KEY', '미국·한국·일본 금리·물가·고용·신용, 최초 발표값, 발표일'),
        ('macro', '한국은행 ECOS', 'ECOS_KEY', '한국 기준금리·국고채·환율'),
        ('macro', '일본 재무성 JGB', '없음', '일본 국채 금리 전 기간'),
    ], columns=['folder', 'source', 'key', 'what'])
    src['collected_at'] = COLLECTED_AT
    save(src, 'metadata/sources.parquet')
    src.to_csv(os.path.join(OUT, 'metadata/sources.csv'), index=False, encoding='utf-8-sig')


def part_summary():
    """실행 로그에 확보 현황을 찍는다(산출물을 내려받지 못할 때 확인용)."""
    pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500); pd.set_option('display.max_columns', 30)
    for rel in ['metadata/run_status.parquet', 'metadata/quality_prices.parquet', 'metadata/coverage_fundamentals.parquet']:
        d = load(rel)
        print(f'\n##### {rel}')
        if d is None:
            print('없음'); continue
        if 'run_status' in rel:
            print(d.groupby('part')['ok'].agg(['sum', 'count']))
            print(d[~d['ok']][['part', 'item', 'note']].to_string())
        else:
            print(d.drop(columns=[c for c in ['name'] if c in d]).to_string())
    v = load('processed/valuation/daily_valuation_pit.parquet')
    if v is not None:
        print('\n##### valuation: 종목별 첫 PER 날짜와 마지막 날 값')
        last = v.sort_values('date').groupby('yticker').tail(1).set_index('yticker')
        first = v[v['PER'].notna()].groupby('yticker')['date'].min()
        cols = [c for c in ['date', 'shares_src', 'market_cap', 'PER', 'PBR', 'PSR', 'EV_EBITDA', 'ROE', 'ROIC', 'debt_ratio', 'dividend_yield', 'FCF_yield'] if c in last]
        print(last[cols].assign(first_PER=first).round(3).to_string())
    for rel in ['processed/market_events/events.parquet', 'raw/corporate_actions/dart_disclosures.parquet', 'raw/corporate_actions/sec_filings.parquet']:
        d = load(rel)
        if d is not None:
            col = 'event_type' if 'event_type' in d else 'event'
            print(f'\n##### {rel} 종류별 건수'); print(d[col].value_counts().head(40).to_string())
    for rel in ['raw/prices/kis_kr_daily_10y.parquet', 'raw/macro/fred_latest_values.parquet', 'processed/macro/alfred_first_release.parquet',
                'raw/fundamentals/yahoo_japan_financials_reference.parquet', 'raw/etf/yahoo_etf_info_current.parquet']:
        d = load(rel)
        if d is None:
            print(f'\n##### {rel}: 없음'); continue
        print(f'\n##### {rel}: {len(d):,}행')
        if 'series_id' in d:
            print(d.groupby('series_id')['date'].agg(['min', 'max', 'count']).to_string())
        elif 'code' in d:
            print(d.groupby(['code', 'adjusted'])['date'].agg(['min', 'max', 'count']).to_string())
        else:
            print(d.head(15).to_string())
