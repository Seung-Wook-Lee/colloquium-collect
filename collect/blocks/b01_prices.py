# ======================================================================
# [블록 1] 야후 시세 — 스튜디오 톰앤수 100 일봉
#   하는 일  : 100종목 일봉(시가·고가·저가·종가·수정종가·거래량)을 받는다.
#              처음 실행은 5년치, 이후에는 최근 1개월만 받아 누적 파일에 이어 붙인다.
#              배당·분할로 수정주가가 바뀐 종목과 새로 편입된 종목은 5년치를 다시 받는다.
#   소스     : yfinance (키 없음, 비공식이라 묶음 10종목·간격 2초·재시도 3회)
#   만드는 것: 수집데이터/00_누적/00_가격이력.csv (누적, 날짜 없는 파일)
#              수집데이터/YYYYMMDD/YYYYMMDD_시세.csv (오늘 종가·등락률·거래량)
#   쓰는 위원: 닉스 3여신(주봉·월봉은 이 일봉으로 계산), 포보스(지수)
#   고칠 곳  : 막힘이 잦으면 PAUSE를 늘리고 CHUNK를 줄인다
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
HIST = f'{KEEP}/00_가격이력.csv'
COLS = {'Open': '시가', 'High': '고가', 'Low': '저가', 'Close': '종가', 'Adj Close': '수정종가', 'Volume': '거래량'}
CHUNK, PAUSE, RETRY = 10, 2.0, 3

def _yf(tickers, period):
    for n in range(RETRY + 1):
        try:
            d = yf.download(tickers, period=period, interval='1d', auto_adjust=False,
                            group_by='ticker', threads=False, progress=False)
            rows = []
            for t in tickers:
                if d is None or d.empty or t not in d.columns.get_level_values(0):
                    continue
                x = d[t].dropna(subset=['Close'])
                if not x.empty:
                    x = x[list(COLS)].rename(columns=COLS)
                    x.insert(0, '티커', t)
                    rows.append(x)
            if not rows:
                raise ValueError('받은 종목 없음')
            out = pd.concat(rows).reset_index().rename(columns={'Date': '날짜'})
            out['날짜'] = pd.to_datetime(out['날짜']).dt.tz_localize(None).dt.normalize()
            return out
        except Exception as e:
            if n == RETRY:
                print(f'  실패 {tickers[:3]}: {e}')
                return pd.DataFrame()
            time.sleep(5 * 3 ** n)

def yf_fetch(tickers, period):
    parts = []
    for i in range(0, len(tickers), CHUNK):
        parts.append(_yf(tickers[i:i + CHUNK], period))
        time.sleep(PAUSE)
    got = pd.concat([p for p in parts if not p.empty] or [pd.DataFrame(columns=['티커'])])
    for t in [t for t in tickers if t not in set(got['티커'])]:   # 빠진 종목은 한 종목씩 한 번 더
        time.sleep(PAUSE)
        one = _yf([t], period)
        if not one.empty:
            got = pd.concat([got, one])
    return got

try:
    first_run = not os.path.exists(HIST)
    if first_run:
        hist, refreshed = yf_fetch(TICKERS, '5y'), ['전체(첫 실행)']
    else:
        hist = pd.read_csv(HIST, parse_dates=['날짜'], dtype={'티커': str})
        new = yf_fetch(TICKERS, '1mo')
        # 배당·분할로 수정주가가 바뀐 종목과 새 편입 종목은 5년치를 다시 받는다
        m = new.merge(hist[['날짜', '티커', '수정종가']], on=['날짜', '티커'], suffixes=('', '_old'))
        changed = set(m.loc[(m['수정종가'] / m['수정종가_old'] - 1).abs() > 0.003, '티커'])
        refreshed = sorted(changed | (set(TICKERS) - set(hist['티커'])))
        if refreshed:
            full = yf_fetch(refreshed, '5y')
            hist = pd.concat([hist[~hist['티커'].isin(full['티커'].unique())], full])
        hist = pd.concat([hist, new])
    hist = (hist[hist['티커'].isin(TICKERS)].drop_duplicates(['날짜', '티커'], keep='last')
            .sort_values(['티커', '날짜']))
    hist.to_csv(HIST, index=False, encoding='utf-8-sig')

    last2 = hist.groupby('티커').tail(2)
    snap = last2.groupby('티커').agg(기준일=('날짜', 'last'), 전일종가=('종가', 'first'),
                                    종가=('종가', 'last'), 거래량=('거래량', 'last')).reset_index()
    snap['등락률(%)'] = (snap['종가'] / snap['전일종가'] - 1).mul(100).round(2)
    snap['기준일'] = snap['기준일'].dt.date
    snap = u[['번호', '정식 종목명', '시장', '구분', '보유/관심', 'yfinance 티커']].merge(
        snap.rename(columns={'티커': 'yfinance 티커'}), on='yfinance 티커', how='left')
    snap = snap.drop(columns='전일종가')
    snap['수집시각(KST)'] = NOW.strftime('%Y-%m-%d %H:%M')
    snap.to_csv(f'{DAY}/{TODAY}_시세.csv', index=False, encoding='utf-8-sig')

    miss = snap.loc[snap['종가'].isna(), '정식 종목명'].tolist()
    log(f'[1 야후 시세] {snap["종가"].notna().sum()}/{len(snap)}종목 | 기준일 ' +
        ', '.join(f'{k} {v}' for k, v in snap.groupby('시장')['기준일'].max().items()) +
        f' | 빠짐: {", ".join(miss) or "없음"} | 5년치 재수신: {", ".join(refreshed) or "없음"}')
except Exception as e:
    traceback.print_exc()
    log(f'[1 야후 시세] 실패: {type(e).__name__} {e}')
