# ======================================================================
# [블록 9] 오늘 브리핑 — 그날 파일을 모아 보기 좋은 한 문서로 만든다
#   하는 일  : 오늘 날짜 폴더의 CSV를 읽어 브리핑 HTML을 만들고, 크로미엄이 있으면 PDF로도 바꾼다.
#              순서: 1 공포와 탐욕 → 2 매크로 → 3 리스크 → 4 보유 종목 → 5 관심 종목
#              색은 각 블록이 적은 '신호' 칸(의장 기준)만 따른다. 브리핑이 따로 판정하지 않는다.
#   읽는 것  : 오늘 공포탐욕·매크로·리스크·시세·밸류에이션·DART실적·SEC실적.csv (없는 파일은 그 칸만 '—')
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_브리핑.pdf (드라이브·폰에서 바로 열림), YYYYMMDD_브리핑.html
#   고칠 곳  : 모양은 CSS, 표 순서는 맨 아래 doc
# ======================================================================
import csv as _csv, html as _html, math


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
    if v is None:
        return '<span class="mute">—</span>'
    c = 'up' if v > 0 else 'dn' if v < 0 else 'mute'
    return f'<span class="{c}">{v:+.{d}f}{unit}</span>'


E = _html.escape
SIG = {'빨강': 'red', '주황': 'amber', '초록': 'green'}
FG_COL = [(25, '#c0392b'), (45, '#e67e22'), (55, '#9aa0a6'), (75, '#7cb342'), (101, '#2e7d32')]


def _fgc(s):
    return next(c for lim, c in FG_COL if s < lim)


def _gauge(score):
    cx, cy, r = 110, 105, 85
    pt = lambda val, rr: (cx + rr * math.cos(math.pi * (1 - val / 100)), cy - rr * math.sin(math.pi * (1 - val / 100)))
    segs, a = [], 0
    for lim, c in FG_COL:
        b = min(lim, 100)
        (x1, y1), (x2, y2) = pt(a, r), pt(b, r)
        segs.append(f'<path d="M{x1:.1f},{y1:.1f} A{r},{r} 0 0 1 {x2:.1f},{y2:.1f}" stroke="{c}" stroke-width="16" fill="none"/>')
        a = b
    nx, ny = pt(score, r - 22)
    return (f'<svg viewBox="0 0 220 125" class="gauge">{"".join(segs)}<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" '
            f'stroke="#222" stroke-width="3" stroke-linecap="round"/><circle cx="{cx}" cy="{cy}" r="5" fill="#222"/></svg>')


def _scale(v):
    lo, hi = 70, 140
    m = lambda x: max(0, min(100, (x - lo) / (hi - lo) * 100))
    return (f'<div class="scale"><div class="zone" style="left:0;width:{m(80)}%;background:#a5d6a7"></div>'
            f'<div class="zone" style="left:{m(125)}%;width:{m(130) - m(125)}%;background:#f5c26b"></div>'
            f'<div class="zone" style="left:{m(130)}%;width:{100 - m(130)}%;background:#e57373"></div>'
            f'<div class="pin" style="left:{m(v)}%"></div>'
            + ''.join(f'<span style="left:{m(x)}%">{x}</span>' for x in [70, 80, 100, 125, 130]) + '</div>')


try:
    fg, mac, risk = _read('공포탐욕'), _read('매크로'), _read('리스크')
    price, val, dart, secr = _read('시세'), _read('밸류에이션'), _read('DART실적'), _read('SEC실적')
    macro_by = {r['항목']: r for r in mac}

    # 1. 공포와 탐욕
    tot = next((r for r in fg if r['구분'] == '종합'), None)
    if tot:
        s = _n(tot['점수'])
        hist = ''.join(f'<div><b>{_f(_n(tot[k]), 1)}</b><small>{k}</small></div>' for k in ['전일', '1주 전', '1개월 전', '1년 전'])
        rows = ''.join(
            f'<tr><td>{E(r["지표"].split(". ", 1)[-1])}</td>'
            f'<td><div class="bar"><div style="width:{_n(r["점수"]) or 0:.0f}%;background:{_fgc(_n(r["점수"]) or 0)}"></div></div></td>'
            f'<td class="r">{_f(_n(r["점수"]), 1)}</td><td class="lab" style="color:{_fgc(_n(r["점수"]) or 0)}">{E(r["판정"])}</td>'
            f'<td class="small">{E(r.get("해석") or "")}</td></tr>' for r in fg if r['구분'] == '지표')
        sec1 = (f'<div class="fg"><div class="fgL">{_gauge(s)}<div class="fgScore" style="color:{_fgc(s)}">{s:.1f}</div>'
                f'<div class="fgLab">{E(tot["판정"])}</div><div class="hist">{hist}</div></div>'
                f'<table class="t fgT">{rows}</table></div>')
    else:
        sec1 = '<p class="mute">공포탐욕 데이터 없음</p>'

    # 2. 매크로
    def sigcls(r):
        return SIG.get(r.get('신호') or '', '')

    idx = ''
    disp = ''
    for r in mac:
        if r['구분'] != '지수':
            continue
        if r['항목'] == '코스피 50일 이격도':
            v = _n(r['값'])
            if v is not None:
                c = sigcls(r)
                disp = (f'<div class="disp"><div><b>코스피 50일 이격도</b> <span class="big {c}">{v:.1f}</span> '
                        f'<span class="small {c}">{E(r["표시"])}</span> <span class="small mute">{E(r["비고"])}</span></div>{_scale(v)}</div>')
            continue
        hi = _n(r['최고 대비(%)'])
        mark = '<b class="new">신고점</b>' if '신고점' in (r['표시'] or '') else _p(hi)
        idx += (f'<tr><td><b>{E(r["항목"])}</b></td><td class="r">{_f(_n(r["값"]))}</td><td class="small mute">{E(r["기준일"] or "")}</td>'
                f'<td class="r">{_p(_n(r["YTD"]))}</td><td class="r">{_p(_n(r["1달"]))}</td><td class="r">{mark}</td>'
                f'<td class="small mute">{E(r["의장 기준(참고)"] or "")}</td></tr>')

    def tiles(grp, dec=2):
        out = ''
        for r in mac:
            if r['구분'] != grp:
                continue
            c, v, unit = sigcls(r), _n(r['값']), r['단위'] if r['단위'] in ('%', '천명') else ''
            pp = r['변화 단위'] == '%p'
            sub = ''
            if _n(r['YTD']) is not None:
                sub += f'YTD {_p(_n(r["YTD"]), 2 if pp else 1, r["변화 단위"])} '
            if _n(r['1달']) is not None:
                sub += f'1달 {_p(_n(r["1달"]), 2 if pp else 1, r["변화 단위"])}'
            val_txt = E(r['비고']) if r['항목'] == '기준금리(범위)' and r['비고'] else f'{_f(v, 0 if unit == "천명" else dec)}{unit}'
            note = r['표시'] or ('' if r['항목'] == '기준금리(범위)' else r['비고'] or '')
            out += (f'<div class="tile {c}"><small>{E(r["항목"])}</small><b>{val_txt}</b><span class="sub">{sub}</span>'
                    f'<em>{E(note)}</em><i>{E(r["기준일"] or "")}</i></div>')
        return out

    # 3. 리스크
    rk_rows, grp = '', None
    for r in risk:
        if r['구분'] != grp:
            grp = r['구분']
            rk_rows += f'<tr class="grp"><td colspan="6">{E(grp)}</td></tr>'
        c = sigcls(r)
        unit = r['단위'] if r['단위'] in ('%', '%p') else ''
        dec = 0 if r['단위'] == '건' else 3 if r['구분'] in ('금융 스트레스', '자금 경색') else 2
        crit = r['표시'] or r['의장 기준(참고)'] or r['일반 기준(참고)'] or ''
        rk_rows += (f'<tr><td><span class="dot {c or "none"}"></span>{E(r["항목"])}</td>'
                    f'<td class="r"><b>{_f(_n(r["값"]), dec)}{unit}</b></td><td class="r mute">{_f(_n(r["1주 전"]), dec)}</td>'
                    f'<td class="r mute">{_f(_n(r["1달 전"]), dec)}</td><td class="small mute">{E(r["기준일"] or "")}</td>'
                    f'<td class="small {c}">{E(crit)}{(" · " + E(r["비고"])) if r["비고"] else ""}</td></tr>')

    # 4·5. 종목
    vby = {r['번호']: r for r in val}
    per = {}
    for r in dart + secr:
        per[r['번호']] = (_n(r.get('PER TTM(시총÷순이익)')), _n(r.get('PER 연환산(최근분기×4)')))

    def per_txt(v):
        return '—' if v is None else ('적자' if v < 0 else f'{v:,.1f}')

    def stocks(kind):
        out = ''
        for r in price:
            if r['보유/관심'] != kind:
                continue
            no, v = r['번호'], vby.get(r['번호'], {})
            px, hi52 = _n(r['종가']), _n(v.get('52주 고가'))
            ttm, run = per.get(no, (None, None))
            src = ''
            if ttm is None and r['구분'] == '개별주' and _n(v.get('PER')) is not None:
                ttm, src = _n(v.get('PER')), '<small class="mute"> 한투</small>'
            fwd = _n(v.get('선행 PER(야후)'))
            fwd_txt = per_txt(fwd) + ('<small class="mute"> 참고</small>' if fwd is not None and r['시장'] == '한국' else '')
            dec = 0 if r['시장'] in ('한국', '일본') else 2
            out += (f'<tr><td class="mute">{no}</td><td>{E(r["정식 종목명"])}</td>'
                    f'<td class="r">{_f(px, dec)}</td><td class="r">{_p(_n(r["등락률(%)"]), 2)}</td>'
                    f'<td class="r">{_p((px / hi52 - 1) * 100 if px and hi52 else None)}</td>'
                    f'<td class="r">{per_txt(ttm)}{src}</td><td class="r">{per_txt(run)}</td><td class="r">{fwd_txt}</td>'
                    f'<td class="r">{_f(_n(v.get("PBR")))}</td></tr>')
        return out

    thead = ('<tr><th></th><th>종목</th><th class="r">종가</th><th class="r">등락</th><th class="r">52주 고점 대비</th>'
             '<th class="r">PER TTM</th><th class="r">PER 연환산</th><th class="r">PER 선행</th><th class="r">PBR</th></tr>')

    wd = '월화수목금토일'[NOW.weekday()]
    doc = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>콜로키움 아침 브리핑 {TODAY}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;600;800&display=swap">
<style>
:root{{--ink:#1d2330;--mute:#6b7280;--line:#e5e7eb;--card:#f7f8fa;--up:#1e8e3e;--dn:#d32f2f;--red:#c62828;--amber:#b26a00;--green:#2e7d32}}
*{{box-sizing:border-box}}
body{{margin:0;background:#fff;color:var(--ink);font:13px/1.45 'Noto Sans KR','Malgun Gothic','Apple SD Gothic Neo',sans-serif}}
.page{{max-width:980px;margin:0 auto;padding:24px 20px}}
header{{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:3px solid var(--ink);padding-bottom:10px;margin-bottom:18px}}
h1{{font-size:24px;margin:0}} header p{{margin:0;color:var(--mute)}}
h2{{font-size:16px;margin:26px 0 10px;padding-left:10px;border-left:4px solid var(--ink)}}
h3{{font-size:13px;margin:14px 0 6px;color:var(--mute);font-weight:600}}
.t{{width:100%;border-collapse:collapse}} .t td,.t th{{padding:5px 6px;border-bottom:1px solid var(--line);vertical-align:middle}}
.t th{{font-weight:600;color:var(--mute);font-size:12px;text-align:left;border-bottom:1.5px solid var(--ink)}}
.r,.t th.r{{text-align:right;font-variant-numeric:tabular-nums}} .small{{font-size:11.5px}} .mute{{color:var(--mute)}}
.up{{color:var(--up)}} .dn{{color:var(--dn)}} .red{{color:var(--red)}} .amber{{color:var(--amber)}} .green{{color:var(--green)}}
.new{{color:#fff;background:var(--up);border-radius:4px;padding:1px 6px;font-size:11px}}
.fg{{display:grid;grid-template-columns:240px 1fr;gap:18px;align-items:center}}
.fgL{{text-align:center}} .gauge{{width:220px}} .fgScore{{font-size:34px;font-weight:800;margin-top:-34px}}
.fgLab{{font-weight:700;margin-bottom:8px}} .hist{{display:flex;justify-content:center;gap:12px}}
.hist div{{display:flex;flex-direction:column;font-size:12px}} .hist small{{color:var(--mute);font-size:10.5px}}
.bar{{width:90px;height:8px;background:#eceff1;border-radius:4px;overflow:hidden}} .bar div{{height:100%}}
.lab{{font-weight:600;font-size:12px;white-space:nowrap}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px}}
.tile{{background:var(--card);border-radius:8px;padding:8px 10px;display:flex;flex-direction:column;border-top:3px solid #d0d4da}}
.tile small{{color:var(--mute);font-size:11.5px}} .tile b{{font-size:17px;font-variant-numeric:tabular-nums}}
.tile .sub{{font-size:11px}} .tile em{{font-style:normal;font-size:11px;min-height:15px}} .tile i{{font-style:normal;font-size:10.5px;color:var(--mute)}}
.tile.red{{border-top-color:var(--red)}} .tile.amber{{border-top-color:#e0a030}} .tile.green{{border-top-color:var(--green)}}
.tile.red em{{color:var(--red)}} .tile.amber em{{color:var(--amber)}} .tile.green em{{color:var(--green)}}
.disp{{margin:10px 0 4px;background:var(--card);border-radius:8px;padding:10px 12px}} .big{{font-size:20px;font-weight:800}}
.scale{{position:relative;height:10px;background:#eceff1;border-radius:5px;margin:10px 0 18px}}
.scale .zone{{position:absolute;top:0;height:100%}} .scale .pin{{position:absolute;top:-4px;width:4px;height:18px;background:var(--ink);border-radius:2px;transform:translateX(-2px)}}
.scale span{{position:absolute;top:13px;font-size:10px;color:var(--mute);transform:translateX(-50%)}}
.dot{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px}}
.dot.red{{background:var(--red)}} .dot.amber{{background:#e0a030}} .dot.green{{background:var(--green)}} .dot.none{{background:#cfd4da}}
tr.grp td{{background:var(--card);font-weight:700;font-size:12px;padding:4px 6px}}
.note{{color:var(--mute);font-size:11px;margin-top:6px}}
footer{{margin-top:28px;border-top:1px solid var(--line);padding-top:8px;color:var(--mute);font-size:11px}}
@media (max-width:700px){{.fg{{grid-template-columns:1fr}} .page{{padding:16px}}}}
@media print{{.page{{padding:0}} h2{{break-after:avoid}} .t tr{{break-inside:avoid}}}}
</style></head><body><div class="page">
<header><div><h1>콜로키움 아침 브리핑</h1><p>{NOW:%Y년 %m월 %d일} ({wd})</p></div><p>만든 시각 {stamp()} KST</p></header>
<h2>1. 공포와 탐욕</h2>{sec1}
<h2>2. 매크로</h2>
<h3>지수</h3>
<table class="t"><tr><th>지수</th><th class="r">종가</th><th>기준일</th><th class="r">YTD</th><th class="r">1달</th><th class="r">사상 최고 대비</th><th>의장 기준</th></tr>{idx}</table>
{disp}
<h3>환율</h3><div class="tiles">{tiles("환율")}</div>
<h3>금리</h3><div class="tiles">{tiles("금리", 3)}</div>
<h3>물가</h3><div class="tiles">{tiles("물가")}</div>
<h3>성장·고용</h3><div class="tiles">{tiles("성장·고용")}</div>
<h3>원자재</h3><div class="tiles">{tiles("원자재", 1)}</div>
<p class="note">YTD는 작년 마지막 거래일 대비, 1달은 한 달 전 대비. 금리는 %p 변화. 월간 지표(물가·고용)의 1달은 직전 발표 대비.</p>
<h2>3. 리스크</h2>
<table class="t"><tr><th>항목</th><th class="r">값</th><th class="r">1주 전</th><th class="r">1달 전</th><th>기준일</th><th>기준·메모</th></tr>{rk_rows}</table>
<p class="note">점 색은 의장 기준이 있는 항목과 VIX 역전에만 붙습니다. 회색 점은 숫자와 일반 기준만 보여 줍니다.</p>
<h2>4. 종목 — 보유</h2><table class="t">{thead}{stocks("보유")}</table>
<h2>5. 종목 — 관심</h2><table class="t">{thead}{stocks("관심")}</table>
<p class="note">PER TTM = 최근 4분기 순이익(DART·SEC), 없으면 한투 값(직전 연간). PER 연환산 = 가장 최근 한 분기 순이익 × 4.
PER 선행 = 야후의 애널리스트 예상 1년 이익 기준(한국 종목은 근거가 불분명해 '참고'). 등락 색은 미국식(초록 상승, 빨강 하락).</p>
<footer>자료: 야후, 한국투자증권, CNN, FRED, 뉴욕연준, 일본 재무성, DART, SEC · 색과 문구는 의장 기준을 옮긴 것이며 투자 판단이 아닙니다.</footer>
</div></body></html>'''
    out_html = f'{DAY}/{TODAY}_브리핑.html'
    with open(out_html, 'w', encoding='utf-8') as f:
        f.write(doc)
    pdf_ok = False
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            pg = b.new_page()
            pg.goto('file://' + os.path.abspath(out_html), wait_until='networkidle', timeout=60000)
            pg.pdf(path=f'{DAY}/{TODAY}_브리핑.pdf', format='A4', print_background=True,
                   margin={'top': '12mm', 'bottom': '12mm', 'left': '10mm', 'right': '10mm'})
            b.close()
        pdf_ok = True
    except Exception as e:
        print('  PDF 변환 건너뜀:', e)
    log(f'[9 브리핑] HTML 만듦 | PDF {"만듦" if pdf_ok else "못 만듦(크로미엄 없음)"}')
except Exception as e:
    traceback.print_exc()
    log(f'[9 브리핑] 실패: {type(e).__name__} {e}')
