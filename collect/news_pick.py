# ======================================================================
# 주가 뉴스 고르기 학습 — 의장이 매일 후보 20건 중 고른 10건(+이유)을 배워 다음 날 프로그램이 10건을 고른다 (2026-11-20 의장)
#   1) 명시 규칙(ALWAYS·NEVER): 의장 이유를 클로드가 규칙으로 옮겨 적는 곳. 점수보다 먼저 적용.
#   2) 점수표(로지스틱 회귀): 제목·요약 낱말, 구분(세계 정세/종목/시장), 출처, FinBERT 긍정·부정, 종목 등락률 크기,
#      발생신호(전쟁 발생, 블록 9-주가뉴스). 의장 이유는 이렇게 '단서 칸'으로 넣고 무게는 판정으로 정한다.
#      같은 자료면 늘 같은 답(무작위 없음). 판정이 MIN_LABELS건 미만이거나 한쪽이 MIN_CLASS건 미만이면 쓰지 않는다.
#   3) 점수표가 없을 때: FinBERT 긍정·부정 확률이 센 순.
#   판정 파일: 드라이브 '콜로키움 수집데이터/뉴스실험실/00_주가뉴스_판정누적.csv'
#             (날짜, 구분, 출처, 종목, 등락률(%), 긍정, 부정, 발생신호, 제목, 요약, 의장선택(1/0), 의장이유, 프로그램추천(1/0))
# ======================================================================
import re

import numpy as np
import pandas as pd

LABEL_PATH = '콜로키움 수집데이터/뉴스실험실/00_주가뉴스_판정누적.csv'
MIN_LABELS = 40       # 이만큼 판정이 쌓이면 점수표를 쓴다
MIN_CLASS = 10        # 고른 것·버린 것 각각 최소 건수
ALWAYS = []           # 제목 정규식 — 맞으면 항상 넣는다(의장 이유에서 옮김, 날짜·근거를 주석으로)
NEVER = []            # 제목 정규식 — 맞으면 항상 뺀다


def _text(df):
    return (df['제목'].fillna('').astype(str) + ' ' + df.get('요약', pd.Series('', index=df.index)).fillna('').astype(str)).str.lower()


def _num(df):
    chg = pd.to_numeric(df.get('등락률(%)', pd.Series(np.nan, index=df.index)), errors='coerce').abs().fillna(0)
    return pd.DataFrame({'긍정': pd.to_numeric(df['긍정'], errors='coerce').fillna(0),
                         '부정': pd.to_numeric(df['부정'], errors='coerce').fillna(0),
                         '등락크기': chg.clip(upper=20) / 20,
                         '발생신호': pd.to_numeric(df.get('발생신호', pd.Series(0, index=df.index)), errors='coerce').fillna(0)})


def fit(labels):
    """판정 누적으로 점수표를 만든다. 모자라면 None과 이유."""
    if labels is None or not len(labels):
        return None, '판정 0건'
    y = pd.to_numeric(labels['의장선택'], errors='coerce').fillna(0).astype(int)
    if len(y) < MIN_LABELS or y.sum() < MIN_CLASS or (len(y) - y.sum()) < MIN_CLASS:
        return None, f'판정 {len(y)}건(고름 {int(y.sum())}) — {MIN_LABELS}건 이상, 고름·버림 각 {MIN_CLASS}건 이상부터 점수표 사용'
    from scipy.sparse import hstack, csr_matrix
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.linear_model import LogisticRegression
    tv = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4), min_df=2, max_features=20000)
    oh = OneHotEncoder(handle_unknown='ignore')
    cat = labels[['구분', '출처']].fillna('').astype(str)
    X = hstack([tv.fit_transform(_text(labels)), oh.fit_transform(cat), csr_matrix(_num(labels).values)]).tocsr()
    m = LogisticRegression(C=1.0, max_iter=2000, class_weight='balanced').fit(X, y)
    return (tv, oh, m), f'점수표 사용(판정 {len(y)}건, 고름 {int(y.sum())})'


def score(df, model):
    """후보마다 점수(0~1). 명시 규칙이 먼저: ALWAYS 2, NEVER -1."""
    if model is None:
        s = pd.concat([pd.to_numeric(df['긍정'], errors='coerce'), pd.to_numeric(df['부정'], errors='coerce')], axis=1).max(axis=1).fillna(0)
    else:
        from scipy.sparse import hstack, csr_matrix
        tv, oh, m = model
        X = hstack([tv.transform(_text(df)), oh.transform(df[['구분', '출처']].fillna('').astype(str)),
                    csr_matrix(_num(df).values)]).tocsr()
        s = pd.Series(m.predict_proba(X)[:, 1], index=df.index)
    t = df['제목'].fillna('').astype(str)
    for pat in ALWAYS:
        s[t.str.contains(pat, regex=True, flags=re.I)] = 2.0
    for pat in NEVER:
        s[t.str.contains(pat, regex=True, flags=re.I)] = -1.0
    return s.round(4)
