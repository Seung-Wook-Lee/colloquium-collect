# ======================================================================
# [블록 9-자금] ETF 자금유입 — 국내·미국 ETF로 실제 돈이 들어왔나 나갔나 (2026-10-29 의장 요청)
#   하는 일  : ETF마다 상장좌수(발행된 ETF 수)를 매일 기록한다. ETF는 돈이 들어오면 새로 설정(좌수 증가),
#              나가면 환매(좌수 감소)되므로, 자금유입 = 좌수 변화 × NAV(없으면 종가).
#              좌수가 없을 때(미국 일부)는 순자산 변화 − 가격 변동분으로 계산한다.
#              1일·5일·20일 누적 유입, 순자산 대비 %, 시장 안 순위를 낸다.
#   대상     : 콜로키움 100의 ETF 전부(국내 30·미국 10) + 미국 섹터 비교용 US_EXTRA(SPDR 섹터 11개, SPY·QQQ·SOXX·MAGS)
#   소스     : 국내 = 한투 국내 현재가(상장주수) + ETF 현재가(NAV·순자산, 안 되면 빈칸)
#              미국 = 한투 해외 현재가 상세(상장주수 shar) + 야후 순자산(totalAssets)·NAV
#              SPDR 펀드(XL*·SPY·SPYM)는 State Street 공식 엑셀(NAV·좌수 일별 이력 1년)을 매일 받아 그것을 쓴다.
#   읽는 것  : 한투 키 2개(블록 2가 받은 토큰이 있으면 그대로 씀)
#   만드는 것: 수집데이터/00_누적/00_ETF좌수이력.csv (하루 한 줄씩 이어 씀, 같은 날 다시 돌리면 덮어씀)
#              수집데이터/YYYYMMDD/YYYYMMDD_ETF자금.csv (ETF 한 줄, 시장별 20일 유입 순)
#   쓰는 위원: 뉴스보이(어느 섹터로 돈이 몰리나, 사실 보고), 라케시스·클로토(수급 가점), 엘피스(갈아타기 기회)
#   주의     : 국내 상장좌수는 설정·환매가 하루 늦게 반영될 수 있다. 기록이 쌓이기 전(5·20영업일)에는 해당 칸이 빈칸.
#              유입은 국내 억원, 미국 백만달러.
#   고칠 곳  : 미국 비교 대상은 US_EXTRA
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
import json

US_EXTRA = {'XLK': '기술', 'XLC': '커뮤니케이션', 'XLY': '임의소비재', 'XLP': '필수소비재', 'XLE': '에너지',
            'XLF': '금융', 'XLV': '헬스케어', 'XLI': '산업재', 'XLB': '소재', 'XLRE': '부동산', 'XLU': '유틸리티',
            'SPY': 'S&P500', 'QQQ': '나스닥100', 'SOXX': '반도체', 'MAGS': '매그니피센트7'}
SPDR = {'XLK', 'XLC', 'XLY', 'XLP', 'XLE', 'XLF', 'XLV', 'XLI', 'XLB', 'XLRE', 'XLU', 'SPY', 'SPYM'}
FLOW_FILE = f'{KEEP}/00_ETF좌수이력.csv'
KIS = 'https://openapi.koreainvestment.com:9443'


def _f(v):
    try:
        x = float(str(v).replace(',', ''))
        return x if x != 0 else None
    except Exception:
        return None


def _kis(path, tr_id, params):
    h = {'content-type': 'application/json; charset=utf-8', 'authorization': f'Bearer {KIS_TOKEN}',
         'appkey': SEC['KIS_APP_KEY'], 'appsecret': SEC['KIS_APP_SECRET'], 'tr_id': tr_id, 'custtype': 'P'}
    for n in range(3):
        try:
            time.sleep(0.3)
            j = requests.get(f'{KIS}{path}', headers=h, params=params, timeout=10).json()
            if j.get('rt_cd') == '0' and j.get('output'):
                return j['output']
        except Exception:
            pass
        time.sleep(1 + 2 * n)
    return None


def _spdr_hist(t):
    """State Street 공식 NAV 이력 엑셀 → 날짜·NAV·좌수 (안 되면 None)"""
    r = get(f'https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/navhist-us-en-{t.lower()}.xlsx',
            retry=1)
    if r is None:
        return None
    raw = pd.read_excel(io.BytesIO(r.content), header=None)
    hdr = raw.index[raw.iloc[:, 0].astype(str).str.strip().str.lower() == 'date'][0]
    df = raw.iloc[hdr + 1:].copy()
    df.columns = [str(c).strip().lower() for c in raw.iloc[hdr]]
    sh = next(c for c in df.columns if 'shares' in c)
    out = pd.DataFrame({'날짜': pd.to_datetime(df['date'], errors='coerce', format='mixed'),
                        'NAV': pd.to_numeric(df['nav'], errors='coerce'),
                        '상장좌수': pd.to_numeric(df[sh].astype(str).str.replace(',', ''), errors='coerce')}).dropna()
    return out.sort_values('날짜')


try:
    if not (SEC.get('KIS_APP_KEY') and SEC.get('KIS_APP_SECRET')):
        raise RuntimeError('한투 키 없음')
    KIS_TOKEN = globals().get('TOKEN')      # 블록 2가 받은 토큰
    if not KIS_TOKEN:                        # 블록 2를 건너뛴 시험 실행이면 새로 받는다
        r = requests.post(f'{KIS}/oauth2/tokenP', timeout=10, json={
            'grant_type': 'client_credentials', 'appkey': SEC['KIS_APP_KEY'], 'appsecret': SEC['KIS_APP_SECRET']})
        KIS_TOKEN = TOKEN = r.json().get('access_token')
    if not KIS_TOKEN:
        raise RuntimeError('한투 토큰 발급 실패')

    etf = u[u['구분'] == 'ETF'][['번호', '정식 종목명', '시장', '거래소', '섹터/테마', '코드', 'yfinance 티커']].copy()
    have = set(etf['코드'])
    extra = [{'번호': f'참고-{t}', '정식 종목명': t, '시장': '미국', '거래소': '', '섹터/테마': s, '코드': t, 'yfinance 티커': t}
             for t, s in US_EXTRA.items() if t not in have]
    etf = pd.concat([etf, pd.DataFrame(extra)], ignore_index=True)

    snap, diag = [], {}
    for _, s in etf.iterrows():
        r = {'수집일': TODAY, '번호': s['번호'], '이름': s['정식 종목명'], '시장': s['시장'], '섹터/테마': s['섹터/테마'],
             '코드': s['코드'], '상장좌수': None, '종가': None, 'NAV': None, '순자산': None, '좌수출처': '', '순자산출처': ''}
        if s['시장'] == '한국':
            x = _kis('/uapi/domestic-stock/v1/quotations/inquire-price', 'FHKST01010100',
                     {'FID_COND_MRKT_DIV_CODE': 'J', 'FID_INPUT_ISCD': s['코드']})
            if x:
                r.update({'상장좌수': _f(x.get('lstn_stcn')), '종가': _f(x.get('stck_prpr')), '좌수출처': '한투'})
            e = _kis('/uapi/etfetn/v1/quotations/inquire-price', 'FHPST02400000',
                     {'fid_cond_mrkt_div_code': 'J', 'fid_input_iscd': s['코드']})
            if e:
                diag.setdefault('국내ETF', e)
                r['NAV'] = _f(e.get('nav'))
                tot = _f(e.get('etf_ntas_ttam'))            # 순자산총액(억원)
                if tot:
                    r.update({'순자산': tot * 1e8, '순자산출처': '한투'})
                if not r['상장좌수'] and _f(e.get('lstn_stcn')):
                    r.update({'상장좌수': _f(e.get('lstn_stcn')), '좌수출처': '한투 ETF'})
        else:
            first = {'NASDAQ': 'NAS', 'NYSE': 'NYS'}.get(s['거래소'], 'AMS')
            for ex in [first] + [e for e in ('AMS', 'NAS', 'NYS') if e != first]:
                x = _kis('/uapi/overseas-price/v1/quotations/price-detail', 'HHDFS76200200',
                         {'AUTH': '', 'EXCD': ex, 'SYMB': s['코드']})
                if x and _f(x.get('last')):
                    diag.setdefault('미국ETF', x)
                    r.update({'상장좌수': _f(x.get('shar')), '종가': _f(x.get('last')), '좌수출처': '한투' if _f(x.get('shar')) else ''})
                    break
            try:
                i = yf.Ticker(s['yfinance 티커']).info or {}
                r['NAV'] = i.get('navPrice')
                r['종가'] = r['종가'] or i.get('regularMarketPreviousClose')
                if i.get('totalAssets'):
                    r.update({'순자산': float(i['totalAssets']), '순자산출처': '야후'})
            except Exception as e:
                print('  야후 실패', s['코드'], e)
            time.sleep(0.4)
        snap.append(r)
    snap = pd.DataFrame(snap)
    if diag:
        with open(f'{DAY}/{TODAY}_진단_ETF응답.json', 'w', encoding='utf-8') as fp:
            json.dump(diag, fp, ensure_ascii=False, indent=1)

    # 누적 파일에 오늘 줄을 붙인다 (같은 날 다시 돌리면 오늘 줄만 바꿈)
    hist = pd.read_csv(FLOW_FILE, dtype={'수집일': str, '코드': str}) if os.path.exists(FLOW_FILE) else pd.DataFrame()
    if len(hist):
        hist = hist[hist['수집일'] != TODAY]
    # SPDR 펀드는 State Street 공식 이력(최근 1년)을 매일 통째로 받아 그 코드의 줄을 바꾼다(좌수 기준을 한 출처로 통일).
    # 못 받으면 한투·야후 오늘 값을 그대로 쓴다.
    back, back_fail = [], []
    for t in sorted(SPDR & set(snap['코드'])):
        try:
            h = _spdr_hist(t)
            if h is None or not len(h):
                raise ValueError('받지 못함')
            h = h.tail(260)
            meta = snap[snap['코드'] == t].iloc[0]
            back.append(pd.DataFrame({'수집일': h['날짜'].dt.strftime('%Y%m%d'), '번호': meta['번호'], '이름': meta['이름'],
                                      '시장': '미국', '섹터/테마': meta['섹터/테마'], '코드': t, '상장좌수': h['상장좌수'],
                                      '종가': None, 'NAV': h['NAV'], '순자산': h['상장좌수'] * h['NAV'],
                                      '좌수출처': 'SPDR 이력', '순자산출처': 'SPDR 이력'}))
        except Exception as e:
            back_fail.append(f'{t}({type(e).__name__})')
    done = {b['코드'].iloc[0] for b in back}
    if len(hist):
        hist = hist[~hist['코드'].isin(done)]
    snap_keep = snap[~snap['코드'].isin(done)]
    parts = [p for p in [hist] + back + [snap_keep] if len(p)]
    hist = pd.concat(parts, ignore_index=True).drop_duplicates(['수집일', '코드'], keep='last').sort_values(['코드', '수집일'])
    hist.to_csv(FLOW_FILE, index=False, encoding='utf-8-sig')

    # 자금유입 계산: 좌수 변화 × NAV(없으면 종가). 좌수가 없으면 순자산 변화 − 가격 변동분
    rows = []
    for code, g in hist.groupby('코드'):
        g = g.sort_values('수집일').reset_index(drop=True)
        px = g['NAV'].fillna(g['종가'])
        if g['상장좌수'].notna().sum() >= 2:
            sh = g['상장좌수'].ffill()
            daily, how = sh.diff() * px.ffill(), '좌수 변화 × NAV'
        else:
            aum = g['순자산']
            daily, how = aum - aum.shift() * (px / px.shift()), '순자산 변화 − 가격 변동'
        last = g.iloc[-1]
        unit = 1e8 if last['시장'] == '한국' else 1e6
        aum_now = last['순자산'] if pd.notna(last['순자산']) else (last['상장좌수'] * px.iloc[-1]
                                                                  if pd.notna(last['상장좌수']) and pd.notna(px.iloc[-1]) else None)
        n = len(g) - 1          # 비교 가능한 날 수
        s = lambda k: round(daily.iloc[-k:].sum() / unit, 1) if n >= k and daily.iloc[-k:].notna().any() else None
        sh_chg = (round((g['상장좌수'].iloc[-1] / g['상장좌수'].iloc[-21] - 1) * 100, 2)
                  if n >= 20 and pd.notna(g['상장좌수'].iloc[-21]) and pd.notna(g['상장좌수'].iloc[-1]) else None)
        rows.append({'번호': last['번호'], '이름': last['이름'], '시장': last['시장'], '섹터/테마': last['섹터/테마'], '코드': code,
                     '단위': '억원' if last['시장'] == '한국' else '백만달러',
                     '순자산': round(aum_now / unit, 1) if aum_now else None,
                     '유입_1일': s(1), '유입_5일': s(5), '유입_20일': s(20),
                     '유입_20일_순자산대비(%)': round(s(20) / (aum_now / unit) * 100, 2) if s(20) is not None and aum_now else None,
                     '좌수변화_20일(%)': sh_chg, '상장좌수': last['상장좌수'], '기록일수': len(g), '계산방식': how,
                     '좌수출처': last['좌수출처'], '순자산출처': last['순자산출처']})
    fl = pd.DataFrame(rows)
    fl['순위_20일'] = fl.groupby('시장')['유입_20일'].rank(ascending=False, method='min')
    fl['순위_5일'] = fl.groupby('시장')['유입_5일'].rank(ascending=False, method='min')
    fl = fl.sort_values(['시장', '유입_20일', '유입_5일'], ascending=[True, False, False], na_position='last')
    fl['계산시각(KST)'] = stamp()
    fl.to_csv(f'{DAY}/{TODAY}_ETF자금.csv', index=False, encoding='utf-8-sig')

    def top(m, k):
        x = fl[(fl['시장'] == m) & fl[k].notna()].sort_values(k, ascending=False)
        if not len(x):
            return '기록 쌓는 중'
        unit = x['단위'].iloc[0]
        fmt = lambda d: ', '.join(f"{r['이름']} {r[k]:+,.0f}" for _, r in d.iterrows())
        return f'유입 {fmt(x.head(3))} / 유출 {fmt(x.tail(3).iloc[::-1])} ({unit})'
    ok = lambda m: f"{int((snap['시장'] == m).sum())}개 중 좌수 {int(snap.loc[snap['시장'] == m, '상장좌수'].notna().sum())}·순자산 {int(snap.loc[snap['시장'] == m, '순자산'].notna().sum())}"
    log(f'[9 ETF자금] 국내 {ok("한국")} | 미국 {ok("미국")} | SPDR 공식 이력 {len(back)}개'
        + (f' (실패 {", ".join(back_fail)})' if back_fail else '')
        + f' | 국내 5일 {top("한국", "유입_5일")} | 미국 5일 {top("미국", "유입_5일")}')
except Exception as e:
    traceback.print_exc()
    log(f'[9 ETF자금] 실패: {type(e).__name__} {e}')
