# ======================================================================
# 회의 발표 — 정례 회의에서 위원별 발표를 회의 순서대로 그래프와 함께 본다 (2026-11-10 의장)
#   읽는 것  : 드라이브 '콜로키움 수집데이터/YYYYMMDD/YYYYMMDD_발표.json'  ← 클로드가 매일 09:40에 쓴다
#              그래프 숫자는 같은 날짜 폴더의 07시 수집 CSV와 '00_누적/00_가격이력.csv'에서만 가져온다.
#              (가격·등락률은 _시세.csv, 수급은 _국내수급.csv — 발표 문장에 숫자를 새로 만들지 않는다)
#   발표 파일: {"date": "20261110", "note": "...", "members": [
#                 {"name": "국장", "role": "밤사이 주요 뉴스", "lines": ["1. 제목: 내용", ...],
#                  "charts": [ {...}, ... ],            # 아래 '그래프 종류'
#                  "sub": [ {같은 모양의 위원}, ... ]}   # 피터·데스크처럼 한 탭 안에 여러 위원
#              ]}
#   그래프 종류(type):
#     change  : _시세.csv 하루 등락률 막대.      tickers=[야후 티커…], labels={티커: 이름}(선택)
#     line    : 가격이력 흐름(시작 = 100).       tickers=[…], days=365(기본)
#     rsi     : 가격이력 → 주봉 RSI(와일더 14).   tickers=[…], weeks=26(기본)
#     bar     : 날짜 폴더 CSV의 한 칸 막대.      file='국내수급', key='종목', value='외국인 20일(억원)', rows=[…], scale=1
#     table   : 날짜 폴더 CSV에서 줄·칸 골라 표.  file='예외검정', key='정식 종목명', rows=[…], cols=[…]
#     grid    : 문장에 쓴 표를 그대로.          columns=[…], rows=[[…], …]
#   이 페이지는 판정하지 않는다. 문장은 발표 파일 그대로, 숫자는 수집 파일 그대로.
# ======================================================================
import io, json, os, sys, datetime as dt
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title='콜로키움 · 회의 발표', page_icon='🗣️', layout='wide')

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    for k in ('DRIVE_URL', 'DRIVE_TOKEN', 'COLLOQ_DATA'):
        if k in st.secrets and not os.environ.get(k):
            os.environ[k] = str(st.secrets[k])
except Exception:
    pass
import drive  # noqa: E402

D_DATA = '콜로키움 수집데이터'
LOCAL = os.environ.get('COLLOQ_DATA', '').strip()
KST = dt.timezone(dt.timedelta(hours=9))
UP, DN = '#1e8e3e', '#d32f2f'                 # 미국식: 초록 상승, 빨강 하락 (2026-10-28 의장)
PALETTE = ['#2563eb', '#d97706', '#7c3aed', '#0891b2', '#db2777', '#65a30d', '#475569', '#b45309', '#0d9488', '#9333ea']


# ---------------------------------------------------------------- 자료 읽기
def _raw(rel):
    if LOCAL:
        p = Path(LOCAL) / rel
        return p.read_bytes() if p.exists() else None
    return drive.get(f'{D_DATA}/{rel}')


@st.cache_data(ttl=600, show_spinner=False)
def days(n=10):
    out, today = [], dt.datetime.now(KST).date()
    for i in range(n):
        d = (today - dt.timedelta(days=i)).strftime('%Y%m%d')
        ok = (Path(LOCAL) / d).is_dir() if LOCAL else bool(drive.ls(f'{D_DATA}/{d}'))
        if ok:
            out.append(d)
    return out


@st.cache_data(ttl=60, show_spinner=False)      # 회의 중 고친 문장이 1분 안에 보이게
def script(day):
    b = _raw(f'{day}/{day}_발표.json')
    if not b:
        return None
    return json.loads(b.decode('utf-8-sig'))


@st.cache_data(ttl=600, show_spinner=False)
def csv(day, name):
    b = _raw(f'{day}/{day}_{name}.csv')
    return pd.read_csv(io.BytesIO(b), encoding='utf-8-sig', dtype={'코드': str}) if b else pd.DataFrame()


@st.cache_data(ttl=6 * 3600, show_spinner='가격 이력 불러오는 중…')
def prices():
    b = _raw('00_누적/00_가격이력.csv')
    if not b:
        return pd.DataFrame()
    p = pd.read_csv(io.BytesIO(b), encoding='utf-8-sig', usecols=['날짜', '티커', '수정종가', '종가'],
                    parse_dates=['날짜'], dtype={'티커': str})
    p['가격'] = p['수정종가'].fillna(p['종가'])
    return p[['날짜', '티커', '가격']]


def num(s):
    return pd.to_numeric(s, errors='coerce')


def names(day):
    """야후 티커 → 종목명 (시세 파일 기준)"""
    p = csv(day, '시세')
    if not len(p):
        return {}
    return dict(zip(p['yfinance 티커'].astype(str), p['정식 종목명'].astype(str)))


# ---------------------------------------------------------------- 그래프 (app/present.py, 첫 화면과 같이 씀)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import present  # noqa: E402
present.setup(csv, prices)
member = present.member


# ---------------------------------------------------------------- 화면
if not LOCAL and not drive.ready():
    st.error('드라이브 창구 비밀값(DRIVE_URL·DRIVE_TOKEN)이 없습니다.')
    st.stop()

with st.sidebar:
    found = days()
    if not found:
        st.error('최근 10일 안에 수집 자료가 없습니다.'); st.stop()
    DAY = st.selectbox('날짜', found, format_func=lambda d: f'{d[:4]}-{d[4:6]}-{d[6:]}')
    if st.button('새로 불러오기', width='stretch'):
        st.cache_data.clear(); st.rerun()

sc = script(DAY)
if not sc:
    st.info(f'{DAY[:4]}-{DAY[4:6]}-{DAY[6:]} 발표 원고가 아직 없습니다. 클로드가 09:40에 올립니다.')
    st.stop()

st.title(f'정례 회의 발표 · {DAY[:4]}-{DAY[4:6]}-{DAY[6:]}')
if sc.get('note'):
    st.caption(sc['note'])
nm = names(DAY)
mem = sc.get('members', [])
tabs = st.tabs([m['name'] for m in mem])
for t, m in zip(tabs, mem):
    with t:
        if m.get('sub'):
            if m.get('lines') or m.get('charts'):
                member(DAY, {k: v for k, v in m.items() if k != 'sub'}, nm)
            subt = st.tabs([s['name'] for s in m['sub']])
            for st_, s in zip(subt, m['sub']):
                with st_:
                    member(DAY, s, nm)
        else:
            member(DAY, m, nm)
