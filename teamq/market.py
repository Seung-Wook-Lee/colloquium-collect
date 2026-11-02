# ======================================================================
# 팀 Q — 시장 자료: 가격(prices), ETF(etf), 거시경제(macro)
#   prices : 야후 일봉 10년(원 시가·고가·저가·종가는 '분할만 반영', 수정종가는 배당까지 반영) + 배당·분할
#            한국 49종목은 한투 일봉으로 원주가·수정주가·거래대금을 따로 받아 대조
#            가공본: 분할 역산 '원주가 종가', 거래대금(한국=한투 실제, 그 밖=종가×거래량 추정 표시)
#   etf    : 한국 ETF NAV·기초지수·거래대금·과거 구성종목(KRX, 로그인 KRX_ID·KRX_PW 있을 때만)
#            미국 ETF 현재 정보(총보수·순자산·설정일) — '현재 값'이라 과거 값으로 쓰지 않도록 표시
#   macro  : FRED(미국·한국·일본 금리·물가·고용·신용·스트레스), ALFRED 발표 당시 값,
#            FRED 지표 발표일, 야후 지수·환율·변동성, 일본 재무성 국채, 한국은행 ECOS(키 있을 때)
# ======================================================================
import io, time
import pandas as pd
import yfinance as yf
from common import *

YCOLS = {'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Adj Close': 'adj_close',
         'Volume': 'volume', 'Dividends': 'dividend', 'Stock Splits': 'split'}


def yahoo_daily(tickers, start=START, chunk=10, pause=2.0):
    out, miss = [], []
    def one(batch):
        for n in range(4):
            try:
                d = yf.download(batch, start=start, interval='1d', auto_adjust=False, actions=True,
                                group_by='ticker', threads=False, progress=False)
                rows = []
                for t in batch:
                    if d is None or d.empty or t not in d.columns.get_level_values(0):
                        continue
                    x = d[t].dropna(subset=['Close'])
                    if x.empty:
                        continue
                    x = x[[c for c in YCOLS if c in x.columns]].rename(columns=YCOLS)
                    x.insert(0, 'yticker', t)
                    rows.append(x)
                if rows:
                    r = pd.concat(rows).reset_index().rename(columns={'Date': 'date', 'index': 'date'})
                    r['date'] = pd.to_datetime(r['date']).dt.tz_localize(None).dt.normalize()
                    return r
                raise ValueError('빈 응답')
            except Exception as e:
                if n == 3:
                    log('  야후 실패', batch[:3], e)
                    return pd.DataFrame()
                time.sleep(5 * 3 ** n)
    for i in range(0, len(tickers), chunk):
        r = one(tickers[i:i + chunk])
        if not r.empty:
            out.append(r)
        time.sleep(pause)
    got = pd.concat(out) if out else pd.DataFrame(columns=['yticker'])
    for t in [t for t in tickers if t not in set(got['yticker'])]:
        time.sleep(pause)
        r = one([t])
        if r.empty:
            miss.append(t)
        else:
            got = pd.concat([got, r])
    return got.reset_index(drop=True), miss


def split_back(px):
    """야후 원 OHLC는 '그 뒤 분할'이 반영된 값 → 분할 비율을 거꾸로 곱해 당시 실제 가격(원주가)을 만든다."""
    out = []
    for t, g in px.sort_values('date').groupby('yticker'):
        s = g['split'].fillna(0).replace(0, 1.0).astype(float)
        after = s[::-1].cumprod()[::-1].shift(-1).fillna(1.0)     # 그날 '이후' 분할 누적
        g = g.copy()
        g['split_factor_after'] = after.values
        for c in ['open', 'high', 'low', 'close']:
            g[f'{c}_raw'] = g[c] * g['split_factor_after']
        g['volume_raw'] = g['volume'] / g['split_factor_after']
        out.append(g)
    return pd.concat(out)


# ---------------- 한투 (한국 일봉: 원주가·수정주가·거래대금) ----------------
KIS = 'https://openapi.koreainvestment.com:9443'
_TOK = {}


def kis_token():
    if 'v' not in _TOK:
        r = requests.post(f'{KIS}/oauth2/tokenP', timeout=15, json={
            'grant_type': 'client_credentials', 'appkey': KEY['KIS_APP_KEY'], 'appsecret': KEY['KIS_APP_SECRET']})
        _TOK['v'] = r.json().get('access_token')
        if not _TOK['v']:
            raise RuntimeError('한투 토큰 실패 ' + str(r.json().get('error_description')))
    return _TOK['v']


def kis_daily(code, adj):
    h = {'content-type': 'application/json; charset=utf-8', 'authorization': f'Bearer {kis_token()}',
         'appkey': KEY['KIS_APP_KEY'], 'appsecret': KEY['KIS_APP_SECRET'], 'tr_id': 'FHKST03010100', 'custtype': 'P'}
    end, rows = pd.Timestamp(TODAY), []
    while end >= pd.Timestamp(START):
        r = get(f'{KIS}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice', headers=h, pause=0.35, params={
            'FID_COND_MRKT_DIV_CODE': 'J', 'FID_INPUT_ISCD': code, 'FID_INPUT_DATE_1': START.replace('-', ''),
            'FID_INPUT_DATE_2': end.strftime('%Y%m%d'), 'FID_PERIOD_DIV_CODE': 'D', 'FID_ORG_ADJ_PRC': '0' if adj else '1'})
        j = r.json() if r is not None else {}
        o = [x for x in (j.get('output2') or []) if x.get('stck_bsop_date')]
        if not o:
            break
        rows += o
        first = pd.Timestamp(min(x['stck_bsop_date'] for x in o))
        if first >= end:
            break
        end = first - pd.Timedelta(days=1)
    if not rows:
        return pd.DataFrame()
    d = pd.DataFrame(rows).drop_duplicates('stck_bsop_date')
    m = {'stck_bsop_date': 'date', 'stck_oprc': 'open', 'stck_hgpr': 'high', 'stck_lwpr': 'low', 'stck_clpr': 'close',
         'acml_vol': 'volume', 'acml_tr_pbmn': 'trading_value', 'flng_cls_code': 'lock_code', 'prdy_vrss': 'chg'}
    d = d[[c for c in m if c in d.columns]].rename(columns=m)
    d['date'] = pd.to_datetime(d['date'])
    for c in ['open', 'high', 'low', 'close', 'volume', 'trading_value']:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    d.insert(0, 'code', code)
    d['adjusted'] = adj
    return d.sort_values('date')


def part_prices():
    tick = U['yticker'].tolist()
    px, miss = yahoo_daily(tick)
    for t in tick:
        n = int((px['yticker'] == t).sum()) if len(px) else 0
        status('prices', f'야후 {t}', n > 0, n)
    px['source'] = 'yahoo(yfinance)'
    px['collected_at'] = COLLECTED_AT
    save(px, 'raw/prices/yahoo_daily_10y.parquet')

    # 한국 49종목 한투 일봉
    kr = []
    if KEY['KIS_APP_KEY']:
        for code in U.loc[U['country'] == '한국', 'code']:
            for adj in (False, True):
                try:
                    d = kis_daily(code, adj)
                except Exception as e:
                    d = pd.DataFrame()
                    log('  한투 실패', code, e)
                status('prices', f'한투 {code} {"수정" if adj else "원주가"}', not d.empty, len(d))
                if not d.empty:
                    kr.append(d)
    kis = pd.concat(kr) if kr else pd.DataFrame(columns=['code', 'date', 'adjusted'])
    kis['source'] = 'KIS 국내주식기간별시세'
    kis['collected_at'] = COLLECTED_AT
    save(kis, 'raw/prices/kis_kr_daily_10y.parquet')

    # 가공본
    p = split_back(px).merge(U[['yticker', 'id', 'name', 'country', 'kind', 'currency', 'code']], on='yticker', how='left')
    p['trading_value'] = p['close_raw'] * p['volume_raw']
    p['trading_value_src'] = '추정(원주가 종가×거래량)'
    k = kis[kis['adjusted'] == False][['code', 'date', 'close', 'trading_value']].rename(
        columns={'close': 'kis_close_raw', 'trading_value': 'kis_trading_value'})
    if len(k):
        p = p.merge(k, on=['code', 'date'], how='left')
        hit = p['kis_trading_value'].notna()
        p.loc[hit, 'trading_value'] = p.loc[hit, 'kis_trading_value']
        p.loc[hit, 'trading_value_src'] = '한투 실제 거래대금'
        p['raw_close_diff_pct'] = (p['close_raw'] / p['kis_close_raw'] - 1) * 100
    p['ret_adj'] = p.groupby('yticker')['adj_close'].pct_change()
    p['listing_first_date'] = p.groupby('yticker')['date'].transform('min')
    p['note'] = 'close=분할 반영, close_raw=당시 실제 가격(분할 역산), adj_close=배당·분할 반영. 시가총액·발행주식수는 valuation 참고'
    save(p, 'processed/prices/daily_prices_10y.parquet')

    # 배당·분할 (corporate_actions 로)
    ca = px[(px['dividend'].fillna(0) != 0) | (px['split'].fillna(0) != 0)][['yticker', 'date', 'dividend', 'split']]
    ca = ca.merge(U[['yticker', 'id', 'name', 'country', 'currency']], on='yticker', how='left')
    ca['event'] = ca.apply(lambda r: '주식분할/병합' if r['split'] not in (0, None) and pd.notna(r['split']) and r['split'] != 0 else '배당락', axis=1)
    ca['date_meaning'] = '배당락일(ex-date) 또는 분할 적용일, 야후 기준. 배당금은 그 뒤 분할만큼 조정된 값'
    ca['source'] = 'yahoo(yfinance)'
    save(ca, 'raw/corporate_actions/yahoo_dividends_splits.parquet')
    if miss:
        log('  야후에서 못 받은 종목:', miss)


# ---------------- ETF ----------------
def part_etf():
    et = U[U['kind'] == 'etf']
    # 현재 정보(야후) — 과거 값 아님
    info = []
    for t in et['yticker']:
        try:
            i = yf.Ticker(t).info or {}
        except Exception as e:
            i = {'error': str(e)}
        info.append({'yticker': t, 'name': i.get('longName'), 'category': i.get('category'), 'fund_family': i.get('fundFamily'),
                     'expense_ratio_pct': i.get('netExpenseRatio') or i.get('annualReportExpenseRatio'),
                     'total_assets': i.get('totalAssets'), 'nav_price': i.get('navPrice'),
                     'inception_date': pd.to_datetime(i.get('fundInceptionDate'), unit='s', errors='coerce') if i.get('fundInceptionDate') else None,
                     'yield': i.get('yield'), 'currency': i.get('currency'), 'as_of': COLLECTED_AT,
                     'warning': '수집 시점 현재 값. 과거 시점 값으로 쓰지 말 것'})
        time.sleep(1.0)
    save(pd.DataFrame(info), 'raw/etf/yahoo_etf_info_current.parquet')
    status('etf', '야후 ETF 현재 정보', True, len(info))
    # 미국 ETF 현재 상위 구성(참고용)
    top = []
    for t in et.loc[et['country'] == '미국', 'yticker']:
        try:
            fd = yf.Ticker(t).funds_data
            h = fd.top_holdings.reset_index()
            h.insert(0, 'yticker', t)
            top.append(h)
        except Exception as e:
            log('  구성 실패', t, e)
        time.sleep(1.0)
    if top:
        th = pd.concat(top)
        th['as_of'] = COLLECTED_AT
        th['warning'] = '현재 상위 구성. 과거 구성으로 간주 금지'
        save(th, 'raw/etf/yahoo_us_etf_top_holdings_current.parquet')
    status('etf', '미국 ETF 현재 상위 구성', bool(top), sum(len(x) for x in top))

    # 한국 ETF: KRX (pykrx, 로그인 필요)
    if not (KEY['KRX_ID'] and KEY['KRX_PW']):
        status('etf', '한국 ETF NAV·과거 구성(KRX)', False, note='KRX_ID·KRX_PW 없음(pykrx 1.2+는 KRX 로그인 필요)')
        return
    from pykrx import stock
    nav, pdf = [], []
    for code in et.loc[et['country'] == '한국', 'code']:
        try:
            d = stock.get_etf_ohlcv_by_date(START.replace('-', ''), TODAY.replace('-', ''), code).reset_index()
            d.insert(0, 'code', code)
            nav.append(d)
            status('etf', f'KRX NAV {code}', len(d) > 0, len(d))
        except Exception as e:
            status('etf', f'KRX NAV {code}', False, note=e)
            continue
        dates = pd.to_datetime(d.iloc[:, 1]) if len(d) else []
        if len(dates):   # 분기 말 거래일마다 구성종목(PDF) 스냅숏
            q = pd.Series(dates).groupby(pd.Series(dates).dt.to_period('Q')).max().tolist() + [max(dates)]
            for day in sorted(set(q)):
                try:
                    h = stock.get_etf_portfolio_deposit_file(code, day.strftime('%Y%m%d')).reset_index()
                    h.insert(0, 'code', code)
                    h.insert(1, 'as_of_date', day)
                    pdf.append(h)
                except Exception as e:
                    log('  PDF 실패', code, day.date(), e)
                time.sleep(0.5)
    if nav:
        n = pd.concat(nav)
        n['source'] = 'KRX(pykrx)'
        save(n, 'raw/etf/krx_kr_etf_daily_nav.parquet')
    if pdf:
        p = pd.concat(pdf)
        p['source'] = 'KRX ETF PDF(pykrx), 분기 말 거래일 스냅숏'
        save(p, 'raw/etf/krx_kr_etf_holdings_quarterly.parquet')
    status('etf', 'KRX 과거 구성(분기 말)', bool(pdf), sum(len(x) for x in pdf))


# ---------------- 거시경제 ----------------
FRED_IDS = {
    # 미국 금리·정책
    'DFF': '미국 실효 연방기금금리(일)', 'DFEDTARU': '미국 기준금리 상단', 'DFEDTARL': '미국 기준금리 하단',
    'DGS3MO': '미국 3개월', 'DGS2': '미국 2년', 'DGS10': '미국 10년', 'DGS30': '미국 30년', 'DFII10': '미국 10년 실질',
    'T10Y2Y': '미국 10년-2년', 'T10Y3M': '미국 10년-3개월', 'T5YIE': '미국 5년 BEI',
    # 미국 물가·고용·경기
    'CPIAUCSL': '미국 CPI', 'CPILFESL': '미국 근원 CPI', 'PCEPILFE': '미국 근원 PCE', 'UNRATE': '미국 실업률',
    'PAYEMS': '미국 비농업 고용', 'ICSA': '미국 신규 실업수당', 'INDPRO': '미국 산업생산', 'UMCSENT': '미시간 소비자심리',
    'GDPC1': '미국 실질 GDP', 'USREC': '미국 경기침체 구간(NBER)', 'SAHMREALTIME': '샴 지표', 'M2SL': '미국 M2', 'WALCL': '연준 총자산',
    # 신용·스트레스·변동성·달러
    'BAMLH0A0HYM2': '미국 하이일드 스프레드', 'BAMLC0A0CM': '미국 투자등급 스프레드', 'BAA10Y': 'Baa-10년',
    'AAA10Y': 'Aaa-10년', 'NFCI': '시카고연준 금융여건', 'STLFSI4': '세인트루이스 금융스트레스', 'VIXCLS': 'VIX(FRED)',
    'DTWEXBGS': '달러지수(광의)', 'DEXKOUS': '원/달러(FRED)', 'DEXJPUS': '엔/달러(FRED)',
    # 한국·일본 (OECD 경유, 대부분 월간)
    'IRLTLT01KRM156N': '한국 10년 국채(월)', 'IR3TIB01KRM156N': '한국 3개월 금리(월)', 'KORCPIALLMINMEI': '한국 CPI',
    'LRHUTTTTKRM156S': '한국 실업률', 'IRLTLT01JPM156N': '일본 10년 국채(월)', 'IR3TIB01JPM156N': '일본 3개월 금리(월)',
    'IRSTCI01JPM156N': '일본 콜금리(월)', 'JPNCPIALLMINMEI': '일본 CPI', 'LRHUTTTTJPM156S': '일본 실업률',
}
ALFRED_IDS = ['CPIAUCSL', 'CPILFESL', 'PCEPILFE', 'UNRATE', 'PAYEMS', 'GDPC1', 'INDPRO', 'ICSA']
FRED_RELEASES = {10: 'CPI', 50: '고용상황(비농업)', 53: 'GDP', 54: '개인소득·PCE', 101: 'FOMC 성명'}
YAHOO_MACRO = {'^GSPC': 'S&P500', '^IXIC': '나스닥', '^NDX': '나스닥100', '^KS11': '코스피', '^KQ11': '코스닥', '^N225': '니케이225',
               '^SOX': '필라델피아 반도체', '^TWII': '대만 가권', '^VIX': 'VIX', '^VIX3M': 'VIX3M', '^MOVE': 'MOVE',
               '^TNX': '미국 10년(야후)', 'KRW=X': '원/달러', 'JPY=X': '엔/달러', 'JPYKRW=X': '원/엔', 'DX-Y.NYB': '달러지수',
               'GC=F': '금', 'CL=F': 'WTI', 'HG=F': '구리'}
ECOS = [  # (통계표, 주기, 항목코드, 이름) — 코드가 틀리면 결과에 '실패'로 남는다
    ('722Y001', 'D', '0101000', '한국은행 기준금리'), ('817Y002', 'D', '010195000', '국고채 2년'),
    ('817Y002', 'D', '010200000', '국고채 3년'), ('817Y002', 'D', '010210000', '국고채 10년'),
    ('817Y002', 'D', '010300000', '회사채 AA- 3년'), ('731Y001', 'D', '0000001', '원/달러 매매기준율'),
    ('731Y001', 'D', '0000002', '원/100엔'), ('901Y009', 'M', '0', '소비자물가지수'),
]


def fred(path, **params):
    r = get(f'https://api.stlouisfed.org/fred/{path}', params={'api_key': KEY['FRED_KEY'], 'file_type': 'json', **params}, pause=0.6)
    return r.json() if r is not None and r.ok else None


def part_macro():
    rows = []
    if KEY['FRED_KEY']:
        for sid, nm in FRED_IDS.items():
            j = fred('series/observations', series_id=sid, observation_start='2005-01-01')
            obs = (j or {}).get('observations') or []
            for o in obs:
                rows.append({'series_id': sid, 'name': nm, 'date': o['date'], 'value': pd.to_numeric(o['value'], errors='coerce'),
                             'realtime_start': o.get('realtime_start')})
            status('macro', f'FRED {sid}', bool(obs), len(obs))
    f = pd.DataFrame(rows)
    if len(f):
        f['date'] = pd.to_datetime(f['date'])
        f['source'] = 'FRED(최신 수정값)'
        f['warning'] = '최신 수정값. 당시 알 수 있던 값은 alfred_first_release 참고'
    save(f, 'raw/macro/fred_latest_values.parquet')

    # ALFRED: 발표 시점별 값 → 최초 발표값
    vint = []
    if KEY['FRED_KEY']:
        for sid in ALFRED_IDS:
            j = fred('series/observations', series_id=sid, observation_start='2013-01-01',
                     realtime_start='1776-07-04', realtime_end='9999-12-31')
            obs = (j or {}).get('observations') or []
            for o in obs:
                vint.append({'series_id': sid, 'date': o['date'], 'value': pd.to_numeric(o['value'], errors='coerce'),
                             'realtime_start': o['realtime_start'], 'realtime_end': o['realtime_end']})
            status('macro', f'ALFRED {sid}', bool(obs), len(obs))
    v = pd.DataFrame(vint)
    if len(v):
        v['date'] = pd.to_datetime(v['date'])
        v['realtime_start'] = pd.to_datetime(v['realtime_start'])
        save(v.assign(source='ALFRED'), 'raw/macro/alfred_vintages.parquet')
        fr = v.dropna(subset=['value']).sort_values('realtime_start').groupby(['series_id', 'date'], as_index=False).first()
        fr = fr.rename(columns={'value': 'first_release_value', 'realtime_start': 'first_release_date'})[
            ['series_id', 'date', 'first_release_value', 'first_release_date']]
        last = v.sort_values('realtime_start').groupby(['series_id', 'date'], as_index=False).last()[['series_id', 'date', 'value']]
        fr = fr.merge(last.rename(columns={'value': 'latest_value'}), on=['series_id', 'date'], how='left')
        fr['revised'] = (fr['latest_value'] - fr['first_release_value']).abs() > 1e-9
        save(fr, 'processed/macro/alfred_first_release.parquet')

    # 지표 발표일
    rel = []
    if KEY['FRED_KEY']:
        for rid, nm in FRED_RELEASES.items():
            info = fred('release', release_id=rid)
            rname = ((info or {}).get('releases') or [{}])[0].get('name')
            j = fred('release/dates', release_id=rid, realtime_start='2015-01-01', include_release_dates_with_no_data='false',
                     sort_order='asc', limit=10000)
            ds = (j or {}).get('release_dates') or []
            for d in ds:
                rel.append({'release_id': rid, 'label': nm, 'fred_release_name': rname, 'date': d['date']})
            status('macro', f'FRED 발표일 {nm} ({rname})', bool(ds), len(ds))
    save(pd.DataFrame(rel), 'raw/market_events/fred_release_dates.parquet')

    # 야후 지수·환율·변동성
    ym, miss = yahoo_daily(list(YAHOO_MACRO), start='2005-01-01')
    ym['name'] = ym['yticker'].map(YAHOO_MACRO)
    ym['source'] = 'yahoo(yfinance)'
    save(ym, 'raw/macro/yahoo_index_fx_vol.parquet')
    for t in YAHOO_MACRO:
        status('macro', f'야후 {t}', t not in miss, int((ym['yticker'] == t).sum()) if len(ym) else 0)

    # 일본 재무성 국채 금리(전 기간)
    jp = []
    for url in ['https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv',
                'https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv']:
        r = get(url, retry=1)
        if r is None or not r.ok:
            continue
        try:
            x = pd.read_csv(io.StringIO(r.content.decode('utf-8', 'ignore')), skiprows=1)
            x = x.rename(columns={x.columns[0]: 'date'})
            x['date'] = pd.to_datetime(x['date'], errors='coerce')
            jp.append(x.dropna(subset=['date']))
        except Exception as e:
            log('  재무성 형식 오류', e)
    if jp:
        j = pd.concat(jp).drop_duplicates('date', keep='last').sort_values('date')
        j = j.melt(id_vars='date', var_name='tenor', value_name='yield_pct')
        j['yield_pct'] = pd.to_numeric(j['yield_pct'], errors='coerce')
        j['source'] = '일본 재무성 JGB'
        save(j.dropna(subset=['yield_pct']), 'raw/macro/japan_mof_jgb_yields.parquet')
    status('macro', '일본 재무성 국채', bool(jp))

    # 한국은행 ECOS
    if KEY['ECOS_KEY']:
        ec = []
        for tb, cyc, item, nm in ECOS:
            s, e = ('20050101', TODAY.replace('-', '')) if cyc == 'D' else ('200501', TODAY[:7].replace('-', ''))
            r = get(f'https://ecos.bok.or.kr/api/StatisticSearch/{KEY["ECOS_KEY"]}/json/kr/1/100000/{tb}/{cyc}/{s}/{e}/{item}', pause=0.3)
            rows_ = ((r.json() if r is not None and r.ok else {}).get('StatisticSearch') or {}).get('row') or []
            for o in rows_:
                ec.append({'stat_code': tb, 'item_code': item, 'name': nm, 'time': o.get('TIME'), 'value': pd.to_numeric(o.get('DATA_VALUE'), errors='coerce'), 'unit': o.get('UNIT_NAME')})
            status('macro', f'ECOS {nm}', bool(rows_), len(rows_))
        save(pd.DataFrame(ec).assign(source='한국은행 ECOS'), 'raw/macro/ecos_korea.parquet')
    else:
        status('macro', '한국은행 ECOS', False, note='ECOS_KEY 없음 → 한국 일별 국고채·기준금리는 결측(FRED 월간 한국 금리로 대체 가능)')
