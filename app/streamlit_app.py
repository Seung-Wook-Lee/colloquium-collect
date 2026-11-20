# ======================================================================
# 스튜디오 톰앤수 — 회의 화면 (2026-11-20 의장: "스트림릿 오후회의, 오전 회의 2개만 해. 단순화하라고")
#   국장전 회의(10:00)와 미장전 회의(22:00) 두 칸만. 각 칸은 회의에서 읽는 원고(회의원고.md)를 그대로 보여 준다.
#   읽는 것: 드라이브 '콜로키움 수집데이터/YYYYMMDD/YYYYMMDD_회의원고.md', 'YYYYMMDD_미장전_회의원고.md'
#            (meeting.yml이 만든다. 원고와 화면이 같은 파일이라 회의 발표와 화면이 어긋나지 않는다)
#   드라이브는 수집 프로그램과 같은 창구(drive.py, 비밀값 DRIVE_URL·DRIVE_TOKEN)로 읽는다.
# ======================================================================
import os, re, sys, datetime as dt
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    for k in ('DRIVE_URL', 'DRIVE_TOKEN', 'COLLOQ_DATA'):
        if k in st.secrets and not os.environ.get(k):
            os.environ[k] = str(st.secrets[k])
except Exception:
    pass
import drive  # noqa: E402

st.set_page_config(page_title='스튜디오 톰앤수 회의', page_icon='📊', layout='wide')
st.markdown('''<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css">
<style>
.block-container {max-width: 1100px; padding-top: 2rem;}
.stMarkdown p, .stMarkdown li, .stMarkdown td, .stMarkdown th {font-size: 16px; line-height: 1.9;}
.stMarkdown table {width: 100%; border-collapse: collapse;}
.stMarkdown td, .stMarkdown th {padding: 8px 12px;}
.item-t {font-size: 15px; font-weight: 400; color: #555; padding-top: 6px;}
.item-v {font-size: 17px; font-weight: 400; line-height: 1.6;}
h1, h2, h3, h4, h5 {font-weight: 500 !important; letter-spacing: -0.2px;}
.stMarkdown strong, .stMarkdown b, [data-testid="stMetricValue"] {font-weight: 500 !important;}
.stMarkdown th {font-weight: 500;}
.why {font-size: 13px; color: #888; line-height: 1.6;}
.sec-t {font-size: 22px; font-weight: 500; line-height: 1.4; margin: 2px 0 10px; font-family: inherit; font-variant-numeric: lining-nums;}
.big-t td, .big-t th {font-size: 18px !important; padding: 8px 14px !important;}
.who {font-size: 14px; font-weight: 500; color: #4a4a4a; margin-left: 10px; letter-spacing: 0.2px;}
.box-t {font-size: 17px; font-weight: 500; color: #333; margin-bottom: 4px;}
.note {font-size: 12px; color: #8a8a8a; line-height: 1.6; margin-top: 10px;}
.sub {font-size: 13px; color: #888; line-height: 1.7;}
.num-t {width: 100%; border-collapse: collapse; margin-top: 4px;}
.num-t th {font-size: 12.5px !important; font-weight: 400 !important; color: #999; text-align: right; padding: 4px 10px !important; border: none !important; border-bottom: 1px solid #eee !important;}
.num-t td {font-size: 24px !important; font-weight: 400; color: #222; text-align: right; padding: 6px 10px !important; border: none !important; font-variant-numeric: tabular-nums;}
.num-t td.lab {font-size: 13px !important; color: #888; text-align: left;}
html, body, [class*='css'], .stMarkdown, .stMetric, button, input {font-family: 'Pretendard Variable', Pretendard, -apple-system, 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif !important;}
</style>''', unsafe_allow_html=True)

D_DATA = '콜로키움 수집데이터'
KST = dt.timezone(dt.timedelta(hours=9))
LOCAL = os.environ.get('COLLOQ_DATA', '').strip()
SESSIONS = [('국장전 회의 (10:00)', '회의원고.md'), ('미장전 회의 (22:00)', '미장전_회의원고.md')]


@st.cache_data(ttl=300, show_spinner=False)
def read(day, name):
    rel = f'{day}/{day}_{name}'
    if LOCAL:
        p = Path(LOCAL) / rel
        return p.read_text(encoding='utf-8') if p.exists() else None
    b = drive.get(f'{D_DATA}/{rel}')
    return b.decode('utf-8-sig') if b else None


EN = [   # 11/20 의장: 사람·센터 이름은 영어로, 작게
    ('마켓 센터', 'Market Center'), ('엔진 블록 센터', 'Engine Block Center'), ('퀀트센터', 'Quant Center'), ('닉스 팀', 'Team Nyx'),
    ('미스터 마켓', 'Mr. Market'), ('미스 시타델', 'Miss Citadel'), ('미스 리스크', 'Miss Risk'), ('미스 차트', 'Miss Chart'),
    ('미스 밸류', 'Miss Value'), ('미스 세마이', 'Miss Semi'), ('미스터 빅스', 'Mr. Bix'), ('미스터 로보', 'Mr. Robo'),
    ('미스 파이낸스', 'Miss Finance'), ('마담헤비', 'Madame Heavy'), ('일라이 존슨', 'Eli Johnson'), ('엘피스', 'Elpis'),
    ('클로토', 'Clotho'), ('라케시스', 'Lachesis'), ('아트로포스', 'Atropos'), ('뚜지', 'Ttuji'), ('국장', 'Chief'),
    ('(센터장)', ', Head'), ('(팀장)', ', Head'), ('센터장', 'Head'), ('팀장', 'Head')]


def en(t):
    for k, v in EN:
        t = re.sub(re.escape(k) + ('(?!전)' if k == '국장' else ''), v, t)   # '국장전'은 그대로
    return t


def sec_title(title):
    name, _, who = title.partition(' | ')
    if ' — ' in name:   # '4 퀀트센터 — 닉스 팀' → 이름 칸은 센터·팀(영어 작게)로
        name, team = name.split(' — ', 1)
        who = f'{team} · {who}' if who else team
    w = f'<span class="who">{en(who)}</span>' if who else ''
    return f'<div class="sec-t">{en(name)}{w}</div>'


def order_premarket(secs):
    """11/20 23:42 의장 미장전 순서: 1 바닥 근접도 | 엔진 블록 센터 → 2 미장전 시황 | 미스터 마켓 → 나머지는 한 칸씩 뒤로.
    옛 원고의 '결론' 칸은 보이지 않는다."""
    mm, rest = [], []
    for t, b in secs:
        num, _, nm = t.partition(' ')
        if '결론' in t:
            continue
        if '마켓 센터' in t or '미스터 마켓' in t:
            mm.append(b)
            continue
        m = re.match(r'(\d+)(.*)', num)
        rest.append((f'{int(m.group(1)) + 1}{m.group(2)} {nm}' if m else t, b))
    return ([('2 미장전 시황 | 마켓 센터', '\n\n'.join(mm))] if mm else []) + rest


def sections(md):
    """'## 칸 제목' 단위로 나눈다. 맨 앞(제목·오늘의 한 종목)은 머리말."""
    parts = re.split(r'(?m)^## ', md)
    head = re.sub(r'(?m)^# .*\n?', '', parts[0]).strip()
    return head, [(p.split('\n', 1)[0].strip(), p.split('\n', 1)[1] if '\n' in p else '') for p in parts[1:]]


ITEM = re.compile(r'^\*\*(\d+)\.\s*(.+?)\*\*\s*$')
STOCK = re.compile(r'([^,()/]+?)\(52주 고점 대비 (-?[\d.]+)%,?\s*([^)]*)\)')
STAT = re.compile(r'([A-Za-z가-힣][A-Za-z가-힣0-9()/ ]*?) ([+-][\d.]+)%\(승률 (\d+)%\)')
GROUP = re.compile(r'평균 ([+-][\d.]+)%, 승률 ([\d.]+)%\(전체 주 ([+-][\d.]+)%, ([\d.]+)%\)')
RED, BLUE = '#c8372d', '#2b6cb0'


CHEAP = re.compile(r'(,\s*)?\+?\s*싼가\s*[\d.]+( 이상)?|(,\s*)?싼가(?!\s*[\d.])[^,·)]*')


def clean(t):
    return CHEAP.sub('', t)


def blocks(body):
    """빈 줄로 나눈 덩어리: ('item', 번호, 제목, 내용, 근거) / ('table', md) / ('text', md)"""
    out = []
    body = re.sub(r'(?m)^[*\s]*오늘의 한 종목.*\n?', '', body)   # 11/21 의장: 한 종목 줄은 어느 회의에도 안 보임
    for b in re.split(r'\n\s*\n', clean(body).strip()):
        lines = [l.rstrip() for l in b.split('\n') if l.strip()]
        if not lines:
            continue
        if len(lines) == 1 and lines[0].endswith(':') and len(lines[0]) < 20:
            continue                                   # '미스 시타델:' 같은 발표자 줄
        m = ITEM.match(lines[0])
        if m:
            why = [l for l in lines[1:] if l.startswith('*근거')]
            val = [l.rstrip(' ') for l in lines[1:] if not l.startswith('*근거')]
            out.append(('item', m.group(1), m.group(2), ' '.join(v.strip() for v in val),
                        ' '.join(w.strip('*') for w in why)))
        elif all(l.startswith('|') for l in lines):
            out.append(('table', '\n'.join(lines)))
        else:
            out.append(('text', '\n'.join(lines)))
    return out


def stock_chart(rows):
    df = pd.DataFrame(rows, columns=['종목', '52주 고점 대비(%)', '그 밖의 숫자'])
    df['종목'] = df['종목'].str.strip()
    st.dataframe(df, hide_index=True, use_container_width=True)


def stat_chart(why):
    rows = [(n.strip(), float(r), float(w)) for n, r, w in STAT.findall(why)]
    g = GROUP.search(why)
    if g:
        rows = [('떨어진 우량주 묶음', float(g.group(1)), float(g.group(2))), ('전체', float(g.group(3)), float(g.group(4)))] + rows
    if len(rows) < 2:
        return False
    df = pd.DataFrame(rows, columns=['묶음', '26주 평균 수익률(%)', '승률(%)']).drop_duplicates('묶음')
    df = df.sort_values('26주 평균 수익률(%)', ascending=False)
    base = alt.Chart(df).encode(y=alt.Y('묶음:N', sort=None, title=None, axis=alt.Axis(labelFontSize=13, labelLimit=220)))
    bars = base.mark_bar(cornerRadiusEnd=3, height=18).encode(
        x=alt.X('26주 평균 수익률(%):Q', title='26주 평균 수익률(%)'),
        color=alt.condition('datum["26주 평균 수익률(%)"] >= 0', alt.value(BLUE), alt.value(RED)),
        tooltip=list(df.columns))
    text = base.mark_text(align='left', dx=5, fontSize=13).encode(
        x='26주 평균 수익률(%):Q', text=alt.Text('label:N')).transform_calculate(
        label='format(datum["26주 평균 수익률(%)"], "+.1f") + "%  · 승률 " + format(datum["승률(%)"], ".0f") + "%"')
    st.caption('같은 조건이었던 과거 26주 성적')
    st.altair_chart((bars + text).properties(height=34 * len(df) + 20), use_container_width=True)
    return True


QUOTE = re.compile(r'^(-?[\d,]+(?:\.\d+)?%?)\s*\(([+-][\d.]+)%\)')
FLOW = re.compile(r'([^,/]+?)\s([+-][\d,]+(?:\.\d+)?)(억|백만달러)')
NUM = re.compile(r'^[+-]?[\d,]+(?:\.\d+)?')


def hbar(df, label, val, fmt='+,.1f', unit='', height=None):
    """양수 파랑·음수 빨강 가로 막대 + 막대 끝 값 글자(글자 들어갈 여백을 둔다)"""
    df = df.copy()
    df['_t'] = df[val].map(lambda v: (f'{v:+,.2f}' if abs(v) < 100 else f'{v:+,.0f}') + unit)
    lo, hi = min(0.0, df[val].min()), max(0.0, df[val].max())
    pad = (hi - lo or 1) * 0.28
    dom = [lo - (pad if lo < 0 else 0), hi + (pad if hi > 0 else 0)]
    y = alt.Y(f'{label}:N', sort=None, title=None, axis=alt.Axis(labelFontSize=14, labelLimit=260, domain=False, ticks=False))
    x = alt.X(f'{val}:Q', title=None, scale=alt.Scale(domain=dom, nice=False),
              axis=alt.Axis(labelFontSize=11, labelColor='#999', grid=True, gridColor='#f0f0f0', domain=False, ticks=False, format='~s'))
    base = alt.Chart(df).encode(y=y)
    bars = base.mark_bar(cornerRadiusEnd=3, height=16).encode(
        x=x, color=alt.condition(f'datum["{val}"] >= 0', alt.value(BLUE), alt.value(RED)))
    pos = base.mark_text(align='left', dx=5, fontSize=13, color='#333').encode(x=alt.X(f'{val}:Q'), text='_t:N').transform_filter(f'datum["{val}"] >= 0')
    neg = base.mark_text(align='right', dx=-5, fontSize=13, color=RED).encode(x=alt.X(f'{val}:Q'), text='_t:N').transform_filter(f'datum["{val}"] < 0')
    st.altair_chart((bars + pos + neg).properties(height=height or 30 * len(df) + 24).configure_view(strokeWidth=0),
                    use_container_width=True)


def num(x):
    m = NUM.match(str(x).strip().replace('−', '-'))
    return float(m.group(0).replace(',', '')) if m else None


def md_table(md):
    rows = [[c.strip() for c in l.strip().strip('|').split('|')] for l in md.split('\n')]
    rows = [r for r in rows if not all(re.fullmatch(r':?-+:?', c) for c in r)]
    return pd.DataFrame(rows[1:], columns=rows[0]) if len(rows) > 1 else None


def table_chart(md):
    """표 + 첫 숫자 열(부호 있는 값)을 막대로"""
    df = md_table(md)
    if df is None or df.empty:
        st.markdown(md); return
    lab = [c for c in df.columns if df[c].map(num).isna().all()]
    def signed(c):
        v = df[c].astype(str).str.strip()
        units = set(v.str.replace(r'^[+-−]?[\d,.]+', '', regex=True))
        return df[c].map(num).notna().mean() > 0.6 and v.str.match(r'^[+-−]').mean() > 0.6 and len(units) == 1
    numc = [c for c in df.columns if c not in lab and signed(c) and re.search(r'%|억|달러', c + ''.join(df[c].astype(str)))]
    if '종가' in df.columns:   # 11/20 의장: 지수 종가·전일 대비는 위 시세 그래프와 겹침 → 남는 칸만
        return
    if lab and numc and len(df) >= 2:   # 11/20 의장: 순매수·순매도(유입·유출) 그래프는 따로, 그래프 묶음과 표 묶음도 따로
        d = df.copy()
        grp = lab[0] if len(lab) > 1 and df[lab[0]].nunique() <= 3 else None
        key = lab[1] if grp else lab[0]
        d['_l'] = d[key]
        d['_v'] = d[numc[0]].map(num)
        d = d.dropna(subset=['_v'])
        parts = [(g, d[d[grp] == g]) for g in d[grp].drop_duplicates()] if grp else [(numc[0], d)]
        cols = st.columns(len(parts))
        for col, (g, x) in zip(cols, parts):
            with col:
                st.markdown(f'<div class="item-t">{g}</div>', unsafe_allow_html=True)
                hbar(x.reindex(x['_v'].abs().sort_values(ascending=False).index), '_l', '_v', unit='')
                if grp:   # 11/20 의장: 왼쪽 = 순매수(유입) 그래프와 표, 오른쪽 = 순매도(유출) 그래프와 표
                    st.dataframe(x[[c for c in df.columns if c != grp]], hide_index=True, use_container_width=True)
        if not grp:
            st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.dataframe(df, hide_index=True, use_container_width=True)


def flow_chart(val):
    rows = []
    for part in val.split('/'):
        sign = '유출' if '유출' in part[:4] else '유입'
        part = re.sub(r'^\s*(유입|유출)\s*', '', part)
        for n, v, u in FLOW.findall(part):
            rows.append((n.strip(), num(v), u))
    if len(rows) < 2:
        return False
    df = pd.DataFrame(rows, columns=['이름', '값', '단위'])
    st.caption(f'5일 자금 ({df["단위"].iloc[0]})')
    hbar(df, '이름', '값')
    return True


def kospi_gap():
    """11/20 의장: 코스피 50일 이격을 그래프로(지수2년.csv ^KS11, 종가 ÷ 50일 평균 × 100, 의장 기준 125 과열 주의·130 과열)."""
    import io
    rel = '00_퀀트입력/지수2년.csv'
    try:
        if LOCAL:
            I = pd.read_csv(Path(LOCAL) / rel, encoding='utf-8-sig', index_col=0, parse_dates=True)
        else:
            b = drive.get(f'{D_DATA}/{rel}')
            I = pd.read_csv(io.BytesIO(b), encoding='utf-8-sig', index_col=0, parse_dates=True) if b else None
    except Exception:
        I = None
    if I is None or '^KS11' not in I:
        return False
    s = pd.to_numeric(I['^KS11'], errors='coerce').dropna()
    g = (s / s.rolling(50).mean() * 100).dropna().tail(260)
    if g.empty:
        return False
    df = pd.DataFrame({'날짜': g.index, '50일 이격': g.round(1).values})
    lo, hi = min(df['50일 이격'].min(), 95) - 3, max(df['50일 이격'].max(), 130) + 3
    ax = alt.Axis(grid=True, gridColor='#eee', domain=False, ticks=False, labelColor='#888', labelFontSize=11)
    x = alt.X('날짜:T', title=None, axis=alt.Axis(format='%y.%m', grid=False, domain=False, ticks=False, labelColor='#888', labelFontSize=11))
    y = alt.Y('50일 이격:Q', title=None, scale=alt.Scale(domain=[lo, hi]), axis=ax)
    band = alt.Chart(pd.DataFrame({'a': [125], 'b': [hi]})).mark_rect(color='#f3d6d3', opacity=0.5).encode(y='a:Q', y2='b:Q')
    base = alt.Chart(pd.DataFrame({'y': [100]})).mark_rule(color='#bbb', strokeWidth=1).encode(y='y:Q')
    area = alt.Chart(df).mark_area(
        line={'color': BLUE, 'strokeWidth': 1.6}, interpolate='monotone',
        color=alt.Gradient(gradient='linear', stops=[alt.GradientStop(color='white', offset=0), alt.GradientStop(color='#cfe0f3', offset=1)],
                           x1=1, x2=1, y1=1, y2=0)).encode(x=x, y=y, y2=alt.datum(lo), tooltip=['날짜:T', '50일 이격:Q'])
    last = df.tail(1)
    dot = alt.Chart(last).mark_circle(size=60, color=BLUE).encode(x='날짜:T', y='50일 이격:Q')
    txt = alt.Chart(last).mark_text(align='right', dx=-8, dy=-10, fontSize=13, color='#333').encode(
        x='날짜:T', y='50일 이격:Q', text=alt.Text('50일 이격:Q', format='.1f'))
    tags = alt.Chart(pd.DataFrame({'y': [125, 100], 't': ['과열 주의 125 이상', '50일 평균 100']})).mark_text(
        align='left', dx=4, dy=-6, fontSize=11, color='#999').encode(y='y:Q', x=alt.value(0), text='t:N')
    st.markdown('<div class="item-t">코스피 50일 이격</div>', unsafe_allow_html=True)
    st.altair_chart((band + base + area + dot + txt + tags).properties(height=240).configure_view(strokeWidth=0),
                    use_container_width=True)
    return True


@st.cache_data(ttl=3600, show_spinner=False)
def _fred(sid, start):
    import io, urllib.request
    u = f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}'
    raw = urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20).read()
    d = pd.read_csv(io.BytesIO(raw))
    d.columns = ['날짜', '값']
    d['날짜'] = pd.to_datetime(d['날짜'])
    d['값'] = pd.to_numeric(d['값'], errors='coerce')
    return d.dropna()


def hy_chart():
    """11/20 의장: 하이일드 스프레드 그래프(FRED BAMLH0A0HYM2, 최근 1년). 3% 위 주의, 5% 위 위기(리스크 규칙)."""
    try:
        df = _fred('BAMLH0A0HYM2', (dt.date.today() - dt.timedelta(days=372)).isoformat())
    except Exception:
        return False
    if df.empty:
        return False
    lo, hi = min(df['값'].min(), 2.5) - 0.2, max(df['값'].max(), 5.0) + 0.3
    x = alt.X('날짜:T', title=None, axis=alt.Axis(format='%y.%m', grid=False, domain=False, ticks=False, labelColor='#888', labelFontSize=11))
    y = alt.Y('값:Q', title=None, scale=alt.Scale(domain=[lo, hi]),
              axis=alt.Axis(grid=True, gridColor='#eee', domain=False, ticks=False, labelColor='#888', labelFontSize=11, format='.1f'))
    zones = pd.DataFrame({'a': [3.0, 5.0], 'b': [5.0, hi], 'c': ['#fbe9d2', '#f3d6d3']})
    band = alt.Chart(zones).mark_rect(opacity=0.55).encode(y='a:Q', y2='b:Q', color=alt.Color('c:N', scale=None))
    line = alt.Chart(df).mark_line(color=BLUE, strokeWidth=1.6, interpolate='monotone').encode(x=x, y=y, tooltip=['날짜:T', '값:Q'])
    last = df.tail(1)
    dot = alt.Chart(last).mark_circle(size=60, color=BLUE).encode(x='날짜:T', y='값:Q')
    txt = alt.Chart(last).mark_text(align='right', dx=-8, dy=-10, fontSize=13, color='#333').encode(
        x='날짜:T', y='값:Q', text=alt.Text('값:Q', format='.2f'))
    tags = alt.Chart(pd.DataFrame({'y': [3.0, 5.0], 't': ['주의 3%', '위기 5%']})).mark_text(
        align='left', dx=4, dy=-6, fontSize=11, color='#999').encode(y='y:Q', x=alt.value(0), text='t:N')
    st.markdown('<div class="item-t">하이일드 스프레드 (%)</div>', unsafe_allow_html=True)
    st.altair_chart((band + line + dot + txt + tags).properties(height=220).configure_view(strokeWidth=0), use_container_width=True)
    return True


FULL = [('HY spread', 'High Yield Spread'), ('UST 10Y yield', 'US Treasury 10-Year Yield'),
        ('HMM bear-regime probability', 'Hidden Markov Model bear-regime probability')]


def full_name(t):   # 11/20 의장: 약자로 쓰지 말고 다 쓴다
    for k, v in FULL:
        t = t.replace(k, v)
    return t


def why_box(why):
    short = re.sub(r'\s*—\s*퀀트센터/\S+', '', why)
    short = re.sub(r'\(\S+\.csv[^)]*\)|07시 |\S+\.csv', '', short)
    with st.expander('근거', expanded=False):
        st.markdown(f'<div class="why">{short}</div>', unsafe_allow_html=True)


FG_BANDS = [(0, 25, '#c0392b', 'Extreme Fear'), (25, 45, '#e67e22', 'Fear'), (45, 55, '#9aa0a6', 'Neutral'),
            (55, 75, '#7cb342', 'Greed'), (75, 100, '#2e7d32', 'Extreme Greed')]


def fg_color(v):
    return next(c for lo, hi, c, _ in FG_BANDS if v < hi or hi == 100)


def gauge_svg(score, label):
    """11/21 의장: 공포탐욕은 구간이 보이는 그림으로(옛 게이지 되살림)"""
    import base64, math
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
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 175">{segs}{ticks}'
           f'<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="#1d2330" stroke-width="4" stroke-linecap="round"/>'
           f'<circle cx="{cx}" cy="{cy}" r="7" fill="#1d2330"/></svg>')
    b64 = base64.b64encode(svg.encode()).decode()
    return (f'<div style="text-align:center"><img src="data:image/svg+xml;base64,{b64}" style="width:100%;max-width:320px">'
            f'<div style="font-size:40px;font-weight:400;line-height:1;margin-top:-6px;color:{col}">{score:.1f}</div>'
            f'<div style="font-size:14px;color:{col}">{label}</div></div>')


def score_bar(score, label):
    col = fg_color(score)
    marks = ''.join(f'<div style="position:absolute;left:{t}%;top:0;bottom:0;border-left:1px solid #fff"></div>' for t in (25, 45, 55, 75))
    return (f'<div style="display:flex;align-items:center;gap:10px"><div style="position:relative;flex:1;height:10px;background:#eceff1;'
            f'border-radius:5px;overflow:hidden"><div style="width:{score:.0f}%;height:100%;background:{col}"></div>{marks}</div>'
            f'<span style="font-size:18px;font-variant-numeric:tabular-nums;min-width:38px;text-align:right">{score:.0f}</span>'
            f'<span style="color:{col};font-size:12px;min-width:84px">{label}</span></div>')


FG_TOTAL = re.compile(r'Fear & Greed Index ([\d.]+) ([A-Za-z ]+?) — 전일 ([+-]?[\d.]+), 1주 전 대비 ([+-]?[\d.]+), 1개월 전 대비 ([+-]?[\d.]+)')


def fg_total(val):
    m = FG_TOTAL.search(val)
    if not m:
        return False
    s = float(m.group(1))
    c1, c2 = st.columns([1, 1.3], gap='large')
    c1.html(gauge_svg(s, m.group(2)))
    rows = ''.join(f'<tr><td style="padding:6px 8px;color:#6b7280">{k}</td><td style="padding:6px 8px;text-align:right;'
                   f'color:{RED if float(v) < 0 else BLUE};font-size:18px">{float(v):+.1f}</td></tr>'
                   for k, v in (('전일 대비', m.group(3)), ('1주 전 대비', m.group(4)), ('1개월 전 대비', m.group(5))))
    c2.html('<div style="font-size:13px;color:#888;margin:28px 0 4px">CNN Fear & Greed Index · 0 공포 ~ 100 탐욕</div>'
            f'<table style="width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:15px">{rows}</table>')
    return True


def fg_seven(df):
    """7개 지표: 지표마다 0~100 막대(구간 색) + 오늘 값 한 줄"""
    cols = st.columns(2)
    for i, (_, r) in enumerate(df.iterrows()):
        try:
            sc = float(str(r['점수']).replace(',', ''))
        except ValueError:
            continue
        with cols[i % 2].container(border=True):
            st.markdown(f"<div style='font-size:14px;color:#333'>{str(r['지표']).split('. ', 1)[-1]}</div>", unsafe_allow_html=True)
            st.html(score_bar(sc, r['구간']))
            mean = re.sub(r'\s*\((공포|탐욕|중립) 쪽\)\s*$', '', str(r.get('시장 의미', '')))
            st.markdown(f"<div style='font-size:12px;color:#888;line-height:1.5'>{mean}</div>", unsafe_allow_html=True)


def signal_chips(md):
    """시장 블록 표 → 켜진 신호만 부담·기회 두 줄 칩(11/21 의장: 난잡한 표 대신)"""
    df = md_table(md)
    if df is None or '쪽' not in df or '오늘' not in df:
        return False
    on = df[df['오늘'].str.strip() == '켜짐']
    c1, c2 = st.columns(2, gap='large')
    for col, side, color, name in ((c1, '부담', RED, '나쁜 신호'), (c2, '기회', '#2e7d32', '좋은 신호')):
        x = on[on['쪽'].str.contains(side)]
        tot = df['쪽'].str.contains(side).sum()
        chips = ''.join(
            f"<div style='border-left:3px solid {color};padding:6px 10px;margin:6px 0;background:#fafafa'>"
            f"<div style='font-size:14px;color:#333'>{str(r['공식']).split(' — ', 1)[-1].split(' — ')[0]}</div>"
            f"<div style='font-size:12px;color:#999'>{r['질문']}</div></div>" for _, r in x.iterrows())
        col.html(f"<div style='font-size:13px;color:#888'>{name}</div>"
                 f"<div style='font-size:30px;color:{color};line-height:1.2'>{len(x)}<span style='font-size:14px;color:#999'> / {tot}개 켜짐</span></div>"
                 + (chips or "<div style='color:#999;font-size:13px;margin-top:6px'>없음</div>"))
    return True


SKIP_BOX = ('매크로 체크리스트', '리스크 표')   # 11/21 의장: 겹치는 표는 화면에서 뺌
SKIP_ITEM = ('공포 쪽 지표', '탐욕 쪽 지표')


def render(body):
    bl = blocks(body)
    quotes = [b for b in bl if b[0] == 'item' and QUOTE.match(b[3])]
    if len(quotes) >= 4:                       # 시세 칸: 한 장의 막대그래프 + 값
        df = pd.DataFrame([(b[2], QUOTE.match(b[3]).group(1), float(QUOTE.match(b[3]).group(2))) for b in quotes],
                          columns=['지표', '값', '전일 대비(%)'])
        df['지표'] = df['지표'] + '  ' + df['값']
        st.caption('전일 대비 %')
        hbar(df, '지표', '전일 대비(%)', unit='%')
        bl = [b for b in bl if b not in quotes]
    rows, whys = [], []

    cnt = [0]
    CIRC = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚'

    def circ(t):   # 11/20 의장: 칸 안 항목은 동그라미 번호를 위에서부터
        cnt[0] += 1
        return f"{CIRC[cnt[0] - 1] if cnt[0] <= len(CIRC) else cnt[0]} {t}"

    def flush():
        if rows:
            t = '| 항목 | 내용 |\n|---|---|\n' + '\n'.join(f'| {circ(r[0])} | {r[1].replace("|", "·")} |' for r in rows)
            st.markdown(t)
            rows.clear()

    merged = []
    for b in bl:   # '**제목**' 바로 뒤 표 → 한 묶음
        if b[0] == 'table' and merged and merged[-1][0] == 'text' and merged[-1][1].strip().startswith('**') and merged[-1][1].strip().endswith('**'):
            merged[-1] = ('titled', merged[-1][1].strip().strip('*'), b[1])
        else:
            merged.append(b)
    bl = merged
    for b in bl:
        if b[0] == 'item':
            _, n, title, val, why = b
            title = full_name(title.replace('근원 CPI', 'Core CPI').replace('근원 PCE', 'Core PCE'))   # 11/20 의장: 연준 용어 그대로
            if '10년 실질' in title:   # 11/20 의장: 10년 실질금리 삭제
                continue
            val = val.replace('직전 발표 대비', '전월 대비')
            if title in SKIP_ITEM:
                continue
            if title == '종합' and 'Fear & Greed' in val:   # 11/21 의장: 공포탐욕은 구간 게이지로
                flush()
                if fg_total(val):
                    continue
            if title == '하이일드 스프레드':   # 11/20 의장: 하이일드 스프레드는 그래프로
                flush()
                if hy_chart():
                    continue
            if why:
                whys.append(f'**{title}** — {why}')
            if '지수(오늘)' in title or (title == '시장 이격' and '50일 이격' in val):   # 11/20 의장: 지수 종가는 위 시세 그래프와 겹침
                continue
            if '50일 이격' in title:   # 11/20 의장: 코스피 50일 이격은 그래프로
                flush()
                if kospi_gap():
                    continue
            stocks = STOCK.findall(val)
            if len(stocks) >= 2 or FLOW.search(val) and len(FLOW.findall(val)) >= 2 or (why and len(STAT.findall(why)) + bool(GROUP.search(why)) >= 2):
                flush()
                st.markdown(f'#### {title}')
                if len(stocks) >= 2:
                    stock_chart(stocks)
                elif not flow_chart(val):
                    st.markdown(f'<div class="item-v">{val}</div>', unsafe_allow_html=True)
                if why:
                    stat_chart(why)
            else:
                rows.append((title, val))
            continue
        flush()
        if b[0] == 'titled' and b[1].startswith(SKIP_BOX):
            continue
        if b[0] == 'titled' and b[1].startswith('시장 블록'):
            with st.container(border=True):
                st.markdown('<div class="box-t">오늘 켜진 시장 신호</div>', unsafe_allow_html=True)
                if not signal_chips(b[2]):
                    table_chart(b[2])
            continue
        if b[0] == 'table' and (b[1].startswith('| 지표 | 점수 | 구간')):
            d7 = md_table(b[1])
            if d7 is not None:
                fg_seven(d7)
                continue
        if b[0] == 'titled':   # 11/20 의장: 제목·그래프·표를 한 상자로
            with st.container(border=True):
                st.markdown(f'<div class="box-t">{b[1]}</div>', unsafe_allow_html=True)
                table_chart(b[2])
        elif b[0] == 'table':
            table_chart(b[1])
        else:
            t = b[1].strip()
            if t.startswith('**') and t.endswith('**'):
                st.markdown(f'#### {t.strip("*")}')
            elif not t.startswith('_출처'):
                st.markdown(t)
    flush()
    if whys:
        with st.expander('근거 보기', expanded=False):
            for w in whys:
                w = re.sub(r'\s*—\s*퀀트센터/\S+', '', w)
                st.markdown(f'<div class="why">{re.sub(r"[(]?[^ (]*[.]csv[^)]*[)]?|07시 ", "", w)}</div>', unsafe_allow_html=True)


def read_csv(day, fname):
    import io
    rel = f'{day}/{day}_{fname}'
    if LOCAL:
        p = Path(LOCAL) / rel
        return pd.read_csv(p, encoding='utf-8-sig') if p.exists() else None
    b = drive.get(f'{D_DATA}/{rel}')
    return pd.read_csv(io.BytesIO(b), encoding='utf-8-sig') if b else None


@st.cache_data(ttl=3 * 3600, show_spinner='바닥 확률 계산 중…')
def bottom_prob():
    """11/21 의장: 연구된 모형으로. Lunde & Timmermann(2004) 위험률 모형(market/lt_bottom.py, 하락 구간은 R bbdetection 필터 그대로)"""
    sys.path.insert(0, str(ROOT / 'market'))
    import lt_bottom as LB
    return LB.hazard_today()


def bottom(day, name, title='바닥 근접도'):
    """이번 하락에서 지금이 바닥(최종 저점 3% 안)일 확률. 지수 종가·VIX·금리로 화면에서 바로 계산."""
    pre = '미장전_' if name.startswith('미장전') else ''
    T = read_csv(day, pre + '바닥확률.csv')   # 엔진(daily.py, 하위 블록 2-12)이 만든 파일을 먼저 읽는다
    if T is None or not len(T) or '확률' not in T:
        try:   # 그 날 파일이 아직 없으면 같은 코드로 바로 계산
            T = bottom_prob()
        except Exception as e:   # noqa: BLE001
            st.caption(f'바닥 확률 계산 실패: {e}')
            return
    NAME = {'^NDX': '나스닥100', '^GSPC': 'S&P500'}

    def pct(v, sign=False):
        x = pd.to_numeric(v, errors='coerce')
        return '' if pd.isna(x) else (f'{x:+.1f}%' if sign else f'{x:.1f}%')
    with st.container(border=True):
        st.markdown(sec_title(title), unsafe_allow_html=True)
        cols = st.columns(len(T))
        for col, (_, r) in zip(cols, T.iterrows()):
            nm = NAME.get(r.get('기준지수'), r.get('기준지수'))
            with col:
                if str(r.get('하락중')) not in ('True', '1', '1.0'):
                    st.metric(f'{nm}', '하락 구간 아님'); continue
                st.metric(f'{nm}이 지금 이번 하락의 바닥일 확률', pct(r.get('확률')))
                st.markdown(f'<div class="sub">고점 대비 {pct(r.get("지금낙폭"))} · {int(r.get("주수"))}주째 · VIX {r.get("VIX"):.1f} · RSI {r.get("RSI"):.0f}</div>'
                            f'<div class="sub">확률이 비슷했던 과거 {int(r.get("비슷한확률_주수"))}주, 그 뒤 지수</div>', unsafe_allow_html=True)
                mdd = (f'{pct(r.get("뒤13주_최대낙폭_평균"), True)} (최악 {pct(r.get("뒤13주_최대낙폭_최악"), True)})'
                       if '뒤13주_최대낙폭_평균' in r and pd.notna(r.get('뒤13주_최대낙폭_평균')) else '자료 없음')
                st.markdown('<table class="num-t"><tr><th></th><th>평균 수익률</th><th>승률</th><th>그 사이 최대 낙폭</th></tr>'
                            f'<tr><td class="lab">13주 뒤</td><td>{pct(r.get("뒤13주_평균"), True)}</td><td>{pct(r.get("뒤13주_승률"))}</td><td>{mdd}</td></tr>'
                            f'<tr><td class="lab">26주 뒤</td><td>{pct(r.get("뒤26주_평균"), True)}</td><td>{pct(r.get("뒤26주_승률"))}</td><td></td></tr></table>', unsafe_allow_html=True)
        tt = '; '.join(f"{NAME.get(r['기준지수'])} AUC {r['검정_AUC']:.2f}" for _, r in T.iterrows())
        st.markdown('<div class="note">산출 방법: Lunde &amp; Timmermann(2004) 위험률 모형. 하락 구간(고점 −5%에서 시작, 저점 +10%에서 끝, R bbdetection 판정) 안에서 '
                    '낙폭·기간·VIX·금리·RSI·200일선 이격으로 "최종 저점 3% 안일 확률"을 계산. '
                    f'2000년부터 해마다 그 전 자료로만 학습해 검정({tt}).</div>', unsafe_allow_html=True)


if not LOCAL and not drive.ready():
    st.error('드라이브 창구 비밀값(DRIVE_URL·DRIVE_TOKEN)이 없습니다.')
    st.stop()

today = dt.datetime.now(KST).date()
day = st.date_input('날짜', today, max_value=today).strftime('%Y%m%d')

for tab, (label, name) in zip(st.tabs([s[0] for s in SESSIONS]), SESSIONS):
    with tab:
        md = read(day, name)
        if not md:
            st.info(f'{day[:4]}-{day[4:6]}-{day[6:]} {label} 원고가 아직 없습니다.')
            continue
        head, secs = sections(md)
        if name.startswith('미장전'):   # 11/20 의장: 원고 첫 줄 자료 메모·한 종목 머리말은 보이지 않음, 순서 1 바닥 근접도 · 2 미장전 시황
            bottom(day, name, '1 바닥 근접도 | 마켓 센터')
            secs = order_premarket(secs)
        else:   # 11/21 의장: 머리말(팀Q 자료 메모·오늘의 한 종목)은 국장전도 보이지 않음
            bottom(day, name)
        merged = []   # 11/20 의장: 같은 이름 칸(퀀트센터 미스 차트·닉스 팀, 섹터 데스크 등)은 상자 하나로
        for title, body in secs:
            nm, _, who = title.partition(' | ')
            base = nm.split(' — ')[0].strip()
            sub = (nm.split(' — ', 1)[1] + ' · ' if ' — ' in nm else '') + who
            if merged and merged[-1][0] == base:
                merged[-1][2].append((sub, body))
            else:
                merged.append([base, title, [(sub, body)], who])
        secs = []
        for base, title, parts, who0 in merged:
            if len(parts) == 1:
                secs.append((title, parts[0][1]))
            else:   # 발표자는 첫 칸 사람 한 명(퀀트센터 = 미스 차트)
                secs.append((f'{base} | {who0}', '\n\n'.join((f"**{en(sub)}**\n\n{b}" if i else b) for i, (sub, b) in enumerate(parts))))
        for title, body in secs:
            with st.container(border=True):
                title = title.replace('수급·포지셔닝', 'Flows & Positioning')   # 11/20 의장: 수급·포지셔닝은 영어로
                st.markdown(sec_title(title), unsafe_allow_html=True)
                render(body)
