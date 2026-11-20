# 회의 발표 그리기 — 발표 파일(YYYYMMDD_발표.json)의 위원 문장과 그래프를 그린다.
#   '회의 발표' 페이지와 첫 화면(발표 순서 탭)이 같이 쓴다. 자료 읽기는 부르는 쪽이 setup()으로 넘긴다.
import altair as alt
import pandas as pd
import streamlit as st

UP, DN = '#1e8e3e', '#d32f2f'
PALETTE = ['#2563eb', '#d97706', '#7c3aed', '#0891b2', '#db2777', '#65a30d', '#475569', '#b45309', '#0d9488', '#9333ea']
_IO = {}


def setup(csv, prices):
    """csv(day, name) → DataFrame, prices() → 가격이력 DataFrame(날짜·티커·가격)"""
    _IO['csv'], _IO['prices'] = csv, prices


def csv(day, name):
    return _IO['csv'](day, name)


def prices():
    return _IO['prices']()


def num(s):
    return pd.to_numeric(s, errors='coerce')


def names(day):
    """야후 티커 → 종목명 (시세 파일 기준)"""
    p = csv(day, '시세')
    if not len(p):
        return {}
    return dict(zip(p['yfinance 티커'].astype(str), p['정식 종목명'].astype(str)))


# ---------------------------------------------------------------- 그래프
def wilder_rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def draw(day, c, nm):
    kind, title = c.get('type'), c.get('title', '')
    lab = lambda t: c.get('labels', {}).get(t) or nm.get(t, t)
    if kind == 'change':
        p = csv(day, '시세')
        if not len(p):
            st.caption('시세 파일 없음'); return
        p = p[p['yfinance 티커'].astype(str).isin(c['tickers'])].copy()
        p['이름'] = p['yfinance 티커'].astype(str).map(lab)
        p['등락률'] = num(p['등락률(%)'])
        order = [lab(t) for t in c['tickers'] if lab(t) in set(p['이름'])]
        base = alt.Chart(p).encode(y=alt.Y('이름:N', sort=order, title=None, axis=alt.Axis(labelOverlap=False, labelLimit=200)),
                                   x=alt.X('등락률:Q', title='하루 등락률(%)'))
        bars = base.mark_bar().encode(color=alt.condition('datum.등락률 >= 0', alt.value(UP), alt.value(DN)),
                                      tooltip=['이름', alt.Tooltip('등락률:Q', format='+.2f')])
        txt = (base.transform_filter('datum.등락률 >= 0').mark_text(align='left', dx=4)
               .encode(text=alt.Text('등락률:Q', format='+.2f'))
               + base.transform_filter('datum.등락률 < 0').mark_text(align='right', dx=-4)
               .encode(text=alt.Text('등락률:Q', format='+.2f')))
        st.altair_chart((bars + txt).properties(title=title or f'{day[4:6]}/{day[6:]} 발표 기준 하루 등락률 (_시세.csv)',
                                                height=30 * len(p) + 50), width='stretch')
    elif kind in ('line', 'rsi'):
        px = prices()
        if not len(px):
            st.caption('가격 이력 없음'); return
        px = px[px['티커'].isin(c['tickers'])]
        rows = []
        for t, g in px.groupby('티커'):
            s = g.set_index('날짜')['가격'].sort_index().dropna()
            if kind == 'line':
                s = s[s.index >= s.index.max() - pd.Timedelta(days=c.get('days', 365))]
                if not len(s):
                    continue
                s = s / s.iloc[0] * 100
                rows.append(pd.DataFrame({'날짜': s.index, '값': s.values, '이름': lab(t)}))
            else:
                w = s.resample('W-FRI').last().dropna()
                r = wilder_rsi(w).dropna().tail(c.get('weeks', 26))
                rows.append(pd.DataFrame({'날짜': r.index, '값': r.values, '이름': lab(t)}))
        if not rows:
            st.caption('가격 이력에 해당 티커 없음'); return
        df = pd.concat(rows)
        order = [lab(t) for t in c['tickers']]
        sc = alt.Scale(domain=order, range=PALETTE[:len(order)])
        ln = alt.Chart(df).mark_line(strokeWidth=2).encode(
            x=alt.X('날짜:T', title=None, axis=alt.Axis(format='%y.%m' if kind == 'line' else '%m/%d')),
            y=alt.Y('값:Q', title='시작 = 100' if kind == 'line' else '주봉 RSI', scale=alt.Scale(zero=False)),
            color=alt.Color('이름:N', scale=sc, legend=alt.Legend(orient='right', title=None)),
            tooltip=['이름', alt.Tooltip('날짜:T', format='%Y-%m-%d'), alt.Tooltip('값:Q', format='.1f')])
        last = df.sort_values('날짜').groupby('이름').tail(1)
        end = alt.Chart(last).mark_text(align='left', dx=5, fontSize=11).encode(
            x='날짜:T', y='값:Q', text=alt.Text('값:Q', format='.0f'), color=alt.Color('이름:N', scale=sc, legend=None))
        refs = [100] if kind == 'line' else [30, 70]
        rule = alt.Chart(pd.DataFrame({'y': refs})).mark_rule(strokeDash=[4, 3], color='#94a3b8').encode(y='y:Q')
        dflt = '1년 흐름 (가격이력, 시작 = 100)' if kind == 'line' else f'주봉 RSI 흐름 (최근 {c.get("weeks", 26)}주, 30·70 점선)'
        st.altair_chart((rule + ln + end).properties(title=title or dflt, height=c.get('height', 300)), width='stretch')
    elif kind == 'bar':
        d = csv(day, c['file'])
        if not len(d):
            st.caption(f'{c["file"]} 파일 없음'); return
        d = d[d[c['key']].astype(str).isin(c['rows'])].copy()
        d['값'] = num(d[c['value']]) * c.get('scale', 1)
        d['이름'] = d[c['key']].astype(str)
        fmtv = c.get('format', ',.0f')
        base = alt.Chart(d).encode(y=alt.Y('이름:N', sort=c['rows'], title=None, axis=alt.Axis(labelOverlap=False, labelLimit=200)),
                                   x=alt.X('값:Q', title=c.get('unit', c['value'])))
        bars = base.mark_bar().encode(color=alt.condition('datum.값 >= 0', alt.value(UP), alt.value(DN)),
                                      tooltip=['이름', alt.Tooltip('값:Q', format=fmtv)])
        txt = (base.transform_filter('datum.값 >= 0').mark_text(align='left', dx=4)
               .encode(text=alt.Text('값:Q', format=fmtv))
               + base.transform_filter('datum.값 < 0').mark_text(align='right', dx=-4)
               .encode(text=alt.Text('값:Q', format=fmtv)))
        st.altair_chart((bars + txt).properties(title=title or f'{c["value"]} (_{c["file"]}.csv)',
                                                height=30 * len(d) + 50), width='stretch')
    elif kind == 'table':
        d = csv(day, c['file'])
        if not len(d):
            st.caption(f'{c["file"]} 파일 없음'); return
        d = d[d[c['key']].astype(str).isin(c['rows'])].drop_duplicates(c['key'])
        d = d.set_index(c['key']).reindex([r for r in c['rows'] if r in set(d[c['key']].astype(str))])
        d = d[[x for x in c['cols'] if x in d.columns]].rename(columns=c.get('rename', {}))
        if c.get('labels'):
            d.insert(0, '종목', [c['labels'].get(k, k) for k in d.index])
        if title:
            st.markdown(f'**{title}**')
        st.dataframe(d, hide_index=True, width='stretch')
        st.caption(f'출처: _{c["file"]}.csv')
    elif kind == 'grid':
        if title:
            st.markdown(f'**{title}**')
        st.dataframe(pd.DataFrame(c['rows'], columns=c['columns']), hide_index=True, width='stretch')
        if c.get('source'):
            st.caption(f'출처: {c["source"]}')


FG_GUIDE = """
**한 줄로**: 7개 지표를 각각 0~100점으로 매기고 평균 낸 것이 공포와 탐욕 지수다. 50이 중간, 25 아래 Extreme Fear, 75 위 Extreme Greed.
묶으면 **가격 셋 · 옵션 둘 · 채권 둘**.

**① 가격 셋 — 주식이 실제로 어떻게 움직였나**

1. **Market Momentum (모멘텀)** — S&P500이 *125일 이동평균*보다 얼마나 위에 있나  
   :small[:gray[왜 들어가나: 지수가 반년 평균보다 한참 위면 사람들이 들떠 있고(탐욕), 평균 아래로 내려가면 겁먹는다. '지수 하나'로 본 분위기.]]
2. **Stock Price Strength (강도)** — 뉴욕거래소에서 *52주 신고가 종목 수 vs 52주 신저가 종목 수*  
   :small[:gray[왜 들어가나: 지수는 큰 종목 몇 개가 끌어올릴 수 있다. 신고가 종목이 많아야 시장 전체가 강한 것. '종목 수'로 본 분위기.]]
3. **Stock Price Breadth (폭)** — *오르는 종목의 거래량 vs 내리는 종목의 거래량*(맥클렐런 거래량 합산 지수)  
   :small[:gray[왜 들어가나: 몇 종목이 올랐냐보다 '돈(거래량)이 어느 쪽에 실렸냐'를 본다. '거래량'으로 본 분위기.]]

:small[정리: 지수(Momentum) → 종목 수(Strength) → 거래량(Breadth). 크게 → 넓게 → 깊게.]

**② 옵션 둘 — 사람들이 앞으로를 어떻게 걸고 있나**

4. **Put and Call Options (풋/콜)** — 최근 5일 *풋옵션 거래 ÷ 콜옵션 거래*  
   :small[:gray[왜 들어가나: 풋은 '떨어질 때 보험', 콜은 '오를 때 베팅'. 보험을 많이 사면(비율 1 위) 공포, 베팅이 많으면(0.7 아래) 탐욕.]]
5. **Market Volatility (변동성)** — *VIX*가 자기 50일 평균보다 높나 낮나  
   :small[:gray[왜 들어가나: VIX는 옵션 값으로 계산한 '앞으로 30일 S&P가 얼마나 흔들릴지' 예상치. 평소보다 높으면 불안(공포), 낮으면 안심(탐욕).]]

:small[정리: 풋/콜 = 사람들이 '산 보험', VIX = 그 보험의 '가격'.]

**③ 채권 둘 — 돈이 안전한 곳으로 도망가나**

6. **Safe Haven Demand (안전자산 수요)** — 최근 20영업일 *주식 수익률 − 미국 국채 수익률*  
   :small[:gray[왜 들어가나: 무서우면 주식을 팔고 국채로 피난한다. 국채가 주식보다 잘 벌었으면(마이너스) 공포, 주식이 이겼으면 탐욕.]]
7. **Junk Bond Demand (정크본드 수요)** — *정크본드(투기등급 회사채) 금리 − 투자등급 회사채 금리*  
   :small[:gray[왜 들어가나: 위험한 회사에 돈을 빌려줄 때 얼마나 더 받느냐. 차이가 좁으면 위험을 기꺼이 짐(탐욕), 벌어지면 겁먹고 웃돈을 요구(공포). 리오가 보는 하이일드 스프레드와 같은 뿌리.]]

:small[정리: Safe Haven = '국채로 피난', Junk Bond = '위험한 회사채도 사 주나'.]

**읽는 요령**: 가격 셋이 공포인데 채권 둘이 멀쩡하면 '주가만 흔들렸고 돈은 아직 안 도망감'. 채권 둘까지 공포로 가면 진짜 위험 회피.
"""


def member(day, m, nm):
    try:
        _member(day, m, nm)
    except Exception as e:   # 2026-11-13: 원고 한 칸의 오류가 아래 칸 전부를 비우지 않게
        st.warning(f'이 칸의 발표 원고를 그리지 못했습니다: {type(e).__name__}')
    # 2026-11-13 의장 "공포와 탐욕 7개 항목을 왜 들어가 있는지 자세히, 매일 보이게"
    if '공포' in (m.get('name') or ''):
        with st.expander('7개 지표 — 가격 셋 · 옵션 둘 · 채권 둘', expanded=True):
            st.markdown(FG_GUIDE)


TABLE_CSS = """<style>
.qt{width:100%;border-collapse:collapse;font-size:15px;line-height:1.6;margin:4px 0 18px}
.qt th{background:#eef3ea;color:#2b3a2b;font-weight:600;text-align:left;padding:10px 12px;border-bottom:2px solid #c9d6c3;white-space:nowrap}
.qt td{padding:11px 12px;border-bottom:1px solid #e3e6e8;vertical-align:top}
.qt td.n{color:#8a8f94;width:2.2em;text-align:right}
.qt td.k{font-weight:600;white-space:nowrap}
.qt td.v{font-weight:600;font-size:16px}
.qt td.c{color:#444;white-space:nowrap}
.qt td.w{color:#8a8f94;font-size:13px}
.qt td.red{background:#fde4e4;color:#a51d1d;font-weight:600}
.qt td.orange{background:#fff1dc;color:#9a5a00;font-weight:600}
.qt td.green{background:#e4f4e6;color:#1d6b2c;font-weight:600}
@media (prefers-color-scheme: dark){.qt th{background:#26302a;color:#dfe8dc;border-color:#3b4a3e}.qt td{border-color:#333}.qt td.c{color:#ccc}
.qt td.red{background:#4a1f1f;color:#ffb3b3}.qt td.orange{background:#4a3517;color:#ffd08a}.qt td.green{background:#1f3d25;color:#a8e6b4}}
</style>"""


def _h(x):
    import html
    import re
    return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html.escape(str(x or '')))


def rows_table(rows):
    """11/20 의장 "엑셀처럼, 줄 간격 넓게, 글자 덜 촘촘하게": [항목 | 값 | 변화 | 기준·신호 | 근거], 신호는 칸 색."""
    has_c = any(r.get('변화') for r in rows); has_k = any(r.get('기준·신호') for r in rows)
    cols = ['', '항목', '값'] + (['변화(1주·1달)'] if has_c else []) + (['기준·신호'] if has_k else []) + ['근거']
    out = [TABLE_CSS, '<table class="qt"><thead><tr>' + ''.join(f'<th>{c}</th>' for c in cols) + '</tr></thead><tbody>']
    for i, r in enumerate(rows, 1):
        tds = [f'<td class="n">{i}</td>', f'<td class="k">{_h(r.get("항목"))}</td>', f'<td class="v">{_h(r.get("값"))}</td>']
        if has_c:
            tds.append(f'<td class="c">{_h(r.get("변화"))}</td>')
        if has_k:
            tds.append(f'<td class="{r.get("신호") or ""}">{_h(r.get("기준·신호"))}</td>')
        tds.append(f'<td class="w">{_h(r.get("근거"))}</td>')
        out.append('<tr>' + ''.join(tds) + '</tr>')
    return ''.join(out) + '</tbody></table>'


def _member(day, m, nm):
    head = ' · '.join(x for x in [m.get('name'), m.get('role')] if x)
    if head:
        st.subheader(head)
    if m.get('rows'):   # 11/20 의장: 번호 나열 대신 표, 표·그래프는 아래에 두 칸
        st.markdown(rows_table(m['rows']), unsafe_allow_html=True)
        charts = list(m.get('charts', []))
        for i in range(0, len(charts), 2):
            cs = st.columns(2)
            for col, c in zip(cs, charts[i:i + 2]):
                with col:
                    with st.container(border=True):
                        _safe_draw(day, c, nm)
        return
    # 2026-11-13: 표·그래프(dict)가 lines에 잘못 들어와도 화면이 멈추지 않게 charts로 옮긴다
    raw = m.get('lines') or []
    lines = [x for x in raw if isinstance(x, str)]
    charts = list(m.get('charts', [])) + [x for x in raw if isinstance(x, dict)]
    m = {**m, 'lines': lines}
    if m.get('lines'):
        left, right = st.columns([5, 7]) if charts else (st.container(), None)
        with left:
            st.markdown('\n'.join(m['lines']))
            if m.get('sources'):
                st.caption('출처: ' + ' · '.join(m['sources']))
        if right is not None:
            with right:
                for c in charts:
                    with st.container(border=True):
                        _safe_draw(day, c, nm)
    else:
        for c in charts:
            with st.container(border=True):
                _safe_draw(day, c, nm)


def _safe_draw(day, c, nm):
    try:
        draw(day, c, nm)
    except Exception as e:   # 그래프 하나가 틀려도 아래 칸은 그려지게
        st.warning(f'그래프를 그리지 못했습니다: {type(e).__name__}')
