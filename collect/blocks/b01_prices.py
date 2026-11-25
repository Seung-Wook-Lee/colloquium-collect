# ======================================================================
# [블록 1] 시세 — 유니버스 일봉(11/25 의장: 저장본 하나에 새 거래일만)
#   하는 일  : 드라이브 1_data/가격10년_*(저장본)에 새 거래일만 덧붙이고(px_store.update), 그 저장본에서 5년치를 잘라
#              00_가격이력.csv를 만든다. 5년치·1달치를 따로 다시 받던 것은 지움. 새 종목만 그 종목 과거치를 받는다.
#   소스     : 드라이브 저장본. 새 거래일은 미국 야후, 한국 한투(07시엔 한국 새 장이 없어 한투 접속 없음)
#   만드는 것: 수집데이터/00_누적/00_가격이력.csv (누적, 날짜 없는 파일)
#              수집데이터/YYYYMMDD/YYYYMMDD_시세.csv (오늘 종가·등락률·거래량)
#   쓰는 위원: 닉스 3여신(주봉·월봉은 이 일봉으로 계산), 포보스(지수)
#   고칠 곳  : 막힘이 잦으면 PAUSE를 늘리고 CHUNK를 줄인다
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
HIST = f'{KEEP}/00_가격이력.csv'
COLS = {'Open': '시가', 'High': '고가', 'Low': '저가', 'Close': '종가', 'Adj Close': '수정종가', 'Volume': '거래량'}

try:
    # 11/25 의장 "블록과 회의프로그램 모두 저장된 것을 쓰도록, 하루 2번 업데이트하면 블록은 그걸 가지고 계산":
    #   야후에서 5년치·1달치를 따로 받던 것을 지움. 가격 저장본은 드라이브 1_data/가격10년_* 하나(px_store.py).
    #   07시엔 미국 전날 장만 새로 있어 미국만 덧붙이고(한투 접속 없음), 저녁 미장전 회의 준비 코드가 한국 오늘 장을 덧붙인다.
    #   00_가격이력.csv(닉스·섹터·데스크 블록이 읽는 긴 표)는 이 저장본에서 잘라 만든다.
    import sys as _s
    _s.path.insert(0, os.path.abspath('data'))   # collect/run.py가 collect 폴더에서 돎 → collect/data(px_store·kis)
    import px_store as PS
    PXD = f'{DATA}/1_data_가격'
    os.makedirs(PXD, exist_ok=True)
    if not IN_COLAB:
        for k in PS.F:
            b_ = gdrive.get(f'{D_DATA}/1_data/{PS.name(k)}')
            if b_:
                open(f'{PXD}/{PS.name(k)}', 'wb').write(b_)
    B0 = PS.load(PXD)
    _msg = []
    B = PS.update(B0, u, NOW.replace(tzinfo=None), log=_msg.append)
    B, _drop = PS.keep(B, u['yfinance 티커'].dropna())   # 11/25 의장: 유니버스에 없는 종목 기록은 지움
    if _drop:
        _msg.append(f'유니버스에 없는 종목 {len(_drop)}개 지움')
    if not IN_COLAB and B is not B0:
        for nm in PS.save(B, PXD):
            gdrive.put(f'{D_DATA}/1_data/{nm}', open(f'{PXD}/{nm}', 'rb').read())
        _msg.append('드라이브 1_data/가격10년 저장(새 날짜 덧붙임)')
    cut = B['Close'].index.max() - pd.Timedelta(days=5 * 366)
    long = []
    for k, col in (('Open', '시가'), ('High', '고가'), ('Low', '저가'), ('Close', '종가'), ('Volume', '거래량')):
        d = B[k][[t for t in TICKERS if t in B[k].columns]]
        d = d[d.index >= cut].stack().rename(col)
        long.append(d)
    hist = pd.concat(long, axis=1).reset_index()
    hist.columns = ['날짜', '티커'] + list(hist.columns[2:])
    hist['수정종가'] = hist['종가']
    hist = hist[['날짜', '티커', '시가', '고가', '저가', '종가', '수정종가', '거래량']].dropna(subset=['종가']).sort_values(['티커', '날짜'])
    hist.to_csv(HIST, index=False, encoding='utf-8-sig')
    refreshed = _msg
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
        f' | 빠짐: {", ".join(miss) or "없음"} | 저장본: {" / ".join(refreshed) or "없음"}')
except Exception as e:
    traceback.print_exc()
    log(f'[1 야후 시세] 실패: {type(e).__name__} {e}')
