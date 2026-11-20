# ======================================================================
# 콜로키움 — 회의 화면 (2026-11-20 의장: "스트림릿 오후회의, 오전 회의 2개만 해. 단순화하라고")
#   국장전 회의(10:00)와 미장전 회의(22:00) 두 칸만. 각 칸은 회의에서 읽는 원고(회의원고.md)를 그대로 보여 준다.
#   읽는 것: 드라이브 '콜로키움 수집데이터/YYYYMMDD/YYYYMMDD_회의원고.md', 'YYYYMMDD_미장전_회의원고.md'
#            (meeting.yml이 만든다. 원고와 화면이 같은 파일이라 회의 발표와 화면이 어긋나지 않는다)
#   드라이브는 수집 프로그램과 같은 창구(drive.py, 비밀값 DRIVE_URL·DRIVE_TOKEN)로 읽는다.
# ======================================================================
import os, re, sys, datetime as dt
from pathlib import Path

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
                st.markdown(body)
