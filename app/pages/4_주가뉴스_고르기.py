# ======================================================================
# 주가 뉴스 고르기 — 07시 후보 20건 중 의장이 10건을 고르고 이유 한 줄을 적는다 (2026-11-20 의장)
#   읽는 것: 드라이브 '콜로키움 수집데이터/YYYYMMDD/YYYYMMDD_주가뉴스후보.csv' (07시 블록 9-주가뉴스)
#   쓰는 것: '콜로키움 수집데이터/뉴스실험실/00_주가뉴스_판정누적.csv' (날짜별로 바꿔 넣음)
#            다음 날 07시 news_pick.py가 이 누적으로 점수표(로지스틱 회귀)를 만들어 10건을 고른다.
# ======================================================================
import io, os, sys
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title='스튜디오 톰앤수 · 주가 뉴스 고르기', page_icon='🗞️', layout='wide')

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / 'collect'), str(ROOT / 'app')]
try:
    for k in ('DRIVE_URL', 'DRIVE_TOKEN'):
        if k in st.secrets and not os.environ.get(k):
            os.environ[k] = str(st.secrets[k])
except Exception:
    pass
import drive  # noqa: E402
import news_pick  # noqa: E402

DATA = '콜로키움 수집데이터'
GOAL = 10

if not drive.ready():
    st.error('드라이브 창구 비밀값(DRIVE_URL·DRIVE_TOKEN)이 없습니다.')
    st.stop()


def read(path):
    b = drive.get(path)
    return pd.read_csv(io.BytesIO(b), encoding='utf-8-sig') if b else None


@st.cache_data(ttl=300, show_spinner=False)
def dates():
    now = pd.Timestamp.now(tz='Asia/Seoul').normalize()
    days = [(now - pd.Timedelta(days=i)).strftime('%Y%m%d') for i in range(14)]
    return [d for d in days if any(x['name'] == f'{d}_주가뉴스후보.csv' for x in drive.ls(f'{DATA}/{d}'))]


st.title('🗞️ 주가 뉴스 고르기')
st.caption(f'07시 후보 20건 중 **{GOAL}건**을 골라 체크하고, 이유를 한 줄 적어 주세요(고른 것·버린 것 모두 적으면 더 좋습니다). '
           '판정이 쌓이면 다음 날부터 프로그램이 의장님 기준으로 10건을 고릅니다.')

ds = dates()
if not ds:
    st.info('아직 후보 파일이 없습니다. 매일 07시 수집 때 만들어집니다.')
    st.stop()
day = st.selectbox('날짜', ds, format_func=lambda d: f'{d[:4]}-{d[4:6]}-{d[6:]}')

cand = read(f'{DATA}/{day}/{day}_주가뉴스후보.csv')
if '발생대상' not in cand:
    cand['발생대상'], cand['발생신호'] = '', 0
cand['발생대상'] = cand['발생대상'].fillna('')
cand['의장선택'] = False
cand['의장이유'] = ''
acc = read(news_pick.LABEL_PATH)
if acc is not None and len(acc) and (acc['날짜'].astype(str) == day).any():
    m = acc[acc['날짜'].astype(str) == day].set_index('제목')
    cand['의장선택'] = [bool(int(m.loc[t, '의장선택'])) if t in m.index else False for t in cand['제목']]
    cand['의장이유'] = [str(m.loc[t, '의장이유']) if t in m.index and pd.notna(m.loc[t, '의장이유']) else '' for t in cand['제목']]
    st.success('이 날짜는 이미 저장하셨습니다. 고치고 다시 저장할 수 있습니다.')

# 11/20 의장: "기사 내용이 보여야 한다, 평가는 뒤로" → 표 대신 기사 카드. 제목·요약이 앞, 고름·이유는 카드 맨 아래.
cand = cand.reset_index(drop=True)
sel, why = [], []
for i, r in cand.iterrows():
    with st.container(border=True):
        ko_t = str(r.get('제목(한글)', '') or '').strip()
        ko_t = '' if ko_t.lower() == 'nan' else ko_t
        st.markdown(f"**{ko_t or r['제목']}**" + (f"  [원문]({r['링크']})" if str(r.get('링크', '')).startswith('http') else ''))
        ko_s = str(r.get('요약(한글)', '') or '').strip()
        ko_s = '' if ko_s.lower() == 'nan' else ko_s
        if ko_s or (pd.notna(r.get('요약')) and str(r.get('요약')).strip()):
            st.write(ko_s or str(r['요약']))
        if ko_t:
            st.caption(f"원제목: {r['제목']}")
        bits = [str(r.get('출처', '')), str(r.get('구분', ''))]
        if pd.notna(r.get('종목')) and str(r.get('종목')).strip():
            bits.append(f"{r['종목']} {r['등락률(%)']}%" if pd.notna(r.get('등락률(%)')) and str(r.get('등락률(%)')).strip() else str(r['종목']))
        bits.append(f"긍정 {r.get('긍정')} · 부정 {r.get('부정')}")
        if r.get('발생대상'):
            bits.append(f"전쟁 발생: {r['발생대상']}")
        bits.append('프로그램 추천' if str(r.get('프로그램추천')) in ('1', 'True', '1.0') else '프로그램 비추천')
        st.caption(' · '.join(b for b in bits if b and b != 'nan'))
        c1, c2 = st.columns([1, 4])
        sel.append(c1.checkbox('고름', value=bool(cand['의장선택'].iloc[i]), key=f's_{day}_{i}'))
        why.append(c2.text_input('이유', value=cand['의장이유'].iloc[i], key=f'w_{day}_{i}',
                                 placeholder='이유 한 줄', label_visibility='collapsed'))
edited = cand.copy()
edited['의장선택'], edited['의장이유'] = sel, why
edited['프로그램추천'] = pd.to_numeric(edited['프로그램추천'], errors='coerce').fillna(0).astype(int)

k = int(edited['의장선택'].sum())
same = int((edited['의장선택'] & (edited['프로그램추천'] == 1)).sum())
st.write(f'고른 것 {k}/{GOAL}건 · 프로그램과 같은 것 {same}건')

if st.button('저장', type='primary'):
    out = cand.copy()
    out['의장선택'] = edited['의장선택'].astype(int).values
    out['의장이유'] = edited['의장이유'].values
    out['날짜'] = day
    keep = ['날짜', '구분', '출처', '종목', '등락률(%)', '긍정', '부정', '발생신호', '제목(한글)', '제목', '요약(한글)', '요약', '의장선택', '의장이유', '프로그램추천', '링크']
    out = out.reindex(columns=keep)
    acc = out if acc is None else pd.concat([acc[acc['날짜'].astype(str) != day].reindex(columns=keep), out])
    drive.put(news_pick.LABEL_PATH, acc.sort_values('날짜').to_csv(index=False).encode('utf-8-sig'))
    st.cache_data.clear()
    st.success(f'저장했습니다. 고름 {k}건·버림 {len(out) - k}건이 판정 누적에 들어갔고, 내일 07시 고르기에 반영됩니다.')

with st.expander('지금까지 쌓인 판정과 프로그램 일치'):
    acc = read(news_pick.LABEL_PATH)
    if acc is None or acc.empty:
        st.write('아직 없습니다.')
    else:
        acc['같음'] = (acc['의장선택'].astype(int) == 1) & (acc['프로그램추천'].astype(int) == 1)
        g = acc.groupby('날짜').agg(후보=('제목', 'size'), 의장고름=('의장선택', 'sum'), 프로그램과같음=('같음', 'sum'))
        st.dataframe(g.sort_index(ascending=False), use_container_width=True)
        n = len(acc)
        st.write(f'판정 {n}건 — {news_pick.MIN_LABELS}건 이상(고름·버림 각 {news_pick.MIN_CLASS}건 이상)부터 프로그램이 의장님 점수표로 고릅니다.')
        st.dataframe(acc.groupby(['구분', '의장선택']).size().unstack(fill_value=0), use_container_width=True)
