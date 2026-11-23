"""우리 자료에 없는 것을 한투에서 받아 드라이브에 저장 (11/23 의장).
목록: collect/data/추가자료_목록.yaml → 드라이브 '콜로키움 수집데이터/1_data/추가자료_종가.csv'(칸 = 티커/지수, 저가는 '_LOW').
처음엔 10년치, 그다음부터는 최근 1년치를 받아 앞 기록에 덧붙인다."""
import io
import os
import sys

import pandas as pd
import yaml

sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), os.path.dirname(os.path.abspath(__file__))]
import drive  # noqa: E402
import kis  # noqa: E402

PATH = '콜로키움 수집데이터/1_data/추가자료_종가.csv'
L = yaml.safe_load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '추가자료_목록.yaml'), encoding='utf-8'))
old = None
if drive.ready():
    b = drive.get(PATH)
    if b:
        old = pd.read_csv(io.BytesIO(b), index_col=0, parse_dates=True, encoding='utf-8-sig')
days = 3650 if old is None else 400
def full(k):
    """새로 더한 항목이거나 중간에 빈 날이 많으면(영업일의 85% 미만) 10년치를 다시 받아 메운다."""
    if old is None or k not in old.columns:
        return True
    s = old[k].dropna()
    return len(s) < 0.85 * len(pd.bdate_range(s.index.min(), s.index.max()))
cols, rep = {}, []
for t in (L.get('미국') or {}):
    d = kis.daily_us(t, days=3650 if full(t) else 400, pages=30 if full(t) else 5)
    rep.append(f'{t} {len(d)}일' + (f' {d.index[0]:%Y-%m-%d}~{d.index[-1]:%Y-%m-%d}' if len(d) else ' 못 받음'))
    if len(d):
        cols[t] = d['Close']; cols[f'{t}_LOW'] = d['Low']
for c, nm in (L.get('국내지수') or {}).items():
    k = {'1001': 'KOSDAQ', '0001': 'KOSPI'}.get(str(c), f'KRX{c}')
    d = kis.daily_index_kr(str(c), days=3650 if full(k) else 400)
    rep.append(f'{k} {len(d)}일' + (f' {d.index[0]:%Y-%m-%d}~{d.index[-1]:%Y-%m-%d}' if len(d) else ' 못 받음'))
    if len(d):
        cols[k] = d['Close']; cols[f'{k}_LOW'] = d['Low']
for c, nm in (L.get('해외지수') or {}).items():
    d = kis.daily_index_us(str(c), days=3650 if full(str(c)) else 400)
    rep.append(f'{c} {len(d)}일' + (f' {d.index[0]:%Y-%m-%d}~{d.index[-1]:%Y-%m-%d}' if len(d) else ' 못 받음'))
    if len(d):
        cols[str(c)] = d['Close']; cols[f'{c}_LOW'] = d['Low']
new = pd.DataFrame(cols)
D = new if old is None else new.combine_first(old)
D = D.sort_index()
print('\n'.join(rep)); print('합친 표', D.shape, D.index.min(), D.index.max())
if drive.ready() and len(D):
    drive.put(PATH, D.to_csv(encoding='utf-8-sig').encode('utf-8-sig'))
    print('드라이브 저장', PATH)
