"""국내 종목 신용잔고(융자) 일별 — 한투 FHPST04760000 → 드라이브 '콜로키움 수집데이터/1_data/신용잔고_일별.csv' (11/23 의장: 강제 매도 반등 검정).
칸: 날짜, 코드, 융자잔고주수, 잔고율(%), 융자금액. 처음엔 받을 수 있는 만큼(최대 10년), 그다음은 저장본 마지막 날 뒤만 덧붙인다(11/25 의장)."""
import io
import os
import sys

import pandas as pd

sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), os.path.dirname(os.path.abspath(__file__))]
import drive  # noqa: E402
import kis  # noqa: E402

PATH = '콜로키움 수집데이터/1_data/신용잔고_일별.csv'
import px_store as PS  # noqa: E402
U = PS.universe(drive)   # 11/26 의장 "하나로 통일해": 유니버스 = 10년치 데이터베이스 칸
codes = U[(U['시장'] == '한국') & (U['구분'] == '개별주')]['코드'].dropna().str.zfill(6).unique()
old = None
if drive.ready():
    b = drive.get(PATH)
    if b:
        old = pd.read_csv(io.BytesIO(b), dtype={'코드': str}, parse_dates=['날짜'], encoding='utf-8-sig')
have = set(old['코드']) if old is not None else set()
import datetime as _dt
since = {} if old is None else {c: max(5, (_dt.date.today() - d.date()).days + 3) for c, d in old.groupby('코드')['날짜'].max().items()}
parts, rep = [], []
for i, c in enumerate(codes):
    d = kis.credit_kr(c, days=since.get(c, 3650), probe=(i == 0))   # 11/25 의장: 받아 둔 것에 그날 것만(저장본 마지막 날 3일 전부터)
    rep.append(f'{c} {len(d)}일' + (f' {d.index[0]:%Y-%m-%d}~{d.index[-1]:%Y-%m-%d}' if len(d) else ' 못 받음'))
    if len(d):
        parts.append(d.reset_index().assign(코드=c))
new = pd.concat(parts) if parts else pd.DataFrame()
D = new if old is None else pd.concat([new, old])
D = D.drop_duplicates(['날짜', '코드'], keep='first').sort_values(['코드', '날짜'])
print('\n'.join(rep)); print('합친 표', D.shape)
if drive.ready() and len(D):
    drive.put(PATH, D.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'))
    print('드라이브 저장', PATH)
    # 작은 압축본: 잔고율(%)만 날짜×코드 표로 → 프로젝트 폴더로 내려받아 검정에 쓴다
    import gzip
    T = D.pivot_table(index='날짜', columns='코드', values='잔고율')
    drive.put('콜로키움 수집데이터/1_data/신용잔고율_표.csv.gz', gzip.compress(T.to_csv(float_format='%.4g', encoding='utf-8-sig').encode('utf-8-sig')))
    print('드라이브 저장 신용잔고율_표.csv.gz', T.shape)
