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


def member(day, m, nm):
    head = ' · '.join(x for x in [m.get('name'), m.get('role')] if x)
    if head:
        st.subheader(head)
    charts = m.get('charts', [])
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
                        draw(day, c, nm)
    else:
        for c in charts:
            with st.container(border=True):
                draw(day, c, nm)


