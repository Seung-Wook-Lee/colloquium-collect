"""11/23 CCC 대체: 무디스 Baa−10년(BAA10Y, 1986~)·Aaa−10년(AAA10Y) 긴 이력 → collect/research/out/무디스스프레드_이력.csv"""
import os, pandas as pd, requests
KEY = os.environ.get('FRED_KEY'); out = {}
for sid in ('BAA10Y', 'AAA10Y'):
    j = requests.get('https://api.stlouisfed.org/fred/series/observations', params=dict(series_id=sid, api_key=KEY, file_type='json'), timeout=90).json()
    s = pd.Series({o['date']: o['value'] for o in j.get('observations', [])}); s = pd.to_numeric(s, errors='coerce').dropna(); s.index = pd.to_datetime(s.index)
    out[sid] = s; print(sid, len(s), s.index.min(), s.index.max())
D = pd.DataFrame(out); os.makedirs('collect/research/out', exist_ok=True)
D.to_csv('collect/research/out/무디스스프레드_이력.csv', encoding='utf-8-sig', index_label='날짜')
print(D.resample('YE').agg(['median', 'max']).round(2).tail(30).to_string())
