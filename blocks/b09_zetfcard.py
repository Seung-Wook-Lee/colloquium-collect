# ======================================================================
# [블록 9-ETF카드] 미스 ETF — 콜로키움 100 안의 ETF 35개(+의장 계좌 ETF) 바구니 카드와 반도체 ETF 겹침 표
#   언제     : 매주 일요일 07시 실행분에서만 만든다(11/15 의장 "매주 일요일 갱신"). 손으로 돌리려면 python run.py etfcard
#   하는 일  : 국내 상장은 한투 ETF 구성종목·ETF 현재가(NAV·괴리율·추적오차), 해외 종목 ETF는 한투가 비면 같은 지수의 미국 ETF로 대신,
#              미국 상장은 야후 funds_data(상위 10·섹터·보수). 상위 3 쏠림, 환헤지, 과세 문구를 붙여 카드 한 장씩 쓴다.
#              반도체 ETF 8개(국내 6·미국 2)는 상위 10끼리 겹친 비중(작은 쪽 합) 표를 만든다.
#   소스     : 한투(블록 2 토큰), 야후, misetf/meta.csv(번호·기초자산·미국대리·반도체 겹침 대상), 유니버스(코드)
#   만드는 것: YYYYMMDD/YYYYMMDD_ETF카드.txt(카드 전부, '=====' 줄로 나눔), YYYYMMDD_ETF구성.csv, YYYYMMDD_ETF겹침_반도체.csv
#              작업 창이 카드를 위원공부/미스ETF/ETF카드_<번호>_<이름>.txt로 나눠 넣고 위원 검색 색인을 다시 만든다.
#   주의     : 국내 ETF가 담은 해외 종목은 한글 이름으로 올 수 있어, 미국 ETF와 겹침 비교가 덜 잡힐 수 있다(첫 실행 뒤 확인).
#   실패하면 : ETF 하나가 실패해도 '자료 없음' 카드로 두고 계속, 블록 전체 실패는 점검 파일에 남김
# ======================================================================
import sys as _sys
_sys.path.insert(0, 'misetf')
import etfcard as ec

_names = globals().get('ONLY_NAMES', [])
if NOW.weekday() != 6 and 'etfcard' not in _names:
    log('[ETF카드] 일요일이 아니라 건너뜀(손으로: python run.py etfcard)')
else:
    try:
        meta = pd.read_csv('misetf/meta.csv', dtype=str).fillna('')
        code = dict(zip(u['번호'], u['코드']))
        meta['코드'] = [c or code.get(n, '') for n, c in zip(meta['번호'], meta['코드'])]
        kis_ok = bool(SEC.get('KIS_APP_KEY') and SEC.get('KIS_APP_SECRET'))
        if kis_ok and ('TOKEN' not in globals() or not TOKEN):
            TOKEN = kis_token()
        rows, cards, bad = [], [], []
        for _, r in meta.iterrows():
            hold, q, src = [], {}, ''
            try:
                if r['상장'] == '미국':
                    hold, q = ec.us_holdings(r['코드'])
                    src = f'야후 funds_data {r["코드"]}'
                elif r['기초자산'] in ('금',):
                    src = '구성종목 없음(금 현물)'
                else:
                    if not r['코드']: raise RuntimeError('유니버스에 코드 없음')
                    if not kis_ok and not r['미국대리']: raise RuntimeError('한투 키 없음')
                    try:
                        q = ec.kr_quote(TOKEN, SEC['KIS_APP_KEY'], SEC['KIS_APP_SECRET'], r['코드']) if kis_ok else {}
                    except Exception:
                        q = {}
                    try:
                        if not kis_ok: raise RuntimeError('한투 키 없음')
                        hold, n = ec.kr_holdings(TOKEN, SEC['KIS_APP_KEY'], SEC['KIS_APP_SECRET'], r['코드'])
                        src = f'한투 ETF 구성종목 {r["코드"]} (전체 {n}줄)'
                    except Exception as x:
                        if not r['미국대리']: raise
                        hold = []
                    if not hold and r['미국대리']:
                        hold, q2 = ec.us_holdings(r['미국대리'])
                        q.setdefault('설명', q2.get('설명')); q['섹터'] = q2.get('섹터')
                        src = f'한투 구성 비어 같은 지수 미국 ETF {r["미국대리"]}(야후)로 대신'
            except Exception as x:
                bad.append(f'{r["번호"]}({str(x)[:40]})')
                src = src or f'실패: {str(x)[:60]}'
            cards.append(ec.card(r, hold, q, src, TODAY))
            rows += [dict(번호=r['번호'], ETF=r['이름'], 순위=i, 코드=c, 이름=n, 비중=w, 열쇠=ec.okey(c, n))
                     for i, (c, n, w) in enumerate(hold, 1)]
        H = pd.DataFrame(rows)
        open(f'{DAY}/{TODAY}_ETF카드.txt', 'w', encoding='utf-8').write(('\n' + '=' * 60 + '\n').join(cards))
        if len(H):
            H.to_csv(f'{DAY}/{TODAY}_ETF구성.csv', index=False, encoding='utf-8-sig')
            semi = meta.loc[meta['반도체겹침표'] == 'Y', '번호'].tolist()
            M = ec.overlap(H, semi)
            M.index = [f'{n} {meta.set_index("번호").이름[n]}' for n in M.index]
            M.to_csv(f'{DAY}/{TODAY}_ETF겹침_반도체.csv', encoding='utf-8-sig')
        log(f'[ETF카드] 카드 {len(cards)}장, 구성 {len(H)}줄' + (f', 실패 {len(bad)}: {" ".join(bad)}' if bad else ''))
    except Exception as e:
        log(f'[ETF카드] 실패: {type(e).__name__} {e}')
