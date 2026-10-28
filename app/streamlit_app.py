# ======================================================================
# 콜로키움 화면 (스트림릿) — 매일 아침 수집한 자료를 웹 화면으로 본다
#   읽는 것  : 드라이브 '콜로키움 수집데이터/YYYYMMDD/' 의 CSV·PDF·점검 파일, '00_누적/00_가격이력.csv'
#              드라이브는 수집 프로그램과 같은 창구(drive.py, 비밀값 DRIVE_URL·DRIVE_TOKEN)로 읽는다.
#              PC에서 돌릴 때는 환경변수 COLLOQ_DATA 에 '콜로키움 수집데이터' 폴더 경로를 넣으면 그 폴더를 바로 읽는다.
#   화면     : 오늘 시장 / 회의록 / 종목 / 주봉 차트 / 수집 점검
#              회의록은 드라이브 '콜로키움/오늘의 시장해석/' 의 txt(회의록_YYYYMMDD.txt 등)를 그대로 보여 준다.
#              색과 문구는 수집 블록이 적은 '신호'·'표시' 칸(의장 기준)만 따른다. 화면이 따로 판정하지 않는다.
#   실행     : streamlit run app/streamlit_app.py
# ======================================================================
import io, os, sys, datetime as dt
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title='콜로키움', page_icon='📈', layout='wide')

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:                                        # 스트림릿 클라우드: Secrets → 환경변수 (drive.py가 읽는다)
    for k in ('DRIVE_URL', 'DRIVE_TOKEN', 'COLLOQ_DATA'):
        if k in st.secrets and not os.environ.get(k):
            os.environ[k] = str(st.secrets[k])
except Exception:
    pass
import drive  # noqa: E402

D_DATA = '콜로키움 수집데이터'
D_MEET = '콜로키움/오늘의 시장해석'          # 회의록·시장해석 txt
LOCAL = os.environ.get('COLLOQ_DATA', '').strip()
KST = dt.timezone(dt.timedelta(hours=9))
SIG_ICON = {'빨강': '🔴', '주황': '🟠', '초록': '🟢'}
UP, DN = '#d32f2f', '#1565c0'                 # 한국식: 빨강 상승, 파랑 하락


# ---------------------------------------------------------------- 자료 읽기
def _raw(rel):
    """'20261028/20261028_시세.csv' 같은 상대 경로 → bytes (없으면 None)"""
    if LOCAL:
        p = Path(LOCAL) / rel
        return p.read_bytes() if p.exists() else None
    return drive.get(f'{D_DATA}/{rel}')


@st.cache_data(ttl=600, show_spinner=False)
def days(n=10):
    """오늘부터 거꾸로 n일 중 자료 폴더가 있는 날짜(YYYYMMDD) 목록"""
    out, today = [], dt.datetime.now(KST).date()
    for i in range(n):
        d = (today - dt.timedelta(days=i)).strftime('%Y%m%d')
        ok = (Path(LOCAL) / d).is_dir() if LOCAL else bool(drive.ls(f'{D_DATA}/{d}'))
        if ok:
            out.append(d)
    return out


@st.cache_data(ttl=600, show_spinner=False)
def csv(day, name):
    b = _raw(f'{day}/{day}_{name}.csv')
    return pd.read_csv(io.BytesIO(b), encoding='utf-8-sig', dtype={'코드': str}) if b else pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def blob(day, name):
    return _raw(f'{day}/{day}_{name}')


@st.cache_data(ttl=600, show_spinner=False)
def notes():
    """회의록 폴더의 txt 이름 목록 (최근 것 먼저)"""
    if LOCAL:
        return []
    names = [f['name'] for f in drive.ls(D_MEET) if f['name'].lower().endswith('.txt')]
    return sorted(names, key=lambda n: (''.join(ch for ch in n if ch.isdigit())[:8], n), reverse=True)


@st.cache_data(ttl=600, show_spinner=False)
def note(name):
    b = drive.get(f'{D_MEET}/{name}')
    return b.decode('utf-8', errors='replace') if b else ''


@st.cache_data(ttl=6 * 3600, show_spinner='가격 이력 불러오는 중…')
def prices():
    b = _raw('00_누적/00_가격이력.csv')
    if not b:
        return pd.DataFrame()
    p = pd.read_csv(io.BytesIO(b), encoding='utf-8-sig', usecols=['날짜', '티커', '수정종가', '종가'], parse_dates=['날짜'])
    p['가격'] = p['수정종가'].fillna(p['종가'])
    return p[['날짜', '티커', '가격']]


def num(s):
    return pd.to_numeric(s, errors='coerce')


def updown(v):
    if pd.isna(v) or v == 0:
        return ''
    return f'color:{UP}' if v > 0 else f'color:{DN}'


def fmt(v, d=2, unit=''):
    return '—' if v is None or pd.isna(v) else f'{v:,.{d}f}{unit}'


# ---------------------------------------------------------------- 사이드바
if not LOCAL and not drive.ready():
    st.error('드라이브 창구 비밀값(DRIVE_URL·DRIVE_TOKEN)이 없습니다. 스트림릿 Secrets에 넣어 주세요.')
    st.stop()

with st.sidebar:
    st.title('콜로키움')
    with st.spinner('날짜 확인 중…'):
        found = days()
    if not found:
        st.error('최근 10일 안에 수집 자료가 없습니다.')
        st.stop()
    DAY = st.selectbox('날짜', found, format_func=lambda d: f'{d[:4]}-{d[4:6]}-{d[6:]}')
    if st.button('새로 불러오기', width='stretch'):
        st.cache_data.clear()
        st.rerun()
    pdf = blob(DAY, '브리핑.pdf')
    if pdf:
        st.download_button('브리핑 PDF 받기', pdf, file_name=f'{DAY}_브리핑.pdf', mime='application/pdf',
                           width='stretch')
    st.caption('자료: 야후, 한국투자증권, CNN, FRED, 뉴욕연준, 일본 재무성, DART, SEC\n\n'
               '색과 문구는 의장 기준을 옮긴 것이며 투자 판단이 아닙니다.')

fg, mac, risk = csv(DAY, '공포탐욕'), csv(DAY, '매크로'), csv(DAY, '리스크')
price, val = csv(DAY, '시세'), csv(DAY, '밸류에이션')
dart, secr = csv(DAY, 'DART실적'), csv(DAY, 'SEC실적')
trend_df = csv(DAY, '추이')
FG_BANDS = [(0, 25, '#c0392b', '극단적 공포'), (25, 45, '#e67e22', '공포'), (45, 55, '#9aa0a6', '중립'),
            (55, 75, '#7cb342', '탐욕'), (75, 100, '#2e7d32', '극단적 탐욕')]


def series(kind, name):
    """추이 파일에서 한 항목의 시계열 (없으면 빈 Series)"""
    if not len(trend_df):
        return pd.Series(dtype=float)
    t = trend_df[(trend_df['구분'] == kind) & (trend_df['항목'] == name)]
    return pd.Series(num(t['값']).values, index=pd.to_datetime(t['날짜'])).sort_index().dropna()


def spark(kind, name):
    s = series(kind, name)
    return s.tolist() if len(s) >= 2 else None


def fg_color(v):
    return next(c for lo, hi, c, _ in FG_BANDS if v < hi or hi == 100)


def fg_label(v):
    return next(t for lo, hi, _, t in FG_BANDS if v < hi or hi == 100)


def gauge_svg(score, label):
    import math
    cx, cy, r = 150, 140, 115
    pt = lambda val, rr: (cx + rr * math.cos(math.pi * (1 - val / 100)), cy - rr * math.sin(math.pi * (1 - val / 100)))
    segs = ''
    for lo, hi, c, _ in FG_BANDS:
        (x1, y1), (x2, y2) = pt(lo, r), pt(hi, r)
        segs += f'<path d="M{x1:.1f},{y1:.1f} A{r},{r} 0 0 1 {x2:.1f},{y2:.1f}" stroke="{c}" stroke-width="22" fill="none"/>'
    ticks = ''.join(f'<text x="{pt(t, r + 22)[0]:.1f}" y="{pt(t, r + 22)[1] + 4:.1f}" font-size="11" fill="#6b7280" '
                    f'text-anchor="middle">{t}</text>' for t in (0, 25, 45, 55, 75, 100))
    nx, ny = pt(score, r - 30)
    col = fg_color(score)
    import base64
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 175">{segs}{ticks}'
           f'<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="#1d2330" stroke-width="4" stroke-linecap="round"/>'
           f'<circle cx="{cx}" cy="{cy}" r="7" fill="#1d2330"/></svg>')
    b64 = base64.b64encode(svg.encode()).decode()   # st.html은 svg 태그를 지우므로 그림으로 넣는다
    return (f'<div style="text-align:center"><img src="data:image/svg+xml;base64,{b64}" style="width:100%;max-width:340px">'
            f'<div style="font-size:44px;font-weight:800;line-height:1;margin-top:-6px;color:{col}">{score:.1f}</div>'
            f'<div style="font-size:18px;font-weight:700;color:{col}">{label}</div></div>')


def score_bar(score, label):
    if pd.isna(score):
        return '<div style="color:#6b7280">—</div>'
    col = fg_color(score)
    return (f'<div style="display:flex;align-items:center;gap:8px"><div style="flex:1;height:10px;background:#eceff1;'
            f'border-radius:5px;overflow:hidden"><div style="width:{score:.0f}%;height:100%;background:{col}"></div></div>'
            f'<b style="font-variant-numeric:tabular-nums">{score:.1f}</b>'
            f'<span style="color:{col};font-weight:600;font-size:13px">{label}</span></div>')


def fg_chart(h):
    d = h.rename('점수').rename_axis('날짜').reset_index()
    bands = pd.DataFrame([{'lo': lo, 'hi': hi, 'c': c, '구간': n} for lo, hi, c, n in FG_BANDS])
    x0, x1 = d['날짜'].min(), d['날짜'].max()
    band = alt.Chart(bands).mark_rect(opacity=0.12).encode(
        y=alt.Y('lo:Q', scale=alt.Scale(domain=[0, 100]), title=None), y2='hi:Q',
        color=alt.Color('c:N', scale=None), tooltip=[alt.Tooltip('구간:N')]).transform_calculate(
        x0=f'datetime({x0.year},{x0.month - 1},{x0.day})', x1=f'datetime({x1.year},{x1.month - 1},{x1.day})').encode(
        x=alt.X('x0:T', title=None), x2='x1:T')
    rule = alt.Chart(pd.DataFrame({'y': [70]})).mark_rule(strokeDash=[4, 4], color='#6b7280').encode(y='y:Q')
    line = alt.Chart(d).mark_line(strokeWidth=2, color='#1d2330').encode(
        x=alt.X('날짜:T', axis=alt.Axis(format='%m-%d', grid=False)), y=alt.Y('점수:Q', scale=alt.Scale(domain=[0, 100])))
    hover = alt.selection_point(fields=['날짜'], nearest=True, on='pointerover', empty=False)
    pts = alt.Chart(d).mark_point(size=70, filled=True, color='#1d2330').encode(
        x='날짜:T', y='점수:Q', opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip('날짜:T', format='%Y-%m-%d'), alt.Tooltip('점수:Q', format='.1f')]).add_params(hover)
    return (band + rule + line + pts).properties(height=300)


t1, t5, t2, t3, t4 = st.tabs(['오늘 시장', '회의록', '종목', '주봉 차트', '수집 점검'])

# ---------------------------------------------------------------- 1. 오늘 시장
with t1:
    m = mac.set_index('항목') if len(mac) else pd.DataFrame()

    def mget(name, col='값'):
        try:
            return num(pd.Series([m.loc[name, col]])).iloc[0]
        except Exception:
            return None

    # ---- 공포와 탐욕 (맨 위, 가장 자세히)
    st.subheader('공포와 탐욕')
    tot = fg[fg['구분'] == '종합'].iloc[0] if len(fg) and (fg['구분'] == '종합').any() else None
    if tot is None:
        st.info('이 날짜의 공포탐욕 자료가 없습니다.')
    else:
        s = num(pd.Series([tot['점수']])).iloc[0]
        left, right = st.columns([1, 2], gap='large')
        with left:
            st.html(gauge_svg(s, tot['판정']))
            trs = ''
            for k in ['전일', '1주 전', '1개월 전', '1년 전']:
                pv = num(pd.Series([tot.get(k)])).iloc[0]
                if pd.isna(pv):
                    continue
                dv = s - pv
                dc = '#c0392b' if dv < 0 else '#2e7d32'
                trs += (f'<tr><td style="padding:4px 8px;color:#6b7280">{k}</td>'
                        f'<td style="padding:4px 8px;text-align:right;font-weight:700;color:{fg_color(pv)}">{pv:.1f}</td>'
                        f'<td style="padding:4px 8px;color:{fg_color(pv)};font-size:13px">{fg_label(pv)}</td>'
                        f'<td style="padding:4px 8px;text-align:right;color:{dc}">지금 {dv:+.1f}</td></tr>')
            if trs:
                st.html('<table style="width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;'
                        f'font-size:15px">{trs}</table>')
        with right:
            fh = series('공포탐욕', 'Fear & Greed Index')
            if len(fh):
                span = st.segmented_control('기간', ['1달', '3달', '6달', '1년'], default='3달', key='fgspan',
                                            label_visibility='collapsed')
                months = {'1달': 1, '3달': 3, '6달': 6, '1년': 12}[span or '3달']
                st.altair_chart(fg_chart(fh[fh.index >= fh.index[-1] - pd.DateOffset(months=months)]), width='stretch')
                st.caption(f'CNN 공포탐욕 종합 점수 추이. 띠 색: 0–25 극단적 공포 · 25–45 공포 · 45–55 중립 · 55–75 탐욕 · 75–100 극단적 탐욕. '
                           f'점선 70 = 의장 기준(70 넘으면 현금↑). 최근 1년 최저 {fh.min():.1f}({fh.idxmin():%Y-%m-%d}), 최고 {fh.max():.1f}({fh.idxmax():%Y-%m-%d}).')
            else:
                st.caption('추이 자료는 다음 수집부터 쌓입니다.')

        st.markdown('**7개 지표** — 점수(0–100)와 원천값 최근 1달')
        f7 = fg[fg['구분'] == '지표']
        cols = st.columns(4)
        for i, (_, r) in enumerate(f7.iterrows()):
            sc = num(pd.Series([r['점수']])).iloc[0]
            raw = series('공포탐욕', r['지표'])
            with cols[i % 4].container(border=True):
                st.markdown(f'**{r["지표"].split(". ", 1)[-1]}**')
                st.html(score_bar(sc, r['판정']))
                if len(raw):
                    st.metric(r.get('원천값 설명') or '원천값', fmt(raw.iloc[-1], 2), chart_data=raw.tolist(), help=r.get('원천값 설명'),
                              label_visibility='visible')
                if pd.notna(r.get('해석')):
                    st.caption(r['해석'])

    st.divider()
    c = st.columns(3)
    if len(m) and '코스피 50일 이격도' in m.index:
        r = m.loc['코스피 50일 이격도']
        c[0].metric(f'{SIG_ICON.get(r["신호"], "")} 코스피 50일 이격도'.strip(), fmt(num(pd.Series([r['값']])).iloc[0], 1),
                    chart_data=spark('매크로', '코스피 50일 이격도'),
                    help=f'125 이상 과열 주의, 130 이상 과열. {r["비고"] if pd.notna(r["비고"]) else ""}')
        if pd.notna(r['표시']):
            c[0].caption(r['표시'])
    vix = risk[risk['항목'] == 'VIX'] if len(risk) else pd.DataFrame()
    if len(vix):
        v = vix.iloc[0]
        c[1].metric('VIX', fmt(num(pd.Series([v['값']])).iloc[0]),
                    f'{num(pd.Series([v["값"]])).iloc[0] - num(pd.Series([v["1주 전"]])).iloc[0]:+.2f} (1주 전 대비)',
                    delta_color='inverse', chart_data=spark('리스크', 'VIX'))
    if mget('미국 10년') is not None:
        r = m.loc['미국 10년']
        c[2].metric(f'{SIG_ICON.get(r["신호"], "")} 미국 10년'.strip(), fmt(mget('미국 10년'), 3, '%'),
                    f'{mget("미국 10년", "1달"):+.2f}%p (1달)' if pd.notna(mget('미국 10년', '1달')) else None,
                    delta_color='inverse', chart_data=spark('매크로', '미국 10년'))

    st.subheader('지수')
    if len(mac):
        ix = mac[(mac['구분'] == '지수') & (mac['항목'] != '코스피 50일 이격도')].copy()
        ix['최근 1달'] = ix['항목'].map(lambda k: spark('매크로', k) or None)
        ix = ix[['항목', '값', '최근 1달', '기준일', 'YTD', '1달', '최고 대비(%)', '표시', '의장 기준(참고)']]
        for k in ['값', 'YTD', '1달', '최고 대비(%)']:
            ix[k] = num(ix[k])
        ix[['표시', '의장 기준(참고)']] = ix[['표시', '의장 기준(참고)']].fillna('')
        ix = ix.rename(columns={'YTD': 'YTD(%)', '1달': '1달(%)', '최고 대비(%)': '사상 최고 대비(%)', '의장 기준(참고)': '의장 기준'})
        st.dataframe(
            ix.style.map(updown, subset=['YTD(%)', '1달(%)']).format(
                {'값': '{:,.2f}', 'YTD(%)': '{:+.1f}', '1달(%)': '{:+.1f}', '사상 최고 대비(%)': '{:+.1f}'}, na_rep='—'),
            hide_index=True, width='stretch',
            column_config={'최근 1달': st.column_config.LineChartColumn('최근 1달', width='small')})

    def tiles(grp, dec=2):
        g = mac[mac['구분'] == grp] if len(mac) else pd.DataFrame()
        cols = st.columns(4)
        for i, (_, r) in enumerate(g.iterrows()):
            v, unit = num(pd.Series([r['값']])).iloc[0], r['단위'] if r['단위'] in ('%', '천명') else ''
            if r['항목'] == '기준금리(범위)' and pd.notna(r['비고']):
                shown = r['비고']
            else:
                shown = fmt(v, 0 if unit == '천명' else dec, unit)
            pp = r['변화 단위'] == '%p'
            d1, ytd = num(pd.Series([r['1달'], r['YTD']]))
            delta = f'{d1:+.{2 if pp else 1}f}{r["변화 단위"]} (1달)' if pd.notna(d1) else None
            note = ' · '.join(str(x) for x in [r['표시'], r['비고'] if r['항목'] != '기준금리(범위)' else None,
                                               f'YTD {ytd:+.{2 if pp else 1}f}{r["변화 단위"]}' if pd.notna(ytd) else None,
                                               f'기준일 {r["기준일"]}'] if pd.notna(x) and x)
            cols[i % 4].metric(f'{SIG_ICON.get(r["신호"], "")} {r["항목"]}'.strip(), shown, delta,
                               delta_color='off' if grp in ('환율', '원자재') else 'inverse', help=note or None,
                               chart_data=spark('매크로', r['항목']))

    for grp, dec in [('환율', 2), ('금리', 3), ('물가', 2), ('성장·고용', 2), ('원자재', 1)]:
        st.subheader(grp)
        tiles(grp, dec)
    st.caption('작은 선은 최근 1달 값입니다(월간·주간 지표는 최근 13번 발표). 🔴🟠🟢 표시는 의장 기준이 있는 항목에만 붙습니다. '
               '칸 위에 마우스를 올리면 기준과 기준일이 보입니다. 월간 지표(물가·고용)의 1달은 직전 발표 대비입니다.')

    st.subheader('리스크')
    if len(risk):
        rk = risk.copy()
        rk['신호'] = rk['신호'].map(lambda x: f'{SIG_ICON[x]} {x}' if x in SIG_ICON else '')
        rk['기준·메모'] = rk[['표시', '의장 기준(참고)', '일반 기준(참고)']].bfill(axis=1).iloc[:, 0]
        rk['최근 1달'] = rk['항목'].map(lambda k: spark('리스크', k) or None)
        rk = rk[['구분', '항목', '값', '최근 1달', '단위', '1주 전', '1달 전', '기준일', '신호', '기준·메모', '비고']]
        rk[['단위', '기준일', '기준·메모', '비고']] = rk[['단위', '기준일', '기준·메모', '비고']].fillna('')
        for k in ['값', '1주 전', '1달 전']:
            rk[k] = num(rk[k])
        st.dataframe(rk, hide_index=True, width='stretch', height=38 * (len(rk) + 1),
                     column_config={'기준·메모': st.column_config.TextColumn(width='large'),
                                    '최근 1달': st.column_config.LineChartColumn('최근 1달', width='small')})

# ---------------------------------------------------------------- 2. 종목
def stock_table():
    if not len(price):
        return pd.DataFrame()
    t = price[['번호', '정식 종목명', '시장', '구분', '보유/관심', 'yfinance 티커', '종가', '등락률(%)']].copy()
    if len(val):
        v = val.set_index('번호')
        t['52주 고점 대비(%)'] = (num(t['종가']) / num(t['번호'].map(v['52주 고가'])) - 1) * 100
        t['한투 PER'] = num(t['번호'].map(v['PER']))
        t['PER 선행'] = num(t['번호'].map(v['선행 PER(야후)'])) if '선행 PER(야후)' in v else float('nan')
        t['PBR'] = num(t['번호'].map(v['PBR']))
    fin = pd.concat([x for x in (dart, secr) if len(x)], ignore_index=True) if len(dart) or len(secr) else pd.DataFrame()
    if len(fin):
        f = fin.set_index('번호')
        t['PER TTM'] = num(t['번호'].map(f['PER TTM(시총÷순이익)']))
        t['PER 연환산'] = num(t['번호'].map(f['PER 연환산(최근분기×4)'])) if 'PER 연환산(최근분기×4)' in f else float('nan')
        t['ROE(%)'] = num(t['번호'].map(f['ROE TTM(%)']))
    if '한투 PER' in t:   # 실적 PER이 없는 개별주는 한투 값(직전 연간)으로 채운다
        t['PER TTM'] = t.get('PER TTM', pd.Series(index=t.index, dtype=float)).fillna(
            t['한투 PER'].where(t['구분'] == '개별주'))
    t['종가'] = num(t['종가'])
    t['등락률(%)'] = num(t['등락률(%)'])
    return t


with t5:
    if LOCAL:
        st.info('PC 모드에서는 회의록을 읽지 않습니다. 회의록은 드라이브 "콜로키움/오늘의 시장해석" 폴더에 있습니다.')
    else:
        allnotes = notes()
        mine = [n for n in allnotes if DAY in n]
        if not allnotes:
            st.info('아직 회의록이 없습니다. 7:30 회의가 끝나면 이 폴더에 올라옵니다.')
        else:
            if not mine:
                st.caption(f'{DAY[:4]}-{DAY[4:6]}-{DAY[6:]} 회의록은 아직 없습니다. 아래에서 지난 회의록을 고르세요.')
            pick = st.selectbox('회의록', allnotes, index=allnotes.index(mine[0]) if mine else 0,
                                label_visibility='collapsed')
            with st.container(border=True):
                st.markdown(note(pick).replace('~', '\\~'))
            st.caption('드라이브 "콜로키움/오늘의 시장해석" 폴더의 txt를 그대로 보여 줍니다. 회의가 끝나면 회의록_YYYYMMDD.txt로 올라옵니다.')

with t2:
    tb = stock_table()
    if not len(tb):
        st.info('이 날짜의 시세 파일이 없습니다.')
    else:
        a, b, c = st.columns([1, 2, 2])
        kind = a.radio('보유/관심', ['전체', '보유', '관심'], horizontal=True)
        mk = b.multiselect('시장', sorted(tb['시장'].unique()), placeholder='전체')
        gb = c.multiselect('구분', sorted(tb['구분'].unique()), placeholder='전체')
        v = tb
        if kind != '전체':
            v = v[v['보유/관심'] == kind]
        if mk:
            v = v[v['시장'].isin(mk)]
        if gb:
            v = v[v['구분'].isin(gb)]
        show = [x for x in ['번호', '정식 종목명', '시장', '구분', '보유/관심', '종가', '등락률(%)', '52주 고점 대비(%)',
                            'PER TTM', 'PER 연환산', 'PER 선행', 'PBR', 'ROE(%)'] if x in v]
        st.dataframe(
            v[show].style.map(updown, subset=[x for x in ['등락률(%)', '52주 고점 대비(%)'] if x in show]).format(
                {'종가': '{:,.2f}', '등락률(%)': '{:+.2f}', '52주 고점 대비(%)': '{:+.1f}', 'PER TTM': '{:,.1f}',
                 'PER 연환산': '{:,.1f}', 'PER 선행': '{:,.1f}', 'PBR': '{:,.2f}', 'ROE(%)': '{:,.1f}'}, na_rep='—'),
            hide_index=True, width='stretch', height=min(38 * (len(v) + 1), 900))
        st.caption(f'{len(v)}종목. PER TTM = 최근 4분기 순이익(DART·SEC), 없으면 한투(직전 연간). PER 연환산 = 최근 한 분기 × 4. '
                   'PER 선행 = 야후 애널리스트 예상(한국 종목은 참고). 음수 PER은 적자입니다. 표 머리를 누르면 정렬됩니다.')

# ---------------------------------------------------------------- 3. 주봉 차트
with t3:
    tb = stock_table()
    if not len(tb):
        st.info('이 날짜의 시세 파일이 없습니다.')
    else:
        names = (tb['번호'] + ' ' + tb['정식 종목명']).tolist()
        a, b = st.columns([3, 1])
        pick = a.selectbox('종목', names)
        years = b.select_slider('기간', options=[1, 2, 3, 5], value=3, format_func=lambda y: f'{y}년')
        row = tb.iloc[names.index(pick)]
        p = prices()
        s = p[p['티커'] == row['yfinance 티커']].set_index('날짜')['가격'].sort_index() if len(p) else pd.Series(dtype=float)
        if not len(s):
            st.info('가격 이력이 없습니다.')
        else:
            w = s.resample('W-FRI').last().dropna().to_frame('주봉 종가')
            w['20주선'] = w['주봉 종가'].rolling(20).mean()
            w['60주선'] = w['주봉 종가'].rolling(60).mean()
            last = w.iloc[-1]
            c = st.columns(4)
            dec = 0 if row['시장'] in ('한국', '일본') else 2
            c[0].metric('최근 주봉 종가', fmt(last['주봉 종가'], dec))
            for i, k in [(1, '20주선'), (2, '60주선')]:
                gap = (last['주봉 종가'] / last[k] - 1) * 100 if pd.notna(last[k]) else None
                c[i].metric(f'{k} 대비', fmt(gap, 1, '%'), help=f'{k} {fmt(last[k], dec)}')
            hi = s[s.index >= s.index[-1] - pd.Timedelta(days=365)].max()
            c[3].metric('52주 고점 대비', fmt((s.iloc[-1] / hi - 1) * 100, 1, '%'))

            w = w[w.index >= w.index[-1] - pd.DateOffset(years=years)].reset_index().rename(columns={'날짜': '주'})
            long = w.melt('주', var_name='선', value_name='가격').dropna()
            color = alt.Color('선:N', scale=alt.Scale(domain=['주봉 종가', '20주선', '60주선'],
                                                      range=['#2a78d6', '#eb6834', '#1baf7a']),
                              legend=alt.Legend(orient='top', title=None))
            base = alt.Chart(long).encode(x=alt.X('주:T', title=None, axis=alt.Axis(format='%Y-%m', grid=False)),
                                          y=alt.Y('가격:Q', title=None, scale=alt.Scale(zero=False),
                                                  axis=alt.Axis(gridOpacity=0.4)),
                                          color=color)
            lines = base.mark_line(strokeWidth=2)
            hover = alt.selection_point(fields=['주'], nearest=True, on='pointerover', empty=False)
            pts = base.mark_point(size=60, filled=True).encode(
                opacity=alt.condition(hover, alt.value(1), alt.value(0)),
                tooltip=[alt.Tooltip('주:T', title='주', format='%Y-%m-%d'), alt.Tooltip('선:N', title='선'),
                         alt.Tooltip('가격:Q', title='가격', format=',.2f')]).add_params(hover)
            rule = alt.Chart(long).mark_rule(color='#9aa0a6').encode(x='주:T').transform_filter(hover)
            st.altair_chart((lines + pts + rule).properties(height=420), width='stretch')
            st.caption('수정종가(배당·분할 반영)의 주간 마지막 값과 20주·60주 이동평균입니다. 선 위에 마우스를 올리면 값이 보입니다.')
            with st.expander('표로 보기'):
                st.dataframe(w.sort_values('주', ascending=False), hide_index=True, width='stretch')

# ---------------------------------------------------------------- 4. 수집 점검
with t4:
    txt = blob(DAY, '수집점검.txt')
    if txt:
        st.code(txt.decode('utf-8', errors='replace'), language=None, wrap_lines=True)
    else:
        st.info('이 날짜의 점검 파일이 없습니다.')
