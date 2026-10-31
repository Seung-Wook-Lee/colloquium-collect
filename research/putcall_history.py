# 풋/콜 비율 이력 비교 (2026-10-31 의장 질문, 포보스 보고용) — Actions에서 한 번 돌려 로그로 읽는다.
# CNN 공포탐욕 graphdata(2020-01-01부터 요청)의 put_call_options(5일 평균 풋/콜)와 종합 점수, S&P500 종가를 맞춰
# 평소·중립(45~55점)·사상 최고가 근처·큰 하락 구간의 풋/콜 수준을 출력한다.
import requests, pandas as pd, yfinance as yf

H = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://edition.cnn.com/'}
j = requests.get('https://production.dataviz.cnn.io/index/fearandgreed/graphdata/2020-01-01', headers=H, timeout=30).json()

def ser(key):
    d = j.get(key, {}).get('data', [])
    s = pd.Series({pd.to_datetime(p['x'], unit='ms').normalize(): p['y'] for p in d}, dtype=float)
    return s[~s.index.duplicated()].sort_index()

pc, fg = ser('put_call_options'), ser('fear_and_greed_historical')
print('키:', list(j.keys()))
print(f'풋콜 기간 {pc.index.min():%Y-%m-%d}~{pc.index.max():%Y-%m-%d} {len(pc)}일 / 점수 {fg.index.min():%Y-%m-%d}~ {len(fg)}일')
spx = yf.Ticker('^GSPC').history(start='2019-01-01')['Close']
spx.index = spx.index.tz_localize(None).normalize()
df = pd.DataFrame({'pc': pc, 'fg': fg}).join(spx.rename('spx'), how='left').dropna(subset=['pc'])
df['ath'] = spx.cummax().reindex(df.index)
df['dd'] = (df['spx'] / df['ath'] - 1) * 100
q = df['pc'].quantile([.05, .1, .25, .5, .75, .9, .95]).round(3)
print('\n[전체 분포] 5·10·25·50·75·90·95%:', q.tolist(), ' 평균', round(df['pc'].mean(), 3))
cur = df.iloc[-1]
print(f'[현재] {df.index[-1]:%Y-%m-%d} 풋콜 {cur.pc:.3f} 점수 {cur.fg:.1f} 백분위 {(df.pc < cur.pc).mean() * 100:.0f}%')
for yr, g in df.groupby(df.index.year):
    print(f'  {yr}: 중앙값 {g.pc.median():.3f} 최저 {g.pc.min():.3f} 최고 {g.pc.max():.3f}({g.pc.idxmax():%m-%d})')
nz = df[(df.fg >= 45) & (df.fg <= 55)]
print(f'\n[중립 45~55점일 때] {len(nz)}일 중앙값 {nz.pc.median():.3f}')
for lo, hi, nm in [(0, 25, '극단적 공포'), (25, 45, '공포'), (55, 75, '탐욕'), (75, 101, '극단적 탐욕')]:
    g = df[(df.fg >= lo) & (df.fg < hi)]
    print(f'  {nm} {lo}~{hi}: {len(g)}일 중앙값 {g.pc.median():.3f}')
ath = df[df.dd >= -1]
print(f'[S&P 사상 최고가 1% 안] {len(ath)}일 중앙값 {ath.pc.median():.3f}')
print('\n[S&P 큰 하락(고점 대비 -10% 이상) 구간별 최저점과 그 전후 풋콜 최고]')
inside, start = False, None
for d, r in df.iterrows():
    if r.dd <= -10 and not inside:
        inside, start = True, d
    elif r.dd > -3 and inside:
        g = df.loc[start:d]
        print(f'  {start:%Y-%m-%d}~{d:%Y-%m-%d}: S&P 최저 {g.dd.min():.1f}%({g.dd.idxmin():%Y-%m-%d}), 풋콜 최고 {g.pc.max():.3f}({g.pc.idxmax():%Y-%m-%d}), 점수 최저 {g.fg.min():.1f}')
        inside = False
if inside:
    g = df.loc[start:]
    print(f'  {start:%Y-%m-%d}~진행 중: S&P 최저 {g.dd.min():.1f}%, 풋콜 최고 {g.pc.max():.3f}({g.pc.idxmax():%Y-%m-%d})')
print('\n[풋콜 상위 15일]')
print(df.sort_values('pc', ascending=False).head(15)[['pc', 'fg', 'dd']].round(2).to_string())
print('\n[최근 30일]')
print(df.tail(30)[['pc', 'fg', 'dd']].round(3).to_string())
