"""국내 종목 신용잔고(융자) 일별 — 한투 FHPST04760000 → 드라이브 '콜로키움 수집데이터/1_data/신용잔고_일별.csv' (11/23 의장: 강제 매도 반등 검정).
칸: 날짜, 코드, 융자잔고주수, 잔고율(%), 융자금액. 처음엔 받을 수 있는 만큼(최대 10년), 그다음은 최근 60일을 덧붙인다."""
import io
import os
import sys

import pandas as pd

sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), os.path.dirname(os.path.abspath(__file__))]
import drive  # noqa: E402
import kis  # noqa: E402

PATH = '콜로키움 수집데이터/1_data/신용잔고_일별.csv'
U = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'teamq', 'universe_20261120.csv'), dtype={'코드': str})
codes = U[(U['시장'] == '한국') & (U['구분'] == '개별주')]['코드'].dropna().str.zfill(6).unique()
old = None
if drive.ready():
    b = drive.get(PATH)
    if b:
        old = pd.read_csv(io.BytesIO(b), dtype={'코드': str}, parse_dates=['날짜'], encoding='utf-8-sig')
have = set(old['코드']) if old is not None else set()
parts, rep = [], []
for i, c in enumerate(codes):
    d = kis.credit_kr(c, days=60 if c in have else 3650, probe=(i == 0))
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
