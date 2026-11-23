"""시장 기록 장부(11/23 의장): "몇 달 뒤에 '나스닥이 올해 상승분을 모두 반납한 날이 언제지?' 하면 우리 자료에서 찾아 얘기할 수 있어야."
매일 원고의 지수 기록(personas._milestones: 올해 상승분 모두 반납·하락분 모두 회복, 'D 이후 가장 낮은/높은 종가', 'D 이후 가장 큰 하루 하락/상승')을
드라이브 '콜로키움 수집데이터/시장기록_장부.csv'에 쌓는다. 처음 한 번은 1990년부터 지난 날을 같은 공식으로 채운다(backfill).
find(q, L): 질문 낱말(지수·기록)로 장부에서 날짜를 찾는다. ask.py가 '언제·날짜·며칠' 질문에 먼저 쓴다."""
import re

import pandas as pd

COLS = ['날짜', '지수', '종가', '전일대비(%)', '연초대비(%)', '기록']
NAMES = {'나스닥': ['나스닥', 'nasdaq', 'ixic'], 'S&P500': ['s&p', 'sp500', 's&p500', '에스앤피'], '다우': ['다우', 'dow'],
         '필라델피아 반도체(SOX)': ['sox', '반도체 지수', '필라델피아'], '코스피': ['코스피', 'kospi'], '코스닥': ['코스닥', 'kosdaq']}
WORDS = {'반납': '상승분 모두 반납', '회복': '하락분 모두 회복', '낮은': '가장 낮은 종가', '최저': '가장 낮은 종가', '저점': '가장 낮은 종가',
         '높은': '가장 높은 종가', '최고': '가장 높은 종가', '하락': '가장 큰 하루 하락', '급락': '가장 큰 하루 하락', '폭락': '가장 큰 하루 하락',
         '상승': '가장 큰 하루 상승', '급등': '가장 큰 하루 상승'}


def rows_for(x, name, gap, start=None):
    """지수 종가 x의 날마다 기록(personas._milestones와 같은 공식). start 뒤 날만."""
    from personas import _milestones
    x = x.dropna(); out = []
    idx = x.index if start is None else x.index[x.index >= pd.Timestamp(start)]
    for t in idx:
        s = x.loc[:t]
        if len(s) < 30:
            continue
        ytd, rec = _milestones(s, gap)
        for r in rec:
            out.append({'날짜': str(t.date()), '지수': name, '종가': round(float(s.iloc[-1]), 2), '전일대비(%)': round((s.iloc[-1] / s.iloc[-2] - 1) * 100, 2),
                        '연초대비(%)': None if ytd is None else round(ytd, 1), '기록': r})
    return out


def merge(L, new):
    D = pd.concat([L if L is not None else pd.DataFrame(columns=COLS), pd.DataFrame(new, columns=COLS)], ignore_index=True)
    return D.drop_duplicates(['날짜', '지수', '기록'], keep='last').sort_values(['날짜', '지수']).reset_index(drop=True)


def find(q, L, n=10):
    """질문에서 지수·기록 낱말을 찾아 장부 줄을 돌려준다. 없으면 None."""
    if L is None or not len(L):
        return None
    ql = q.lower()
    idx = [k for k, ws in NAMES.items() if any(w in ql for w in ws)]
    qq = q.replace('상승분', '').replace('하락분', '')   # '상승분 반납'의 '상승'을 '하루 상승'으로 읽지 않게
    kinds = list(dict.fromkeys(v for k, v in WORDS.items() if k in qq))
    if not idx and not kinds:
        return None
    T = L.copy()
    if idx:
        T = T[T['지수'].isin(idx)]
    if kinds:
        T = T[T['기록'].astype(str).apply(lambda s: any(k in s for k in kinds))]
    m = re.search(r'(19|20)\d{2}', q)
    if m:
        T = T[T['날짜'].astype(str).str.startswith(m.group(0))]
    return T.sort_values('날짜', ascending=False).head(n)
