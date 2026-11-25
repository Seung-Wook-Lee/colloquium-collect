"""CBOE 주식 풋/콜 비율(CPCE) 일별 이력 받기 (11/22 의장 그림: 빌 루비 CPCE 10일 EMA와 126일 엔벨로프).
1) CBOE 옛 파일 equitypc.csv(2006-11~2019-10) 2) 2019-10 뒤는 CBOE 날짜별 시장 통계 JSON에서 'EQUITY PUT/CALL RATIO'.
결과: history/CPCE.csv (날짜, CPCE)"""
import os, io, time, datetime as dt
import pandas as pd, requests
os.makedirs('history', exist_ok=True)
H = {'User-Agent': 'Mozilla/5.0'}
out = {}
try:
    t = requests.get('https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv', headers=H, timeout=60).text
    lines = t.splitlines(); i0 = next(i for i, l in enumerate(lines) if l.upper().startswith('DATE'))
    df = pd.read_csv(io.StringIO('\n'.join(lines[i0:])))
    df.columns = [c.strip().upper() for c in df.columns]
    rc = next(c for c in df.columns if 'RATIO' in c)
    for d, v in zip(pd.to_datetime(df['DATE'], errors='coerce'), pd.to_numeric(df[rc], errors='coerce')):
        if pd.notna(d) and pd.notna(v): out[d.normalize()] = v
    print('옛 파일', len(out), min(out), max(out))
except Exception as e:
    print('옛 파일 실패', e)
start = max(out) + pd.Timedelta(days=1) if out else pd.Timestamp('2019-10-01')
d, miss, n0 = start, 0, len(out)
URLS = ['https://cdn.cboe.com/data/us/options/market_statistics/daily/{d}_daily_options']
while d <= pd.Timestamp.today():
    if d.weekday() < 5:
        for u in URLS:
            try:
                r = requests.get(u.format(d=d.strftime('%Y-%m-%d')), headers=H, timeout=20)
                if r.status_code != 200: continue
                j = r.json()
                for x in j.get('ratios', []):
                    if 'EQUITY' in str(x.get('name', '')).upper():
                        out[d] = float(x['value']); break
                break
            except Exception as e:
                miss += 1
        if d.day == 1: print(d.date(), len(out) - n0, flush=True)
    d += pd.Timedelta(days=1)
S = pd.Series(out).sort_index(); S.index.name = '날짜'
S.rename('CPCE').to_csv('history/CPCE.csv', encoding='utf-8-sig')
print('합계', len(S), S.index.min(), S.index.max(), '새로', len(out) - n0, '실패', miss); print(S.tail())
