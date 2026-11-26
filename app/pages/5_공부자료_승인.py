# ======================================================================
# 공부자료 승인 — 위원이 스스로 모은 자료 후보를 의장이 허락한다 (2026-11-20 의장)
#   읽는 것: 10년치 데이터베이스 칸 1_data/가격10년_공부후보(후보날짜 칸, meeting/study.py gather)
#   쓰는 것: 같은 칸의 의장판정·의장이유 + 칸 1_data/가격10년_공부승인 — 11/26 의장 "데이터베이스칸으로 합쳐"
#            승인된 자료만 서재(위원공부/서재/<위원>/)에 카드로 들어가 회의에서 근거로 쓰인다.
# ======================================================================
import io, os, sys
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title='스튜디오 톰앤수 · 공부자료 승인', page_icon='📚', layout='wide')
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / 'collect'), str(ROOT / 'collect' / 'data'), str(ROOT / 'app')]
try:
    for k in ('DRIVE_URL', 'DRIVE_TOKEN'):
        if k in st.secrets and not os.environ.get(k):
            os.environ[k] = str(st.secrets[k])
except Exception:
    pass
import drive  # noqa: E402
import px_store as PS  # noqa: E402  11/26 의장 "데이터베이스칸으로 합쳐": 후보·승인 = 1_data/가격10년_공부후보·공부승인

BASE = '콜로키움 수집데이터/위원공부'
if not drive.ready():
    st.error('드라이브 창구 비밀값(DRIVE_URL·DRIVE_TOKEN)이 없습니다.')
    st.stop()


def read(path):
    b = drive.get(path)
    return pd.read_csv(io.BytesIO(b), encoding='utf-8-sig', dtype=str).fillna('') if b else None


st.title('📚 공부자료 승인')
st.caption('위원들이 스스로 모은 자료 후보입니다. **승인**한 자료만 위원 서재에 쌓여 회의 근거로 쓰입니다. '
           '목표는 정확한 바닥이 아니라 **바닥 즈음**을 알아보는 것입니다.')

ALL = PS.rows(drive, '공부후보')
files = sorted(ALL['후보날짜'].astype(str).unique(), reverse=True) if '후보날짜' in ALL else []
if not len(files):
    st.info('아직 후보가 없습니다.')
    st.stop()
name = st.selectbox('날짜', files, format_func=lambda f: f'{f[:4]}-{f[4:6]}-{f[6:8]}')
C = ALL[ALL['후보날짜'].astype(str) == name].drop(columns='후보날짜').reset_index(drop=True)

pick, why = [], []
for who, g in C.groupby('위원', sort=False):
    st.subheader(f"{who} · {g['분야'].iloc[0]}")
    for i, r in g.iterrows():
        with st.container(border=True):
            st.markdown(f"**{r['번호']}. {r['제목(한글)'] or r['원제목']}**  [원문]({r['링크']})")
            if r['요약(한글)'] or r['요약']:
                st.write(r['요약(한글)'] or r['요약'])
            st.caption(f"{r['출처']} · {r['날짜']} · {r['종류']} · 쓰일 칸: {r['쓰일칸']} · 원제목: {r['원제목']}")
            a, b = st.columns([1, 4])
            opts = ['미정', '승인', '거절']
            pick.append((i, a.radio('판정', opts, index=opts.index(r['의장판정']) if r['의장판정'] in opts else 0,
                                    key=f'p_{name}_{i}', horizontal=True, label_visibility='collapsed')))
            why.append(b.text_input('이유', value=r['의장이유'], key=f'w_{name}_{i}', placeholder='이유 한 줄(선택)',
                                    label_visibility='collapsed'))

if st.button('저장', type='primary'):
    for (i, p), w in zip(pick, why):
        C.at[i, '의장판정'] = '' if p == '미정' else p
        C.at[i, '의장이유'] = w
    PS.put_day(drive, '공부후보', '후보날짜', name, C)
    acc = PS.rows(drive, '공부승인')
    done = C[C['의장판정'].isin(['승인', '거절'])].assign(후보날짜=name[:8])
    acc = done if acc.empty else pd.concat([acc[~acc['링크'].isin(done['링크'])], done], ignore_index=True)
    PS.put_rows(drive, '공부승인', acc)
    st.success(f"저장했습니다. 승인 {int((C['의장판정'] == '승인').sum())}건 · 거절 {int((C['의장판정'] == '거절').sum())}건. "
               '승인 자료는 다음 회의 준비 때 서재에 들어갑니다.')

with st.expander('서재(승인된 자료) 보기'):
    acc = PS.rows(drive, '공부승인')
    if acc.empty:
        st.write('아직 없습니다.')
    else:
        ok = acc[acc['의장판정'] == '승인']
        st.dataframe(ok[['후보날짜', '위원', '제목(한글)', '출처', '날짜', '쓰일칸']], use_container_width=True, hide_index=True)
