# ======================================================================
# 뉴스 고르기 — 뉴스 실험실 후보에 의장이 '쓸 것/버릴 것'과 이유 한 줄을 표시한다 (2026-11-14 의장)
#   읽는 것: 드라이브 '콜로키움 수집데이터/뉴스실험실/YYYYMMDD_후보.csv' (매일 06:30 제미나이가 1차로 고름)
#   쓰는 것: 같은 폴더 'YYYYMMDD_판정.csv'(그날 표시 전체) + '00_판정누적.csv'(날짜별로 바꿔 넣음)
#            다음 날 제미나이가 누적 파일의 사례(특히 의장이 다르게 고른 것)를 읽고 따라 고른다.
# ======================================================================
import io, os, sys, datetime as dt
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title='스튜디오 톰앤수 · 뉴스 고르기', page_icon='📰', layout='wide')

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / 'collect'), str(ROOT / 'app')]
try:
    for k in ('DRIVE_URL', 'DRIVE_TOKEN'):
        if k in st.secrets and not os.environ.get(k):
            os.environ[k] = str(st.secrets[k])
except Exception:
    pass
import drive  # noqa: E402

D = '콜로키움 수집데이터/뉴스실험실'
CHOICES = ['', '쓸 것', '버릴 것']

if not drive.ready():
    st.error('드라이브 창구 비밀값(DRIVE_URL·DRIVE_TOKEN)이 없습니다.')
    st.stop()


@st.cache_data(ttl=300, show_spinner=False)
def dates():
    names = [f['name'] for f in drive.ls(D)]
    return sorted({n[:8] for n in names if n.endswith('_후보.csv')}, reverse=True)


def read(name):
    b = drive.get(f'{D}/{name}')
    return pd.read_csv(io.BytesIO(b), dtype=str, encoding='utf-8-sig').fillna('') if b else None


st.title('📰 뉴스 고르기')
st.caption('제미나이가 고른 후보에 의장님이 **쓸 것/버릴 것**과 이유 한 줄을 표시합니다. '
           '제미나이와 다르게 고른 것이 다음 날 고르기에 가장 크게 반영됩니다. 이유는 짧게(예: "연합 받아쓰기", "외신 원문 있음").')

ds = dates()
if not ds:
    st.info('아직 후보 파일이 없습니다. 매일 06:30에 만들어집니다.')
    st.stop()
day = st.selectbox('날짜', ds, format_func=lambda d: f'{d[:4]}-{d[4:6]}-{d[6:]}')

cand = read(f'{day}_후보.csv')
for col in ('의장판정', '의장이유'):
    if col not in cand:
        cand[col] = ''
done = read(f'{day}_판정.csv')
if done is not None and len(done):
    m = done.set_index('제목')[['의장판정', '의장이유']].to_dict('index')
    cand['의장판정'] = [m.get(t, {}).get('의장판정', '') for t in cand['제목']]
    cand['의장이유'] = [m.get(t, {}).get('의장이유', '') for t in cand['제목']]
    st.success(f'이 날짜는 이미 {sum(cand["의장판정"] != "")}건 표시해 두셨습니다. 고치고 다시 저장할 수 있습니다.')

c1, c2 = st.columns([1, 3])
if c1.button('비어 있는 칸을 제미나이 추천대로 채우기'):
    cand['의장판정'] = [p or (g if g in CHOICES else '') for p, g in zip(cand['의장판정'], cand['제미나이추천'])]
    st.session_state[f'pre_{day}'] = cand['의장판정'].tolist()
    for i in range(len(cand)):
        st.session_state.pop(f'p_{day}_{i}', None)
if f'pre_{day}' in st.session_state:
    cand['의장판정'] = st.session_state[f'pre_{day}']
c2.caption('제미나이 추천이 맞으면 이 버튼으로 채운 뒤 다른 것만 고치면 됩니다.')

# 11/20 의장: "기사 내용이 보여야 한다, 평가는 뒤로" → 표 대신 기사 카드. 제목·내용(요약)이 앞, 판정·이유는 카드 맨 아래.
st.caption('기사마다 제목과 내용을 먼저 보고, 맨 아래 칸에서 판정과 이유를 고르시면 됩니다.')
picks, reasons = [], []
for i, r in cand.reset_index(drop=True).iterrows():
    with st.container(border=True):
        ko_t = str(r.get('제목(한글)', '') or '').strip()
        st.markdown(f"**{ko_t or r['제목']}**" + (f"  [원문]({r['링크']})" if str(r.get('링크', '')).startswith('http') else ''))
        ko_s = str(r.get('요약(한글)', '') or '').strip()
        if ko_s:
            st.write(ko_s)
        if r.get('제미나이이유'):
            st.write(r['제미나이이유'])
        if ko_t:
            st.caption(f"원제목: {r['제목']}")
        if r.get('보강'):
            st.caption(f"같은 사건 다른 보도: {r['보강']}")
        st.caption(f"{r['매체']} · {r['시각']} · {r['분류']} · 중요도 {r['중요도']} · 제미나이 {r['제미나이추천'] or '—'}")
        c1, c2 = st.columns([1, 3])
        cur = st.session_state.get(f'pre_{day}', cand['의장판정'].tolist())[i]
        picks.append(c1.selectbox('판정', CHOICES, index=CHOICES.index(cur) if cur in CHOICES else 0,
                                  key=f'p_{day}_{i}', label_visibility='collapsed'))
        reasons.append(c2.text_input('이유', value=cand['의장이유'].iloc[i], key=f'r_{day}_{i}',
                                     placeholder='이유 한 줄', label_visibility='collapsed'))
edited = cand.reset_index(drop=True).copy()
edited['의장판정'], edited['의장이유'] = picks, reasons

n = int((edited['의장판정'] != '').sum())
diff = int(((edited['의장판정'] != '') & (edited['의장판정'] != edited['제미나이추천'])).sum())
st.write(f'표시 {n}/{len(edited)}건 · 제미나이와 다르게 고른 것 {diff}건')

if st.button('저장', type='primary'):
    out = cand.copy()
    out['의장판정'] = edited['의장판정'].values
    out['의장이유'] = edited['의장이유'].values
    out['날짜'] = day
    drive.put(f'{D}/{day}_판정.csv', out.to_csv(index=False).encode('utf-8-sig'))
    acc = read('00_판정누적.csv')
    keep = ['날짜', '분류', '매체', '제목', '제미나이추천', '중요도', '제미나이이유', '의장판정', '의장이유', '링크']
    marked = out[out['의장판정'] != ''][keep]
    acc = marked if acc is None else pd.concat([acc[acc['날짜'] != day].reindex(columns=keep), marked])
    drive.put(f'{D}/00_판정누적.csv', acc.sort_values('날짜').to_csv(index=False).encode('utf-8-sig'))
    st.session_state.pop(f'pre_{day}', None)
    st.cache_data.clear()
    st.success(f'저장했습니다. {len(marked)}건이 판정 누적에 들어갔고, 내일 아침 제미나이 고르기에 반영됩니다.')

with st.expander('지금까지 쌓인 판정(제미나이와 일치율)'):
    acc = read('00_판정누적.csv')
    if acc is None or acc.empty:
        st.write('아직 없습니다.')
    else:
        acc['일치'] = acc['의장판정'] == acc['제미나이추천']
        st.dataframe(acc.groupby('날짜').agg(표시=('제목', 'size'), 일치율=('일치', 'mean')).sort_index(ascending=False)
                     .style.format({'일치율': '{:.0%}'}), use_container_width=True)
        st.dataframe(acc.groupby(['분류', '의장판정']).size().unstack(fill_value=0), use_container_width=True)
