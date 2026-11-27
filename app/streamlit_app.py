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
sys.path[:0] = [str(ROOT / 'collect'), str(ROOT / 'app')]   # 11/21 두 폴더: collect(수집)·app(스튜디오)
try:
    for k in ('DRIVE_URL', 'DRIVE_TOKEN', 'COLLOQ_DATA', 'GEMINI_API_KEY'):
        if k in st.secrets and not os.environ.get(k):
            os.environ[k] = str(st.secrets[k])
except Exception:
    pass
import drive  # noqa: E402

st.set_page_config(page_title='스튜디오 톰앤수 회의', page_icon='📊', layout='wide')
st.markdown('''<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css">
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css');
.block-container {max-width: 1100px; padding-top: 2rem;}
.stMarkdown p, .stMarkdown li, .stMarkdown td, .stMarkdown th {font-size: 13.5px; line-height: 1.65;}
.stMarkdown table {width: 100%; border-collapse: collapse;}
.it {width: 100%; border-collapse: collapse; margin: 2px 0 6px;}
.it td {font-size: 13px !important; line-height: 1.6; padding: 6px 8px !important; border: none !important; border-bottom: 1px solid #eee !important; vertical-align: top; color: #222;}
.it td.n, .it th.n {text-align: right; white-space: nowrap; width: 1%; padding-right: 14px !important; font-variant-numeric: tabular-nums;}
.it th {font-size: 12px !important; color: #888; font-weight: 500; padding: 4px 8px !important; border: none !important; border-bottom: 1px solid #ddd !important; background: none !important;}
.it td.d {text-align: right; white-space: nowrap; width: 1%; vertical-align: top;}
.it td.k {font-size: 12px !important; color: #666; white-space: nowrap; width: 30%;}
.stMarkdown td, .stMarkdown th {padding: 6px 10px;}
.item-t {font-size: 12.5px; font-weight: 400; color: #555; padding-top: 6px;}
.item-v {font-size: 13.5px; font-weight: 400; line-height: 1.6;}
h1, h2, h3, h4, h5 {font-weight: 500 !important; letter-spacing: -0.2px;}
h4 {font-size: 15px !important;}
.stMarkdown strong, .stMarkdown b, [data-testid="stMetricValue"] {font-weight: 500 !important;}
.stMarkdown th {font-weight: 500; font-size: 12.5px; color: #777;}
.why {font-size: 13px; color: #888; line-height: 1.6;}
.sec-t {font-size: 18px; font-weight: 500; line-height: 1.4; margin: 2px 0 10px; font-family: inherit; font-variant-numeric: lining-nums;}
.big-t td, .big-t th {font-size: 14px !important; padding: 8px 14px !important;}
.who {font-size: 12px; font-weight: 500; color: #4a4a4a; margin-left: 10px; letter-spacing: 0.2px;}
.box-t {font-size: 14.5px; font-weight: 500; color: #333; margin-bottom: 4px;}
.note {font-size: 12px; color: #8a8a8a; line-height: 1.6; margin-top: 10px;}
.sub {font-size: 13px; color: #888; line-height: 1.7;}
.num-t {width: 100%; border-collapse: collapse; margin-top: 4px;}
.num-t th {font-size: 12.5px !important; font-weight: 400 !important; color: #999; text-align: right; padding: 4px 10px !important; border: none !important; border-bottom: 1px solid #eee !important;}
.num-t td {font-size: 16px !important; font-weight: 400; color: #222; text-align: right; padding: 6px 10px !important; border: none !important; font-variant-numeric: tabular-nums;}
.num-t td.lab {font-size: 12px !important; color: #888; text-align: left; white-space: nowrap;}
[data-testid="stMetricValue"] {font-size: 28px !important;}
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
    ('미스 밸류', 'Miss Value'), ('미스 세마이', 'Miss Semi'), ('미스터 빅스', 'Mr. Big'), ('미스터 로보', 'Mr. Robo'),
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
    return ([('2 미장전 시황 | 미스터 마켓', '\n\n'.join(mm))] if mm else []) + rest


def sections(md):
    """'## 칸 제목' 단위로 나눈다. 맨 앞(제목·오늘의 한 종목)은 머리말."""
    parts = re.split(r'(?m)^## ', md)
    head = re.sub(r'(?m)^# .*\n?', '', parts[0]).strip()
    return head, [(p.split('\n', 1)[0].strip(), p.split('\n', 1)[1] if '\n' in p else '') for p in parts[1:]]


SIGMARK = re.compile(r'^⟦(red|orange|green)⟧\s*')   # personas.render_md가 신호 있는 줄 앞에 붙임
SIGCOL = {'red': '#c8372d', 'orange': '#e08a1e', 'green': '#1b8a2e'}
ITEM = re.compile(r'^\*\*(\d+)\.\s*(.+?)\*\*\s*$')
STOCK = re.compile(r'([^,()/]+?)\(52주 고점 대비 (-?[\d.]+)%,?\s*([^)]*)\)')
STAT = re.compile(r'([A-Za-z가-힣][A-Za-z가-힣0-9()/ ]*?) ([+-][\d.]+)%\(승률 (\d+)%\)')
GROUP = re.compile(r'평균 ([+-][\d.]+)%, 승률 ([\d.]+)%\(전체 주 ([+-][\d.]+)%, ([\d.]+)%\)')
RED, BLUE = '#c8372d', '#2b6cb0'


CHEAP = re.compile(r'(,\s*)?\+?\s*싼가\s*[\d.]+( 이상)?|(,\s*)?싼가(?!\s*[\d.])[^,·)]*')


def clean(t):
    return CHEAP.sub('', t)


FORMULA = {   # 11/23 의장: 항목 밑 계산법(collect/flowpos.py와 같은 식)
    'JPM 추세 신호 전환': '공식: ① S&P500 종가가 21·63·100거래일 전 종가보다 높으면 그 기간은 매수 신호(0~3개) '
                        '② 5거래일 전보다 매수 신호 수가 늘었고 ③ CTA positioning(σ)도 5거래일 전보다 올랐으면 = 전환. '
                        '②·③ 둘 다 맞아야 신호 나옴',
}


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
    if len(rows) <= 1:
        return None
    k = len(rows[0])   # 11/23: 칸 수가 다른 줄(빈 칸·'|' 섞임)이 있어도 화면이 멈추지 않게 맞춤
    return pd.DataFrame([(r + [''] * k)[:k] for r in rows[1:]], columns=rows[0])


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


@st.cache_data(ttl=3 * 3600, show_spinner=False)
def _db_close():
    """10년치 데이터베이스 종가(드라이브 1_data/가격10년_종가.csv.gz) — 화면도 이 하나만 읽음(11/26 의장)."""
    import io
    rel = '1_data/가격10년_종가.csv.gz'
    try:
        if LOCAL:
            return pd.read_csv(Path(LOCAL) / rel, encoding='utf-8-sig', index_col=0, parse_dates=True)
        b = drive.get(f'{D_DATA}/{rel}')
        return pd.read_csv(io.BytesIO(b), compression='gzip', encoding='utf-8-sig', index_col=0, parse_dates=True) if b else None
    except Exception:
        return None


def kospi_gap():
    """11/20 의장: 코스피 50일 이격을 그래프로(10년치 데이터베이스 ^KS11, 종가 ÷ 50일 평균 × 100, 의장 기준 125 과열 주의·130 과열)."""
    I = _db_close()
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


@st.cache_data(ttl=3 * 3600, show_spinner=False)
def _pos_hist():
    import io
    rel = '1_data/가격10년_수급포지셔닝.csv.gz'   # 10년치 데이터베이스 칸(11/26 의장, 옛 00_누적 이력)
    if LOCAL:
        p = Path(LOCAL) / rel
        b = p.read_bytes() if p.exists() else None
    else:
        b = drive.get(f'{D_DATA}/{rel}')
    if not b:
        return None
    H = pd.read_csv(io.BytesIO(b), encoding='utf-8-sig', parse_dates=['날짜'], compression='gzip')
    return H[H['날짜'] >= H['날짜'].max() - pd.Timedelta(days=372)]


POS_PANEL = [   # (칸, 제목, 단위, 기준선[(값, 이름, 색)], 칠할 구간[(아래, 위, 색)])
    ('CTA σ(근사)', 'CTA positioning — 추세추종 펀드 포지션', 'σ',
     [(0, '0', '#999'), (-4, '바닥 −4σ', '#1b8a2e'), (4, '고점 +4σ', '#c8372d')], [(-9, -4, '#dff0e1'), (4, 9, '#f7dedc')]),
    ('변동성타기팅 노출(배)', 'Vol-target exposure — 변동성 목표 펀드 보유 배수', '배',
     [(0.6, '많이 팜 0.6배', '#1b8a2e'), (1.0, '보통 1배', '#999')], [(0, 0.6, '#dff0e1')]),
    ('추세 신호 매수 수(21·63·100일)', 'CTA 추세 신호 — 21·63·100일 매수 신호 수', '/3',
     [(3, '전부 매수 3', '#1b8a2e')], []),
    ('VIX', 'VIX·VXN — S&P500·나스닥100 옵션 변동성 예상(11/26 의장: 백분위 대신 숫자)', '',
     [(33.5, 'L12 33.5', '#1b8a2e'), (15.5, '옛 기준 15.5', '#c8372d')], [(33.5, 90, '#dff0e1')]),
]


def _pos_line(H, col, title, unit, refs, zones):
    """11/23 의장 '크기도 작고 조잡한 디자인 → 더 자세하게, 선그래프로': 1년 선그래프 + 기준선 + 오늘·1주 전·1달 전."""
    cols = [col] + (['VXN'] if col == 'VIX' else [])
    D = H[['날짜'] + cols].melt('날짜', var_name='지표', value_name='값').dropna()
    if D.empty:
        return
    s = H.set_index('날짜')[col].dropna()
    last = s.index[-1]
    def at(days):
        x = s[s.index <= last - pd.Timedelta(days=days)]
        return x.iloc[-1] if len(x) else None
    f = (lambda v: f'{v:.0f}') if unit in ('%', '/3') else (lambda v: f'{v:+.2f}' if unit == 'σ' else f'{v:.2f}')
    now = f(s.iloc[-1]) + ('' if unit == '/3' else unit)
    if col == 'VIX':
        f = lambda v: f'{v:.1f}'
        now = f"VIX {s.iloc[-1]:.1f} · VXN {H['VXN'].dropna().iloc[-1]:.1f}"
    elif unit == '/3':
        now = f"매수 {int(s.iloc[-1])}/3 · 매수 전환까지 S&P {H['CTA 매수 전환까지(%)'].dropna().iloc[-1]:+.1f}%"
    w1, m1 = at(7), at(30)
    sub = ' · '.join(x for x in (f'1주 전 {f(w1)}{"" if unit == "/3" else unit}' if w1 is not None else '',
                                  f'1달 전 {f(m1)}{"" if unit == "/3" else unit}' if m1 is not None else '') if x)
    # 11/23 22:20 의장 '촌스럽고 다닥다닥 → 위아래 여유': 제목·값·비교 세 줄로 나누고 줄 사이를 띄움
    st.markdown(f'<div style="padding:4px 2px 0 2px">'
                f'<div style="font-size:13px;font-weight:600;color:#2e7d32;letter-spacing:-0.2px">{title}</div>'
                f'<div style="font-size:24px;font-weight:700;color:#222;line-height:1.2;margin-top:10px">{now}</div>'
                f'<div style="font-size:12px;color:#999;margin-top:6px;margin-bottom:14px">{sub + " · " if sub else ""}{last:%Y-%m-%d} 기준</div>'
                f'</div>', unsafe_allow_html=True)
    lo = min(D['값'].min(), *[r[0] for r in refs]); hi = max(D['값'].max(), *[r[0] for r in refs])
    pad = (hi - lo) * 0.08 or 0.5
    dom = [lo - pad, hi + pad] if unit != '%' else [0, 100]
    if unit == '/3':
        dom = [-0.2, 3.3]
    x = alt.X('날짜:T', title=None, axis=alt.Axis(format='%y.%m', grid=False, domain=False, ticks=False, labelColor='#888', labelFontSize=11))
    y = alt.Y('값:Q', title=None, scale=alt.Scale(domain=dom, clamp=True),
              axis=alt.Axis(grid=True, gridColor='#eee', domain=False, ticks=False, labelColor='#888', labelFontSize=11))
    lay = []
    if zones:
        Z = pd.DataFrame([(max(a, dom[0]), min(b, dom[1]), c) for a, b, c in zones if b > dom[0] and a < dom[1]], columns=['a', 'b', 'c'])
        if len(Z):
            lay.append(alt.Chart(Z).mark_rect(opacity=0.7).encode(y=alt.Y('a:Q', scale=alt.Scale(domain=dom)), y2='b:Q', color=alt.Color('c:N', scale=None)))
    R = pd.DataFrame(refs, columns=['y', 't', 'c'])
    lay.append(alt.Chart(R).mark_rule(strokeDash=[4, 3], strokeWidth=1).encode(y=alt.Y('y:Q', scale=alt.Scale(domain=dom)), color=alt.Color('c:N', scale=None)))
    lay.append(alt.Chart(R).mark_text(align='left', dx=4, dy=-6, fontSize=11).encode(
        y=alt.Y('y:Q', scale=alt.Scale(domain=dom)), x=alt.value(0), text='t:N', color=alt.Color('c:N', scale=None)))
    pal = alt.Scale(domain=cols, range=['#1b5e20', '#e08a1e'][:len(cols)])
    lay.append(alt.Chart(D).mark_line(strokeWidth=2, interpolate='step-after' if unit == '/3' else 'monotone').encode(
        x=x, y=y, color=alt.Color('지표:N', scale=pal, legend=alt.Legend(orient='top', title=None, labelFontSize=11) if len(cols) > 1 else None),
        tooltip=['날짜:T', '지표:N', alt.Tooltip('값:Q', format='.2f')]))
    E = D[D['날짜'] == D['날짜'].max()]
    lay.append(alt.Chart(E).mark_circle(size=70).encode(x='날짜:T', y=alt.Y('값:Q', scale=alt.Scale(domain=dom)), color=alt.Color('지표:N', scale=pal, legend=None)))
    st.altair_chart(alt.layer(*lay).properties(height=220, padding={'top': 6, 'bottom': 4, 'left': 2, 'right': 8})
                    .configure_view(strokeWidth=0), use_container_width=True)


def pos_board(title, md):
    """11/23 의장: 미국 포지셔닝은 아주 중요 → 2 수급·포지셔닝 맨 위, 크게, 4개 지표 1년 선그래프 + 자세한 표."""
    st.markdown(f'<div style="font-size:17px;font-weight:800;color:#1b5e20;border-left:5px solid #2e7d32;padding-left:8px;margin-bottom:4px">{title}</div>',
                unsafe_allow_html=True)
    H = _pos_hist()
    if H is not None and len(H):
        st.caption('최근 1년 · 점선 = 기준선 · 색 띠 = 바닥(녹색)·과열(붉은색) 구간 · 출처 10년치 데이터베이스 수급포지셔닝 칸')
        for i in range(0, len(POS_PANEL), 2):
            if i:
                st.markdown('<div style="height:22px"></div>', unsafe_allow_html=True)   # 11/23 의장: 위아래 여유
            cc = st.columns(2, gap='large')
            for c, pnl in zip(cc, POS_PANEL[i:i + 2]):
                with c:
                    if pnl[0] in H:
                        with st.container(border=True):
                            _pos_line(H, *pnl)
        st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
    df = md_table(md)
    if df is None or df.empty:
        st.markdown(md); return
    body = ''.join('<tr>' + ''.join(f'<td style="padding:6px 8px;border-bottom:1px solid #eee;{"font-weight:700;" if j == 0 else ""}'
                                    f'{"white-space:nowrap;" if j < 4 else ""}{"color:#1b5e20;font-weight:700;" if j == 3 and ("기회" in str(v) or "바닥" in str(v)) else ""}">{v}</td>'
                                    for j, v in enumerate(r)) + '</tr>' for r in df.values.tolist())
    head = ''.join(f'<th style="text-align:left;padding:6px 8px;background:#e8f5e9;color:#1b5e20">{c}</th>' for c in df.columns)
    st.html(f'<table style="font-size:13px;border-collapse:collapse;width:100%;margin-top:6px"><tr>{head}</tr>{body}</table>')


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


# 11/23 의장 "약자로 쓰지 말고" · "신호 나옴이면 뭐 하라는 거야. 구체적으로": 칩마다 풀어 쓴 이름 + 할 일(의장 기준·블록 규칙 그대로)
ABBR = [(r'\bHY 스프레드', '하이일드 스프레드(High Yield Spread)'), (r'\bHY\b', '하이일드 스프레드(High Yield Spread)'),
        (r'\bHMM\b', '은닉 마르코프 모형(Hidden Markov Model)'), (r'\b10Y−2Y\b', '미국 10년−2년 국채 금리차'),
        (r'(?<!미국 )10년물', '미국 10년 국채금리'), (r'\bSOFR−IORB\b', '담보부 익일물 금리(SOFR) − 지급준비금 이자율(IORB)'),
        (r'\bMOVE\b(?!\()', 'MOVE(미국 국채 변동성 지수)'), (r'\bVIX\b(?!\()', 'VIX(S&P500 변동성 지수)'), (r'공포탐욕', 'CNN 공포탐욕 지수(Fear & Greed)')]
CHIP_DO = [
    (r'HMM.*한국|한국 HMM', '한국 시장이 하락 국면으로 계산됨 → 부담 1개로 셈(현금 집행 여건 계산에서 기회와 맞섬)'),
    (r'HMM.*미국|미국 HMM', '미국 시장이 하락 국면으로 계산됨 → 부담 1개로 셈'),
    (r'(?:HY|하이일드 스프레드) 3~4', '의장 기준: 3~4% 주의, 5% 이상 위기 징후. 오늘은 주의 단계 → 5%를 넘으면 L07 위기 공식으로 넘어감'),
    (r'(?:HY|하이일드) 스프레드 5', '의장 기준: 5% 이상 = 위기 징후(신용 경색)'),
    (r'10년물 5\.0', '의장 기준: 5.0% 돌파 = Derisking(위험자산 줄이기)'),
    (r'10년물 4\.8', '의장 기준: 4.8% 돌파 = 주식 위험 프리미엄 감소 → 주식 비중 축소'),
    (r'10Y−2Y', '의장 기준: 마이너스면 경기침체 가능성 높아짐'),
    (r'MOVE 100', '의장 기준: MOVE 100~110 = 채권 변동성 저점 구간 → 기회 1개로 셈'),
    (r'VIX 33\.5', '1990년 이후 첫날 25번: S&P500 12달 뒤 평균 +17.8%, 승률 84% → 기회 1개로 셈'),
    (r'VIX 15\.5', '의장 기준: 15.5 이하 = 과열 조짐 → 현금 늘림'),
    (r'공포탐욕 10', '의장 기준: 사건으로 생긴 하락의 바닥을 재는 신호 → 기회 1개로 셈'),
    (r'공포탐욕 75', '의장 기준: 70 넘으면 현금 늘림'),
    (r'보유 배수 0\.6', '변동성 목표 펀드가 이미 많이 팜 → 변동성이 내려가면 공식대로 다시 사는 돈(기회 1개)'),
    (r'방어 국면', '규칙: 방어 국면이면 기회가 많아도 현금 집행 여건은 \'아님\''),
    (r'금융 스트레스', '0 위 = 금융 스트레스가 평균보다 큼'),
]


def unabbr(t):
    for a, b in ABBR:
        t = re.sub(a, b, t)
    return t


def chip_do(t):
    return next((d for a, d in CHIP_DO if re.search(a, t)), '')


def signal_chips(md):
    """시장 블록 표 → 켜진 신호만 부담·기회 두 줄 칩(11/21 의장: 난잡한 표 대신)"""
    df = md_table(md)
    if df is None or '쪽' not in df or '오늘' not in df:
        # 11/21 의장: 원고 표는 '블록·질문·지표·오늘·공식'(좋고 나쁨 없음). 카드 색(빨강·초록)은 그대로 → 엔진 시장블록.csv에서 읽음
        try:
            M = read_csv(day, '시장블록.csv')
        except Exception:   # noqa: BLE001
            M = None
        if M is None or '방향' not in M:
            return False
        M = M.copy()
        M['_k'] = M['블록'].astype(str) + M['방향'].astype(str) + M['공식'].astype(str).str.replace(r'[−+-]?[\d.]+', '#', regex=True)
        M['_on'] = M['결과'] == '통과'
        M = M.sort_values('_on', ascending=False).drop_duplicates('_k')
        df = pd.DataFrame({'쪽': M['방향'].astype(str), '오늘': M['_on'].map({True: '신호 나옴', False: '신호 안 나옴'}), '질문': M['질문'].astype(str),
                           '공식': ' — ' + M['공식'].astype(str).str.replace(r'\((기회|부담)\)', '', regex=True).str.strip()})
    on = df[df['오늘'].str.strip() == '신호 나옴']
    nb, no = on['쪽'].str.contains('부담').sum(), on['쪽'].str.contains('기회').sum()
    dfn = on['공식'].astype(str).str.contains('방어 국면').any()
    go = no > nb and not dfn   # rules.yaml 미스 리스크 여건_규칙 "기회 > 부담 and not 방어"
    st.html(f"<div style='font-size:15px;font-weight:700;color:{'#1b8a2e' if go else '#c8372d'};margin:2px 0 6px'>"
            f"오늘 할 일: {'현금 집행 여건 됨 → 분할 매수 기준(Opportunity Block 개수) 확인 뒤 집행' if go else '새 돈 넣지 않음 — 현금 집행 여건 아님'}</div>"
            f"<div style='font-size:12px;color:#777;margin-bottom:6px'>좋은 신호 {no}개 vs 나쁜 신호 {nb}개, 방어 국면 {'예' if dfn else '아니오'}. "
            "규칙: 좋은 신호가 나쁜 신호보다 많고 방어 국면이 아닐 때만 '됨'</div>")
    c1, c2 = st.columns(2, gap='large')
    for col, side, color, name in ((c1, '부담', RED, '나쁜 신호'), (c2, '기회', '#2e7d32', '좋은 신호')):
        x = on[on['쪽'].str.contains(side)]
        tot = df['쪽'].str.contains(side).sum()
        def _chip(r):
            t = str(r['공식']).split(' — ', 1)[-1].split(' — ')[0]
            do = chip_do(t)
            return (f"<div style='border-left:3px solid {color};padding:6px 10px;margin:6px 0;background:#fafafa'>"
                    f"<div style='font-size:14px;color:#333'>{unabbr(t)}</div>"
                    + (f"<div style='font-size:13px;color:{color};font-weight:600;margin-top:2px'>→ {do}</div>" if do else '')
                    + f"<div style='font-size:12px;color:#999'>{r['질문']}</div></div>")
        chips = ''.join(_chip(r) for _, r in x.iterrows())
        col.html(f"<div style='font-size:13px;color:#888'>{name}</div>"
                 f"<div style='font-size:30px;color:{color};line-height:1.2'>{len(x)}<span style='font-size:14px;color:#999'> / {tot}개 신호 나옴</span></div>"
                 + (chips or "<div style='color:#999;font-size:13px;margin-top:6px'>없음</div>"))
    return True


SKIP_BOX = ('매크로 체크리스트', '리스크 표')   # 11/21 의장: 겹치는 표는 화면에서 뺌
SKIP_ITEM = ('공포 쪽 지표', '탐욕 쪽 지표')


# 11/21 의장 "시장보다 약함·동료보다 약함 이런 걸 다 써야 하나? 색깔 있는 작은 동그라미로" → 빠지는 이유는 색 점, 뜻은 칸 아래 한 줄
# 11/21 10:15 의장: 원 안에 글자(빨강 시약·주황 동약·파랑 외·보라 ETF, 이익하향은 회색 원), 크기 키워 표 맨 오른쪽 끝에
WHY_DOT = [('시장보다 약함', '#c8372d', '시약'), ('동료보다 약함', '#e08a1e', '동약'), ('외국인 20일 순매도', '#2b6cb0', '외'),
           ('업종 ETF 자금 이탈', '#7b4fb3', 'ETF'), ('이익 추정치 하향', '#6b7280', '')]
USED_DOTS = set()


def dot(name, col, lab=''):
    return (f'<span title="{name}" style="display:inline-block;width:24px;height:24px;line-height:24px;border-radius:50%;background:{col};'
            f'color:#fff;font-size:10px;font-weight:600;text-align:center;letter-spacing:-0.5px;margin-left:3px;vertical-align:middle">{lab}</span>')


_KO = None


def ko(v):
    """11/21 의장 "번역하라니까. 한글로": 영어 줄은 한글 번역(app/ko_cache.json, 없으면 제미나이 키가 있을 때 바로 번역)."""
    global _KO
    if _KO is None:
        try:
            import json
            _KO = json.load(open(Path(__file__).resolve().parent / 'ko_cache.json', encoding='utf-8'))
        except Exception:   # noqa: BLE001
            _KO = {}
    t = str(v).strip()
    if t in _KO:
        return _KO[t]
    if len(re.findall(r'[A-Za-z]', t)) > 15 and not re.search('[가-힣]', t) and os.environ.get('GEMINI_API_KEY'):
        try:
            import ko_translate
            r = ko_translate.translate([t], log=lambda *a: None)[0]
            if r:
                _KO[t] = r
                return r
        except Exception:   # noqa: BLE001
            pass
    return t


def _dothead(used):
    """11/23 의장: 그래프처럼 위에 열 이름을 작은 글씨로(시장보다 약함 …)."""
    return ''.join(f'<th style="text-align:center;font-size:10px !important;color:#888;white-space:normal;word-break:keep-all;width:58px;line-height:1.25">{n}</th>' for n in used)


def _dotcells(used, hits):
    """해당되면 그 열 칸에 붉은 원."""
    return ''.join('<td style="text-align:center;vertical-align:middle">'
                   + ('<span style="display:inline-block;width:11px;height:11px;border-radius:50%;background:#c8372d"></span>' if n in hits else '')
                   + '</td>' for n in used)


def lines_(v):
    """내용 한 칸: 쉼표·가운뎃점으로 이어 쓴 것을 줄바꿈 + '- '로(11/21 의장). 빠지는 이유는 색 점. '$'는 &#36;(수식으로 안 깨지게)."""
    v = ko(v).replace('$', '&#36;').replace('빠지는 이유: ', '')
    news = ''
    if '기사: ' in v:   # 기사 제목 안의 쉼표·가운뎃점은 나누지 않음
        v, news = v.split('기사: ', 1)
        v = re.sub(r'\s*·\s*$', '', v.strip())
    eng = len(re.findall(r'[A-Za-z]', v)) > 0.5 * max(1, len(re.findall(r'[A-Za-z가-힣]', v)))
    if eng or v.lstrip().startswith(('"', "'")):   # 영어 기사 제목·인용은 쉼표로 나누지 않음
        parts = [v.strip()]
    else:
        parts = [p.strip() for p in re.split(r',\s+(?![^()]*\))|\s+·\s+(?![^()]*\))|\s+\|\s+', v) if p.strip()]
    dots, keep = [], []
    for p in parts:
        hit = next((w for w in WHY_DOT if p == w[0]), None)
        if hit:
            dots.append(hit[0])
        else:
            keep.append(p)
    # 11/23 의장 "촌스럽다": 글자 원 대신 → 표 위 열 이름(작은 글씨) + 해당 칸에 붉은 원(flush의 _dotcols)
    if news:
        keep.append(f'<span style="color:#2b6cb0">기사</span> {news.strip()}')
    if len(keep) <= 1:
        return (keep[0] if keep else ''), dots
    return '<br>'.join('- ' + p for p in keep), dots


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
    sigrow = {}   # 11/23 의장 "신호등은 무조건 강조해서 색깔이": 원고 줄의 신호색(⟦red⟧ 등)을 항목·내용 글자색으로

    cnt = [0]
    CIRC = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚'

    def circ(t):   # 11/20 의장: 칸 안 항목은 동그라미 번호를 위에서부터
        cnt[0] += 1
        return f"{CIRC[cnt[0] - 1] if cnt[0] <= len(CIRC) else cnt[0]} {t}"

    def flush():
        if rows:
            # 11/21 의장 "글자 크기를 줄여서 1줄로": 항목 칸은 작은 글씨·줄바꿈 없음
            # 11/21 의장 "쉼표 대신 줄바꾸기와 - 표시, 작은 글씨": 내용은 ', '·' · ' 마다 줄을 바꿔 '- '로
            # 11/21 의장 "글자 크기 키우지 말라": 표 머리줄 없이 작은 글씨 HTML 표(공포탐욕 카드와 같은 크기)
            mv = [re.match(r'^(.*) ([+-]?\d+(?:\.\d+)?%)$', r[0]) for r in rows]
            m20 = [re.match(r'^20일 ([+-]?\d+(?:\.\d+)?%)\s*(?:·\s*)?(.*)$', str(r[1]), re.S) for r in rows]
            if all(mv) and all(m20):   # 11/21 10:17 의장: 등락은 종목 이름에서 떼어 오른쪽 칸에, '20일'은 제목에 한 번만
                L_ = [lines_(b.group(2)) if b.group(2).strip() else ('', []) for b in m20]
                used = [w[0] for w in WHY_DOT if any(w[0] in d for _, d in L_)]
                body = ''
                for a, b, (c, d) in zip(mv, m20, L_):
                    body += (f'<tr><td class="k">{circ(a.group(1))}</td><td class="n">{a.group(2)}</td><td class="n">{b.group(1)}</td>'
                             f'<td class="v">{c}</td>{_dotcells(used, d)}</tr>')
                st.markdown('<table class="it"><tr><th></th><th class="n">전일</th><th class="n">20일</th><th></th>' + _dothead(used) + '</tr>' + body + '</table>',
                            unsafe_allow_html=True)
                rows.clear()
            def _c(r, x):
                col = SIGCOL.get(sigrow.get(r[0], ''))
                return f'<span style="color:{col};font-weight:700">{x}</span>' if col else x
            L_ = [lines_(r[1]) for r in rows]
            used = [w[0] for w in WHY_DOT if any(w[0] in d for _, d in L_)]
            head = ('<tr><th></th><th></th>' + _dothead(used) + '</tr>') if used else ''
            def _fx(r, a):   # 11/23 의장 '밑에 공식 좀 써줘': 공식이 있는 항목은 값 밑에 작은 회색 글씨로 계산법
                f = next((v for k, v in FORMULA.items() if k in str(r[0])), '')
                return a + (f'<div style="font-size:11px;color:#999;margin-top:3px;line-height:1.5">{f}</div>' if f else '')
            t = '' if not rows else '<table class="it">' + head + ''.join(f'<tr><td class="k">{_c(r, circ(r[0]))}</td><td class="v">{_c(r, _fx(r, a))}</td>{_dotcells(used, b)}</tr>'
                                                for r, (a, b) in zip(rows, L_)) + '</table>'
            if t:
                st.markdown(t, unsafe_allow_html=True)
            rows.clear()

    merged = []
    for b in bl:   # '**제목**' 바로 뒤 표 → 한 묶음
        if b[0] == 'table' and merged and merged[-1][0] == 'text' and merged[-1][1].strip().startswith('**') and merged[-1][1].strip().endswith('**'):
            _tt = merged[-1][1].strip().strip('*')
            _tt = {'포지셔닝': '미국 포지셔닝(S&P500·나스닥100 기준)'}.get(_tt, _tt)   # 11/23 의장: 어느 나라 것인지 제목에(옛 원고도 바로)
            merged[-1] = ('titled', _tt, b[1])
        else:
            merged.append(b)
    bl = merged
    _pos = [b for b in bl if b[0] == 'titled' and '포지셔닝' in b[1]]   # 11/23 의장: 미국 포지셔닝은 칸 맨 위
    bl = _pos + [b for b in bl if b not in _pos]
    for b in bl:
        if b[0] == 'item':
            _, n, title, val, why = b
            title = full_name(title.replace('근원 CPI', 'Core CPI').replace('근원 PCE', 'Core PCE'))   # 11/20 의장: 연준 용어 그대로
            if '10년 실질' in title:   # 11/20 의장: 10년 실질금리 삭제
                continue
            val = val.replace('직전 발표 대비', '전월 대비')
            _m = SIGMARK.match(val)
            if _m:
                sigrow[title] = _m.group(1); val = val[_m.end():]
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
                st.markdown(f'<div class="box-t" style="margin-top:10px">{title}</div>', unsafe_allow_html=True)
                if len(stocks) >= 2:
                    stock_chart(stocks)
                elif not flow_chart(val):
                    st.markdown(f'<div class="item-v">{val}</div>', unsafe_allow_html=True)
                if why:
                    stat_chart(why)
            elif title.endswith(' 실적') and ('SEC' in why or 'DART' in why or '분기' in val):
                continue   # 11/21 의장 "예전 자료 가지고 매출이나 얘기하고… 무슨 의미" → 실적 줄은 화면에 안 보임
            elif rows and title.endswith(' 기사') and rows[-1][0].startswith(title.rsplit(' ', 1)[0] + ' '):
                rows[-1] = (rows[-1][0], rows[-1][1] + ' · 기사: ' + val)   # 11/21 의장: 한 기업 한 칸
            else:
                rows.append((title, val))
            continue
        flush()
        if b[0] == 'titled' and b[1].startswith(SKIP_BOX):
            continue
        if b[0] == 'titled' and b[1].startswith('시장 블록'):
            with st.container(border=True):
                st.markdown('<div class="box-t">오늘 신호 나온 시장 공식</div>', unsafe_allow_html=True)
                if not signal_chips(b[2]):
                    table_chart(b[2])
            continue
        if b[0] == 'table' and (b[1].startswith('| 지표 | 점수 | 구간')):
            d7 = md_table(b[1])
            if d7 is not None:
                fg_seven(d7)
                continue
        if b[0] == 'titled' and '포지셔닝' in b[1]:
            flush()
            with st.container(border=True):
                pos_board(b[1], b[2])
            continue
        if b[0] == 'titled':   # 11/20 의장: 제목·그래프·표를 한 상자로
            with st.container(border=True):
                st.markdown(f'<div class="box-t">{b[1]}</div>', unsafe_allow_html=True)
                table_chart(b[2])
        elif b[0] == 'table':
            table_chart(b[1])
        else:
            t = b[1].strip()
            if t.startswith('**') and t.endswith('**'):   # 칸 안 작은 제목(데스크 이름 등): 큰 제목 대신 작은 회색 글씨
                cnt[0] = 0   # 11/21 10:16 의장: 전문위원마다 번호를 1번부터
                st.markdown(f'<div class="box-t" style="margin-top:10px">{t.strip("*")}</div>', unsafe_allow_html=True)
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
    sys.path.insert(0, str(ROOT / 'app' / 'market'))
    import lt_bottom as LB
    return LB.hazard_today()


def bottom(day, name, title='단기 바닥 ±10% 안에 들어왔을 확률'):
    """11/27 의장: '바닥 근접도'를 지우고 "지금이 단기 바닥에서 ±10% 안에 들어왔을 확률"을 본 숫자로.
    아래에 로지스틱 회귀(옛 계산)를 따로 둠. 둘 다 엔진(daily.py, 하위 블록 2-12)이 만든 바닥확률.csv를 먼저 읽는다."""
    pre = '미장전_' if name.startswith('미장전') else ''
    T = read_csv(day, pre + '바닥확률.csv')
    if T is None or not len(T) or '띠10_확률' not in T:
        try:   # 그 날 파일이 아직 없거나 옛 파일이면 같은 코드로 바로 계산
            T = bottom_prob()
        except Exception as e:   # noqa: BLE001
            st.caption(f'바닥 확률 계산 실패: {e}')
            return
    NAME = {'^NDX': '나스닥100', '^GSPC': 'S&P500'}

    def pct(v, sign=False):
        x = pd.to_numeric(v, errors='coerce')
        return '' if pd.isna(x) else (f'{x:+.1f}%' if sign else f'{x:.1f}%')

    def down(r, k='띠10_하락중'):
        return str(r.get(k)) in ('True', '1', '1.0')
    with st.container(border=True):
        st.markdown(sec_title(title), unsafe_allow_html=True)
        cols = st.columns(len(T))
        for col, (_, r) in zip(cols, T.iterrows()):
            nm = NAME.get(r.get('기준지수'), r.get('기준지수'))
            with col:
                if not down(r):
                    st.metric(f'{nm}', '하락 구간 아님'); continue
                st.metric(f'{nm}: 최종 저점이 지금 가격의 10% 안일 확률', pct(r.get('띠10_확률')))
                st.markdown(f'<div class="sub">고점({r.get("띠10_고점일")}) 대비 {pct(r.get("띠10_지금낙폭"))} · '
                            f'과거 하락 중 이만큼 이상 빠졌던 {int(r.get("띠10_비교수"))}번 기준 · 그 하락들의 최종 낙폭 중앙값 {pct(r.get("띠10_최종낙폭_중앙값"))}</div>'
                            f'<div class="sub">그 {int(r.get("띠10_비교수"))}번이 지금 낙폭에 처음 닿은 날 산 경우</div>', unsafe_allow_html=True)
                st.markdown('<table class="num-t"><tr><th></th><th>평균 수익률</th><th>승률</th></tr>'
                            f'<tr><td class="lab">13주 뒤</td><td>{pct(r.get("띠10_뒤13주_평균"), True)}</td><td>{pct(r.get("띠10_뒤13주_승률"))}</td></tr>'
                            f'<tr><td class="lab">26주 뒤</td><td>{pct(r.get("띠10_뒤26주_평균"), True)}</td><td>{pct(r.get("띠10_뒤26주_승률"))}</td></tr></table>', unsafe_allow_html=True)
        st.markdown('<div class="note">산출 방법: 하락 구간 = Lunde &amp; Timmermann(2004) 필터(고점 −5%에서 시작, 저점 +10%에서 끝, R bbdetection 코드 그대로). '
                    '확률 = 과거 끝난 하락 구간 중 지금 낙폭 이상 빠졌던 것들에서, 최종 저점이 지금 가격의 10% 안이었던 비율. '
                    '10%는 같은 필터의 하락 끝 기준과 같은 크기. 자료: S&amp;P500 1928~, 나스닥100 1985~.</div>', unsafe_allow_html=True)
    if '확률' in T:   # 11/27 의장: 로지스틱 회귀는 살려서 아래에 따로
        with st.container(border=True):
            st.markdown(sec_title('로지스틱 회귀: 최종 저점 3% 안일 확률'), unsafe_allow_html=True)
            cols = st.columns(len(T))
            for col, (_, r) in zip(cols, T.iterrows()):
                nm = NAME.get(r.get('기준지수'), r.get('기준지수'))
                with col:
                    if not down(r, '하락중'):
                        st.metric(f'{nm}', '하락 구간 아님'); continue
                    st.metric(f'{nm}', pct(r.get('확률')))
                    st.markdown(f'<div class="sub">{int(r.get("주수"))}주째 · VIX {r.get("VIX"):.1f} · RSI {r.get("RSI"):.0f} · 검정 AUC {r.get("검정_AUC"):.2f}</div>',
                                unsafe_allow_html=True)
            st.markdown('<div class="note">하락 구간 안의 주마다 낙폭·기간·VIX·VIX 4주 변화·10년 금리 4주 변화·RSI·200일선 이격·4주 수익으로 로지스틱 회귀. '
                        '하락 구간 판정만 Lunde &amp; Timmermann(2004) 그대로이고, "저점 3% 안" 기준과 변수 6개는 11/21에 정한 것(논문 그대로 아님). '
                        '2000년부터 해마다 그 전 자료로만 학습.</div>', unsafe_allow_html=True)


@st.cache_data(ttl=3 * 3600, show_spinner='분할 매수 판정 계산 중…')
def buy_plan():
    """11/21 의장: '다음 주부터 3주, 금요일마다 현금 1/3씩 지수를 사겠다. 어때?'에 매번 답하는 장치(market/buy_plan.py)."""
    sys.path.insert(0, str(ROOT / 'app' / 'market'))
    import buy_plan as BP
    return BP.judge()


TURN_NAMES = ['기술주 쏠림: 나스닥100 vs 동일가중 S&P (QQQ:RSP)', '지금 S&P 500 (2023~2026) + 추세 점수(CTM)', '닷컴 붕괴 때 S&P 500 (1994~2002) · 비교용',
              'NVDA 지지선 (VWAP·피보나치)', '2000년 고점 때 S&P 500 이평 묶음 · 비교용', '지금 S&P 500 이평 묶음',
              '성장주 vs 현금 (SPYG:BIL)', '성장주 vs 가치주 월봉 (IWF:IWD)', '빅테크 MGK 주봉 + 추세 점수(CTM)']   # 11/23 의장: 쉽고 돋보이게

# 11/23 의장: 비교용 그림은 지금 그림 바로 밑에 'n-1' — 닷컴 붕괴는 2-1, 2000년 이평 묶음은 지금 이평 묶음(4) 밑 4-1. 파일 번호(_변곡점_N.png)는 그대로.
TURN_SHOW = [(1, '1'), (2, '2'), (3, '2-1'), (4, '3'), (6, '4'), (5, '4-1'), (7, '5'), (8, '6'), (9, '7')]


@st.cache_data(ttl=3 * 3600, show_spinner=False)
def _turn_png(day, n):
    rel = f'{day}/{day}_변곡점_{n}.png'
    if LOCAL:
        p = Path(LOCAL) / rel
        return p.read_bytes() if p.exists() else None
    return drive.get(f'{D_DATA}/{rel}')


@st.cache_data(ttl=3 * 3600, show_spinner=False)
def _day_png(day, stem):
    """날짜 폴더의 그림 한 장(YYYYMMDD/YYYYMMDD_{stem}.png)."""
    rel = f'{day}/{day}_{stem}.png'
    if LOCAL:
        p = Path(LOCAL) / rel
        return p.read_bytes() if p.exists() else None
    return drive.get(f'{D_DATA}/{rel}')


TURN_COL = {'상향 돌파': '#1b8a2e', '하향 돌파': '#c8372d', '위에서 닿음': '#e67e22', '아래에서 닿음': '#e67e22', '위': '#333', '아래': '#333'}


def _turn_lines(T):
    """11/23 의장: 그림 밑에 '대상 값 · 기준선 값 · 차이 · 상태(위/아래/닿음/돌파)' 표. 돌파는 돌파한 봉부터 4봉, 닿음은 선과 ±1% 안."""
    if not len(T):
        return
    # 11/23 의장 "너무 복잡하지 않게": 대상마다 돌파·닿은 선 + 바로 위 선 1개·바로 아래 선 1개만(전체는 드라이브 변곡점_선.csv)
    keep, cnt = [], []
    for w, g in T.groupby('대상', sort=False):
        d = pd.to_numeric(g['차이'].astype(str).str.rstrip('%점'), errors='coerce')
        stt = g['상태'].astype(str)
        hot = d[stt.str.contains('돌파|닿음')].abs().nsmallest(2)   # 돌파·닿은 선 중 가장 가까운 2개
        up, dn = d[d < 0], d[d >= 0]   # 차이<0 = 선이 위에 있음
        idx = set(hot.index)
        if len(up): idx.add(up.idxmax())
        if len(dn): idx.add(dn.idxmin())
        keep += [i for i in g.index if i in idx]
        c = ', '.join(f'{k} {v}개' for k, v in stt.value_counts().items() if '돌파' in k or '닿음' in k)
        if c:
            cnt.append(f'{w} 선 {len(g)}개 중 {c}')
    T = T.loc[keep]
    r0 = T.iloc[0]
    rows = ''.join(f"<tr><td>{r['기준선']}</td><td style='text-align:right'>{r['선 값']}</td><td style='text-align:right'>{r['차이']}</td>"
                   f"<td style='color:{TURN_COL.get(r['상태'], '#333')};font-weight:600'>{r['상태']}</td></tr>"
                   for _, r in T.iterrows())
    who = ' · '.join(f"{w} <b>{v}</b>" for w, v in T.drop_duplicates('대상')[['대상', '대상 값']].values)
    if cnt:
        who += '<br><span style="color:#777">' + ' · '.join(cnt) + '</span>'
    st.html(f"<div style='font-size:11px;color:#333'>{r0['기준일']} 기준 · {who}"
            "<table style='font-size:11px;border-collapse:collapse;width:100%;margin-top:2px'>"
            "<tr style='color:#777'><td>기준선</td><td style='text-align:right'>선 값</td><td style='text-align:right'>차이</td><td>상태</td></tr>"
            f"{rows}</table></div>")


def turning_board(day):
    """11/22 의장 '변곡점 판': 의장이 올린 그림 9개를 의장이 정한 순서대로, 원본 그대로 매일 다시 그린 것(daily.py → block33/turning.py)."""
    d0 = dt.datetime.strptime(day, '%Y%m%d').date()
    for back in range(8):   # 주말·휴장일이면 가장 최근 그림
        dd = (d0 - dt.timedelta(days=back)).strftime('%Y%m%d')
        if _turn_png(dd, 1):
            break
    else:
        st.info('바닥 찾기 그래프가 아직 없습니다.')
        return
    try:   # 11/22 의장: S&P 64·109주선 상태 4가지(위 / 하향 돌파 / 아래 / 상향 돌파)
        _S = read_csv(dd, '이평상태.csv')
        if _S is not None and len(_S):
            st.html("<div style='font-size:13px;color:#333;margin:2px 0 6px'>S&amp;P " + ' · '.join(
                f"{r['선']}: <b>{r['상태']}</b> ({float(r['차이']):+.1f}%, 선 {float(r['선값']):,.0f})" for _, r in _S.iterrows() if pd.notna(r['상태'])) + '</div>')
    except Exception:   # noqa: BLE001
        pass
    try:   # 11/23 의장: 그림마다 밑에 대상 값·기준선 값·닿음/돌파
        _LN = read_csv(dd, '변곡점_선.csv')
    except Exception:   # noqa: BLE001
        _LN = None
    st.html(f"<div style='font-size:18px;font-weight:800;color:#1b5e20;margin:6px 0 2px'>바닥 찾기 그래프 모음 <span style='font-size:12px;color:#777;font-weight:400'>{dd[:4]}-{dd[4:6]}-{dd[6:]}</span></div>")   # 11/23 의장: 제일 위 제목
    with st.expander('그래프 9개 펼치기·접기', expanded=True):
        for n, no in TURN_SHOW:
            nm = TURN_NAMES[n - 1]   # 11/22 의장: "늘 같이 준 그래프와 비교할 수 있게 옆에" → 왼쪽 재현, 오른쪽 의장이 준 원본
            b = _turn_png(dd, n)
            st.html(f"<div style='font-size:15px;font-weight:700;color:#1b5e20;border-left:4px solid #2e7d32;padding-left:8px;margin:14px 0 2px'>{no}. {nm}</div>")   # 11/23 의장: 돋보이게, 녹색(그린 라이트)
            c1, c2 = st.columns([3, 2], gap='small')   # 11/23 의장: 원본은 화면에서 뺌(재현 그래프만). 원본 파일은 assets/turning_orig에 그대로 둠
            with c1:
                if b:
                    st.image(b, use_container_width=True)
                else:
                    st.caption('그림 없음')
            with c2:
                if _LN is not None and len(_LN):
                    _turn_lines(_LN[_LN['그림'].astype(int) == n])


def block_bottom():
    """11/21 의장: 블록으로 바닥 찾기, 맨 위. Opportunity Block(과거로 다시 계산되는 블록 공식 20개) 중 13개 이상.
    켜짐은 초록·빨강 원, 과거 성적은 '산출 방법' 안. 매수 가정 = 다음 주 월요일부터 3주 월요일 종가에 1/3씩, 마지막 매수 13주 뒤."""
    try:
        J = buy_plan()
    except Exception as e:   # noqa: BLE001
        st.caption(f'바닥 찾기 계산 실패: {e}')
        return
    G, R = '#2e7d32', '#c8372d'
    S = {r['지수']: r for r in J['지수']}
    sp, nq = S['S&P500'], S['나스닥100']
    dot = lambda ok, s=10: f"<span style='display:inline-block;width:{s}px;height:{s}px;border-radius:50%;background:{G if ok else R};vertical-align:middle'></span>"
    t0 = {k: r['표'].iloc[0] for k, r in S.items()}
    rec = ', '.join(f"{k} {t.사례}번 {'모두' if round(t.이김 * t.사례) == t.사례 else f'중 {round(t.이김 * t.사례)}번'}" for k, t in t0.items())
    inn = [k for k, r in S.items() if r['켜진수'] >= r['기준']]
    out = [f"{k}는 {r['기준'] - r['켜진수']}개 남았습니다" for k, r in S.items() if r['켜진수'] < r['기준']]
    head = (f"오늘 S&P500은 Opportunity Block {sp['전체']}개 중 {sp['켜진수']}개(기준 {sp['기준']}), 나스닥100은 {nq['켜진수']}개(기준 {nq['기준']})가 초록입니다. "
            f"기준 이상일 때 다음 주 월요일부터 3주 나눠 사면 과거 {rec} 3개월 뒤 이겼습니다. "
            + (f"{'·'.join(inn)} 모두 기준에 들어왔습니다." if len(inn) == 2 else (f"{inn[0]}는 들어왔고, " if inn else '') + ', '.join(out) + '.'))
    with st.container(border=True):
        st.markdown(sec_title('바닥 찾기 | 마켓 센터'), unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:14px;color:#222;line-height:1.7;margin:2px 0 10px'>{head}</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        for col, r in ((c1, sp), (c2, nq)):
            ok = r['켜진수'] >= r['기준']
            col.html(f"<div style='font-size:13px;color:#888'>{r['지수']} · 고점 대비 {r['낙폭']:.1f}%</div>"
                     f"<div style='font-size:28px;color:{G if ok else R};line-height:1.3'>{r['켜진수']}<span style='font-size:14px;color:#999'> / {r['전체']} · 기준 {r['기준']}</span></div>")
        names = list(sp['켜짐'].keys()); half = (len(names) + 1) // 2
        cols = st.columns(2)
        for col, part in ((cols[0], names[:half]), (cols[1], names[half:])):
            col.html('<div style="font-size:11px;color:#999;margin:6px 0 2px">S&amp;P · 나스닥</div>' + ''.join(
                f"<div style='font-size:12.5px;color:#333;padding:3px 0;border-bottom:1px solid #f0f0f0'>{dot(sp['켜짐'][k])} {dot(nq['켜짐'].get(k, False))} &nbsp;{k}</div>" for k in part))
        with st.expander('산출 방법', expanded=False):
            rows = ''.join(f"<tr><td class='k'>{t.신호}</td>" + ''.join(
                f"<td>{k} {dot(bool(r['표'].loc[i].오늘), 8)} {r['표'].loc[i].사례}번 중 {round(r['표'].loc[i].이김 * r['표'].loc[i].사례)}번, 최악 {r['표'].loc[i].최악 * 100:+.1f}%</td>" for k, r in S.items()) + '</tr>'
                for i, t in sp['표'].iterrows())
            st.markdown('<div class="note">- Opportunity Block = blocks.yaml에서 과거 자료로 다시 계산되는 지수 판 공식 20개(B02 2 · B06 4 · 시장바닥·B16 7 · B13 1 · B17 5 · 8개 공식 바닥 확률). 문턱은 blocks.yaml 그대로.<br>'
                        '- 기준 S&amp;P 11개·나스닥 13개(나스닥이 −20% 넘게 빠졌으면 8개): 2006-08 이후 두 지수, 하락 한 번 = 한 건, 신호가 처음 나온 금요일 다음 주 월요일부터 3주 월요일 종가에 1/3씩 사서 마지막 매수 13주 뒤. S&amp;P는 14개 이상이면 오히려 나빠짐.</div>'
                        '<table class="it">' + rows + '</table>', unsafe_allow_html=True)


if not LOCAL and not drive.ready():
    st.error('드라이브 창구 비밀값(DRIVE_URL·DRIVE_TOKEN)이 없습니다.')
    st.stop()

today = dt.datetime.now(KST).date()
day = st.date_input('날짜', today, max_value=today).strftime('%Y%m%d')
try:   # 11/22 의장 1순위: B01 CTM 빨간불이면 맨 위에 현금 전환
    _M = read_csv(day, '시장블록.csv')
    _on = lambda k: (lambda r: r if r is not None and len(r) and str(r['결과'].iloc[0]) in ('예', '켜짐', '신호 나옴', '통과', 'True', '1') else None)(
        _M[_M['식'].astype(str).str.contains(k)] if _M is not None and '식' in _M else None)
    _red = [f"{n} ({r['값'].iloc[0]})" for k, n in (('CTM_RED', 'CTM 빨간불'), ('MA_CLUSTER_RED', 'MA 클러스터 빨간불')) if (r := _on(k)) is not None]
    if _red:
        st.error('🔴 ' + ' + '.join(_red) + ' — 모든 분석을 멈추고 현금 전환')
    elif (_g := _on('CTM_GREEN')) is not None:
        st.success(f"🟢 지수 매수 신호(CTM 반등 시작) — S&P CTM {_g['값'].iloc[0]}")
except Exception:   # noqa: BLE001
    pass
try:   # 11/26 의장 "위원 공부 후보·주요 뉴스는 회의 전에 준비됐다고 보고하면 보고 판단": 그날 준비된 후보 수와 판정 화면
    sys.path.append(str(ROOT / 'collect' / 'data'))   # 뒤에 붙여 다른 모듈을 가리지 않게
    import px_store as _PS
    _rd = _PS.ready(drive, day, lambda *_: None)
    _c1, _c2 = st.columns(2)
    _c1.page_link('pages/5_공부자료_승인.py', label=f"위원 공부 후보 {_rd['공부후보']}건 준비됨 → 승인하기", icon='📚')
    _c2.page_link('pages/4_주가뉴스_고르기.py', label=f"주가 뉴스 후보 {_rd['주가뉴스후보']}건 준비됨 → 고르기", icon='🗞️')
except Exception:   # noqa: BLE001
    pass
turning_board(day)   # 11/22 의장: 변곡점 판(그림 9개)을 맨 위에
block_bottom()   # 11/21 의장: 블록 바닥 찾기를 맨 위에

for tab, (label, name) in zip(st.tabs([s[0] for s in SESSIONS]), SESSIONS):
    with tab:
        md = read(day, name)
        if not md:
            st.info(f'{day[:4]}-{day[4:6]}-{day[6:]} {label} 원고가 아직 없습니다.')
            continue
        head, secs = sections(md)
        if name.startswith('미장전'):   # 11/20 의장: 원고 첫 줄 자료 메모·한 종목 머리말은 보이지 않음, 순서 1 바닥 근접도 · 2 미장전 시황
            bottom(day, name, '1 단기 바닥 ±10% 안에 들어왔을 확률 | 마켓 센터')
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
                if '기술적 분석' in title:   # 11/26 의장 "미스 차트는 그래프로, 큼지막하게": SPYM·QQQM·TIGER 200 그림을 칸 맨 위에 크게
                    for _i in (1, 2, 3):
                        _b = _day_png(day, f"{'미장전_' if name.startswith('미장전') else ''}미스차트_{_i}")
                        if _b:
                            st.image(_b, use_container_width=True)
                render(body)
