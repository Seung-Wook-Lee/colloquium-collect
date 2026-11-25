"""11/23 의장 'CCC 기준 검정해서 만들자': ICE BofA CCC 이하(BAMLH0A3HYC)·하이일드(BAMLH0A0HYM2) 스프레드 긴 이력.
FRED는 최근 3년만 주므로 ALFRED 옛 판(vintage)을 이어 붙인다. → history/신용스프레드_이력.csv"""
import os, time
import pandas as pd, requests

KEY = os.environ.get('FRED_KEY')
URL = 'https://api.stlouisfed.org/fred/series/observations'


def get(sid, rt=None):
    p = dict(series_id=sid, api_key=KEY, file_type='json', observation_start='1996-12-31')
    if rt:
        p.update(realtime_start=rt, realtime_end=rt)
    for i in range(3):
        try:
            j = requests.get(URL, params=p, timeout=90).json()
            ob = j.get('observations')
            if ob is None:
                print(sid, rt, 'err', str(j)[:200]); return pd.Series(dtype=float)
            s = pd.Series({o['date']: o['value'] for o in ob})
            s = pd.to_numeric(s, errors='coerce').dropna(); s.index = pd.to_datetime(s.index)
            return s
        except Exception as e:   # noqa: BLE001
            print(sid, rt, 'retry', e); time.sleep(3)
    return pd.Series(dtype=float)


out = {}
for sid, nm in (('BAMLH0A3HYC', 'CCC 이하'), ('BAMLH0A0HYM2', '하이일드')):
    parts = [get(sid)]
    print(sid, '현재판', len(parts[0]), parts[0].index.min() if len(parts[0]) else None)
    for rt in ('2025-06-01', '2023-06-01', '2021-06-01', '2019-06-01', '2017-06-01', '2015-06-01', '2012-06-01', '2009-06-01'):
        s = get(sid, rt)
        print(sid, rt, len(s), s.index.min() if len(s) else None, s.index.max() if len(s) else None)
        parts.append(s)
    s = pd.concat(parts)
    s = s[~s.index.duplicated(keep='first')].sort_index()   # 최신 판 값을 우선
    out[nm] = s
    print(nm, '합친 것', len(s), s.index.min(), s.index.max())
D = pd.DataFrame(out)
os.makedirs('history', exist_ok=True)
D.to_csv('history/신용스프레드_이력.csv', encoding='utf-8-sig', index_label='날짜')
y = D.resample('YE').agg(['min', 'median', 'max']).round(2)
print(y.to_string())
