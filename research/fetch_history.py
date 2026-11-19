# 과거 자료 한 번에 받기(11/19 의장: 바닥 징후 분석, FRED·지정학 위험 지수 10년치). 무료 공개 자료만.
#   만드는 것: history/FRED_일별.csv, history/GPR_일별.csv
import io, os, time, requests, pandas as pd
os.makedirs('history', exist_ok=True)
H = {'User-Agent': 'Mozilla/5.0 (colloquium research)'}
FRED = {'BAMLH0A0HYM2': 'HY', 'STLFSI4': 'STLFSI', 'T10Y2Y': 'T10Y2Y', 'DGS10': 'US10Y', 'DGS2': 'US2Y', 'SOFR': 'SOFR', 'IORB': 'IORB',
        'DFII10': 'REAL10Y', 'BAMLC0A0CM': 'IG', 'VIXCLS': 'VIX_FRED', 'NFCI': 'NFCI'}
out = []
for sid, nm in FRED.items():
    for k in range(4):
        try:
            r = requests.get(f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd=2005-01-01', headers=H, timeout=60); r.raise_for_status()
            s = pd.read_csv(io.StringIO(r.text)); s.columns = ['날짜', nm]
            s['날짜'] = pd.to_datetime(s['날짜']); s[nm] = pd.to_numeric(s[nm], errors='coerce'); out.append(s.set_index('날짜')[nm]); print(sid, len(s)); break
        except Exception as e:
            print(sid, '재시도', e); time.sleep(5)
pd.concat(out, axis=1).sort_index().to_csv('history/FRED_일별.csv', encoding='utf-8-sig')
for url in ('https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls',):
    g = pd.read_excel(io.BytesIO(requests.get(url, headers=H, timeout=120).content))
    g.to_csv('history/GPR_일별.csv', index=False, encoding='utf-8-sig'); print('GPR', g.shape, list(g.columns)[:8])
