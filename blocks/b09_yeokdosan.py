# ======================================================================
# [블록 9-역도산] 미스터 역도산 — 미국 SPDR 섹터 ETF 11개와 상위 10종목 주봉(한투) 쌓기 + 지금판
#   하는 일  : 한투 해외 주봉(수정주가)을 종목마다 한 번씩 받아 최근 주를 창고에 덮어 넣는다(진행 중인 주는 매일 갱신).
#              창고로 지금판(ETF·종목별 20·60주 이격, 첫 터치, 하향돌파 뒤 상향돌파, RSI, MACD)을 만든다.
#              ETF 60주선 첫 터치가 있으면 미스터 역도산이 회의 맨 먼저 끼어든다(11/7 의장).
#   소스     : 한투 HHDFS76240000(블록 2 토큰), 목록·기준 yeokdosan/ (holdings_top10.csv, yeokdosan.py CFG)
#   만드는 것: 수집데이터/00_누적/00_역도산_주봉.csv (창고, 2003~ 과거분은 research/yeokdosan_backfill.py가 한 번 채움)
#              수집데이터/YYYYMMDD/YYYYMMDD_역도산.csv (지금판), YYYYMMDD_역도산.txt (끼어들기 한 줄 + 터치 목록)
#   쓰는 위원: 미스터 역도산. 백테스트(Team_Q contrarian/)도 이 창고를 그대로 읽는다(야후 안 씀).
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
import sys as _sys
_sys.path.insert(0, 'yeokdosan')                 # run.py는 저장소 맨 위에서 돈다
import yeokdosan as ydo

try:
    if not (SEC.get('KIS_APP_KEY') and SEC.get('KIS_APP_SECRET')):
        raise RuntimeError('한투 키 없음')
    if 'TOKEN' not in globals() or not TOKEN:
        TOKEN = kis_token()
    hold = pd.read_csv('yeokdosan/holdings_top10.csv')
    syms = ['SPY'] + list(dict.fromkeys(hold.ETF)) + list(hold.티커)
    path = f'{KEEP}/00_역도산_주봉.csv'
    store = pd.read_csv(path, parse_dates=['날짜']) if os.path.exists(path) else pd.DataFrame(columns=ydo.COLS)
    new, bad = [], []
    for tk in syms:
        ex, nm, rows = ydo.find_exchange(TOKEN, SEC['KIS_APP_KEY'], SEC['KIS_APP_SECRET'], tk)
        if rows: new.append(ydo.to_frame(tk, rows))
        else: bad.append(tk)
    store = ydo.merge(store, pd.concat(new) if new else None)
    store.to_csv(path, index=False, encoding='utf-8-sig')
    T, cut = ydo.now_table(store, hold)
    T.to_csv(f'{DAY}/{TODAY}_역도산.csv', index=False, encoding='utf-8-sig')
    lines = [f'미스터 역도산 {TODAY} (한투 주봉, 마지막 주 {store.날짜.max():%Y-%m-%d})']
    lines.append(('끼어들기: ' + ', '.join(f'{e} 60주선 첫 터치' for e in cut)) if cut else '끼어들기 없음(ETF 60주선 첫 터치 없음)')
    for col, name in [('60주 첫터치', '60주선 첫 터치'), ('60주 상향돌파', '60주선 하향돌파 뒤 상향돌파'), ('20주 첫터치', '20주선 첫 터치')]:
        x = T[T.get(col) == '예'] if col in T else T.iloc[0:0]
        lines.append(f'{name}: ' + (', '.join(f'{r.티커}({r.ETF})' for r in x.itertuples()) or '없음'))
    open(f'{DAY}/{TODAY}_역도산.txt', 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    log(f'[9 역도산] 주봉 {len(syms) - len(bad)}/{len(syms)}종목 | 창고 {store.티커.nunique()}종목·{len(store)}줄 | '
        f'{lines[1]} | 실패: {", ".join(bad) or "없음"}')
except Exception as e:
    traceback.print_exc()
    log(f'[9 역도산] 실패: {type(e).__name__} {e}')
