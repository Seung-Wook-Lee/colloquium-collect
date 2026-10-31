# ======================================================================
# [블록 10] 오늘 브리핑 — 그날 파일을 모아 한 장짜리 텍스트로 만든다
#   하는 일  : 오늘 날짜 폴더의 CSV를 읽어 브리핑 txt를 만든다(2026-10-28 의장: 문서는 txt, 보는 화면은 스트림릿).
#              순서: 1 공포와 탐욕 → 2 오늘 일정·간밤 국제 뉴스 → 3 매크로 → 4 리스크 → 5 보유 종목 → 6 관심 종목
#              '신호' 칸(의장 기준)은 [빨강]·[주황]·[초록]으로 옮겨 적기만 한다. 브리핑이 따로 판정하지 않는다.
#   읽는 것  : 오늘 공포탐욕·일정·뉴스·매크로·리스크·매크로체크리스트·시세·밸류에이션·DART실적·SEC실적.csv (없는 파일은 그 칸만 '—')
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_브리핑.txt (제미나이·클로드가 바로 읽는 파일)
#   고칠 곳  : 칸 순서와 문구는 맨 아래 out 목록
# ======================================================================
import csv as _csv, math


def _read(name):
    p = f'{DAY}/{TODAY}_{name}.csv'
    if not os.path.exists(p):
        return []
    with open(p, encoding='utf-8-sig', newline='') as f:
        return list(_csv.DictReader(f))


def _n(x):
    try:
        v = float(str(x).replace(',', ''))
        return None if math.isnan(v) else v
    except Exception:
        return None


def _f(v, d=2):
    return '—' if v is None else f'{v:,.{d}f}'


def _p(v, d=1, unit='%'):
    return '—' if v is None else f'{v:+.{d}f}{unit}'


def _sig(r):
    return f'[{r["신호"]}] ' if r.get('신호') else ''


def _h(title):
    return ['', '=' * 60, title, '=' * 60]


try:
    fg, mac, risk = _read('공포탐욕'), _read('매크로'), _read('리스크')
    price, val, dart, secr = _read('시세'), _read('밸류에이션'), _read('DART실적'), _read('SEC실적')
    sch, news = _read('일정'), _read('뉴스')
    rio = _read('매크로체크리스트')
    wd = '월화수목금토일'[NOW.weekday()]
    out = [f'콜로키움 아침 브리핑 — {NOW:%Y년 %m월 %d일} ({wd})', f'만든 시각 {stamp()} KST',
           '자료: 야후, 한국투자증권, CNN, 연합뉴스, CNBC, 구글 뉴스, 네이버 뉴스, Finnhub, Tavily, FRED, 뉴욕연준, 일본 재무성, DART, SEC',
           '[빨강]·[주황]·[초록]은 의장 기준을 옮긴 것이며 투자 판단이 아닙니다. 등락은 +상승 / -하락.']

    # 1. 공포와 탐욕
    out += _h('1. 공포와 탐욕 (CNN Fear & Greed)')
    tot = next((r for r in fg if r['구분'] == '종합'), None)
    if tot:
        out.append(f'종합 {_f(_n(tot["점수"]), 1)} {tot["판정"]} | '
                   + ' | '.join(f'{k} {_f(_n(tot[k]), 1)}' for k in ['전일', '1주 전', '1개월 전', '1년 전']))
        for r in fg:
            if r['구분'] == '지표':
                out.append(f'- {r["지표"]}: {_f(_n(r["점수"]), 1)} {r["판정"]}' + (f' — {r["해석"]}' if r.get('해석') else ''))
    else:
        out.append('공포탐욕 데이터 없음')

    # 2. 오늘 일정·간밤 국제 뉴스
    out += _h('2. 오늘 일정 · 간밤 국제 뉴스')
    out.append('[실적·경제지표 일정, 오늘부터 7일, 시각은 한국]')
    today_s = NOW.strftime('%Y-%m-%d')
    for r in sch:
        mark = f' ({r["보유/관심"]})' if r.get('보유/관심') else ''
        star = '★ ' if r['날짜'] == today_s else '- '
        out.append(f'{star}{r["날짜"][5:]}({r["요일"]}) {r["시각(한국)"]} | {r["구분"]} | {r["대상"]}{mark} | {r["내용"]}')
    if not sch:
        out.append('앞으로 7일 안에 잡힌 일정 없음(또는 수집 실패, 점검 파일 참고)')
    out.append('  ★는 오늘. 한국 실적은 DART 기업설명회·실적예고 공시 본문의 시각, 미국·일본은 야후 예정일, 미국 지표 "통상"은 늘 발표하는 시각.')
    out.append('')
    for src_name, head in [('연합뉴스 국제', '간밤 국제 뉴스 — 연합뉴스, 어제 18시 이후'),
                           ('야후 종목별', '간밤 종목 뉴스 — 야후 파이낸스, 한국·미국·일본 보유·관심 종목'),
                           ('CNBC', '간밤 미국 뉴스 — CNBC 주요 뉴스'),
                           ('한국 종목별', '간밤 한국 종목 뉴스 — 구글 뉴스 검색, 보유·관심 개별주, ( ) 안은 매체'),
                           ('일본 종목별', '간밤 일본 종목 뉴스 — 구글 뉴스 검색, 보유·관심 개별주, ( ) 안은 매체'),
                           ('아침 정리', '아침 정리 기사 — 국내 언론사(구글 뉴스 검색), [ ] 안은 매체'),
                           ('DART 공시', '어제·오늘 DART 공시 — 한국 보유·관심 개별주, [주주환원]·[자본·지배구조] 먼저'),
                           ('네이버 종목별', '간밤 한국 종목 뉴스 — 네이버 뉴스 검색, 제목+요약'),
                           ('Finnhub 종목별', '간밤 미국 종목 뉴스 — Finnhub, 제목+요약, ( ) 안은 매체'),
                           ('사건 검색', '큰 움직임 사건 검색 — 전일 ±5% 넘은 종목의 이유 찾기(Tavily), ( ) 안은 전일 등락률')]:
        rows = [r for r in news if (r.get('출처') or '연합뉴스 국제') == src_name]
        out.append(f'[{head}]')
        for r in rows:
            who = f'[{r["종목"]}] ' if r.get('종목') else ''
            out.append(f'- {r["시각(한국)"]} {who}{r["제목"]}')
            if r.get('요약'):
                out.append(f'    {r["요약"]}')
        if not rows:
            out.append('없음(또는 수집 실패, 점검 파일 참고)')
        out.append('')

    # 3. 매크로
    out += _h('3. 매크로')
    out.append('[지수] 종가 | YTD | 1달 | 사상 최고 대비')
    for r in mac:
        if r['구분'] != '지수':
            continue
        if r['항목'] == '코스피 50일 이격도':
            out.append(f'- {_sig(r)}코스피 50일 이격도 {_f(_n(r["값"]), 1)} {r["표시"] or ""} ({r["비고"] or ""})')
            continue
        hi = '신고점' if '신고점' in (r['표시'] or '') else _p(_n(r['최고 대비(%)']))
        out.append(f'- {r["항목"]}: {_f(_n(r["값"]))} | YTD {_p(_n(r["YTD"]))} | 1달 {_p(_n(r["1달"]))} | 최고 대비 {hi}'
                   f' ({r["기준일"] or ""})')
    for grp, dec in [('환율', 2), ('금리', 3), ('물가', 2), ('성장·고용', 2), ('원자재', 1)]:
        out.append(f'[{grp}]')
        for r in mac:
            if r['구분'] != grp:
                continue
            unit = r['단위'] if r['단위'] in ('%', '천명') else ''
            pp = r['변화 단위'] == '%p'
            v = r['비고'] if r['항목'] == '기준금리(범위)' and r['비고'] else f'{_f(_n(r["값"]), 0 if unit == "천명" else dec)}{unit}'
            chg = ''
            if _n(r['YTD']) is not None:
                chg += f' | YTD {_p(_n(r["YTD"]), 2 if pp else 1, r["변화 단위"])}'
            if _n(r['1달']) is not None:
                chg += f' | 1달 {_p(_n(r["1달"]), 2 if pp else 1, r["변화 단위"])}'
            note = r['표시'] or ('' if r['항목'] == '기준금리(범위)' else r['비고'] or '')
            out.append(f'- {_sig(r)}{r["항목"]}: {v}{chg}' + (f' | {note}' if note else '') + f' ({r["기준일"] or ""})')
    out.append('  YTD는 작년 마지막 거래일 대비, 1달은 한 달 전 대비. 금리는 %p 변화. 월간 지표의 1달은 직전 발표 대비.')

    # 4. 리스크
    out += _h('4. 리스크')
    # 리오 매크로 체크리스트(블록 8-리오): 국면과 반대 신호 n/7, 꺾인 항목
    rsum = next((r for r in rio if r['항목'] == '요약'), None)
    if rsum:
        out.append(f'[매크로 체크리스트] {rsum["값"]}')
        for k in ('좋아질 기미', '나빠질 기미'):
            hit = [f'{r["항목"]}({r["1주 전"] or "—"} → {r["값"]})' for r in rio if r['항목'] != '요약' and r[k] == '예']
            out.append(f'  {k}: ' + (', '.join(hit) or '없음'))
    grp = None
    for r in risk:
        if r['구분'] != grp:
            grp = r['구분']
            out.append(f'[{grp}]')
        unit = r['단위'] if r['단위'] in ('%', '%p') else ''
        dec = 0 if r['단위'] == '건' else 3 if r['구분'] in ('금융 스트레스', '자금 경색') else 2
        crit = r['표시'] or r['의장 기준(참고)'] or r['일반 기준(참고)'] or ''
        out.append(f'- {_sig(r)}{r["항목"]}: {_f(_n(r["값"]), dec)}{unit} | 1주 전 {_f(_n(r["1주 전"]), dec)} | '
                   f'1달 전 {_f(_n(r["1달 전"]), dec)}' + (f' | {crit}' if crit else '')
                   + (f' · {r["비고"]}' if r['비고'] else '') + f' ({r["기준일"] or ""})')

    # 5·6. 종목
    vby = {r['번호']: r for r in val}
    per = {r['번호']: (_n(r.get('PER TTM(시총÷순이익)')), _n(r.get('PER 연환산(최근분기×4)'))) for r in dart + secr}
    # 잠정실적이 정기보고서보다 새것이면 연환산은 잠정 순이익 × 4 (2026-10-29 의장 지시)
    pre = {r['번호']: (_n(r.get('PER 연환산(잠정×4)')), r.get('잠정 분기')) for r in dart if r.get('잠정이 더 새것') == '예'}
    # 한국 PBR은 DART 최신 분기 자본 기준(한투 PBR은 직전 결산 자본이라 이익이 빨리 크는 종목은 크게 높게 나옴)
    pbr_d = {r['번호']: _n(r.get('PBR(시총÷지배자본)')) for r in dart}

    def per_txt(v):
        return '—' if v is None else ('적자' if v < 0 else f'{v:,.1f}')

    def stocks(kind):
        rows = []
        for r in price:
            if r['보유/관심'] != kind:
                continue
            no, v = r['번호'], vby.get(r['번호'], {})
            px, hi52 = _n(r['종가']), _n(v.get('52주 고가'))
            ttm, run = per.get(no, (None, None))
            run_tag = ''
            if pre.get(no, (None,))[0] is not None:
                run, run_tag = pre[no][0], f'(잠정 {pre[no][1]})'
            pbr, pbr_tag = _n(v.get('PBR')), ''
            if pbr_d.get(no) is not None:
                pbr, pbr_tag = pbr_d[no], '(DART)'
            src = ''
            if ttm is None and r['구분'] == '개별주' and _n(v.get('PER')) is not None:
                ttm, src = _n(v.get('PER')), '(한투)'
            fwd = _n(v.get('선행 PER(야후)'))
            fwd_txt = per_txt(fwd) + ('(참고)' if fwd is not None and r['시장'] == '한국' else '')
            dec = 0 if r['시장'] in ('한국', '일본') else 2
            rows.append(f'{no}. {r["정식 종목명"]}: {_f(px, dec)} | {_p(_n(r["등락률(%)"]), 2)} | '
                        f'52주 고점 대비 {_p((px / hi52 - 1) * 100 if px and hi52 else None)} | '
                        f'PER TTM {per_txt(ttm)}{src} · 연환산 {per_txt(run)}{run_tag} · 선행 {fwd_txt} | PBR {_f(pbr)}{pbr_tag}')
        return rows or ['—']

    out += _h('5. 종목 — 보유')
    out += stocks('보유')
    out += _h('6. 종목 — 관심')
    out += stocks('관심')
    out += ['', 'PER TTM = 최근 4분기 순이익(DART·SEC), 없으면 한투 값(직전 연간). PER 연환산 = 가장 최근 한 분기 순이익 × 4.',
            '"(잠정 ○Q)"는 정기보고서보다 새 잠정실적 공시의 순이익 × 4. PBR "(DART)"는 최신 분기 자본 기준, 표시 없으면 한투 값.',
            'PER 선행 = 야후의 애널리스트 예상 1년 이익 기준(한국 종목은 근거가 불분명해 "참고").']
    with open(f'{DAY}/{TODAY}_브리핑.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')
    log(f'[10 브리핑] txt 만듦 ({len(out)}줄)')
except Exception as e:
    traceback.print_exc()
    log(f'[10 브리핑] 실패: {type(e).__name__} {e}')
