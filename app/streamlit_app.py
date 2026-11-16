# ======================================================================
# 콜로키움 화면 (스트림릿) — 매일 아침 수집한 자료를 웹 화면으로 본다
#   읽는 것  : 드라이브 '콜로키움 수집데이터/YYYYMMDD/' 의 CSV·PDF·점검 파일, '00_누적/00_가격이력.csv'
#              드라이브는 수집 프로그램과 같은 창구(drive.py, 비밀값 DRIVE_URL·DRIVE_TOKEN)로 읽는다.
#              PC에서 돌릴 때는 환경변수 COLLOQ_DATA 에 '콜로키움 수집데이터' 폴더 경로를 넣으면 그 폴더를 바로 읽는다.
#   화면     : 오늘 시장(맨 위 이번 주 일정·간밤 뉴스) / 회의록 / 종목 / 섹터 순환 / 주봉 차트 / 수집 점검
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
from interp import interpret, section_note  # noqa: E402

D_DATA = '콜로키움 수집데이터'
D_MEET = '콜로키움/오늘의 시장해석'          # 회의록·시장해석 txt
LOCAL = os.environ.get('COLLOQ_DATA', '').strip()
KST = dt.timezone(dt.timedelta(hours=9))
SIG_ICON = {'빨강': '🔴', '주황': '🟠', '초록': '🟢'}
UP, DN = '#1e8e3e', '#d32f2f'                 # 미국식: 초록 상승, 빨강 하락 (2026-10-28 의장)


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



@st.cache_data(ttl=6 * 3600, show_spinner='수급 이력 불러오는 중…')
def flowpos_hist():
    """미스 시타델 수급·포지셔닝 일별 이력 (00_누적/00_수급포지셔닝_이력.csv, 블록 9-수급)"""
    b = _raw('00_누적/00_수급포지셔닝_이력.csv')
    if not b:
        return pd.DataFrame()
    return pd.read_csv(io.BytesIO(b), encoding='utf-8-sig', parse_dates=['날짜']).set_index('날짜')


@st.cache_data(ttl=6 * 3600, show_spinner='ETF 좌수 이력 불러오는 중…')
def flow_hist():
    """ETF 좌수 일별 이력 (00_누적/00_ETF좌수이력.csv, SPDR 펀드는 공식 1년치)"""
    b = _raw('00_누적/00_ETF좌수이력.csv')
    if not b:
        return pd.DataFrame()
    h = pd.read_csv(io.BytesIO(b), encoding='utf-8-sig', dtype={'수집일': str, '코드': str})
    h = h[h['상장좌수'].notna()].copy()
    h['날짜'] = pd.to_datetime(h['수집일'], format='%Y%m%d', errors='coerce')
    us = h['시장'] == '미국'
    nm = h['이름'].astype(str) if '이름' in h else h['코드']
    h['이름'] = nm.where(~us, h['코드'] + ' ' + h['섹터/테마'].fillna('').astype(str))
    return h.dropna(subset=['날짜'])

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
    brief = blob(DAY, '브리핑.txt')
    if brief:
        st.download_button('브리핑 txt 받기', brief, file_name=f'{DAY}_브리핑.txt', mime='text/plain',
                           width='stretch')
    st.caption('자료: 야후, 한국투자증권, CNN, 연합뉴스, CNBC, FRED, 뉴욕연준, 일본 재무성, DART, SEC\n\n'
               '색과 문구는 의장 기준을 옮긴 것이며 투자 판단이 아닙니다.')

fg, mac, risk = csv(DAY, '공포탐욕'), csv(DAY, '매크로'), csv(DAY, '리스크')
price, val = csv(DAY, '시세'), csv(DAY, '밸류에이션')
dart, secr = csv(DAY, 'DART실적'), csv(DAY, 'SEC실적')
trend_df = csv(DAY, '추이')
sched_df, news_df = csv(DAY, '일정'), csv(DAY, '뉴스')
NEWS_DROP = (r'칼럼|인터뷰|기고|사설|르포|포토|화보|\[인사\]|부고|브랜드평판|브랜드 평판|ESG 브랜드|사회공헌|사회적 가치|'
             r'개막전|스포츠|\d+대\d+ |봉사|후원|기부|캠페인|시상식|축제|사진=|기사와 직접|^["“].*["”]$')
NEWS_KEEP = (r'증시|주가|급등|급락|금리|연준|Fed|채권|국채|유가|원유|달러|환율|관세|무역|실적|매출|영업이익|순이익|인수|합병|'
             r'반도체|AI|인공지능|메모리|HBM|칩|데이터센터|전쟁|이란|이스라엘|우크라|중동|휴전|제재|선거|트럼프|대통령|의회|'
             r'경기|침체|물가|인플레|고용|일자리|GDP|수출|투자|조달|증자|채권 발행|IPO|상장|파산|부도|신용|'
             r'애플|엔비디아|테슬라|마벨|팔란티어|마이크론|알파벳|구글|마이크로소프트|메타|아마존|오라클|삼성|SK|현대')
FG_BANDS = [(0, 25, '#c0392b', '극단적 공포'), (25, 45, '#e67e22', '공포'), (45, 55, '#9aa0a6', '중립'),
            (55, 75, '#7cb342', '탐욕'), (75, 100, '#2e7d32', '극단적 탐욕')]


FG_HELP = {   # 7개 지표 읽는 법 (자세한 공부용: 드라이브 '페르소나 스토리/05_02_포보스_공포와탐욕지수계산법관리')
    'Market Momentum': 'S&P500이 125일(약 6개월) 이동평균선보다 얼마나 위에 있나.\n\n'
                       '- 많이 위 → 탐욕(오르는 힘이 강함)\n- 근처·아래 → 공포(상승 힘이 빠짐)\n\n'
                       '선 위에 있어도 평소보다 이격이 작으면 공포로 나온다. 가장 느린 지표.',
    'Stock Price Strength': 'NYSE 52주 신고가 종목 수 − 신저가 종목 수.\n\n'
                            '- 플러스 → 탐욕(오르는 종목이 넓음)\n- 마이너스 → 공포(신저가가 더 많음)\n\n'
                            '지수는 버티는데 마이너스면 "대형주 몇 개만 지수를 끄는 중"이라는 경고.',
    'Stock Price Breadth': 'McClellan 거래량 합: 오른 종목 거래량 − 내린 종목 거래량의 누적.\n\n'
                           '- 높고 오름 → 탐욕(돈이 오르는 종목으로)\n- 낮고 내림 → 공포\n\n'
                           '절대값보다 최근 몇 주 방향을 본다. Strength와 같은 쪽이면 신뢰도가 높다.',
    'Put and Call Options': '풋(하락 베팅) ÷ 콜(상승 베팅) 거래량, 5일 평균. **숫자가 클수록 공포**.\n\n'
                            '- 0.7 이하: 콜 쏠림, 탐욕\n- 0.7~0.9: 보통\n- 1.0 이상: 공포, 1.2 넘으면 극단(바닥 근처일 때가 많음)\n\n'
                            '가장 빠른 지표. 하루이틀 튀는 건 흘려 본다.',
    'Market Volatility': 'VIX(공포지수)와 그 50일 평균 비교. **VIX가 클수록 공포**.\n\n'
                         '- 15 이하: 평온·방심\n- 15~20: 보통\n- 20~30: 불안\n- 30 이상: 공포, 40 넘으면 패닉\n\n'
                         '50일 평균보다 높으면 불안이 커지는 중.',
    'Safe Haven Demand': '최근 20일 주식 수익률 − 국채 수익률.\n\n'
                         '- 플러스 → 탐욕(주식 선호)\n- 마이너스 → 공포(돈이 국채로 피난)\n\n'
                         '−1%p 이하면 피난이 뚜렷, −3%p 이하면 극단.',
    'Junk Bond Demand': '정크본드 금리 − 우량 회사채 금리(스프레드). **벌어질수록 공포**.\n\n'
                        '- 좁아짐 → 탐욕(위험한 회사에도 돈이 감)\n- 몇 주 새 빠르게 벌어짐 → 경고, 주식보다 먼저 위험을 알리는 경우가 많다.',
}


def series(kind, name):
    """추이 파일에서 한 항목의 시계열 (없으면 빈 Series)"""
    if not len(trend_df):
        return pd.Series(dtype=float)
    t = trend_df[(trend_df['구분'] == kind) & (trend_df['항목'] == name)]
    return pd.Series(num(t['값']).values, index=pd.to_datetime(t['날짜'])).sort_index().dropna()


def at_or_before(s, when):
    x = s[s.index <= pd.Timestamp(when)]
    return float(x.iloc[-1]) if len(x) else None


MONTHLY_GRP = ('물가', '성장·고용')


def day_change(s, pp):
    """직전 관측 대비 변화(1D): %p 항목은 차이, 나머지는 %"""
    if len(s) < 2 or not s.iloc[-2]:
        return None
    return s.iloc[-1] - s.iloc[-2] if pp else (s.iloc[-1] / s.iloc[-2] - 1) * 100


def spark(kind, name):
    s = series(kind, name)
    return s.tolist() if len(s) >= 2 and s.nunique() > 1 else None   # 한 달 내내 같은 값(기준금리 등)은 선을 그리지 않는다


BAR_COLOR = '#2f8f8a'   # 작은 막대 색: 청록(2026-10-31 의장 예시 그림)


def mini_bars(data, h=70):
    """빈틈 없이 붙은 작은 막대(속을 칠한 선처럼 보이게). 세로축은 값 범위에 맞춰 바닥을 올린다."""
    v = pd.Series(data, dtype=float).reset_index(drop=True)
    lo, hi = v.min(), v.max()
    pad = (hi - lo) * 0.15 or abs(hi) * 0.01 or 1
    lo -= pad
    df = pd.DataFrame({'i': range(len(v)), 'v': v})
    return (alt.Chart(df).mark_bar(color=BAR_COLOR, clip=True, width={'band': 1})
            .encode(x=alt.X('i:O', axis=None, scale=alt.Scale(paddingInner=0, paddingOuter=0)),
                    y=alt.Y('v:Q', axis=None, scale=alt.Scale(domain=[lo, hi + pad * 0.2], zero=False)),
                    y2=alt.datum(lo), tooltip=alt.value(None))
            .properties(height=h).configure_view(stroke=None))


def bars_svg(data, w=160, h=34):
    """표 칸용 빈틈 없는 작은 막대 그림(data URL). 표 내장 차트는 선·흐린 면뿐이라 그림으로 넣는다."""
    if not data:
        return None
    import base64
    v = pd.Series(data, dtype=float).dropna().tolist()
    lo, hi = min(v), max(v)
    pad = (hi - lo) * 0.15 or abs(hi) * 0.01 or 1
    lo -= pad
    bw = w / len(v)
    rects = ''.join(f'<rect x="{i * bw:.2f}" y="{h - (x - lo) / (hi - lo) * h:.2f}" width="{bw + 0.3:.2f}" '
                    f'height="{(x - lo) / (hi - lo) * h:.2f}"/>' for i, x in enumerate(v))
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" fill="{BAR_COLOR}">{rects}</svg>'
    return 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode()


def card(where, label, value, delta=None, data=None, border=True, **kw):
    """st.metric + 빈틈 없는 작은 막대 (st.metric 내장 막대는 띄엄띄엄이라 따로 그림)"""
    box = where.container(border=border)
    box.metric(label, value, delta, **kw)
    if data:
        box.altair_chart(mini_bars(data), width='stretch')


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


sec, sec_tr = csv(DAY, '섹터'), csv(DAY, '섹터궤적')
t1, t5, t2, t6, t3, t4 = st.tabs(['회의 자료', '회의록', '종목', '섹터 순환', '주봉 차트', '수집 점검'])

# ---------------------------------------------------------------- 1. 오늘 시장
# 2026-11-10 의장 개편: 맨 위 지표 카드 + 히트맵, 모든 지표는 누르면 최근 1년 그래프(해석 없음),
#   금리는 기준금리·2년·10년·30년 + 일본 10년, 물가 칸 삭제(댈러스·클리블랜드 중 연준 참고만 남김),
#   주간·월간 지표는 전주·전월 대비, 신호 칸 전부 채움(의장 기준 그대로 + 나머지는 '바닥 찾기' 제안), 메모 칸 삭제,
#   해석·긴 설명은 맨 뒤 열.
import html as _h
import re as _re

import heatmap as hmmod  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import present  # noqa: E402
import valuation_view  # noqa: E402
from signal_rules import signal2 as sig_of  # noqa: E402

TABLES = [   # (표 제목, [항목]) — 화면에 보이는 순서. 여기 없는 항목은 화면에 안 나온다(수집 파일·리오 체크리스트엔 그대로).
    ('지수', ['S&P500', '나스닥', '다우', '코스피', '코스닥', '코스피 50일 이격도', '필라델피아 반도체(SOX)',
            '니케이225', '대만 가권', '유로스톡스50']),
    ('환율', ['원/달러', '엔/달러', '100엔당 원', '달러지수']),
    ('금리', ['기준금리(범위)', '미국 2년', '미국 10년', '미국 30년', '일본 10년']),
    ('연준 참고 (댈러스·클리블랜드·애틀랜타)', ['절사평균 PCE(댈러스)', '기대인플레 1년(클리블랜드)',
                                     '기대인플레 10년(클리블랜드)', 'GDPNow']),
    ('고용', ['실업수당 4주 평균', '실업률', '비농업 고용 증감', '샴 룰']),
    ('원자재', ['WTI', '구리', '금']),
    ('변동성', ['VIX', 'VIX3M', 'VIX − VIX3M', 'MOVE']),
    ('신용·금융 스트레스', ['하이일드 스프레드', '투자등급 스프레드', '세인트루이스', '캔자스시티', '시카고 NFCI', '시카고 조정 NFCI']),
    ('침체 신호·자금', ['10년−2년', '10년−3개월', '경기침체 확률', 'SOFR−IORB', '순유동성 4주 변화']),
]
CARDS = ['S&P500', '나스닥', '코스피', '필라델피아 반도체(SOX)', 'VIX', '미국 10년', '원/달러', '엔/달러', '금', 'WTI']
CARD_NAME = {'필라델피아 반도체(SOX)': 'SOX 반도체'}
WEEKLY = {'실업수당 4주 평균', '세인트루이스', '시카고 NFCI', '시카고 조정 NFCI', '순유동성 4주 변화'}
MONTHLY = {'실업률', '비농업 고용 증감', '샴 룰', '절사평균 PCE(댈러스)', '기대인플레 1년(클리블랜드)',
           '기대인플레 10년(클리블랜드)', '경기침체 확률', '캔자스시티'}
CHG_COLS = ['전일 대비', '1년 전 대비']


def _f(x):
    v = num(pd.Series([x])).iloc[0]
    return None if pd.isna(v) else float(v)


def freq_of(name, hist):
    """'전일'·'전주'·'전월'·'직전' — 이력 점 간격으로 정하고, 이력이 짧으면 이름표로"""
    if name in WEEKLY:
        return '전주'
    if name in MONTHLY:
        return '전월'
    if name == 'GDPNow':
        return '직전 추정'
    if len(hist) >= 4:
        gap = pd.Series(hist.index).diff().dt.days.median()
        return '전일' if gap <= 4 else '전주' if gap <= 10 else '전월'
    return '전일'


def _chg(now, past, pp):
    if now is None or past is None:
        return None
    if pp:
        return now - past
    return None if past == 0 else (now / past - 1) * 100


def _txt(v, pp, unit_pp='%p'):
    return '—' if v is None or pd.isna(v) else f'{v:+.2f}{unit_pp if pp else "%"}'


def _color(x):
    x = str(x)
    return f'color:{UP}' if x.startswith('+') and x.strip('+0.%p() 전일주월직추정') else f'color:{DN}' if x.startswith('-') else ''


def build_rows():
    """매크로·리스크 파일 → {항목: 줄}. 줄 = 표 칸 + 그래프용 이력·단위"""
    rows = {}
    vals = {}
    if len(mac):
        for _, r in mac.iterrows():
            vals[r['항목']] = _f(r['값'])
    if len(risk):
        for _, r in risk.iterrows():
            vals[r['항목']] = _f(r['값'])
    srcs = []
    if len(mac):
        srcs += [('매크로', r) for _, r in mac.iterrows()]
    if len(risk):
        srcs += [('리스크', r) for _, r in risk.iterrows()]
    for kind, r in srcs:
        name, grp = r['항목'], r.get('구분')
        now = _f(r['값'])
        unit = '' if pd.isna(r.get('단위')) else str(r.get('단위'))
        hist = series(kind, name)
        if kind == '매크로':
            pp = r.get('변화 단위') == '%p'
            d1, mo, ye, y1 = (_f(r.get(k)) for k in ('전일 값', '1달 전 값', '작년 말 값', '1년 전 값'))
            mo_ready, ytd_ready = _f(r.get('1달')), _f(r.get('YTD'))
            notes = [r.get('의장 기준(참고)'), r.get('비고')]
            dec = 3 if grp == '금리' else 1 if grp == '원자재' else 2
        else:
            pp = unit in ('%', '%p') or '−' in str(name) or grp in ('금융 스트레스', '침체 신호', '자금 경색')
            d1, mo, ye, y1 = (_f(r.get(k)) for k in ('전일', '1달 전', '작년 말', '1년 전'))
            mo_ready = ytd_ready = None
            notes = [r.get('의장 기준(참고)'), r.get('일반 기준(참고)'), r.get('비고')]
            dec = 2
        if d1 is None and len(hist) > 1:
            d1 = float(hist.iloc[-2])
        fq = freq_of(name, hist)
        if fq == '전월':           # 월간 지표는 '1달' 칸이 직전 대비와 같아서 비운다
            mo = mo_ready = None
        mo_v = _chg(now, mo, pp) if mo is not None else mo_ready
        ytd_v = _chg(now, ye, pp) if ye is not None else ytd_ready
        unit_pp = '%p' if unit in ('%', '%p') or kind == '매크로' else 'p'
        hi_gap = _f(r.get('최고 대비(%)'))
        d1_v = _chg(now, d1, pp)
        icon, short_sig, who, crit = sig_of(name, now, r.get('신호'), r.get('표시'), hi_gap=hi_gap, mo=mo_v, d1=d1_v, vals=vals)
        cur = fmt(now, dec, unit if unit in ('%', '천명', '건') else '')
        if name == '기준금리(범위)' and pd.notna(r.get('비고')):
            cur = str(r['비고'])
        why = interpret(grp, name, now, mo_v, pp, hi_gap).replace('한 달 새', '직전보다' if fq == '전월' else '한 달 새')
        extra = ' · '.join(str(x) for x in notes if x is not None and pd.notna(x) and str(x).strip() and str(x) not in crit)
        rows[name] = {
            '항목': name, '현재': cur,
            '전일 대비': (_txt(d1_v, pp, unit_pp) + ('' if fq == '전일' else f' ({fq})')) if d1_v is not None else '—',
            '1년 전 대비': _txt(_chg(now, y1, pp), pp, unit_pp), '_crit': crit,
            '1달': _txt(mo_v, pp, unit_pp), 'YTD': _txt(ytd_v, pp, unit_pp), '1년': _txt(_chg(now, y1, pp), pp, unit_pp),
            '기준일': '' if pd.isna(r.get('기준일')) else str(r.get('기준일')),
            '신호': (f'{icon} {short_sig}' + (' (제안)' if who == '제안' and short_sig else '')).strip(),
            '해석': '. '.join(x for x in [crit, why, extra] if x),
            '_now': now, '_d1pct': d1_v, '_pp': pp, '_unit': unit, '_hist': hist, '_dec': dec,
        }
    return rows


def chart_1y(name, s, unit='', h=280):
    """최근 1년 선 그래프(해석 없음). 이력이 1년보다 짧으면 있는 만큼."""
    s = s[s.index >= s.index[-1] - pd.DateOffset(years=1)] if len(s) else s
    d = s.rename('값').rename_axis('날짜').reset_index()
    lo, hi = float(d['값'].min()), float(d['값'].max())
    pad = (hi - lo) * 0.08 or abs(hi) * 0.01 or 1
    hover = alt.selection_point(fields=['날짜'], nearest=True, on='pointerover', empty=False)
    base = alt.Chart(d).encode(x=alt.X('날짜:T', title=None, axis=alt.Axis(format='%y-%m', grid=False)))
    area = base.mark_area(opacity=0.12, color='#2f8f8a').encode(
        y=alt.Y('값:Q', title=unit or None, scale=alt.Scale(domain=[lo - pad, hi + pad], zero=False)), y2=alt.datum(lo - pad))
    line = base.mark_line(color='#2f8f8a', strokeWidth=2).encode(y='값:Q')
    pts = base.mark_point(size=60, filled=True, color='#1d2330').encode(
        y='값:Q', opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip('날짜:T', format='%Y-%m-%d'), alt.Tooltip('값:Q', format=',.3f')]).add_params(hover)
    return (area + line + pts).properties(height=h, title=f'{name} — 최근 {"1년" if len(s) and s.index[0] <= s.index[-1] - pd.DateOffset(months=11) else f"{(s.index[-1] - s.index[0]).days}일"}')


@st.dialog('최근 1년', width='large')
def show_1y(name, s, unit=''):
    st.altair_chart(chart_1y(name, s, unit, h=380), width='stretch')


def spark_1m(s, up):
    s = s[s.index >= s.index[-1] - pd.DateOffset(months=1)]
    d = s.rename('v').reset_index(drop=True).reset_index()
    lo, hi = float(d['v'].min()), float(d['v'].max())
    pad = (hi - lo) * 0.1 or abs(hi) * 0.01 or 1
    col = UP if up else DN
    return (alt.Chart(d).mark_area(line={'color': col, 'strokeWidth': 1.6}, color=col, opacity=0.12)
            .encode(x=alt.X('index:Q', axis=None), y=alt.Y('v:Q', axis=None, scale=alt.Scale(domain=[lo - pad, hi + pad])),
                    y2=alt.datum(lo - pad), tooltip=alt.value(None))
            .properties(height=48).configure_view(stroke=None))


@st.cache_data(ttl=3 * 3600, show_spinner='히트맵 자료 받는 중(야후)…')
def heatmap_live(markets=('S&P500', '한국')):
    """그날 히트맵 파일이 없을 때(07시 블록 이전 날짜 등) 화면에서 바로 계산"""
    import yfinance as yf
    rows = []
    if 'S&P500' in markets:
        rows += hmmod.sp500(yf, pd.read_csv(ROOT / 'yeokdosan' / 'holdings_top10.csv'))
    if '한국' in markets:
        rows += hmmod.korea(yf, pd.read_csv(ROOT / 'heatmap_kr.csv'))
    return pd.DataFrame(rows, columns=hmmod.COLS)


def treemap(df, period, sized, h=560):
    import plotly.express as px
    d = df.dropna(subset=[period]).copy()
    if sized and d['시총'].notna().any():
        d['크기'] = d['시총'].fillna(d['시총'].median())
    else:
        d['크기'] = 1.0
    cap = {'1일': 3, '1주': 6, '1달': 12}[period]
    d['글'] = d.apply(lambda r: f"{r['이름']}<br>{r[period]:+.2f}%", axis=1)
    fig = px.treemap(d, path=['묶음', '글'], values='크기', color=period,
                     color_continuous_scale=[[0, '#e53935'], [0.3, '#8e2a2a'], [0.5, '#2b2f36'], [0.7, '#1f6b3a'],
                                             [1, '#2ecc71']], range_color=[-cap, cap],
                     custom_data=['티커', '1일', '1주', '1달'])
    fig.update_traces(root_color='rgba(0,0,0,0)', texttemplate='%{label}', textposition='middle center',
                      hovertemplate='<b>%{label}</b><br>%{customdata[0]}<br>1일 %{customdata[1]:+.2f}% · '
                                    '1주 %{customdata[2]:+.2f}% · 1달 %{customdata[3]:+.2f}%<extra></extra>',
                      marker=dict(line=dict(width=1, color='#111')), tiling=dict(pad=2),
                      textfont=dict(size=14, color='#fff'), pathbar=dict(visible=False))
    fig.update_layout(margin=dict(t=8, l=0, r=0, b=0), height=h, coloraxis_showscale=False,
                      uniformtext=dict(minsize=11, mode='hide'))
    return fig


@st.cache_data(ttl=60, show_spinner=False)      # 회의 중 고친 발표 문장이 1분 안에 보이게
def script(day):
    import json
    b = _raw(f'{day}/{day}_발표.json')
    return json.loads(b.decode('utf-8-sig')) if b else None


def wilder_rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn)


def rsi_chart(name, r, h=190):
    d = r.rename('RSI').rename_axis('날짜').reset_index()
    bands = alt.Chart(pd.DataFrame({'y': [30, 70], 'c': [UP, DN]})).mark_rule(strokeDash=[4, 4]).encode(
        y='y:Q', color=alt.Color('c:N', scale=None))
    zone = alt.Chart(pd.DataFrame({'lo': [0], 'hi': [30]})).mark_rect(opacity=0.07, color=UP).encode(y='lo:Q', y2='hi:Q')
    line = alt.Chart(d).mark_line(color='#1d2330', strokeWidth=1.8).encode(
        x=alt.X('날짜:T', title=None, axis=alt.Axis(format='%y-%m', grid=False)),
        y=alt.Y('RSI:Q', title=None, scale=alt.Scale(domain=[0, 100])),
        tooltip=[alt.Tooltip('날짜:T', format='%Y-%m-%d'), alt.Tooltip('RSI:Q', format='.1f')])
    return (zone + bands + line).properties(height=h, title=f'{name}  주봉 RSI {d.iloc[-1]["RSI"]:.1f}')


def hbar(df, label, value, title='', fmtv='+,.1f', h=None, sort=None, unit=''):
    """가로 막대(오름 초록, 내림 빨강) + 끝에 숫자"""
    d = df[[label, value]].dropna().copy()
    d.columns = ['이름', '값']
    order = sort or d.sort_values('값', ascending=False)['이름'].tolist()
    base = alt.Chart(d).encode(y=alt.Y('이름:N', sort=order, title=None, axis=alt.Axis(labelLimit=220, labelOverlap=False)),
                               x=alt.X('값:Q', title=unit or None))
    bars = base.mark_bar().encode(color=alt.condition('datum.값 >= 0', alt.value(UP), alt.value(DN)),
                                  tooltip=['이름', alt.Tooltip('값:Q', format=fmtv)])
    txt = (base.transform_filter('datum.값 >= 0').mark_text(align='left', dx=4, fontSize=11)
           .encode(text=alt.Text('값:Q', format=fmtv))
           + base.transform_filter('datum.값 < 0').mark_text(align='right', dx=-4, fontSize=11)
           .encode(text=alt.Text('값:Q', format=fmtv)))
    return (bars + txt).properties(title=title, height=h or 24 * len(d) + 40)


def gap_bars(df, label, col, title, base_line=100):
    """이격(선 = 100) 막대: 100 위 초록, 아래 빨강"""
    d = df[[label, col]].dropna().copy()
    d.columns = ['이름', '값']
    d['차'] = d['값'] - base_line
    order = d.sort_values('값')['이름'].tolist()
    base = alt.Chart(d).encode(y=alt.Y('이름:N', sort=order, title=None, axis=alt.Axis(labelLimit=200)),
                               x=alt.X('차:Q', title=f'{col} − {base_line}'))
    bars = base.mark_bar().encode(color=alt.condition('datum.차 >= 0', alt.value(UP), alt.value(DN)),
                                  tooltip=['이름', alt.Tooltip('값:Q', format='.1f')])
    txt = base.mark_text(align='left', dx=4, fontSize=11).encode(text=alt.Text('값:Q', format='.1f'))
    return (bars + txt).properties(title=title, height=24 * len(d) + 40)


def speech(sc, keys, nm):
    """발표 파일에서 이 위원(keys 중 하나를 이름에 포함)의 문장·그래프. 없으면 False."""
    if not sc:
        return False
    for m in sc.get('members', []):
        if any(k in str(m.get('name', '')) for k in keys):
            if m.get('sub'):
                if m.get('lines') or m.get('charts'):
                    present.member(DAY, {k: v for k, v in m.items() if k not in ('sub', 'name', 'role')}, nm)
                for s_ in m['sub']:   # 하위 칸(섹터별)도 탭 대신 아래로 차례로
                    present.member(DAY, s_, nm)   # 섹터 이름은 member가 소제목으로
            else:
                present.member(DAY, {k: v for k, v in m.items() if k not in ('name', 'role')}, nm)   # 위원 이름·칸 이름은 위 제목과 겹치므로 뺌
            return True
    return False


def short(n):
    for w in ('TIGER ', 'KODEX ', 'PLUS ', 'SOL ', 'RISE ', 'HANARO ', '코리아', '플러스', 'TOP10', 'TOP3', 'TOP2'):
        n = n.replace(w, '')
    return n.replace('미국필라델피아반도체나스닥', '미국반도체').replace('글로벌HBM반도체', 'HBM반도체').strip()


def data_head(spoke):
    if spoke:
        st.divider()
    st.markdown('##### 자료')


def market_tables(R, groups):
    """TABLES 중 groups 표만. 줄을 누르면 바로 아래 최근 1년 그래프."""
    SHOW = ['항목', '현재', '전일 대비', '1년 전 대비', '기준일', '신호']
    for title, names_ in TABLES:
        if title not in groups:
            continue
        rows = [R[n] for n in names_ if n in R]
        if not rows:
            continue
        st.markdown(f'**{title}**')
        df = pd.DataFrame(rows)
        ev = st.dataframe(df[SHOW].style.map(_color, subset=CHG_COLS), hide_index=True, width='stretch',
                          height=36 * (len(df) + 1) + 4, on_select='rerun', selection_mode='single-row',
                          key=f'tbl_{title}', column_config={'신호': st.column_config.TextColumn(width='large')})
        sel = ev.selection.rows if ev and ev.selection else []
        if sel:
            r = rows[sel[0]]
            if len(r['_hist']) >= 2:
                st.altair_chart(chart_1y(r['항목'], r['_hist'], r['_unit']), width='stretch')
                if r['_crit']:
                    st.caption(r['_crit'])
            else:
                st.caption(f'{r["항목"]}: 그래프 이력이 아직 없습니다.')


TABLES += [('지수 · 변동성', ['VIX', 'VIX3M', 'VIX − VIX3M'])]
PRESENTERS = [   # 2026-11-10 의장 확정 회의 순서. (내부 키, 탭 제목, 발표 파일 name에서 찾을 말) — 1. 시장은 탭 위 맨 위.
    # 스트림릿은 회의 자료라 위원 이름을 쓰지 않는다(의장). 찾을 말에 옛 위원 이름도 넣어 둔 것은 지난 발표 파일 호환용.
    # 2026-11-15 의장 "미스 시타델을 만들어서 회의 초반에 매일 보고" → 3. 수급·포지셔닝(뉴스 다음, 순서는 의장이 바꿀 수 있음)
    ('뉴스', '2. 주요 뉴스', ['주요 뉴스', '국장']), ('수급', '3. 수급·포지셔닝', ['포지셔닝', '미스 시타델', '미스시타델', '자금 흐름', '역도산']),
    # 2026-11-15 의장 "역도산은 폐지하고 모든 수급을 시타델이 하는 것으로 통합" → 4. 자금 흐름 칸을 3에 합침(옛 발표 파일 말도 3이 찾음)
    ('리스크', '4. 리스크 체크', ['리스크', '리오']), ('공포', '5. 공포와 탐욕', ['공포', '포보스']),
    ('섹터', '6. 섹터 분석', ['섹터 분석', '미스 밸류', '미스밸류', '피터', '데스크']), ('기술', '7. 기술적 분석', ['기술적', '미스 차트', '미스차트']),
    ('일본', '8. 일본 분석', ['일본', '아야카']), ('긍정', '9. 긍정 요인', ['긍정', '엘피스']), ('기타', '10. 기타', ['기타'])]
KEYS = {k: ks for k, _, ks in PRESENTERS}
TOP_CARDS = ['S&P500', '나스닥', '코스피', '필라델피아 반도체(SOX)', '원/달러', '미국 10년']

with t1:
    st.html('<style>[data-testid="stMetricValue"]{font-size:1.55rem}</style>')   # 카드 6개 한 줄에 숫자가 잘리지 않게
    R = build_rows()
    present.setup(csv, prices)
    sc = script(DAY)
    nm = present.names(DAY)

    # ---- 맨 위: 시장 한눈에 — 미국·한국 히트맵 + 지표 카드 한 줄
    hm = csv(DAY, '히트맵')
    live = False
    st.header('1. 시장', anchor='sec-시장')
    # 2026-11-11 의장 "처음에 볼 수 있게": 맨 위 = 지수 밸류·등락(선행 P/E 밴드, 필반 200일 이격도, 주요국·미국 등락)
    valuation_view.show(csv, _raw, DAY)
    h0, h1 = st.columns([3, 1])
    h0.markdown('#### 히트맵')
    per = h1.segmented_control('기간', ['1일', '1주', '1달'], default='1일', key='hm_per',
                               label_visibility='collapsed') or '1일'
    need = {'S&P500'} - (set(hm['시장']) if len(hm) else set())   # 11/10 의장: 히트맵은 미국만
    if need:
        try:
            hm, live = pd.concat([hm, heatmap_live(tuple(sorted(need)))], ignore_index=True), True
        except Exception as e:
            st.warning(f'히트맵 자료를 받지 못했습니다: {type(e).__name__}')
    for c in ('시총', '1일', '1주', '1달'):
        if c in hm:
            hm[c] = num(hm[c])
    # 2026-11-11 의장: 콜로키움 100(층별) → 하루 등락 상·하위 10 → 미국 S&P500 히트맵
    part = hm[hm['시장'] == '콜로키움 100'] if len(hm) else hm
    if len(part):
        st.markdown('**콜로키움 100 (층별)**')
        st.plotly_chart(treemap(part, per, False, h=460), width='stretch', config={'displayModeBar': False}, key='hm_c100')
    if len(price):
        pp_ = price.assign(v=num(price['등락률(%)'])).dropna(subset=['v'])
        if len(pp_):
            tb_ = pd.concat([pp_.nlargest(10, 'v'), pp_.nsmallest(10, 'v')]).drop_duplicates('정식 종목명')
            st.altair_chart(hbar(tb_, '정식 종목명', 'v', '콜로키움 100 하루 등락 상·하위 10 (%)', fmtv='+.2f'), width='stretch')
    for col, mk, ttl in ((st.container(), 'S&P500', '미국 S&P500'),):
        part = hm[hm['시장'] == mk] if len(hm) else hm
        with col:
            st.markdown(f'**{ttl}**')
            if len(part):
                st.plotly_chart(treemap(part, per, True, h=600), width='stretch', config={'displayModeBar': False},
                                key=f'hm_{mk}')
            else:
                st.info(f'{ttl} 히트맵 자료가 없습니다.')
    base = hm['기준일'].dropna().max() if len(hm) and '기준일' in hm else ''
    st.caption('미국 S&P500 = SPDR 섹터 ETF 11개 상위 10종목. 칸 크기 = 시가총액, '
               f'초록 = 오름, 빨강 = 내림. 기준일 {base}.' + (' (07시 파일이 없어 지금 야후에서 받은 값)' if live else ''))
    have = [k for k in TOP_CARDS if k in R and R[k]['_now'] is not None]
    if have:
        cols = st.columns(len(have))
        for c, k in zip(cols, have):
            r = R[k]
            with c.container(border=True):
                dv = r['_d1pct']
                st.metric(CARD_NAME.get(k, k), r['현재'], None if dv is None else (f'{dv:+.2f}%p' if r['_pp'] else f'{dv:+.2f}%'))
                if len(r['_hist']) >= 2:
                    st.altair_chart(spark_1m(r['_hist'], (dv or 0) >= 0), width='stretch')
                    if st.button('1년 그래프', key=f'c1y_{k}', width='stretch'):
                        show_1y(k, r['_hist'], r['_unit'])

    # ---- 발표 순서대로 아래로 이어짐
    if not sc:
        st.caption('오늘 발표 원고(_발표.json)는 아직 없습니다. 칸마다 자료만 보입니다.')
    CARD = ('<div style="font-family:inherit;border:1px solid rgba(128,128,128,.25);border-radius:12px;'
            'padding:6px 16px 10px;">{}</div>')
    # 11/10 의장 "탭 말고 아래로 내리면 차례로" — 2~10을 한 페이지에 순서대로 이어 붙인다(회의 때 스크롤로 진행)
    T = {}
    for k, t, _ in PRESENTERS:
        T[k] = st.container()
        with T[k]:
            st.divider()
            st.header(t, anchor=f'sec-{k}')

    # 2 국장: 간밤 국제 뉴스 · 이번 주 일정
    with T['뉴스']:
        data_head(speech(sc, KEYS['뉴스'], nm))
        c_n, c_s = st.columns(2, gap='large')
        with c_s:
            st.subheader('이번 주 일정')
            if len(sched_df):
                sd = sched_df.copy()
                sd['보유/관심'] = sd['보유/관심'].fillna('')
                timed = set(zip(sd.loc[sd['시각(한국)'] != '미정', '날짜'], sd.loc[sd['시각(한국)'] != '미정', '대상']))
                sd = sd[~((sd['시각(한국)'] == '미정') & pd.Series([(d, w) in timed for d, w in zip(sd['날짜'], sd['대상'])], index=sd.index))]   # 같은 날 시각 있는 줄이 있으면 '미정' 줄은 뺀다
                def _chk(r):   # 11/3: 확인 정도 — 확정·발표됨은 회색, 예상은 연한 글씨, 날짜 다름은 주황
                    c = str(r.get('확인') or '')
                    if not c or c == 'nan':
                        return ''
                    col = '#d97706' if '다름' in c else '#6b7280'
                    return f'<span style="font-size:.75rem;color:{col};margin-left:6px;">({_h.escape(c)})</span>'

                def _memo(r):  # 간밤 실적은 숫자(EPS·매출)를 한 줄 더
                    if '간밤' not in str(r.get('구분')):
                        return ''
                    return f'<div style="font-size:.82rem;color:#6b7280;">{_h.escape(str(r.get("내용") or ""))}</div>'

                def _sched_html(sd):
                  body = ''
                  for (d, wd), g in sd.groupby(['날짜', '요일'], sort=True):
                    body += (f'<div style="margin:12px 0 4px;font-weight:700;font-size:.95rem;">'
                             f'{str(d)[5:].replace("-", "/")} ({wd})</div>')
                    for _, r in g.iterrows():
                        mark = r['보유/관심']
                        tag = (f'<span style="font-size:.72rem;padding:1px 7px;border-radius:9px;margin-left:6px;'
                               f'background:{"#2f8f8a" if mark == "보유" else "rgba(128,128,128,.25)"};'
                               f'color:{"#fff" if mark == "보유" else "inherit"};">{_h.escape(mark)}</span>') if mark else ''
                        body += (f'<div style="display:flex;gap:12px;padding:5px 0;border-top:1px solid rgba(128,128,128,.12);">'
                                 f'<div style="min-width:64px;color:#6b7280;font-variant-numeric:tabular-nums;font-size:.88rem;">'
                                 f'{_h.escape(str(r["시각(한국)"]))}</div>'
                                 f'<div style="font-size:.92rem;"><b>{_h.escape(str(r["대상"]))}</b>{tag}'
                                 f'<span style="color:#6b7280;"> · {_h.escape(str(r["구분"]))}</span>'
                                 f'{_chk(r)}{_memo(r)}</div></div>')
                  return body
                sd = sd.sort_values(['날짜', '시각(한국)'])
                today = f'{DAY[:4]}-{DAY[4:6]}-{DAY[6:]}'
                sd = sd[sd['날짜'].astype(str) >= today] if (sd['날짜'].astype(str) >= today).any() else sd
                first, rest = sd.head(6), sd.iloc[6:]
                st.html(CARD.format(_sched_html(first)))
                if len(rest):
                    with st.expander(f'이번 주 일정 {len(rest)}건 더 보기'):
                        st.html(CARD.format(_sched_html(rest)))
                st.caption('한국 시각. 미국 실적은 야후 예정 시각이라 분 단위가 다를 수 있음(예: 06:00경 → 실제 06:05·06:30).')
            else:
                st.info('오늘 일정 파일이 없습니다.')
        with c_n:
            st.subheader('간밤 국제 뉴스')
            nd = news_df.copy() if len(news_df) else pd.DataFrame(columns=['시각(한국)', '제목', '링크', '출처', '종목'])
            if len(nd):
                # 2026-11-02 의장 "영어 뉴스·지난 뉴스는 빼고 간밤 것만": 한국어 제목, 전날 18시 이후,
                # 연합뉴스는 기사 주소의 날짜(AKR20261030…)가 전날 이전이면 뺌(재송고된 옛 기사),
                # 월요일엔 '아침 정리'(지난 금요일 뉴욕 마감)를 뺌. 국제 5 + 아침 정리 3 + 종목 6건까지.
                day0 = pd.to_datetime(DAY)
                prev = (day0 - pd.Timedelta(days=1)).strftime('%m-%d') + ' 18:00'
                nd = nd[nd['제목'].astype(str).str.contains('[가-힣]', regex=True)]
                nd = nd[nd['시각(한국)'].astype(str) >= prev]
                nd = nd[~nd['제목'].astype(str).str.contains('블로그|Blog|카페', regex=True)]   # 블로그 글 제외
                # 2026-11-03 의장 "홍보 기사를 주요뉴스라고 붙이는 건 판단력 부재": 칼럼·인터뷰·홍보·스포츠 빼고,
                # 연합뉴스는 시장과 닿는 말이 제목에 있는 것만(07시 수집 b09와 같은 기준)
                nd = nd[~nd['제목'].astype(str).str.contains(NEWS_DROP, regex=True)]
                is_yna = nd['출처'].astype(str).str.contains('연합')
                nd = nd[~is_yna | nd['제목'].astype(str).str.contains(NEWS_KEEP, regex=True)]
                akr = nd['링크'].astype(str).str.extract(r'AKR(\d{8})')[0]
                nd = nd[akr.isna() | (akr >= (day0 - pd.Timedelta(days=1)).strftime('%Y%m%d'))]
                if day0.weekday() == 0:
                    nd = nd[nd['출처'].astype(str) != '아침 정리']
                # 2026-11-11 의장 "믿을 만한 언론만. 매경, 연합뉴스, 조선일보 정도": 아침 정리는 세 매체만(이미 수집된 날도 화면에서 거름)
                is_am = nd['출처'].astype(str) == '아침 정리'
                nd = nd[~is_am | nd['종목'].astype(str).str.strip().isin(['매일경제', '연합뉴스', '조선일보'])]
                nd = nd.drop_duplicates('제목').sort_values('시각(한국)', ascending=False)
                cap = {'아침 정리': 3}
                grp = nd['출처'].astype(str).map(lambda x: '국제' if '연합' in x else x if x == '아침 정리' else '종목')
                nd, grp = nd[grp != '종목'], grp[grp != '종목']   # 11/9 의장 "보유 종목 뉴스는 필요 없고 주요 국제뉴스만"
                nd = nd.groupby(grp, group_keys=False).apply(lambda g: g.head(cap.get(g.name, 5 if g.name == '국제' else 6)))
                nd = nd.sort_values('시각(한국)', ascending=False)
                nd['묶음'] = grp.reindex(nd.index)
            if len(nd):
              SRC = '<span style="color:#6b7280;font-size:.8rem;"> · {}</span>'
              SHOW = {'국제': 2, '아침 정리': 1, '종목': 2}   # 11/3 의장 '단순화': 첫 화면 5건, 나머지는 접기
              rank = nd.groupby('묶음').cumcount()
              lead = nd[rank < nd['묶음'].map(SHOW).fillna(0)]
              more = nd.drop(lead.index)

              def _news_html(nd):
                body = ''
                for gname, glabel in (('국제', '간밤 국제'), ('아침 정리', '뉴욕 마감 정리'), ('종목', '보유·관심 종목')):
                    g = nd[nd['묶음'] == gname]
                    if not len(g):
                        continue
                    body += f'<div style="margin:12px 0 2px;font-weight:700;font-size:.95rem;">{glabel}</div>'
                    for _, r in g.iterrows():
                        src = str(r.get('종목') or '') if gname != '국제' else '연합뉴스'
                        src = '' if src == 'nan' else src
                        link = str(r.get('링크') or '')
                        title = _h.escape(_re.sub(r'\s+(\([^()]+\)|[-–]\s+[^-–]+)$', '', str(r['제목'])))   # 끝의 '(매체)'·'- 매체' 떼기
                        ttl = (f'<a href="{_h.escape(link)}" target="_blank" style="color:inherit;text-decoration:none;">{title}</a>'
                               if link.startswith('http') else title)
                        body += (f'<div style="display:flex;gap:12px;padding:6px 0;border-top:1px solid rgba(128,128,128,.12);">'
                                 f'<div style="min-width:44px;color:#6b7280;font-variant-numeric:tabular-nums;font-size:.85rem;">'
                                 f'{_h.escape(str(r["시각(한국)"])[6:])}</div>'
                                 f'<div style="font-size:.92rem;line-height:1.4;">{ttl}'
                                 f'{SRC.format(_h.escape(src)) if src else ""}</div></div>')
                return body
              st.html(CARD.format(_news_html(lead)))
              if len(more):
                  with st.expander(f'간밤 뉴스 {len(more)}건 더 보기'):
                      st.html(CARD.format(_news_html(more)))
            else:
                st.info('간밤(전날 18시 이후) 한국어 뉴스가 없습니다.')
    # 3 미스 시타델: 누가 반드시 사야 하고 누가 이미 다 팔았나 (2026-11-15 의장, 시타델 GMI 자료)
    with T['수급']:
        data_head(speech(sc, KEYS['수급'], nm))
        fp = flowpos_hist()
        fpt = csv(DAY, '수급포지셔닝')
        if not len(fp):
            st.info('수급·포지셔닝 이력이 아직 없습니다(07시 블록 9-수급이 처음 돈 뒤부터 보임).')
        else:
            span_ = st.segmented_control('기간', ['1년', '3년', '2018년 이후'], default='1년', key='fpspan',
                                         label_visibility='collapsed') or '1년'
            w_ = fp if span_ == '2018년 이후' else fp[fp.index >= fp.index[-1] - pd.DateOffset(years=1 if span_ == '1년' else 3)]

            def fp_line(col, title, rules=(), h=230, fmt_='.1f'):
                d_ = w_[[col]].dropna().reset_index().rename(columns={col: 'v'})
                base = alt.Chart(d_).mark_line(color='#8e44ad', strokeWidth=1.6).encode(
                    x=alt.X('날짜:T', title=None), y=alt.Y('v:Q', title=None, scale=alt.Scale(zero=False)),
                    tooltip=[alt.Tooltip('날짜:T'), alt.Tooltip('v:Q', title=col, format=fmt_)])
                layers = [base]
                for val, colr in rules:
                    layers.append(alt.Chart(pd.DataFrame({'y': [val]})).mark_rule(color=colr, strokeDash=[4, 3]).encode(y='y:Q'))
                return alt.layer(*layers).properties(height=h, title=title)

            last_ = fp.iloc[-1]
            m1, m2, m3, m4 = st.columns(4)
            def _d(col, days):
                s_ = fp[col].dropna()
                p_ = s_[s_.index <= s_.index[-1] - pd.Timedelta(days=days)]
                return None if not len(p_) else float(s_.iloc[-1] - p_.iloc[-1])
            for c_, col, f_ in ((m1, 'CTA σ(근사)', '{:+.1f}σ'), (m2, '변동성타기팅 노출(배)', '{:.2f}배'),
                                (m3, '상대 RSI(14일)', '{:.1f}'), (m4, '비율 1년 백분위(%)', '{:.0f}%')):
                if col in fp:
                    dv = _d(col, 7)
                    c_.metric(col, f_.format(last_[col]), None if dv is None else f'{dv:+.2f} (1주)')
            if 'CTA σ(근사)' in fp:
                st.altair_chart(fp_line('CTA σ(근사)', 'CTA 포지셔닝 σ (근사, 시타델 눈금) — 점선 ±4',
                                        rules=((4, '#2e86de'), (-4, '#c0392b'), (0, '#999')), h=280), width='stretch')
                st.caption('시타델 실제 값이 아니라 가격으로 흉내 낸 근사(시타델 그림 27점과 상관 0.88). '
                           '기준(2002~): 처음 −4σ 아래 17번 → S&P 3달 뒤 +6.6%(오른 비율 76%) · '
                           '+4σ 찍고 1.5σ 꺾인 날 16번 → 6달 뒤 +1.5%(평소 +6.0%). 판정 문턱은 룰 미정.')
            g1_, g2_ = st.columns(2)
            if '상대 RSI(14일)' in fp:
                g1_.altair_chart(fp_line('상대 RSI(14일)', '동일가중 S&P500 ÷ 나스닥100 상대 RSI(14일) — 70·30',
                                         rules=((70, '#c0392b'), (30, '#2e86de'))), width='stretch')
            if '비율 1년 백분위(%)' in fp:
                g2_.altair_chart(fp_line('비율 1년 백분위(%)', '동일가중 ÷ 나스닥100 비율의 1년 백분위(%)', fmt_='.0f'),
                                 width='stretch')
            g3_, g4_ = st.columns(2)
            if '변동성타기팅 노출(배)' in fp:
                g3_.altair_chart(fp_line('변동성타기팅 노출(배)', '변동성 타기팅 노출(10% ÷ 실현변동성, 상한 1.5)', fmt_='.2f'),
                                 width='stretch')
            if 'VIX−실현변동성(%p)' in fp:
                g4_.altair_chart(fp_line('VIX−실현변동성(%p)', 'VIX − S&P 실현변동성(%p): 사건 보험료', rules=((0, '#999'),)),
                                 width='stretch')
        if len(fpt):
            cols_ = [c for c in ['항목', '값', '전일', '1주 전', '1달 전', '판정', '무엇', '읽는 법(참고)'] if c in fpt]
            st.dataframe(fpt[cols_], hide_index=True, width='stretch')

        # 2026-11-15 의장 "역도산은 폐지하고 모든 수급을 시타델이 하는 것으로 통합": ETF 자금·국내 수급도 여기
        st.markdown('**ETF 자금 · 국내 수급**')
        fca_, fcb_ = st.columns(2, gap='large')
        fl = csv(DAY, 'ETF자금')
        if len(fl) and '유입_5일' in fl:
            for mk_, lbl_, where in (('미국', '미국', fca_), ('한국', '국내', fcb_)):
                f_ = fl[fl['시장'].astype(str) == mk_].assign(v=lambda x: num(x['유입_5일']))
                # 2026-11-11 SOXX 5일 +206억 달러(순자산의 47%) 오류: 하루·5일 유입이 순자산의 10%를 넘으면 좌수 자료 오류로 보고 뺀다
                aum_ = num(f_['순자산']).abs()
                bad_ = ((f_['v'].abs() > aum_ * 0.10) | (num(f_['유입_1일']).abs() > aum_ * 0.10)) & aum_.gt(0)
                if bad_.any():
                    where.caption(f'{lbl_} 좌수 자료 점검 중이라 뺌: ' + ', '.join(f_.loc[bad_, '코드'].astype(str)))
                f_ = f_[~bad_]
                if len(f_):
                    f_ = pd.concat([f_.nlargest(6, 'v'), f_.nsmallest(4, 'v')]).drop_duplicates('이름')
                    where.altair_chart(hbar(f_, '이름', 'v', f'{lbl_} ETF 자금 5일 유입 상·하위', fmtv='+,.0f'), width='stretch')
        # 2026-11-11 의장 "ETF 자금 유입을 1년·6달·3달 그래프로, 액수보다 추세": 좌수(발행 수) 흐름, 시작 = 100.
        # 좌수는 가격과 무관하게 돈이 들어오면 늘고 나가면 줄어 자금 추세를 바로 보여 준다.
        fh_ = flow_hist()
        if len(fh_):
            span_ = st.segmented_control('기간', ['3달', '6달', '1년'], default='6달', key='flowspan',
                                         label_visibility='collapsed')
            start_ = fh_['날짜'].max() - pd.DateOffset(months={'3달': 3, '6달': 6, '1년': 12}[span_ or '6달'])
            for mk_, deflt in (('미국', ['SPY', 'XLK', 'XLF', 'XLV', 'XLE']),
                               # 국내 기본 6개 (11/11 의장)
                               ('한국', ['TIGER 200', 'TIGER 반도체', 'KODEX 미국S&P500', 'ACE 미국빅테크', 'SOL 초단기채', '커버드콜'])):
                w_ = fh_[(fh_['시장'] == mk_) & (fh_['날짜'] >= start_)].sort_values('날짜').copy()
                if not len(w_):
                    continue
                w_['이름'] = w_.groupby('코드')['이름'].transform('last')
                # 하루에 좌수가 10% 넘게 바뀐 ETF는 자료 오류로 보고 뺀다(11/11 SOXX)
                jump_ = w_.groupby('코드')['상장좌수'].transform(lambda x: x.pct_change().abs().max())
                if (jump_ > 0.10).any():
                    st.caption(f'{"미국" if mk_ == "미국" else "국내"} 좌수 자료 점검 중이라 뺌: '
                               + ', '.join(sorted(w_.loc[jump_ > 0.10, '코드'].astype(str).unique())))
                w_ = w_[~(jump_ > 0.10)]
                if not len(w_):
                    continue
                first_ = w_.groupby('코드')['날짜'].transform('min')
                full_ = (first_ <= start_ + pd.Timedelta(days=10))
                if full_.any():
                    w_ = w_[full_]                                     # 기간 처음부터 기록이 있는 ETF만
                since_ = w_['날짜'].min()
                w_['지수'] = w_['상장좌수'] / w_.groupby('코드')['상장좌수'].transform('first') * 100
                chg_ = w_.groupby('이름')['지수'].last().sub(100).round(1).reset_index()
                lbl_ = '미국' if mk_ == '미국' else '국내'
                st.markdown(f'**{lbl_} ETF 자금 추세 · 좌수(발행 수) 흐름, 시작 = 100** '
                            f':small[:gray[{since_:%Y-%m-%d}부터]]')
                fa, fb = st.columns([3, 2], gap='large')
                names_ = chg_.sort_values('지수', ascending=False)['이름'].tolist()
                key_ = lambda n: str(n).replace(' ', '').upper()
                if mk_ == '미국':
                    dft_ = [n for n in names_ if n.split()[0] in deflt]
                else:
                    dft_ = [n for n in names_ if any(key_(d) in key_(n) for d in deflt)]
                pick_ = fa.multiselect('ETF', names_, default=dft_, key=f'flowpick_{mk_}', label_visibility='collapsed')
                if pick_:
                    ln_ = w_[w_['이름'].isin(pick_)]
                    fa.altair_chart(
                        alt.Chart(ln_).mark_line(strokeWidth=2).encode(
                            x=alt.X('날짜:T', title=None, axis=alt.Axis(format='%y.%m.%d' if mk_ == '한국' else '%y.%m')),
                            y=alt.Y('지수:Q', title=None, scale=alt.Scale(zero=False)),
                            color=alt.Color('이름:N', title=None, legend=alt.Legend(orient='bottom', columns=2, labelLimit=260)),
                            tooltip=['이름', alt.Tooltip('날짜:T', format='%Y-%m-%d'), alt.Tooltip('지수:Q', format='.1f')])
                        + alt.Chart(pd.DataFrame({'y': [100]})).mark_rule(strokeDash=[4, 4], color='#9ca3af').encode(y='y:Q'),
                        width='stretch')
                sel_ = chg_[chg_['이름'].isin(pick_)] if pick_ else chg_
                fb.altair_chart(hbar(sel_, '이름', '지수', f'기간 중 좌수 변화(%)', fmtv='+.1f'), width='stretch')
            st.caption('좌수 = 발행된 ETF 수. 돈이 들어오면 늘고 나가면 준다(가격 오르내림과 무관). '
                       'SPDR(XL*·SPY·SPYM)은 State Street 공식 1년 이력. 국내와 QQQ·SOXX 등은 10/29부터 쌓는 중이라 그 날부터 보임.')
        kf = csv(DAY, '국내수급')
        if len(kf) and '외국인 5일(억원)' in kf:
            k_ = kf.assign(v=num(kf['외국인 5일(억원)']))
            st.altair_chart(hbar(k_, '종목', 'v', '국내 종목 외국인 5일 순매수(억원)', fmtv='+,.0f'), width='stretch')

    # 4 리오: 금리·환율·유가·금·MOVE·하이일드 등
    with T['리스크']:
        data_head(speech(sc, KEYS['리스크'], nm))
        # 2026-11-11 의장 "리스크 지표도 비교가 중요한데 오늘 것만 나와 있다, 그래프로": 핵심 지표 흐름 + 1주·1달·1년 전 비교
        RISK_KEY = ['미국 10년', '미국 30년', 'MOVE', 'VIX', '하이일드 스프레드', '10년−2년', '원/달러', 'WTI']
        rk_ = [n for n in RISK_KEY if n in R and len(R[n]['_hist']) >= 2]
        if rk_:
            rspan = st.segmented_control('기간', ['3달', '6달', '1년'], default='6달', key='riskspan', label_visibility='collapsed')
            rmon = {'3달': 3, '6달': 6, '1년': 12}[rspan or '6달']
            for i in range(0, len(rk_), 4):
                cols_ = st.columns(4)
                for c_, n in zip(cols_, rk_[i:i + 4]):
                    h_ = R[n]['_hist']
                    now_ = float(h_.iloc[-1])
                    cmp_ = []
                    for lab, off in (('1주', pd.DateOffset(weeks=1)), ('1달', pd.DateOffset(months=1)), ('1년', pd.DateOffset(years=1))):
                        pv = at_or_before(h_, h_.index[-1] - off)
                        if pv is not None and h_.index[0] <= h_.index[-1] - off:
                            cmp_.append(f'{lab} 전 {pv:,.2f}')
                    w = h_[h_.index >= h_.index[-1] - pd.DateOffset(months=rmon)]
                    with c_.container(border=True):
                        st.markdown(f'**{n}** {now_:,.2f}  \n:small[:gray[{" · ".join(cmp_) or "비교 이력 없음"}]]')
                        st.altair_chart(chart_1y(n, w, R[n]['_unit'], h=150).properties(title=''), width='stretch')
        st.caption('줄을 누르면 그 지표의 최근 1년 그래프가 표 아래에 나옵니다. 주간·월간 지표는 전주·전월 대비. '
                   '신호: 의장 기준은 그대로, 나머지는 바닥 찾기 기준 클로드 제안(제안 표시). 🟢 바닥 쪽 · 🟠 주의 · 🔴 위험 · ⚪ 평상.')
        market_tables(R, ['금리', '환율', '원자재', '변동성', '신용·금융 스트레스', '연준 참고 (댈러스·클리블랜드·애틀랜타)',
                          '고용', '침체 신호·자금'])

    # 5 포보스: 공포탐욕 게이지(발표 때 반드시) · 7개 지표 · 추이
    with T['공포']:
        data_head(speech(sc, KEYS['공포'], nm))
        tot = fg[fg['구분'] == '종합'].iloc[0] if len(fg) and (fg['구분'] == '종합').any() else None
        if tot is None:
            st.info('이 날짜의 공포탐욕 자료가 없습니다.')
        else:
            g1, g2 = st.columns([1, 2], gap='large')
            s = num(pd.Series([tot['점수']])).iloc[0]
            with g1:
                st.html(gauge_svg(s, tot['판정']))
                trs = ''
                for k in ['전일', '1주 전', '1개월 전', '1년 전']:
                    pv = num(pd.Series([tot.get(k)])).iloc[0]
                    if pd.isna(pv):
                        continue
                    dv = s - pv
                    trs += (f'<tr><td style="padding:4px 8px;color:#6b7280">{k}</td>'
                            f'<td style="padding:4px 8px;text-align:right;font-weight:700;color:{fg_color(pv)}">{pv:.1f}</td>'
                            f'<td style="padding:4px 8px;color:{fg_color(pv)};font-size:13px">{fg_label(pv)}</td>'
                            f'<td style="padding:4px 8px;text-align:right;color:{DN if dv < 0 else UP}">지금 {dv:+.1f}</td></tr>')
                if trs:
                    st.html('<table style="width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;'
                            f'font-size:15px">{trs}</table>')
            with g2:
                fh = series('공포탐욕', 'Fear & Greed Index')
                if len(fh):
                    span = st.segmented_control('기간', ['1달', '3달', '6달', '1년'], default='3달', key='fgspan',
                                                label_visibility='collapsed')
                    months = {'1달': 1, '3달': 3, '6달': 6, '1년': 12}[span or '3달']
                    st.altair_chart(fg_chart(fh[fh.index >= fh.index[-1] - pd.DateOffset(months=months)]), width='stretch')
                    st.caption('점선 70 = 의장 기준(70 넘으면 현금↑).')
        f7 = fg[fg['구분'] == '지표'] if len(fg) else fg
        if len(f7):
            # 7개 지표 구간 표 (스트림릿 순서, 영어)
            rows7 = []
            for _, r in f7.iterrows():
                sc7 = num(pd.Series([r['점수']])).iloc[0]
                rows7.append({'Indicator': r['지표'].split('. ', 1)[-1], 'Score': sc7, 'Rating': r['판정']})
            cols = st.columns(4)
            for i, (_, r) in enumerate(f7.iterrows()):
                key = r['지표'].split('. ', 1)[-1]
                raw = series('공포탐욕', r['지표'])
                with cols[i % 4].container(border=True):
                    st.markdown(f'**{key}**')
                    st.html(score_bar(num(pd.Series([r['점수']])).iloc[0], r['판정']))
                    if len(raw):
                        st.metric(r.get('원천값 설명') or '원천값', fmt(raw.iloc[-1], 2))
                        if st.button('1년 그래프', key=f'f1y_{key}', width='stretch'):
                            show_1y(key, raw)
        market_tables(R, ['지수 · 변동성'])

    # 6 미스 밸류·데스크: 데스크 하위 탭(발표 파일), 콜로키움 100 히트맵(층별), 하루 등락 상·하위
    with T['섹터']:
        data_head(speech(sc, KEYS['섹터'], nm))
        market_tables(R, ['지수'])

    # 7 미스 차트: 예외 검정, 바닥 기준(일봉 RSI≤30 + 50일 이격≤90 + 월봉 5개월선 아래), 60주선 근처
    with T['기술']:
        data_head(speech(sc, KEYS['기술'], nm))
        ex = csv(DAY, '예외검정')
        if len(ex):
            p10, p13 = num(ex.get('10년_하락p')), num(ex.get('잔차13주_하락p'))
            hit = ex[(p10 <= 0.05) | (p13 <= 0.05)]
            cols_ = [c for c in ['정식 종목명', '52주고점대비(%)', '10년_하락p', '잔차13주_하락p', '베타(주간2년)', '예외 정리'] if c in ex]
            st.markdown(f'**예외적 하락 (10년 자기역사 p ≤ 0.05 또는 베타 잔차 13주 p ≤ 0.05) · {len(hit)}종목**')
            st.dataframe(hit[cols_].sort_values(cols_[2] if len(cols_) > 2 else cols_[0]), hide_index=True, width='stretch')
        # 섹터 ETF 60·20주선 지도: 2026-11-15 역도산 폐지 → 차트 칸으로(담당은 의장 확인 중)
        yd = csv(DAY, '역도산')
        a, b = st.columns(2, gap='large')
        if len(yd) and '60주 이격' in yd:
            e = yd[yd['구분'] == 'ETF'].copy()
            e['이름'] = e['ETF'].map(lambda x: f'{hmmod.SECTOR_KO.get(x, x)} {x}')
            a.altair_chart(gap_bars(e, '이름', '60주 이격', '미국 섹터 ETF · 60주선 이격(100 = 선 위치)'), width='stretch')
            b.altair_chart(gap_bars(e, '이름', '20주 이격', '미국 섹터 ETF · 20주선 이격'), width='stretch')
        else:
            a.info('섹터 ETF 지도(_역도산.csv)가 없습니다.')
        if len(sec) and '주_20주_이격도' in sec:
            s_ = sec.assign(이름=sec['종목'].map(short), v=num(sec['주_20주_이격도']))
            a.altair_chart(gap_bars(s_, '이름', 'v', '국내 섹터 ETF · 20주선 이격'), width='stretch')
        nx = csv(DAY, '닉스')
        if len(nx) and {'일_RSI', '일_50일_이격도', '월_5개월선'} <= set(nx.columns) and len(price):
            cl = price.set_index('yfinance 티커')['종가']
            nx = nx.assign(종가=num(nx['yfinance 티커'].map(cl)))
            ok = nx[(num(nx['일_RSI']) <= 30) & (num(nx['일_50일_이격도']) <= 90) & (nx['종가'] < num(nx['월_5개월선']))]
            st.markdown(f'**바닥 기준 세 조건 충족 (일봉 RSI ≤ 30 · 50일 이격 ≤ 90 · 월봉 5개월선 아래) · {len(ok)}종목**')
            st.dataframe(ok[['정식 종목명', '일_RSI', '일_50일_이격도']], hide_index=True, width='stretch') if len(ok) else st.caption('없음')
        yd = csv(DAY, '역도산')
        if len(yd) and '60주 이격' in yd:
            near = yd[(yd['구분'] == '종목') & (num(yd['60주 이격']).between(97, 103))]
            st.markdown(f'**60주선 근처(이격 97~103) 미국 섹터 상위 종목 · {len(near)}종목**')
            if len(near):
                st.dataframe(near[[c for c in ['티커', 'ETF', '60주 이격', '20주 이격', 'RSI'] if c in near]], hide_index=True, width='stretch')

    # 8 아야카 상: 일본 종목 주봉 RSI 흐름
    with T['일본']:
        data_head(speech(sc, KEYS['일본'], nm))
        jd = csv(DAY, '일본')
        jp = price[price['시장'].astype(str).str.contains('일본')] if len(price) and '시장' in price else pd.DataFrame()
        if not len(jp):
            st.info('이 날짜의 시세 파일에 일본 종목이 없습니다.')
        else:
            ph = prices()
            span = st.segmented_control('기간', ['1년', '2년', '5년'], default='2년', key='jp_span',
                                        label_visibility='collapsed') or '2년'
            yrs = {'1년': 1, '2년': 2, '5년': 5}[span]
            st.caption('주봉 RSI(와일더 14주). 점선 30 아래(옅은 초록 칸) = 과매도, 70 위 = 과열. 판정 없이 흐름만.')
            cols, k = st.columns(2), 0
            for _, r in jp.iterrows():
                c = ph[ph['티커'] == r['yfinance 티커']].set_index('날짜')['가격'].sort_index() if len(ph) else pd.Series(dtype=float)
                if len(c) < 30:
                    continue
                w = c.groupby(c.index.to_period('W-FRI')).last()
                w.index = w.index.to_timestamp(how='end').normalize()
                rs = wilder_rsi(w).dropna()
                rs = rs[rs.index >= rs.index[-1] - pd.DateOffset(years=yrs)]
                if len(rs) < 2:
                    continue
                with cols[k % 2].container(border=True):
                    st.altair_chart(rsi_chart(r['정식 종목명'], rs), width='stretch')
                k += 1
        if len(jd):
            with st.expander('일본 날씨·주봉 위치 표 (_일본.csv)'):
                st.dataframe(jd, hide_index=True, width='stretch')

    # 9 엘피스: 코스피 50일 이격, 아직 공포가 깊은 지표(🟢), 많이 빠진 종목
    with T['긍정']:
        data_head(speech(sc, KEYS['긍정'], nm))
        a, b = st.columns(2, gap='large')
        with a:
            r = R.get('코스피 50일 이격도')
            if r and len(r['_hist']) >= 2:
                st.altair_chart(chart_1y('코스피 50일 이격도', r['_hist']), width='stretch')
            deep = [x for x in R.values() if str(x['신호']).startswith('🟢')]
            st.markdown('**바닥 쪽 신호(🟢)가 켜진 지표**')
            if deep:
                st.dataframe(pd.DataFrame(deep)[['항목', '현재', '신호']], hide_index=True, width='stretch')
            else:
                st.caption('없음')
        with b:
            ex = csv(DAY, '예외검정')
            if len(ex) and '52주고점대비(%)' in ex:
                ex_ = ex.assign(v=num(ex['52주고점대비(%)'])).nsmallest(15, 'v')
                st.altair_chart(hbar(ex_, '정식 종목명', 'v', '콜로키움 100 · 52주 고점 대비 가장 많이 빠진 15종목(%)',
                                     fmtv='+.1f'), width='stretch')

    # 10 기타: 발표 파일에서 위 칸에 안 걸린 위원, 종목 전체 표·수집 점검 안내
    with T['기타']:
        spoke = speech(sc, KEYS['기타'], nm)
        used = [k for _, _, ks in PRESENTERS[:-1] for k in ks]
        for m in (sc or {}).get('members', []):
            if not any(k in str(m.get('name', '')) for k in used + ['기타']):
                present.member(DAY, m, nm); spoke = True
        if not spoke:
            st.caption('종목 전체 표·주봉 차트·회의록·수집 점검은 위쪽 다른 탭(종목·주봉 차트·회의록·수집 점검)에 있습니다.')

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

# ---------------------------------------------------------------- 포트폴리오 (종목·비중%만, 금액 없음)
PF_DIRS = ['실전 투자 자료', '콜로키움/포트폴리오']    # 앞 폴더부터 찾는다 (드라이브 창구 Code.gs 허용 폴더여야 함)
GOAL_PCT, GOAL_DAY = 20.0, dt.date(2026, 12, 31)       # 첫 목표(2026-10-31 의장): 연말까지 +20%


@st.cache_data(ttl=600, show_spinner=False)
def pf_files():
    """(폴더, 비중 파일 이름들, 제안비중 파일 이름들) — 최근 버전 먼저"""
    for d in PF_DIRS:
        try:
            names = [f['name'] for f in drive.ls(d)]
        except Exception:
            continue
        hold = sorted([n for n in names if n.startswith('주력포트폴리오_Ver.') and n.endswith('.csv')], reverse=True)
        prop = sorted([n for n in names if n.startswith('주력포트폴리오_제안비중_Ver.') and n.endswith('.csv')], reverse=True)
        if hold:
            return d, hold, prop
    return None, [], []


@st.cache_data(ttl=600, show_spinner=False)
def pf_csv(path):
    b = drive.get(path)
    return pd.read_csv(io.BytesIO(b), encoding='utf-8-sig', dtype={'번호': str}) if b else pd.DataFrame()


@st.cache_data(show_spinner=False)
def pf_map():
    return pd.read_csv(ROOT / 'app' / 'portfolio_map.csv', encoding='utf-8-sig', dtype=str)


def ver_date(name):
    m = pd.Series([name]).str.extract(r'Ver\.(\d{8})')[0].iloc[0]
    return dt.datetime.strptime(m, '%Y%m%d').date() if isinstance(m, str) else dt.date.today()


def hbar(df, cat, val, h=None, color='#2a78d6', fmt_='.1f'):
    base = alt.Chart(df).encode(y=alt.Y(f'{cat}:N', sort='-x', title=None),
                                x=alt.X(f'{val}:Q', title=None, axis=alt.Axis(grid=False)))
    bars = base.mark_bar(color=color, cornerRadiusEnd=3)
    text = base.mark_text(align='left', dx=4, fontSize=12).encode(text=alt.Text(f'{val}:Q', format=fmt_))
    return (bars + text).properties(height=h or 28 * len(df) + 10)


with t7:
    folder, hold_names, prop_names = (None, [], []) if LOCAL else pf_files()
    a, b = st.columns([3, 2])
    up_h = b.file_uploader('또는 csv 직접 올리기(이 화면에서만 쓰고 저장하지 않음)', type='csv', key='pf_up')
    hold, prop, src = pd.DataFrame(), pd.DataFrame(), ''
    if up_h is not None:
        hold, src = pd.read_csv(up_h, encoding='utf-8-sig', dtype={'번호': str}), up_h.name
    elif hold_names:
        src = a.selectbox('포트폴리오 파일', hold_names, help=f'드라이브 "{folder}" 폴더')
        hold = pf_csv(f'{folder}/{src}')
        if prop_names:
            prop = pf_csv(f'{folder}/{prop_names[0]}')
    if not len(hold):
        st.info('포트폴리오 csv가 없습니다. 드라이브 "실전 투자 자료" 폴더에 주력포트폴리오_Ver.YYYYMMDD_HHMM.csv'
                '(칸: 시장, 종목, 구분, 전체비중% …)를 두거나 오른쪽에서 csv를 올려 주세요. '
                '"실전 투자 자료"를 읽으려면 드라이브 창구(apps_script/Code.gs)를 새 버전으로 배포해야 합니다.')
    else:
        try:
            h = P.load(hold, pf_map())
        except ValueError as e:
            st.error(str(e))
            st.stop()
        miss = h.loc[h['번호'].isna() & (h['비중'] > 0), '종목'].tolist()
        st.caption(f'{src} · {len(h)}줄 · 비중 합 {h["비중"].sum():.1f}%'
                   + (f' · 콜로키움 100에서 못 찾은 종목: {", ".join(miss)} (가격 계산에서 빠짐)' if miss else '')
                   + (f' · 제안 비중: {prop_names[0]}' if len(prop) else ''))
        px = prices()

        # ---- 목표 진척
        st.subheader('첫 목표 진척')
        c = st.columns([1, 1, 1, 1])
        base = c[0].date_input('기준일', value=ver_date(src) if src else dt.date.today(),
                               help='이 날 종가부터 지금까지의 수익률. 지금 비중을 기준일부터 들고 있었다고 봅니다.')
        contrib, tot, last = P.since(h, px, base) if len(px) else (pd.DataFrame(), float('nan'), None)
        c[1].metric('기준일 뒤 수익률', fmt(tot, 2, '%'),
                    help=f'최근 가격 {last.date() if last is not None else "—"} · 현지 통화 기준(환율 미반영)')
        c[2].metric(f'목표 {GOAL_DAY:%m/%d}까지', f'+{GOAL_PCT:.0f}%',
                    delta=None if pd.isna(tot) else f'남은 {GOAL_PCT - tot:.1f}%p', delta_color='off')
        c[3].metric('남은 날', f'{(GOAL_DAY - dt.datetime.now(KST).date()).days}일')
        if len(contrib):
            k = contrib.dropna(subset=['기여%p'])
            with st.expander('종목별 기여(%p) 보기'):
                st.dataframe(k[['종목', '비중', '기준일 뒤%', '기여%p']].style.map(updown, subset=['기준일 뒤%', '기여%p'])
                             .format({'비중': '{:.1f}', '기준일 뒤%': '{:+.1f}', '기여%p': '{:+.2f}'}),
                             hide_index=True, width='stretch')

        # ---- 1. 목표 대비 차이
        st.subheader('1. 목표 배분 대비 (현금성 30 · 지수 30 · 주식·ETF 40)')
        tg = P.target_gap(h)
        mk_w = h.groupby('시장')['비중'].sum().round(1)
        st.caption('시장 비중: ' + ' · '.join(f'{k} {v:.1f}%' for k, v in mk_w.sort_values(ascending=False).items())
                   + '. 목표는 시장마다 같은 30/30/40 틀(12/15~12/31 전환, 의장 10/31)입니다.')
        cols = st.columns(len(tg['시장'].unique()))
        for col, (mk, g) in zip(cols, tg.groupby('시장', sort=False)):
            col.markdown(f'**{mk}**')
            d = g.melt(id_vars='자산군', value_vars=['시장 안%', '목표%'], var_name='구분', value_name='%')
            ch = alt.Chart(d).mark_bar().encode(
                y=alt.Y('자산군:N', title=None, sort=list(P.TARGET)), x=alt.X('%:Q', title=None, scale=alt.Scale(domain=[0, 100])),
                yOffset=alt.YOffset('구분:N', sort=['시장 안%', '목표%']), color=alt.Color('구분:N', scale=alt.Scale(domain=['시장 안%', '목표%'], range=['#2a78d6', '#c7ccd4']),
                                                legend=alt.Legend(orient='bottom', title=None)),
                tooltip=['자산군', '구분', alt.Tooltip('%:Q', format='.1f')]).properties(height=170)
            col.altair_chart(ch, width='stretch')
            col.dataframe(g[['자산군', '시장 안%', '목표%', '차이%p']].style.map(updown, subset=['차이%p'])
                          .format({'시장 안%': '{:.1f}', '목표%': '{:.0f}', '차이%p': '{:+.1f}'}),
                          hide_index=True, width='stretch')

        # ---- 2. 쏠림
        st.subheader('2. 쏠림 점검')
        stats, by_desk, by_mk, by_sec = P.concentration(h)
        c = st.columns(5)
        for i, (k, v) in enumerate(stats.items()):
            c[i].metric(k, v if isinstance(v, str) else (f'{v:.1f}%' if '%' in k else f'{v:g}'),
                        help='비중이 모두 같다면 몇 종목을 든 것과 같은지(HHI 역수)' if k == '실효 종목 수' else None)
        a, b = st.columns(2)
        a.markdown('**섹터 데스크별**')
        a.altair_chart(hbar(by_desk, '데스크', '비중%'), width='stretch')
        b.markdown('**업종별 (상위 12, 반도체는 하나로)**')
        b.altair_chart(hbar(by_sec.head(12), '업종', '비중%', color='#1baf7a'), width='stretch')

        # ---- 3. 위험도
        st.subheader('3. 위험도 (베타 · 최대 낙폭 · 상관)')
        if not len(px):
            st.info('가격 이력이 없어 위험도를 계산하지 못했습니다.')
        else:
            bt = P.betas(h, px)
            hb = h.assign(베타=h['yfinance 티커'].map(bt))
            ok = hb.dropna(subset=['베타'])
            wbeta = (ok['베타'] * ok['비중']).sum() / ok['비중'].sum() if len(ok) else float('nan')
            s3 = P.port_series(h, px, 3)
            s1 = s3[s3.index >= s3.index[-1] - pd.DateOffset(years=1)] if len(s3) else s3
            dd1, st1, en1 = P.drawdown(s1)
            dd3, st3, en3 = P.drawdown(s3)
            c = st.columns(3)
            c[0].metric('가중 베타', fmt(wbeta, 2), help='종목별 2년 주간 베타(한국=TIGER 200, 미국=SPYM)를 비중으로 평균')
            c[1].metric('1년 최대 낙폭', fmt(dd1, 1, '%'),
                        help=f'{st1:%Y-%m-%d} → {en1:%Y-%m-%d}' if st1 is not None else None)
            c[2].metric('3년 최대 낙폭', fmt(dd3, 1, '%'),
                        help=f'{st3:%Y-%m-%d} → {en3:%Y-%m-%d}' if st3 is not None else None)
            if len(s3):
                dd = (s3 / s3.cummax() - 1).mul(100).rename('낙폭%').reset_index().rename(columns={'index': '날짜'})
                dd.columns = ['날짜', '낙폭%']
                st.altair_chart(alt.Chart(dd).mark_area(color=DN, opacity=0.35, line={'color': DN}).encode(
                    x=alt.X('날짜:T', title=None, axis=alt.Axis(format='%Y-%m', grid=False)),
                    y=alt.Y('낙폭%:Q', title='고점 대비 %'),
                    tooltip=[alt.Tooltip('날짜:T', format='%Y-%m-%d'), alt.Tooltip('낙폭%:Q', format='.1f')]
                ).properties(height=180), width='stretch')
                st.caption('지금 비중을 3년 동안 그대로 들고 있었다면의 고점 대비 낙폭(현지 통화, 환율 미반영).')
            a, b = st.columns([3, 2])
            cm, pairs = P.corr(h, px)
            if len(cm):
                long = cm.reset_index(names='종목 1').melt('종목 1', var_name='종목 2', value_name='상관')
                order = list(cm.columns)
                a.markdown('**1년 주간 수익률 상관 (비중 1% 이상)**')
                a.altair_chart(alt.Chart(long).mark_rect().encode(
                    x=alt.X('종목 2:N', sort=order, title=None, axis=alt.Axis(labelAngle=-60, labelOverlap=False)),
                    y=alt.Y('종목 1:N', sort=order, title=None, axis=alt.Axis(labelOverlap=False)),
                    color=alt.Color('상관:Q', scale=alt.Scale(scheme='blueorange', domain=[-1, 1]), legend=None),
                    tooltip=['종목 1', '종목 2', alt.Tooltip('상관:Q', format='.2f')]).properties(height=22 * len(order) + 20),
                    width='stretch')
            b.markdown('**같이 움직이는 묶음 (상관 0.7 이상)**')
            if len(pairs):
                b.dataframe(pairs, hide_index=True, width='stretch', height=min(38 * (len(pairs) + 1), 300))
            else:
                b.caption('없음')
            b.markdown('**종목별 베타**')
            b.dataframe(hb.loc[hb['비중'] > 0, ['종목', '비중', '베타']].sort_values('베타', ascending=False)
                        .style.format({'비중': '{:.1f}', '베타': '{:.2f}'}, na_rep='—'),
                        hide_index=True, width='stretch', height=300)

        # ---- 4. 닉스 신호 대조
        st.subheader('4. 보유 종목 × 닉스 팀 지표')
        sg = P.signals(h, csv(DAY, '닉스'))
        if not len(sg):
            st.info('이 날짜의 닉스 파일이 없습니다.')
        else:
            st.dataframe(sg.style.map(updown, subset=['52주 고점 대비%']).format(
                {'비중%': '{:.1f}', '52주 고점 대비%': '{:+.1f}', '일 RSI': '{:.0f}', '주 RSI': '{:.0f}', '20주 이격도': '{:.0f}',
                 }, na_rep='—'),
                hide_index=True, width='stretch', height=min(38 * (len(sg) + 1), 900),
                column_config={'눈여겨볼 점': st.column_config.TextColumn(width='large')})
            st.caption('블록 9-닉스 값을 그대로 옮긴 것입니다. "눈여겨볼 점"은 지지·저항 상태, 패턴, 주봉 MACD 방향, '
                       'RSI 30 이하·70 이상, 볼린저 밖 같은 사실만 적고, 신호 판정은 클로토·라케시스·아트로포스가 회의에서 합니다.')

        # ---- 5. 매매 후보표
        st.subheader('5. 매매 후보표 (목표 비중 − 지금 비중)')
        tl = P.trade_list(h, prop)
        tl = tl[(tl['지금%'] > 0) | (tl.get('제안%', pd.Series(0, index=tl.index)).fillna(0) > 0)
                | (tl.get('마감 목표%', pd.Series(0, index=tl.index)).fillna(0) > 0)]
        gapc = [x for x in ('마감까지%p', '제안까지%p') if x in tl]
        st.dataframe(tl.style.map(updown, subset=gapc + [x for x in ['수익률%'] if x in tl]).format(
            {x: '{:.1f}' for x in ('지금%', '마감 목표%', '제안%')} | {x: '{:+.1f}' for x in gapc + ['수익률%']}, na_rep='—'),
            hide_index=True, width='stretch', height=min(38 * (len(tl) + 1), 1000),
            column_config={'제안 근거': st.column_config.TextColumn(width='large')})
        st.caption('제안% = 최근 제안비중 csv(위원 회의안). 마감 목표% = 포트폴리오 csv의 마감비율(시장 안 %)을 전체 %로 바꾼 값 '
                   '(12/15~12/31 전환 목표, 빈칸은 0). 초록은 늘릴 쪽, 빨강은 줄일 쪽. 제안까지 차이가 큰 순서입니다.')


# ---------------------------------------------------------------- 섹터 순환
QUAD_COLOR = {'선도': UP, '약화': '#e8a33d', '침체': DN, '개선': '#2a78d6'}


def short(n):
    for w in ('TIGER ', 'KODEX ', 'PLUS ', 'SOL ', 'RISE ', 'HANARO ', '코리아', '플러스', 'TOP10', 'TOP3', 'TOP2'):
        n = n.replace(w, '')
    return n.replace('미국필라델피아반도체나스닥', '미국반도체').replace('글로벌HBM반도체', 'HBM반도체').strip()


with t6:
    if not len(sec):
        st.info('이 날짜의 섹터 파일이 없습니다(블록 9-섹터는 2026-10-29부터 만듭니다).')
    else:
        sec['이름'] = sec['종목'].map(short)
        jd = sec['판정'].fillna('')
        names_of = lambda w: ', '.join(sec.loc[jd.str.contains(w), '이름']) or '없음'
        c = st.columns(4)
        c[0].metric('20주선 위 섹터', f"{int((sec['20주선_위'] == '위').sum())} / {len(sec)}",
                    help='국내 섹터 전체의 체력(시장 폭). 0이면 모든 섹터가 중기 하락 추세')
        c[1].metric('라케시스 · 추세 강함', names_of('라케시스 추세 강함'))
        c[2].metric('미스 차트 · 반전 후보', names_of('미스 차트 반전 후보'))
        c[3].metric('아트로포스 · 과열·꺾임', str(int(jd.str.contains('아트로포스').sum())) + '개',
                    help=names_of('아트로포스'))
        st.caption('닉스 섹터 순환 룰 v1(2026-10-29 의장 승인). 비교 기준은 TIGER 200. 판정은 충족 여부와 근거만이며 비중 결정은 의장이 합니다.')

        if len(sec_tr):
            tr = sec_tr.merge(sec[['번호', '이름', 'RRG_사분면']], on='번호')
            dflt = sec.loc[jd.str.contains('미스 차트 반전 후보|라케시스 추세 강함'), '이름'].tolist()
            see = st.multiselect('8주 궤적을 볼 섹터', sec['이름'].tolist(), default=dflt,
                                 placeholder='섹터를 고르면 최근 8주 움직임이 선으로 나옵니다')
            rng = lambda k: (min(tr[k].min(), 97) - 2, max(tr[k].max(), 103) + 2)
            (x0, x1), (y0, y1) = rng('RS_Ratio'), rng('RS_Momentum')
            sx = alt.Scale(domain=[x0, x1], nice=False, zero=False)
            sy = alt.Scale(domain=[y0, y1], nice=False, zero=False)
            qc = alt.Color('RRG_사분면:N', scale=alt.Scale(domain=list(QUAD_COLOR), range=list(QUAD_COLOR.values())),
                           legend=alt.Legend(orient='top', title='지금 사분면'))
            x = alt.X('RS_Ratio:Q', scale=sx, title='RS-Ratio (100 위 = 반년 평균보다 시장 대비 강함)')
            y = alt.Y('RS_Momentum:Q', scale=sy, title='RS-Momentum (100 위 = 좋아지는 중)')
            tip = [alt.Tooltip('이름:N', title='섹터'), alt.Tooltip('주:N', title='주'),
                   alt.Tooltip('RS_Ratio:Q', format='.1f'), alt.Tooltip('RS_Momentum:Q', format='.1f')]
            path = alt.Chart(tr[tr['이름'].isin(see)]).mark_line(strokeWidth=2, opacity=0.6).encode(
                x=x, y=y, color=qc, detail='번호:N', order=alt.Order('몇주전:Q', sort='descending'))
            dots = alt.Chart(tr[tr['이름'].isin(see) & (tr['몇주전'] > 0)]).mark_circle(opacity=0.45).encode(x=x, y=y, color=qc, size=alt.value(25), tooltip=tip)
            now = tr[tr['몇주전'] == 0]
            head = alt.Chart(now).mark_circle(size=140, opacity=1).encode(x=x, y=y, color=qc, tooltip=tip)
            label = alt.Chart(now).mark_text(align='left', dx=8, fontSize=12).encode(x=x, y=y, text='이름:N')
            mid = pd.DataFrame({'v': [100]})
            vline = alt.Chart(mid).mark_rule(color='#9aa0a6').encode(x='v:Q')
            hline = alt.Chart(mid).mark_rule(color='#9aa0a6').encode(y='v:Q')
            corner = pd.DataFrame({'x': [x1 - 0.5, x1 - 0.5, x0 + 0.5, x0 + 0.5], 'y': [y1 - 0.5, y0 + 0.5, y0 + 0.5, y1 - 0.5],
                                   't': ['선도', '약화', '침체', '개선'], 'a': ['right', 'right', 'left', 'left'],
                                   'b': ['top', 'bottom', 'bottom', 'top']})
            qtext = alt.layer(*[alt.Chart(corner[corner['t'] == t]).mark_text(
                fontSize=15, fontWeight='bold', opacity=0.35, align=r.a, baseline=r.b, color=QUAD_COLOR[t]).encode(
                x=alt.X('x:Q', scale=sx), y=alt.Y('y:Q', scale=sy), text='t:N') for t, r in zip(corner['t'], corner.itertuples())])
            st.altair_chart((vline + hline + qtext + path + dots + head + label).properties(height=520), width='stretch')
            st.caption('섹터 로테이션 사분면(주봉, 최근 8주 궤적, 큰 점이 이번 주). 섹터는 대개 선도 → 약화 → 침체 → 개선 → 선도 '
                       '순서로 시계방향으로 돕니다. 침체 → 개선은 바닥 반전, 선도 → 약화는 꺾임의 첫 신호입니다. '
                       'RS = 섹터 ÷ TIGER 200, RS-Ratio = RS ÷ 26주 평균, RS-Momentum = RS-Ratio ÷ 4주 전 (원조 RRG 근사식).')

        show = [k for k in ['번호', '이름', '모멘텀순위', '판정', '초과_1개월(%p)', '초과_3개월(%p)', '초과_6개월(%p)',
                            '초과_12개월(%p)', 'RRG_4주전', 'RRG_사분면', '20주선_위', '20주선_기울기', '52주고점대비(%)',
                            '3개월저점대비반등(%)', '일_RSI', '일_RSI_단순평균식', '주_RSI', '주_CCI', '주_STO_K',
                            '주_볼린저_%B', '주_20주_이격도', '주_일목_구름위치', '주_패턴'] if k in sec]
        tbl = sec[show].rename(columns={'일_RSI': '일 RSI', '일_RSI_단순평균식': '일 RSI(미래에셋식)', '주_RSI': '주 RSI',
                                        '주_CCI': '주 CCI', '주_STO_K': '주 STO K', '주_볼린저_%B': '주 %B',
                                        '주_20주_이격도': '20주 이격도', '주_일목_구름위치': '주 일목 구름', '주_패턴': '주봉 패턴'})
        ex = [k for k in tbl if k.startswith('초과_') or k in ('52주고점대비(%)', '3개월저점대비반등(%)')]
        for k in ex + ['일 RSI', '일 RSI(미래에셋식)', '주 RSI', '주 CCI', '주 STO K', '주 %B', '20주 이격도']:
            if k in tbl:
                tbl[k] = num(tbl[k])
        qcol = lambda v: f'color:{QUAD_COLOR[v]};font-weight:600' if v in QUAD_COLOR else ''
        st.dataframe(
            tbl.style.map(updown, subset=ex).map(qcol, subset=[k for k in ('RRG_4주전', 'RRG_사분면') if k in tbl]).format(
                {**{k: '{:+.1f}' for k in ex}, '일 RSI': '{:.1f}', '일 RSI(미래에셋식)': '{:.1f}', '주 RSI': '{:.1f}',
                 '주 CCI': '{:.0f}', '주 STO K': '{:.1f}', '주 %B': '{:.2f}', '20주 이격도': '{:.1f}'}, na_rep='—'),
            hide_index=True, width='stretch', height=38 * (len(tbl) + 1),
            column_config={'판정': st.column_config.TextColumn(width='large'),
                           '주봉 패턴': st.column_config.TextColumn(width='large')})
        st.caption('모멘텀 순위 = 1·3·6개월 TIGER 200 대비 초과수익 순위의 평균. RSI는 와일더식(판정), 미래에셋식(단순평균) 병기. '
                   '7개 기준 전체는 같은 날짜 수집데이터의 _섹터.csv에 있습니다.')
        with st.expander('판정 기준 (룰 v1, 2026-10-29 의장 승인)'):
            st.markdown(
                '- **라케시스 추세 강함**: 사분면 선도 + 모멘텀 순위 상위 1/3 + 20주선 위·20주선 상승. 선도인데 20주선 아래면 "관찰".\n'
                '- **미스 차트 반전 후보**: 52주 고점 대비 -20% 이하에서 반전 증거 3개 중 2개 이상(1개면 "관찰"). '
                '① 상대강도 반전(개선, 또는 4주 전 침체·개선 → 선도) ② 주봉 MACD 오실레이터 음수권 상승 전환 '
                '③ 주봉 바닥 패턴 넥라인 돌파 또는 지지 반등.\n'
                '- **아트로포스 과열**: 주봉 RSI 70 이상, 20주 이격도 120 이상, 주봉 볼린저 상단 위 중 하나. '
                '**꺾임 주의**: 4주 전 선도 → 지금 약화·침체, 주봉 MACD 양수권 하락 전환, 주봉 천장 넥라인 이탈 중 하나. 매도 가격은 제시하지 않습니다.')

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
