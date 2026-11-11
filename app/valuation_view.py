# 스트림릿 '1. 시장' 맨 위 — 지수 밸류·등락 (2026-11-11 의장: 자문사 C 자료의 그림을 우리 자료로, 같은 모양으로)
#   (가) S&P500·나스닥100·필반 12개월 선행 P/E: 우리 계산(07시 b09_valuation, 00_누적/00_지수선행PE.csv)의 선과
#        자문사 C(블룸버그) 캡처의 10년 평균·±1표준편차 참고선(추정치). 과거 컨센서스는 무료로 없어 오늘부터 쌓인다.
#   (나) 필반지수 200일 이격도(100 기준) 1995-10-16부터, 평균·±1표준편차는 우리 자료로 계산.
#   (다) 주요국·미국 지수 이달·연초 이후 등락 막대.
#   판정은 하지 않는다. 그림 아래 회색 작은 글씨는 계산 방법과 출처.
import io

import altair as alt
import pandas as pd
import streamlit as st

import valuation as vmod

LINE, BAND, NAVY = '#5f6368', '#7cb342', '#1f4e79'


@st.cache_data(ttl=3600, show_spinner=False)
def _live_bars():
    import yfinance as yf
    return vmod.bars(yf)


@st.cache_data(ttl=3600, show_spinner=False)
def _live_disp():
    import yfinance as yf
    return vmod.sox_disparity(yf)


def _pe_chart(name, h, ref, h_px=250):
    """선 = 우리 선행 P/E, 점선 = 캡처 참고선, 초록 점 = 최신값"""
    h = h.copy()
    h['날짜'] = pd.to_datetime(h['날짜'])
    h['선행PE'] = pd.to_numeric(h['선행PE'], errors='coerce')
    h = h.dropna(subset=['선행PE'])
    last = h.iloc[-1]
    lo = min(h['선행PE'].min(), ref['-1σ']) - 2
    hi = max(h['선행PE'].max(), ref['+1σ']) + 2
    x0 = min(h['날짜'].min(), pd.Timestamp(vmod.REF_DAY)) - pd.Timedelta(days=7)
    x1 = max(h['날짜'].max(), x0 + pd.Timedelta(days=60)) + pd.Timedelta(days=3)
    X = alt.X('날짜:T', title=None, scale=alt.Scale(domain=[x0, x1]), axis=alt.Axis(format='%m/%d', grid=False))
    Y = alt.Y('v:Q', title=None, scale=alt.Scale(domain=[lo, hi], nice=False), axis=alt.Axis(format='.0f', labelExpr="datum.label + 'x'"))
    rl = pd.DataFrame({'v': [ref['+1σ'], ref['평균'], ref['-1σ']],
                       't': [f"+1 표준편차: {ref['+1σ']:.1f}x", f"10년 평균: {ref['평균']:.1f}x", f"-1 표준편차: {ref['-1σ']:.1f}x"],
                       '날짜': [x1] * 3})
    rules = alt.Chart(rl).mark_rule(color=BAND, strokeDash=[6, 4], strokeWidth=2).encode(y=Y)
    rtxt = alt.Chart(rl).mark_text(color=BAND, align='right', dy=-7, fontWeight='bold', fontSize=11).encode(x=X, y=Y, text='t')
    d = h.rename(columns={'선행PE': 'v'})
    line = alt.Chart(d).mark_line(color=LINE, strokeWidth=1.8, point=len(d) < 30).encode(
        x=X, y=Y, tooltip=[alt.Tooltip('날짜:T', format='%Y-%m-%d'), alt.Tooltip('v:Q', title='선행 P/E', format='.1f')])
    cap = pd.DataFrame({'날짜': [pd.Timestamp(vmod.REF_DAY)], 'v': [ref['캡처값']],
                        't': [f"캡처 {pd.Timestamp(vmod.REF_DAY):%m/%d}: {ref['캡처값']:.1f}x"]})
    capm = alt.Chart(cap).mark_point(color=BAND, size=70, strokeWidth=2, filled=False).encode(x=X, y=Y, tooltip=['t'])
    capt = alt.Chart(cap).mark_text(color=BAND, align='left', dx=8, dy=14, fontSize=10).encode(x=X, y=Y, text='t')
    lp = pd.DataFrame({'날짜': [last['날짜']], 'v': [last['선행PE']], 't': [f"{last['날짜']:%Y.%m.%d}: {last['선행PE']:.1f}x"]})
    dot = alt.Chart(lp).mark_circle(color=BAND, size=140, opacity=1).encode(x=X, y=Y)
    dtxt = alt.Chart(lp).mark_text(color=BAND, align='left', dx=10, dy=-10, fontWeight='bold', fontSize=12).encode(x=X, y=Y, text='t')
    return (rules + rtxt + line + capm + capt + dot + dtxt).properties(height=h_px)


def _disp_chart(d, s, h_px=330):
    d = d.copy()
    d['날짜'] = pd.to_datetime(d['날짜'])
    d['v'] = pd.to_numeric(d['이격도'], errors='coerce')
    d = d.dropna(subset=['v'])
    w = d.set_index('날짜')['v'].resample('W').last().dropna().rename_axis('날짜').reset_index()   # 그림은 주간(가볍게)
    w = pd.concat([w, d[['날짜', 'v']].tail(1)]).drop_duplicates('날짜', keep='last')
    x1 = d['날짜'].max() + pd.Timedelta(days=1100)
    X = alt.X('날짜:T', title=None, scale=alt.Scale(domain=[d['날짜'].min(), x1]), axis=alt.Axis(format="'%y", grid=False))
    Y = alt.Y('v:Q', title=None, scale=alt.Scale(domain=[25, 225]), axis=alt.Axis(values=list(range(25, 226, 25))))
    line = alt.Chart(w).mark_line(color=LINE, strokeWidth=1).encode(
        x=X, y=Y, tooltip=[alt.Tooltip('날짜:T', format='%Y-%m-%d'), alt.Tooltip('v:Q', title='이격도', format='.1f')])
    base = alt.Chart(pd.DataFrame({'v': [100]})).mark_rule(color='#9aa0a6', strokeWidth=1).encode(y=Y)
    rl = pd.DataFrame({'v': [s['+1σ'], s['평균'], s['-1σ']]})
    rules = alt.Chart(rl).mark_rule(color=BAND, strokeDash=[6, 4], strokeWidth=2).encode(y=Y)
    xe = d['날짜'].max() + pd.Timedelta(days=150)
    lab = pd.DataFrame({'날짜': [xe] * 4, 'v': [s['+1σ'] + 4, s['평균'] + 4, s['현재'] - 6, s['-1σ'] - 6],
                        't': [f"+1 표준편차: {s['+1σ']:.1f}", f"평균: {s['평균']:.1f}", f"현재: {s['현재']:.1f}",
                              f"-1 표준편차: {s['-1σ']:.1f}"],
                        'c': [BAND, BAND, '#202124', BAND]})
    txt = alt.Chart(lab).mark_text(align='left', fontWeight='bold', fontSize=11).encode(
        x=X, y=Y, text='t', color=alt.Color('c:N', scale=None))
    lp = d.tail(1)
    dot = alt.Chart(lp).mark_circle(color=BAND, size=140, opacity=1).encode(x=X, y=Y)
    return (base + rules + line + dot + txt).properties(height=h_px)


def _bar_chart(df, col, h_px=260):
    d = df[['지수', col]].dropna().rename(columns={col: 'v'})
    if not len(d):
        return None
    order = d.sort_values('v', ascending=False)['지수'].tolist()
    X = alt.X('지수:N', sort=order, title=None, axis=alt.Axis(labelAngle=0, labelFontSize=11, orient='bottom',
                                                            labelPadding=6, labelFontWeight='bold'))
    lo, hi = min(0.0, d['v'].min()), max(0.0, d['v'].max())
    pad = (hi - lo) * 0.12 or 1
    Y = alt.Y('v:Q', title=None, scale=alt.Scale(domain=[lo - pad, hi + pad], nice=False),
              axis=alt.Axis(grid=True, gridOpacity=0.35))
    b = alt.Chart(d).encode(x=X, y=Y)
    bars = b.mark_bar(color=NAVY, size=34).encode(tooltip=['지수', alt.Tooltip('v:Q', format='+.2f')])
    up = b.transform_filter('datum.v >= 0').mark_text(dy=-8, fontWeight='bold', fontSize=11).encode(text=alt.Text('v:Q', format='.1f'))
    dn = b.transform_filter('datum.v < 0').mark_text(dy=10, fontWeight='bold', fontSize=11).encode(text=alt.Text('v:Q', format='.1f'))
    zero = alt.Chart(pd.DataFrame({'v': [0]})).mark_rule(color='#9aa0a6').encode(y='v:Q')
    return (bars + zero + up + dn).properties(height=h_px)


def show(csv, raw, day):
    """csv(day, name) → DataFrame, raw('00_누적/파일') → bytes"""
    st.markdown('#### 지수 밸류·등락')

    # (가) 선행 P/E
    st.markdown('**✔ 미국 증시 — 12개월 선행 P/E**')
    b = raw('00_누적/00_지수선행PE.csv')
    pe = pd.read_csv(io.BytesIO(b), encoding='utf-8-sig') if b else pd.DataFrame()
    cols = st.columns(3, gap='medium')
    for c, nm in zip(cols, ['S&P500', '나스닥100', '필반지수']):
        h = pe[pe['지수'] == nm] if len(pe) else pe
        h = h.dropna(subset=['선행PE']) if len(h) else h
        ref = vmod.REF[nm]
        with c:
            if not len(h):
                st.markdown(f'**※ {nm} : P/E —**')
                st.caption(f'우리 계산 값이 아직 없습니다(07시 수집 뒤 생김). 캡처 {vmod.REF_DAY} {ref["캡처값"]}배.')
                continue
            v = float(h.iloc[-1]['선행PE'])
            st.markdown(f'**※ {nm} : P/E {v:.1f}배**')
            st.altair_chart(_pe_chart(nm, h, ref), width='stretch')
            r = h.iloc[-1]
            st.caption(f':gray[{r["날짜"]} 우리 계산 {v:.1f}배 · 구성 {int(r["받은 종목수"])}/{int(r["종목수"])}종목'
                       f'(지수 비중 {r["받은 비중(%)"]:.0f}%) · 캡처 {vmod.REF_DAY[5:].replace("-", "/")} {ref["캡처값"]}배. '
                       f'점선은 {vmod.REF_SRC}.]')
    st.caption(':gray[우리 값 = 구성종목마다 야후 애널리스트 평균 EPS(이번·다음 회계연도를 남은 기간 비율로 섞은 12개월 선행)로 '
               '구한 P/E를 지수 비중으로 합산(필반은 상위 3종목 12·10·8%, 나머지 4% 상한 근사). '
               '블룸버그와 컨센서스가 달라 1배 안팎 차이가 날 수 있습니다. 과거 컨센서스 이력은 무료로 없어 2026-11-11부터 쌓입니다. '
               'S&P500은 500종목이라 토요일에만 새로 계산합니다.]')

    # (나) 필반 200일 이격도
    st.markdown('**✔ 반도체 — 필반지수 200일 이동평균 이격도**')
    dd, live = csv(day, '필반이격도'), False
    if not len(dd):
        try:
            dd, live = _live_disp(), True
        except Exception as e:
            st.info(f'필반 이격도 자료를 받지 못했습니다: {type(e).__name__}')
    if len(dd):
        s = vmod.disp_stats(dd)
        st.markdown(f'**※ 필반지수 이격도: {s["현재"]:.1f}** (100 = 200일선)')
        st.altair_chart(_disp_chart(dd, s), width='stretch')
        st.caption(f':gray[이격도 = 종가 ÷ 200일 이동평균 × 100. 평균·표준편차는 {dd["날짜"].iloc[0]}~{dd["날짜"].iloc[-1]} '
                   f'매일 값으로 계산(야후 ^SOX, 최근은 네이버). 그림은 주 마지막 값.'
                   + (' 07시 파일이 없어 지금 야후에서 받은 값.' if live else '') + ']')

    # (다) 지수 등락
    vb, live = csv(day, '지수등락'), False
    if not len(vb):
        try:
            vb, live = _live_bars(), True
        except Exception as e:
            st.info(f'지수 등락 자료를 받지 못했습니다: {type(e).__name__}')
    if len(vb):
        for c_ in ('이달', '연초 이후'):
            vb[c_] = pd.to_numeric(vb[c_], errors='coerce')
        base = pd.to_datetime(vb['기준일'].dropna().max())
        for g, ttl in (('주요국', '증시 — 주요국'), ('미국', '증시 — 미국')):
            part = vb[vb['묶음'] == g]
            if not len(part):
                continue
            st.markdown(f'**✔ {ttl}**  \n:gray[(좌) {base.month}월({base.month}.{base.day}일), (우) 연초 이후, %]')
            l, r = st.columns(2, gap='large')
            for col, c_ in ((l, '이달'), (r, '연초 이후')):
                ch = _bar_chart(part, c_)
                if ch is not None:
                    col.altair_chart(ch, width='stretch')
        st.caption(':gray[이달 = 지난달 마지막 거래일 종가 대비, 연초 이후 = 작년 마지막 거래일 종가 대비. 지수마다 마지막 거래일이 '
                   '다를 수 있습니다(한국·일본은 하루 앞섬). 출처 야후(코스피·S&P500·나스닥·필반·니케이는 네이버 값 우선).'
                   + (' 07시 파일이 없어 지금 야후에서 받은 값.' if live else '') + ']')
