# ======================================================================
# 콜로키움 — 회의 화면 (2026-11-20 의장: "스트림릿 오후회의, 오전 회의 2개만 해. 단순화하라고")
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

st.set_page_config(page_title='콜로키움 회의', page_icon='📊', layout='wide')
st.markdown('''<style>
.block-container {max-width: 1100px; padding-top: 2rem;}
.stMarkdown p, .stMarkdown li, .stMarkdown td, .stMarkdown th {font-size: 16px; line-height: 1.9;}
.stMarkdown table {width: 100%; border-collapse: collapse;}
.stMarkdown td, .stMarkdown th {padding: 8px 12px;}
.item-t {font-size: 15px; font-weight: 700; color: #555; padding-top: 6px;}
.item-v {font-size: 18px; font-weight: 600; line-height: 1.6;}
.why {font-size: 13px; color: #888; line-height: 1.6;}
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


def sections(md):
    """'## 칸 제목' 단위로 나눈다. 맨 앞(제목·오늘의 한 종목)은 머리말."""
    parts = re.split(r'(?m)^## ', md)
    head = re.sub(r'(?m)^# .*\n?', '', parts[0]).strip()
    return head, [(p.split('\n', 1)[0].strip(), p.split('\n', 1)[1] if '\n' in p else '') for p in parts[1:]]


ITEM = re.compile(r'^\*\*(\d+)\.\s*(.+?)\*\*\s*$')
STOCK = re.compile(r'([^,()]+?)\(52주 고점 대비 (-?[\d.]+)%, 베타 ([\d.]+), 싼가 ([\d.]+)\)')
STAT = re.compile(r'([A-Za-z가-힣][A-Za-z가-힣0-9()/ ]*?) ([+-][\d.]+)%\(승률 (\d+)%\)')
GROUP = re.compile(r'평균 ([+-][\d.]+)%, 승률 ([\d.]+)%\(전체 주 ([+-][\d.]+)%, ([\d.]+)%\)')
RED, BLUE = '#c8372d', '#2b6cb0'


def blocks(body):
    """빈 줄로 나눈 덩어리: ('item', 번호, 제목, 내용, 근거) / ('table', md) / ('text', md)"""
    out = []
    for b in re.split(r'\n\s*\n', body.strip()):
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
    df = pd.DataFrame(rows, columns=['종목', '고점 대비(%)', '베타', '싼가']).astype({'고점 대비(%)': float, '베타': float, '싼가': float})
    st.dataframe(df, hide_index=True, use_container_width=True, column_config={
        '고점 대비(%)': st.column_config.ProgressColumn(format='%.1f%%', min_value=-100, max_value=0),
        '싼가': st.column_config.ProgressColumn(format='%.2f', min_value=0, max_value=1),
        '베타': st.column_config.NumberColumn(format='%.2f')})


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
    """양수 파랑·음수 빨강 가로 막대 + 값 글자"""
    df = df.copy()
    df['_t'] = df[val].map(lambda v: (f'{v:+,.2f}' if abs(v) < 100 else f'{v:+,.0f}') + unit)
    base = alt.Chart(df).encode(y=alt.Y(f'{label}:N', sort=None, title=None, axis=alt.Axis(labelFontSize=14, labelLimit=260)))
    bars = base.mark_bar(cornerRadiusEnd=3, height=18).encode(
        x=alt.X(f'{val}:Q', title=None, axis=alt.Axis(labelFontSize=11)),
        color=alt.condition(f'datum["{val}"] >= 0', alt.value(BLUE), alt.value(RED)))
    df['_z'] = 0.0
    base = alt.Chart(df).encode(y=alt.Y(f'{label}:N', sort=None, title=None, axis=alt.Axis(labelFontSize=14, labelLimit=260)))
    txt = base.mark_text(align='left', dx=4, fontSize=13, fontWeight='bold').encode(x=alt.X(f'{val}:Q'), text='_t:N')
    neg = base.mark_text(align='left', dx=4, fontSize=13, fontWeight='bold', color=RED).encode(x=alt.X('_z:Q'), text='_t:N')
    layer = bars + txt.transform_filter(f'datum["{val}"] >= 0') + neg.transform_filter(f'datum["{val}"] < 0')
    st.altair_chart(layer.properties(height=height or 32 * len(df) + 20), use_container_width=True)


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
    numc = [c for c in df.columns if c not in lab and signed(c)]
    if lab and numc and len(df) >= 2:
        d = df.copy()
        key = lab[1] if len(lab) > 1 and df[lab[0]].nunique() < len(df) else lab[0]
        d['_l'] = (df[lab[0]] + ' · ' + df[key]) if key != lab[0] else df[key]
        d['_v'] = df[numc[0]].map(num)
        c1, c2 = st.columns([1, 1])
        with c1:
            st.caption(numc[0])
            hbar(d.dropna(subset=['_v']), '_l', '_v')
        c2.dataframe(df, hide_index=True, use_container_width=True)
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


def why_box(why):
    short = re.sub(r'\s*—\s*퀀트센터/\S+', '', why)
    short = re.sub(r'\(\S+\.csv[^)]*\)|07시 |\S+\.csv', '', short)
    with st.expander('근거', expanded=False):
        st.markdown(f'<div class="why">{short}</div>', unsafe_allow_html=True)


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

    def flush():
        if rows:
            t = '| 항목 | 내용 |\n|---|---|\n' + '\n'.join(f'| **{r[0]}** | {r[1].replace("|", "·")} |' for r in rows)
            st.markdown(t)
            rows.clear()

    for b in bl:
        if b[0] == 'item':
            _, n, title, val, why = b
            if why:
                whys.append(f'**{title}** — {why}')
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
        if b[0] == 'table':
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
        if head:
            st.markdown(head)
        for title, body in secs:
            with st.container(border=True):
                st.subheader(title)
                render(body)
