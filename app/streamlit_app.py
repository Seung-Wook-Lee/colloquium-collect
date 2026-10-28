# ======================================================================
# 콜로키움 화면 (스트림릿) — 매일 아침 수집한 자료를 웹 화면으로 본다
#   읽는 것  : 드라이브 '콜로키움 수집데이터/YYYYMMDD/' 의 CSV·PDF·점검 파일, '00_누적/00_가격이력.csv'
#              드라이브는 수집 프로그램과 같은 창구(drive.py, 비밀값 DRIVE_URL·DRIVE_TOKEN)로 읽는다.
#              PC에서 돌릴 때는 환경변수 COLLOQ_DATA 에 '콜로키움 수집데이터' 폴더 경로를 넣으면 그 폴더를 바로 읽는다.
#   화면     : 오늘 시장 / 종목 / 주봉 차트 / 수집 점검
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

t1, t2, t3, t4 = st.tabs(['오늘 시장', '종목', '주봉 차트', '수집 점검'])

# ---------------------------------------------------------------- 1. 오늘 시장
with t1:
    m = mac.set_index('항목') if len(mac) else pd.DataFrame()

    def mget(name, col='값'):
        try:
            return num(pd.Series([m.loc[name, col]])).iloc[0]
        except Exception:
            return None

    c = st.columns(4)
    tot = fg[fg['구분'] == '종합'].iloc[0] if len(fg) and (fg['구분'] == '종합').any() else None
    if tot is not None:
        s, prev = num(pd.Series([tot['점수'], tot['전일']]))
        c[0].metric('공포와 탐욕', f'{s:.1f}  {tot["판정"]}', f'{s - prev:+.1f} (전일 대비)' if pd.notna(prev) else None)
    if len(m) and '코스피 50일 이격도' in m.index:
        r = m.loc['코스피 50일 이격도']
        c[1].metric(f'{SIG_ICON.get(r["신호"], "")} 코스피 50일 이격도'.strip(), fmt(num(pd.Series([r['값']])).iloc[0], 1),
                    help=f'125 이상 과열 주의, 130 이상 과열. {r["비고"] if pd.notna(r["비고"]) else ""}')
        if pd.notna(r['표시']):
            c[1].caption(r['표시'])
    vix = risk[risk['항목'] == 'VIX'] if len(risk) else pd.DataFrame()
    if len(vix):
        v = vix.iloc[0]
        c[2].metric('VIX', fmt(num(pd.Series([v['값']])).iloc[0]),
                    f'{num(pd.Series([v["값"]])).iloc[0] - num(pd.Series([v["1주 전"]])).iloc[0]:+.2f} (1주 전 대비)',
                    delta_color='inverse')
    if mget('미국 10년') is not None:
        r = m.loc['미국 10년']
        c[3].metric(f'{SIG_ICON.get(r["신호"], "")} 미국 10년'.strip(), fmt(mget('미국 10년'), 3, '%'),
                    f'{mget("미국 10년", "1달"):+.2f}%p (1달)' if pd.notna(mget('미국 10년', '1달')) else None,
                    delta_color='inverse')

    st.subheader('지수')
    if len(mac):
        ix = mac[(mac['구분'] == '지수') & (mac['항목'] != '코스피 50일 이격도')].copy()
        ix = ix[['항목', '값', '기준일', 'YTD', '1달', '최고 대비(%)', '표시', '의장 기준(참고)']]
        for k in ['값', 'YTD', '1달', '최고 대비(%)']:
            ix[k] = num(ix[k])
        ix[['표시', '의장 기준(참고)']] = ix[['표시', '의장 기준(참고)']].fillna('')
        ix = ix.rename(columns={'YTD': 'YTD(%)', '1달': '1달(%)', '최고 대비(%)': '사상 최고 대비(%)', '의장 기준(참고)': '의장 기준'})
        st.dataframe(
            ix.style.map(updown, subset=['YTD(%)', '1달(%)']).format(
                {'값': '{:,.2f}', 'YTD(%)': '{:+.1f}', '1달(%)': '{:+.1f}', '사상 최고 대비(%)': '{:+.1f}'}, na_rep='—'),
            hide_index=True, width='stretch')

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
                               delta_color='off' if grp in ('환율', '원자재') else 'inverse', help=note or None)

    for grp, dec in [('환율', 2), ('금리', 3), ('물가', 2), ('성장·고용', 2), ('원자재', 1)]:
        st.subheader(grp)
        tiles(grp, dec)
    st.caption('🔴🟠🟢 표시는 의장 기준이 있는 항목에만 붙습니다. 칸 위에 마우스를 올리면 기준과 기준일이 보입니다. '
               '월간 지표(물가·고용)의 1달은 직전 발표 대비입니다.')

    st.subheader('공포와 탐욕 — 7개 지표')
    if len(fg):
        f7 = fg[fg['구분'] == '지표'][[x for x in ['지표', '점수', '판정', '해석'] if x in fg]].copy()
        f7['점수'] = num(f7['점수'])
        st.dataframe(f7, hide_index=True, width='stretch',
                     column_config={'점수': st.column_config.ProgressColumn('점수', min_value=0, max_value=100, format='%.1f'),
                                    '해석': st.column_config.TextColumn('해석', width='large')})

    st.subheader('리스크')
    if len(risk):
        rk = risk.copy()
        rk['신호'] = rk['신호'].map(lambda x: f'{SIG_ICON[x]} {x}' if x in SIG_ICON else '')
        rk['기준·메모'] = rk[['표시', '의장 기준(참고)', '일반 기준(참고)']].bfill(axis=1).iloc[:, 0]
        rk = rk[['구분', '항목', '값', '단위', '1주 전', '1달 전', '기준일', '신호', '기준·메모', '비고']]
        rk[['단위', '기준일', '기준·메모', '비고']] = rk[['단위', '기준일', '기준·메모', '비고']].fillna('')
        for k in ['값', '1주 전', '1달 전']:
            rk[k] = num(rk[k])
        st.dataframe(rk, hide_index=True, width='stretch', height=38 * (len(rk) + 1),
                     column_config={'기준·메모': st.column_config.TextColumn(width='large')})

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
