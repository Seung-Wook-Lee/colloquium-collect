"""우리 자료에 없는 것을 한투에서 받아 드라이브에 저장 (11/23 의장).
목록: collect/data/추가자료_목록.yaml → 드라이브 10년치 저장본 칸 '콜로키움 수집데이터/1_data/가격10년_추가종가.csv.gz'(칸 = 티커/지수, 저가는 '_LOW').
11/26 의장 "10년치 저장본 밖에 따로 있는 과거 자료들을 저장본에 합치시오": 옛 1_data/추가자료_종가.csv는 PS.fetch가 처음 한 번 칸으로 옮기고 휴지통.
처음엔 10년치, 그다음부터는 최근 1년치를 받아 앞 기록에 덧붙인다."""
import os
import sys

import pandas as pd
import yaml

sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), os.path.dirname(os.path.abspath(__file__))]
import drive  # noqa: E402
import kis  # noqa: E402
import px_store as PS  # noqa: E402

PATH = f'{PS.BASE}/1_data/{PS.name("추가종가")}'
L = yaml.safe_load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '추가자료_목록.yaml'), encoding='utf-8'))
old = None
TMP = os.environ.get('RUNNER_TEMP') or '/tmp'
if drive.ready() and PS.fetch(drive, '추가종가', TMP):
    old = pd.read_csv(f'{TMP}/{PS.name("추가종가")}', index_col=0, parse_dates=True, encoding='utf-8-sig')
# 11/25 의장 "저장된 것을 쓰도록, 없을 때만 받으라고": 저장본에 있는 칸은 그 칸 마지막 날 3일 전부터만 받는다.
#   10년치는 저장본에 그 칸이 아예 없을 때만(빈 날이 많다고 다시 받던 규칙은 지움 — 매일 10년치를 다시 받았음).
def full(k):
    return old is None or k not in old.columns or old[k].dropna().empty


def since(k):
    """그 칸을 받을 날 수."""
    if full(k):
        return 3650
    import datetime as _dt
    return max(5, (_dt.date.today() - old[k].dropna().index.max().date()).days + 3)


cols, rep = {}, []
for t in (L.get('미국') or {}):
    d = kis.daily_us(t, days=since(t), pages=30 if full(t) else 1)
    rep.append(f'{t} {len(d)}일' + (f' {d.index[0]:%Y-%m-%d}~{d.index[-1]:%Y-%m-%d}' if len(d) else ' 못 받음'))
    if len(d):
        cols[t] = d['Close']; cols[f'{t}_LOW'] = d['Low']
for c, nm in (L.get('국내지수') or {}).items():
    k = {'1001': 'KOSDAQ', '0001': 'KOSPI'}.get(str(c), f'KRX{c}')
    d = kis.daily_index_kr(str(c), days=since(k))
    rep.append(f'{k} {len(d)}일' + (f' {d.index[0]:%Y-%m-%d}~{d.index[-1]:%Y-%m-%d}' if len(d) else ' 못 받음'))
    if len(d):
        cols[k] = d['Close']; cols[f'{k}_LOW'] = d['Low']
for c, nm in (L.get('해외지수') or {}).items():
    d = kis.daily_index_us(str(c), days=since(str(c)))
    rep.append(f'{c} {len(d)}일' + (f' {d.index[0]:%Y-%m-%d}~{d.index[-1]:%Y-%m-%d}' if len(d) else ' 못 받음'))
    if len(d):
        cols[str(c)] = d['Close']; cols[f'{c}_LOW'] = d['Low']
new = pd.DataFrame(cols)
D = new if old is None else new.combine_first(old)
D = D.sort_index()
print('\n'.join(rep)); print('합친 표', D.shape, D.index.min(), D.index.max())
if drive.ready() and len(D):
    import gzip
    drive.put(PATH, gzip.compress(D.to_csv(encoding='utf-8-sig').encode('utf-8-sig')))
    print('드라이브 저장', PATH)
    if drive.get(PATH) and drive.trash(f'{PS.BASE}/1_data/추가자료_종가.csv.gz'):   # 옛 작은 압축본(칸 하나로 충분)
        print('[저장본] 옛 추가자료_종가.csv.gz 휴지통')
