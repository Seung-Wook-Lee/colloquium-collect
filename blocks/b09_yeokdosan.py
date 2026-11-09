# ======================================================================
# [블록 9-역도산] 미스터 역도산 — 섹터 ETF(해외 SPDR 11개 · 국내 13개)와 상위 10종목 주봉(한투) 쌓기 + 지금판 + 수급
#   하는 일  : 한투 주봉(수정주가)을 종목마다 받아 최근 주를 창고에 덮어 넣는다(진행 중인 주는 매일 갱신).
#              국내 ETF 상위 10은 한투 ETF 구성종목에서 매일 새로 받는다.
#              해외·국내 같은 계산(60·20주선 첫 터치, 하향돌파 뒤 상향돌파, RSI, 주봉 MACD 기울기, 월봉 5개월선 이격)으로 지금판을 만들고,
#              ETF 줄에 ETF 자금(5·20일), 국내 종목 줄에 외국인 5·20일 순매수를 붙인다.
#   회의(11/9 의장): 국장(밤사이 뉴스) 다음 미스터 역도산. 해외 → 국내 두 덩어리, 각각
#              역도산은 '지도'만: ETF 자금 5일 순서, 60·20주선 위치와 첫 터치. 터치가 나오면 상위 10 이름만 닉스 팀에 넘긴다.
#              깊은 차트 분석·바닥 전환 판단(주봉 MACD 기울기·일봉 골든크로스·월봉 5개월선)은 닉스 팀 클로토 몫(_섹터.csv).
#   소스     : 한투(블록 2 토큰), yeokdosan/(목록·CFG), 오늘 폴더 _ETF자금.csv(블록 9-ETF자금)·_국내수급.csv(블록 9-국내수급)
#   만드는 것: 00_누적/00_역도산_주봉.csv(창고), 00_누적/00_역도산_국내구성.csv(국내 ETF 상위 10)
#              YYYYMMDD/YYYYMMDD_역도산.csv(지금판, 시장 칸으로 해외·국내 구분), YYYYMMDD_역도산.txt(회의 원고 뼈대)
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
import sys as _sys
_sys.path.insert(0, 'yeokdosan')                 # run.py는 저장소 맨 위에서 돈다
import yeokdosan as ydo


def _v(x, f='{:+,.0f}'):
    return '-' if x is None or pd.isna(x) else f.format(x)


def _ydo_report(T, cut, title, unit):
    """지도만(11/9 의장): ETF 자금 5일 순서 + 60·20주선 위치·첫 터치. 터치면 상위 10 이름만 닉스 팀에 넘긴다."""
    out = [f'[{title}]']
    out.append(('60주선 첫 터치: ' + ', '.join(cut) + ' → 상위 10 이름을 닉스 팀에 넘김') if cut else '60주선 첫 터치 없음 → 종목 얘기 없음')
    E = T[T.구분 == 'ETF'].copy()
    if '자금5일' not in E: E['자금5일'] = np.nan
    E = E.sort_values('자금5일', ascending=False, na_position='last')
    out.append(f'-- ETF 지도 (자금 5일 많은 순, {unit}): 자금 5일·20일 | 60주 이격 | 20주 이격 | 첫 터치 --')
    for _, r in E.iterrows():
        t = ','.join(n for n in ('60', '20') if r.get(f'{n}주 첫터치') == '예')
        out.append(f"{r['ETF']} {r.get('ETF이름', '') or ''}: {_v(r.get('자금5일'))} · {_v(r.get('자금20일'))} | "
                   f"{_v(r.get('60주 이격'), '{:.1f}')} | {_v(r.get('20주 이격'), '{:.1f}')} | {(t + '주선') if t else '-'}")
    for e in cut:
        x = T[(T.ETF == e) & (T.구분 == '종목')].sort_values('순위')
        out.append(f'-- 닉스 팀에 넘김: {e} 상위 10 -- ' + ', '.join(f"{r['티커']} {r.get('이름', '') or ''}".strip() for _, r in x.iterrows()))
    return out


try:
    if not (SEC.get('KIS_APP_KEY') and SEC.get('KIS_APP_SECRET')):
        raise RuntimeError('한투 키 없음')
    if 'TOKEN' not in globals() or not TOKEN:
        TOKEN = kis_token()
    K_, S_ = SEC['KIS_APP_KEY'], SEC['KIS_APP_SECRET']
    path, cpath = f'{KEEP}/00_역도산_주봉.csv', f'{KEEP}/00_역도산_국내구성.csv'
    store = pd.read_csv(path, parse_dates=['날짜'], dtype={'티커': str}) if os.path.exists(path) else pd.DataFrame(columns=ydo.COLS)
    hus = pd.read_csv('yeokdosan/holdings_top10.csv'); hus['시장'] = '해외'
    ekr = pd.read_csv('yeokdosan/etfs_kr.csv', dtype={'ETF': str})
    # 국내 ETF 구성 상위 10 (매일 새로, 실패하면 어제 것)
    old = pd.read_csv(cpath, dtype={'ETF': str, '티커': str}) if os.path.exists(cpath) else pd.DataFrame(columns=['ETF', '순위', '티커', '이름', '비중'])
    comp, cbad = [], []
    for e in ekr.ETF:
        try:
            c = ydo.kr_components(TOKEN, K_, S_, e)
            if not c: raise RuntimeError('빈 응답')
            comp += [dict(ETF=e, 순위=a, 티커=b, 이름=n, 비중=w) for a, b, n, w in c]
        except Exception as x:
            px_ = ekr.set_index('ETF').미국대리.get(e)
            try:
                if not (isinstance(px_, str) and px_): raise
                comp += [dict(ETF=e, 순위=a, 티커=b, 이름=n, 비중=w) for a, b, n, w in ydo.us_proxy_components(px_)]
            except Exception:
                cbad.append(e); comp += old[old.ETF == e].to_dict('records')
    hkr = pd.DataFrame(comp); hkr['시장'] = '국내'
    if len(hkr): hkr.to_csv(cpath, index=False, encoding='utf-8-sig')
    # 주봉 갱신
    new, bad = [], []
    have = set(store.티커.unique())
    for tk in ['SPY'] + list(dict.fromkeys(hus.ETF)) + list(hus.티커):
        ex, nm, rows = ydo.find_exchange(TOKEN, K_, S_, tk)
        if rows: new.append(ydo.to_frame(tk, rows))
        else: bad.append(tk)
    kus = [t for t in (dict.fromkeys(hkr.티커) if len(hkr) else []) if not (len(str(t)) == 6 and str(t)[:1].isdigit())]
    for tk in kus:                                   # 미국 지수 추종 국내 ETF의 미국 종목(대리 ETF 보유)
        if tk in set(hus.티커): continue
        ex, nm, rows = ydo.find_exchange(TOKEN, K_, S_, tk)
        if rows: new.append(ydo.to_frame(tk, rows))
        else: bad.append(tk)
    for tk in ['069500'] + list(ekr.ETF) + [t for t in (dict.fromkeys(hkr.티커) if len(hkr) else []) if t not in kus]:
        try:
            f = ydo.kr_to_frame(tk, ydo.kr_week_page(TOKEN, K_, S_, tk)) if tk in have else ydo.kr_week_all(TOKEN, K_, S_, tk)
            if f is not None and len(f): new.append(f)
            else: bad.append(tk)
        except Exception:
            bad.append(tk)
    store = ydo.merge(store, pd.concat(new) if new else None)
    store.to_csv(path, index=False, encoding='utf-8-sig')
    # 지금판 + 수급
    names = dict(zip(ekr.ETF, ekr.이름))
    Tus, cus = ydo.now_table(store, hus); Tus['시장'] = '해외'; Tus['ETF이름'] = Tus.ETF.map(globals().get('US_EXTRA', {})).fillna('')
    Tkr, ckr = ydo.now_table(store, hkr) if len(hkr) else (pd.DataFrame(), [])
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
    T.to_csv(f'{DAY}/{TODAY}_역도산.csv', index=False, encoding='utf-8-sig')
    lines = [f'미스터 역도산 {TODAY} (한투 주봉, 마지막 주 {store.날짜.max():%Y-%m-%d}) — 회의 순서: 국장 다음, 해외 → 국내']
    lines += _ydo_report(Tus, cus, '해외 섹터 ETF', '백만달러')
    lines += [''] + (_ydo_report(Tkr, ckr, '국내 섹터 ETF', '억원') if len(Tkr) else ['[국내 섹터 ETF] 구성종목을 받지 못함'])
    open(f'{DAY}/{TODAY}_역도산.txt', 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    log(f'[9 역도산] 창고 {store.티커.nunique()}종목·{len(store)}줄 | 해외 끼어들기 {",".join(cus) or "없음"} | 국내 {",".join(ckr) or "없음"} | '
        f'국내 구성 실패 {",".join(cbad) or "없음"} | 주봉 실패 {len(bad)}: {", ".join(bad[:15])}')
except Exception as e:
    traceback.print_exc()
    log(f'[9 역도산] 실패: {type(e).__name__} {e}')
