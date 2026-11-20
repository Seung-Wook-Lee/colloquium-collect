# ======================================================================
# 유튜브 — 의장이 링크를 넣으면 제미나이가 받아 적어 요약을 보여 주고, 같은 txt가 위원 공부자료가 된다 (2026-11-20 의장)
#   쓰는 것: 드라이브 '콜로키움 수집데이터/유튜브/링크.txt' 에 한 줄 덧붙임(주소 위원 메모)
#   읽는 것: 같은 폴더 '처리목록.csv'(상태) + '위원공부_유튜브/*.txt'(결과)
#   받아쓰기는 GitHub Actions '유튜브 공부자료'(youtube/run.py)가 10분마다 새 링크를 보고 한다. 화면은 창구일 뿐 판단하지 않는다.
# ======================================================================
import io, os, re, sys, datetime as dt
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title='스튜디오 톰앤수 · 유튜브', page_icon='🎬', layout='wide')

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / 'collect'), str(ROOT / 'app')]
try:
    for k in ('DRIVE_URL', 'DRIVE_TOKEN'):
        if k in st.secrets and not os.environ.get(k):
            os.environ[k] = str(st.secrets[k])
except Exception:
    pass
import drive  # noqa: E402

D = '콜로키움 수집데이터/유튜브'
OUTD = f'{D}/위원공부_유튜브'
KST = dt.timezone(dt.timedelta(hours=9))
PERSONAS = ['자동(제미나이가 고름)', '공통', '국장', '피터', '미스세마이', '미스터빅스', '미스터로보', '미스파이낸스',
            '마담헤비', '일라이존슨', '미스차트', '미스터역도산', '리오', '포보스', '엘피스']

if not drive.ready():
    st.error('드라이브 창구 비밀값(DRIVE_URL·DRIVE_TOKEN)이 없습니다.')
    st.stop()


def vid_of(s):
    m = re.search(r'(?:v=|youtu\.be/|shorts/|live/|embed/)([A-Za-z0-9_-]{11})', s or '')
    return m.group(1) if m else None


@st.cache_data(ttl=60, show_spinner=False)
def state():
    b = drive.get(f'{D}/처리목록.csv')
    return pd.read_csv(io.BytesIO(b), dtype=str, encoding='utf-8-sig').fillna('') if b else pd.DataFrame()


@st.cache_data(ttl=60, show_spinner=False)
def links_text():
    b = drive.get(f'{D}/링크.txt')
    return b.decode('utf-8-sig', 'replace') if b else ''


@st.cache_data(ttl=3600, show_spinner=False)
def read_txt(name):
    b = drive.get(f'{OUTD}/{name}')
    return b.decode('utf-8', 'replace') if b else ''


def section(text, title):
    m = re.search(rf'■ {title}\s*\n(.*?)(?=\n■ |\Z)', text, re.S)
    return m.group(1).strip() if m else ''


st.title('🎬 유튜브 요약')
st.caption('링크를 넣으면 제미나이가 자막(없으면 소리)으로 받아 적습니다. 보통 10~20분 안에 아래 목록에 나타나고, '
           '같은 txt가 위원 공부자료(자료 검색)에도 들어갑니다. 일본 유튜브는 제이미 몫이라 건너뜁니다.')

# ---------------------------------------------------------------- 넣기
with st.form('add', clear_on_submit=True):
    c1, c2 = st.columns([3, 1])
    url = c1.text_input('유튜브 주소', placeholder='https://youtu.be/…')
    who = c2.selectbox('위원', PERSONAS)
    memo = st.text_input('메모(선택)', placeholder='예: 50·150·200일선과 거래량')
    ok = st.form_submit_button('요약 맡기기', type='primary')
if ok:
    vid = vid_of(url.strip())
    if not vid:
        st.warning('유튜브 주소를 읽지 못했습니다. youtu.be/… 또는 youtube.com/watch?v=… 꼴로 넣어 주세요.')
    else:
        txt = links_text()
        if vid in txt:
            st.info('이미 넣은 영상입니다.')
        else:
            line = f'https://youtu.be/{vid}' + ('' if who.startswith('자동') else f' {who}') + (f' {memo.strip()}' if memo.strip() else '')
            stamp = dt.datetime.now(KST).strftime('%Y-%m-%d %H:%M')
            drive.put(f'{D}/링크.txt', (txt.rstrip('\n') + f'\n# {stamp} 화면에서 넣음\n{line}\n').lstrip('\n').encode('utf-8'))
            links_text.clear()
            st.success('맡겼습니다. 10~20분 뒤 아래 목록에 나타납니다(1시간 넘는 영상은 더 걸릴 수 있음).')

# ---------------------------------------------------------------- 기다리는 것
sdf = state()
done_ids = set(sdf.loc[sdf.get('상태', pd.Series(dtype=str)).eq('완료'), '영상id']) if len(sdf) else set()
wait = []
for line in links_text().splitlines():
    if line.strip().startswith('#'):
        continue
    v = vid_of(line)
    if v and v not in done_ids:
        row = sdf[sdf['영상id'] == v] if len(sdf) else pd.DataFrame()
        st_ = row.iloc[0]['상태'] if len(row) else '대기'
        memo_ = row.iloc[0]['메모'] if len(row) else ''
        wait.append({'영상': f'https://youtu.be/{v}', '상태': st_, '설명': memo_ if st_ != '대기' else ''})
if wait:
    st.subheader('기다리는 영상')
    st.dataframe(pd.DataFrame(wait), hide_index=True, use_container_width=True,
                 column_config={'영상': st.column_config.LinkColumn('영상')})
    if st.button('새로 고침'):
        state.clear()
        links_text.clear()
        st.rerun()

# ---------------------------------------------------------------- 결과
st.subheader('받아 적은 영상')
if not len(sdf) or not done_ids:
    st.info('아직 없습니다.')
    st.stop()
done = sdf[sdf['상태'] == '완료'].sort_values('처리시각', ascending=False)
f1, f2 = st.columns(2)
pick_who = f1.selectbox('위원으로 거르기', ['전체'] + sorted(done['위원'].unique().tolist()))
q = f2.text_input('제목·채널 찾기')
if pick_who != '전체':
    done = done[done['위원'] == pick_who]
if q:
    done = done[done['제목'].str.contains(q, case=False) | done['채널'].str.contains(q, case=False)]

for _, r in done.head(30).iterrows():
    d = r.get('게시일', '')
    d = f'{d[:4]}-{d[4:6]}-{d[6:]}' if len(d) == 8 else d
    with st.container(border=True):
        st.markdown(f"**{r['제목'] or r['영상id']}**")
        st.caption(f"{r['채널']} · 게시 {d} · {r.get('길이분', '')}분 · 위원 {r['위원']} · "
                   f"{r.get('방식', '')} · [영상](https://youtu.be/{r['영상id']})")
        txt = read_txt(r['파일'])
        one = section(txt, '한 줄 요약')
        if one:
            st.write(one)
        key = section(txt, '핵심 정리')
        if key:
            st.markdown(key)
        with st.expander('전부 보기(사실·출연자 의견·언급 종목·받아쓰기)'):
            st.text(txt)
