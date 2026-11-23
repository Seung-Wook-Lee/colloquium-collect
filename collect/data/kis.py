# 11/21 의장 "야후가 막았으면 한투에서 받도록": 야후가 빈칸으로 돌려준 종목만 한국투자증권(KIS) 조회 API로 채운다.
#   조회만(주문 없음). 키는 환경변수 KIS_APP_KEY·KIS_APP_SECRET, 토큰은 실행 중에만 들고 저장하지 않는다.
#   일봉: 국내 FHKST03010100(수정주가) / 해외 HHDFS76240000(수정주가)
#   분기 손익: 국내 FHKST66430200(억원). 해외 재무는 한투에 없음.
import os, time, datetime as dt, requests, pandas as pd

BASE = 'https://openapi.koreainvestment.com:9443'
EXCD = {'NASDAQ': 'NAS', 'NYSE': 'NYS', 'NYSE American': 'AMS', 'NYSE Arca': 'AMS', 'Cboe BZX': 'AMS'}
_TOK = {}
_ERR = []
_OK = []


def ready():
    return bool(os.environ.get('KIS_APP_KEY') and os.environ.get('KIS_APP_SECRET'))


def _token():
    if 'v' not in _TOK:
        for n in range(3):   # 토큰은 1분에 1번만 발급 → 앞 스크립트가 막 받았으면 61초 기다렸다 다시
            r = requests.post(f'{BASE}/oauth2/tokenP', timeout=10, json={
                'grant_type': 'client_credentials', 'appkey': os.environ['KIS_APP_KEY'],
                'appsecret': os.environ['KIS_APP_SECRET']}).json()
            if r.get('access_token') or n == 2:
                break
            time.sleep(61)
        if not r.get('access_token'):
            raise RuntimeError(f"한투 토큰 실패 {r.get('error_code')} {r.get('error_description')}")
        _TOK['v'] = r['access_token']
    return _TOK['v']


def _get(path, tr, params, retry=2):
    h = {'content-type': 'application/json; charset=utf-8', 'authorization': f'Bearer {_token()}',
         'appkey': os.environ['KIS_APP_KEY'], 'appsecret': os.environ['KIS_APP_SECRET'], 'tr_id': tr, 'custtype': 'P'}
    for n in range(retry + 1):
        try:
            time.sleep(0.12)
            j = requests.get(f'{BASE}{path}', headers=h, params=params, timeout=15).json()
            if j.get('rt_cd') == '0':
                return j
            raise ValueError(f"{j.get('msg_cd')} {j.get('msg1')}")
        except Exception as e:
            if n == retry:
                _ERR.append(f'{tr} {str(e)[:120]}')
                if len(_ERR) <= 3:
                    print('한투 조회 실패', _ERR[-1])
                return None
            time.sleep(1 + 2 * n)


def _f(v):
    try:
        x = float(str(v).replace(',', ''))
        return x if x != 0 else None
    except Exception:
        return None


def daily_kr(code, days=730):
    """국내 일봉 2년: DataFrame(index=날짜, Close·High·Low·Volume)"""
    end, start, rows = dt.date.today(), dt.date.today() - dt.timedelta(days=days), []
    while end > start:
        s = max(start, end - dt.timedelta(days=60))  # 한 번에 50줄까지라 60일(약 42거래일)씩 (11/23 빈칸 1300일 오류)   # 한 번에 100거래일
        j = _get('/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice', 'FHKST03010100',
                 {'FID_COND_MRKT_DIV_CODE': 'J', 'FID_INPUT_ISCD': str(code).zfill(6), 'FID_INPUT_DATE_1': s.strftime('%Y%m%d'),
                  'FID_INPUT_DATE_2': end.strftime('%Y%m%d'), 'FID_PERIOD_DIV_CODE': 'D', 'FID_ORG_ADJ_PRC': '0'})
        for o in (j or {}).get('output2') or []:
            if o.get('stck_bsop_date'):
                rows.append((o['stck_bsop_date'], _f(o.get('stck_clpr')), _f(o.get('stck_hgpr')), _f(o.get('stck_lwpr')), _f(o.get('acml_vol'))))
        end = s - dt.timedelta(days=1)
    return _frame(rows)


def daily_us(sym, exch=None, days=730, pages=8):
    """해외 일봉 2년. 거래소를 모르면 NAS→NYS→AMS 순으로"""
    sym = str(sym).replace('-', '/')
    first = EXCD.get(exch, 'NAS')
    for ex in [first] + [e for e in ('NAS', 'NYS', 'AMS') if e != first]:
        rows, bymd, stop = [], '', dt.date.today() - dt.timedelta(days=days)
        for _ in range(pages):
            j = _get('/uapi/overseas-price/v1/quotations/dailyprice', 'HHDFS76240000',
                     {'AUTH': '', 'EXCD': ex, 'SYMB': sym, 'GUBN': '0', 'BYMD': bymd, 'MODP': '1'})
            out = [o for o in (j or {}).get('output2') or [] if o.get('xymd')]
            if not out:
                break
            rows += [(o['xymd'], _f(o.get('clos')), _f(o.get('high')), _f(o.get('low')), _f(o.get('tvol'))) for o in out]
            last = min(o['xymd'] for o in out)
            if dt.datetime.strptime(last, '%Y%m%d').date() <= stop:
                break
            bymd = (dt.datetime.strptime(last, '%Y%m%d') - dt.timedelta(days=1)).strftime('%Y%m%d')
        if rows:
            return _frame(rows)
    return _frame([])


def _frame(rows):
    d = pd.DataFrame(rows, columns=['날짜', 'Close', 'High', 'Low', 'Volume']).dropna(subset=['Close'])
    if not len(d):
        return d.set_index('날짜')
    d['날짜'] = pd.to_datetime(d['날짜'], format='%Y%m%d')
    return d.drop_duplicates('날짜').set_index('날짜').sort_index()


def quarterly_kr(code):
    """국내 분기 손익(원): [(분기말 'YYYY-MM-DD', 매출, 영업이익, 순이익)]. 같은 해 누적값이면 분기값으로 풀어 준다."""
    if len(_ERR) >= 3 and not _OK:   # 처음 3번이 다 거절되면 이번 실행에선 더 묻지 않는다(11/21 밤 OPSQ0001)
        return []
    j = _get('/uapi/domestic-stock/v1/finance/income-statement', 'FHKST66430200',
             {'FID_DIV_CLS_CODE': '1', 'fid_cond_mrkt_div_code': 'J', 'fid_input_iscd': str(code).zfill(6)})
    out = (j or {}).get('output') or []
    d = pd.DataFrame([(o.get('stac_yymm'), _f(o.get('sale_account')), _f(o.get('bsop_prti')), _f(o.get('thtr_ntin')))
                      for o in out if o.get('stac_yymm')], columns=['ym', '매출', '영업이익', '순이익']).dropna(subset=['ym'])
    if not len(d):
        return []
    _OK.append(code)
    d = d.drop_duplicates('ym').sort_values('ym')
    d['y'], d['m'] = d['ym'].str[:4], d['ym'].str[4:6].astype(int)
    # 누적 여부: 같은 해 안에서 매출이 분기마다 커지고 12월이 3월의 2.5배를 넘으면 누적으로 본다
    cum = []
    for _, g in d.groupby('y'):
        if len(g) >= 3 and g['매출'].notna().all():
            cum.append(g['매출'].is_monotonic_increasing and g['매출'].iloc[-1] > 2.5 * g['매출'].iloc[0])
    if cum and sum(cum) > len(cum) / 2:
        for k in ('매출', '영업이익', '순이익'):
            d[k] = d.groupby('y')[k].diff().fillna(d[k])
        d = d[d.groupby('y')['m'].transform('min') <= 3]   # 앞이 잘린 해(누적 시작 분기 없음)는 뺀다
    res = []
    for _, r in d.iterrows():
        q = pd.Timestamp(int(r['y']), int(r['m']), 1) + pd.offsets.MonthEnd(0)
        res.append((str(q.date()), *(r[k] * 1e8 if pd.notna(r[k]) else None for k in ('매출', '영업이익', '순이익'))))
    return res


def daily_index_kr(code='1001', days=3650):
    """국내 지수 일봉(0001 코스피, 1001 코스닥) — FHKUP03500100. DataFrame(index=날짜, Close·High·Low·Volume)"""
    end, start, rows = dt.date.today(), dt.date.today() - dt.timedelta(days=days), []
    while end > start:
        s = max(start, end - dt.timedelta(days=60))  # 한 번에 50줄까지라 60일(약 42거래일)씩 (11/23 빈칸 1300일 오류)
        j = _get('/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice', 'FHKUP03500100',
                 {'FID_COND_MRKT_DIV_CODE': 'U', 'FID_INPUT_ISCD': code, 'FID_INPUT_DATE_1': s.strftime('%Y%m%d'),
                  'FID_INPUT_DATE_2': end.strftime('%Y%m%d'), 'FID_PERIOD_DIV_CODE': 'D'})
        for o in (j or {}).get('output2') or []:
            if o.get('stck_bsop_date'):
                rows.append((o['stck_bsop_date'], _f(o.get('bstp_nmix_prpr')), _f(o.get('bstp_nmix_hgpr')), _f(o.get('bstp_nmix_lwpr')), _f(o.get('acml_vol'))))
        end = s - dt.timedelta(days=1)
    return _frame(rows)


def daily_index_us(code='SOX', days=3650):
    """해외 지수 일봉(SOX 필라델피아 반도체 등) — FHKST03030100, 시장구분 N(해외지수). DataFrame(Close·High·Low·Volume)"""
    end, start, rows = dt.date.today(), dt.date.today() - dt.timedelta(days=days), []
    while end > start:
        s = max(start, end - dt.timedelta(days=60))  # 한 번에 50줄까지라 60일(약 42거래일)씩 (11/23 빈칸 1300일 오류)
        j = _get('/uapi/overseas-price/v1/quotations/inquire-daily-chartprice', 'FHKST03030100',
                 {'FID_COND_MRKT_DIV_CODE': 'N', 'FID_INPUT_ISCD': code, 'FID_INPUT_DATE_1': s.strftime('%Y%m%d'),
                  'FID_INPUT_DATE_2': end.strftime('%Y%m%d'), 'FID_PERIOD_DIV_CODE': 'D'})
        for o in (j or {}).get('output2') or []:
            if o.get('stck_bsop_date'):
                rows.append((o['stck_bsop_date'], _f(o.get('ovrs_nmix_prpr')), _f(o.get('ovrs_nmix_hgpr')), _f(o.get('ovrs_nmix_lwpr')), _f(o.get('acml_vol'))))
        end = s - dt.timedelta(days=1)
    return _frame(rows)
