# ======================================================================
# [블록 9-시타델] 섹터 ETF 주봉 창고와 섹터 지도(미스 시타델 수급 자료)
#   하는 일  : 섹터 ETF(해외 SPDR 11개 · 국내 13개)와 각 ETF 상위 10종목의 한투 주봉(수정주가)을 창고에 쌓고,
#              60·20주선 이격·첫 터치·하향돌파 뒤 상향돌파·RSI·주봉 MACD 기울기·월봉 5개월선 이격으로 섹터 지도를 만든다.
#              ETF 줄에 ETF 자금(5·20일), 국내 종목 줄에 외국인 5일 순매수를 붙인다.
#   소스     : 한투(저녁 8시 한국 수집, 토큰 하나), citadel/(목록·CFG), 오늘 폴더 _ETF자금.csv·_국내수급.csv
#   만드는 것: 10년치 저장본 칸 1_data/가격10년_섹터주봉.csv.gz(창고, 11/26 의장: 옛 00_누적/00_시타델_주봉.csv), 00_누적/00_시타델_국내구성.csv(국내 ETF 상위 10)
#              YYYYMMDD/YYYYMMDD_시타델.csv(섹터 지도, 시장 칸으로 해외·국내 구분)
#   쓰는 곳  : B18 업종 ETF 60주선 이격·업종 자금(엔진), 미스 시타델 수급 해석, 스트림릿 섹터 지도
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
import sys as _sys
_sys.path.insert(0, 'citadel')                    # run.py는 collect/ 에서 돈다
import citadel as ct


def _v(x, f='{:+,.0f}'):
    return '-' if x is None or pd.isna(x) else f.format(x)


try:
    if not (SEC.get('KIS_APP_KEY') and SEC.get('KIS_APP_SECRET')):
        raise RuntimeError('한투 키 없음')
    if 'TOKEN' not in globals() or not TOKEN:
        TOKEN = kis_token()
    K_, S_ = SEC['KIS_APP_KEY'], SEC['KIS_APP_SECRET']
    # 11/26 의장 "10년치 저장본 밖에 따로 있는 과거 자료들을 저장본에 합치시오": 주봉 창고는 저장본 칸(가격10년_섹터주봉)
    _sys.path.insert(0, os.path.abspath('data'))
    import px_store as PS
    _PXD = f'{DATA}/1_data_가격'; os.makedirs(_PXD, exist_ok=True)
    if not IN_COLAB:
        PS.fetch(gdrive, '섹터주봉', _PXD, log)   # 칸이 아직 없으면 옛 00_누적/00_시타델_주봉.csv를 칸으로 옮기고 휴지통
    path, cpath = f'{_PXD}/{PS.name("섹터주봉")}', f'{KEEP}/00_시타델_국내구성.csv'
    store = pd.read_csv(path, parse_dates=['날짜'], dtype={'티커': str}) if os.path.exists(path) else pd.DataFrame(columns=ct.COLS)
    hus = pd.read_csv('citadel/holdings_top10.csv'); hus['시장'] = '해외'
    ekr = pd.read_csv('citadel/etfs_kr.csv', dtype={'ETF': str})
    # 국내 ETF 구성 상위 10 (매일 새로, 실패하면 어제 것)
    old = pd.read_csv(cpath, dtype={'ETF': str, '티커': str}) if os.path.exists(cpath) else pd.DataFrame(columns=['ETF', '순위', '티커', '이름', '비중'])
    comp, cbad = [], []
    for e in ekr.ETF:
        try:
            c = ct.kr_components(TOKEN, K_, S_, e)
            if not c: raise RuntimeError('빈 응답')
            comp += [dict(ETF=e, 순위=a, 티커=b, 이름=n, 비중=w) for a, b, n, w in c]
        except Exception as x:
            px_ = ekr.set_index('ETF').미국대리.get(e)
            try:
                if not (isinstance(px_, str) and px_): raise
                comp += [dict(ETF=e, 순위=a, 티커=b, 이름=n, 비중=w) for a, b, n, w in ct.us_proxy_components(px_)]
            except Exception:
                cbad.append(e); comp += old[old.ETF == e].to_dict('records')
    hkr = pd.DataFrame(comp); hkr['시장'] = '국내'
    if len(hkr): hkr.to_csv(cpath, index=False, encoding='utf-8-sig')
    # 주봉 갱신
    new, bad = [], []
    have = set(store.티커.unique())
    for tk in ['SPY'] + list(dict.fromkeys(hus.ETF)) + list(hus.티커):
        ex, nm, rows = ct.find_exchange(TOKEN, K_, S_, tk)
        if rows: new.append(ct.to_frame(tk, rows))
        else: bad.append(tk)
    kus = [t for t in (dict.fromkeys(hkr.티커) if len(hkr) else []) if not (len(str(t)) == 6 and str(t)[:1].isdigit())]
    for tk in kus:                                   # 미국 지수 추종 국내 ETF의 미국 종목(대리 ETF 보유)
        if tk in set(hus.티커): continue
        ex, nm, rows = ct.find_exchange(TOKEN, K_, S_, tk)
        if rows: new.append(ct.to_frame(tk, rows))
        else: bad.append(tk)
    for tk in ['069500'] + list(ekr.ETF) + [t for t in (dict.fromkeys(hkr.티커) if len(hkr) else []) if t not in kus]:
        try:
            f = ct.kr_to_frame(tk, ct.kr_week_page(TOKEN, K_, S_, tk)) if tk in have else ct.kr_week_all(TOKEN, K_, S_, tk)
            if f is not None and len(f): new.append(f)
            else: bad.append(tk)
        except Exception:
            bad.append(tk)
    store = ct.merge(store, pd.concat(new) if new else None)
    store.to_csv(path, index=False, encoding='utf-8-sig', compression='gzip')
    if not IN_COLAB:
        gdrive.put(f'{D_DATA}/1_data/{PS.name("섹터주봉")}', open(path, 'rb').read())
    # 지금판 + 수급
    names = dict(zip(ekr.ETF, ekr.이름))
    Tus, cus = ct.now_table(store, hus); Tus['시장'] = '해외'; Tus['ETF이름'] = Tus.ETF.map(globals().get('US_EXTRA', {})).fillna('')
    Tkr, ckr = ct.now_table(store, hkr) if len(hkr) else (pd.DataFrame(), [])
    if len(Tkr): Tkr['시장'] = '국내'; Tkr['ETF이름'] = Tkr.ETF.map(names).fillna('')
    fp, kp = f'{DAY}/{TODAY}_ETF자금.csv', f'{DAY}/{TODAY}_국내수급.csv'
    if os.path.exists(fp):
        fl = pd.read_csv(fp, dtype={'코드': str}).set_index('코드')
        for T in (Tus, Tkr):
            if len(T):
                T['자금5일'] = [fl['유입_5일'].get(e) if r == 'ETF' else None for e, r in zip(T.ETF, T.구분)]
                T['자금20일'] = [fl['유입_20일'].get(e) if r == 'ETF' else None for e, r in zip(T.ETF, T.구분)]
    if os.path.exists(kp) and len(Tkr):
        kf = pd.read_csv(kp, dtype={'코드': str}).set_index('코드')
        c5 = next((c for c in kf.columns if c.startswith('외국인 5일')), None)
        if c5: Tkr['외국인5일'] = Tkr.티커.map(kf[c5])
    T = pd.concat([Tus, Tkr], ignore_index=True)
    T.to_csv(f'{DAY}/{TODAY}_시타델.csv', index=False, encoding='utf-8-sig')
    log(f'[9 시타델] 창고 {store.티커.nunique()}종목·{len(store)}줄 | 해외 60주 첫 터치 {",".join(cus) or "없음"} | 국내 {",".join(ckr) or "없음"} | '
        f'국내 구성 실패 {",".join(cbad) or "없음"} | 주봉 실패 {len(bad)}: {", ".join(bad[:15])}')
except Exception as e:
    traceback.print_exc()
    log(f'[9 시타델] 실패: {type(e).__name__} {e}')
