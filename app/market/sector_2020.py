"""2020 코로나: 섹터 ETF 11개 + 금·장기채, 금 바닥(3/19) 뒤 상승률과 시기 (11/23 의장)."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import pandas as pd
import yfinance as yf

OUT = Path('/mnt/project-files/유니버스/start/covid_rotation/')
fm.fontManager.addfont('/root/.fonts/NanumGothic.ttf'); plt.rcParams['font.family'] = 'NanumGothic'; plt.rcParams['axes.unicode_minus'] = False
S = {'XLK': '기술', 'XLV': '헬스케어', 'XLF': '금융', 'XLY': '임의소비재', 'XLP': '필수소비재', 'XLE': '에너지', 'XLI': '산업재',
     'XLB': '소재', 'XLU': '유틸리티', 'XLRE': '부동산', 'XLC': '커뮤니케이션', 'GLD': '금', 'TLT': '미국 장기채', '^GSPC': 'S&P500', '^NDX': '나스닥100', '^KS11': '코스피'}
COL = dict(zip(S, ['#1f77b4', '#2ca02c', '#8c564b', '#e377c2', '#7f7f7f', '#000000', '#17becf', '#bcbd22', '#9467bd', '#ff7f0e', '#d62728', '#d4a017', '#1f5fa8', '#444444', '#7b1fa2', '#00897b']))
P = yf.download(list(S), start='2020-02-01', end='2020-10-01', auto_adjust=True, progress=False)['Close'].ffill()
g = pd.Timestamp('2020-03-19')
N = P[list(S)].div(P[list(S)].loc[g]) * 100
# 1) 겹친 그래프
fig, ax = plt.subplots(figsize=(14, 7.5))
for t, nm in S.items():
    y = N[t]['2020-03-01':'2020-09-30']
    ax.plot(y.index, y, color=COL[t], lw=3.2 if t.startswith('^') else (2.2 if t == 'GLD' else 1.4), ls='--' if t in ('GLD', 'TLT') else (':' if t.startswith('^') else '-'))
    ax.annotate(f'{nm} {y.iloc[-1]:.0f}', (y.index[-1], y.iloc[-1]), xytext=(4, 0), textcoords='offset points', fontsize=9, color=COL[t], va='center')
for d, txt in (('2020-03-19', '금 바닥 3/19'), ('2020-03-23', 'S&P 바닥 3/23')):
    ax.axvline(pd.Timestamp(d), color='#888', lw=1); ax.text(pd.Timestamp(d), 182, txt, fontsize=9, rotation=90, va='top')
ax.axhline(100, color='#999', lw=0.6); ax.grid(alpha=0.25); ax.set_xlim(pd.Timestamp('2020-03-01'), pd.Timestamp('2020-10-20'))
ax.set_title('2020 섹터 ETF 11개 + 금·장기채·S&P500·나스닥100·코스피(점선 굵게) (금 바닥 3/19 = 100)', loc='left', fontsize=13)
ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%m/%d'))
fig.savefig(OUT / '2020_섹터_겹침.png', dpi=160, bbox_inches='tight'); plt.close(fig)
# 2) 구간별 상승률 표(2주 단위, 금 바닥부터)
cuts = [g] + [g + pd.Timedelta(weeks=w) for w in (1, 2, 4, 6, 8, 10, 12, 16, 20, 26)]
lab = ['1주', '2주', '3~4주', '5~6주', '7~8주', '9~10주', '11~12주', '13~16주', '17~20주', '21~26주']
R = pd.DataFrame({l: (P[list(S)].asof(b) / P[list(S)].asof(a) - 1) * 100 for l, a, b in zip(lab, cuts[:-1], cuts[1:])})
R.index = [S[t] for t in R.index]
lo = {S[t]: P[t]['2020-02-15':'2020-05-15'].idxmin().strftime('%m/%d') for t in S}
pk = {}
for t in S:
    c = P[t][g:]; y = c / c.iloc[0]
    pk[S[t]] = ((c / c.shift(10) - 1).idxmax())   # 10거래일 상승이 가장 컸던 끝날
T = pd.DataFrame({'저점일': lo, '1개월(%)': (P[list(S)].asof(g + pd.DateOffset(months=1)) / P[list(S)].loc[g] - 1).set_axis([S[t] for t in S]) * 100,
                  '3개월(%)': (P[list(S)].asof(g + pd.DateOffset(months=3)) / P[list(S)].loc[g] - 1).set_axis([S[t] for t in S]) * 100,
                  '6개월(%)': (P[list(S)].asof(g + pd.DateOffset(months=6)) / P[list(S)].loc[g] - 1).set_axis([S[t] for t in S]) * 100,
                  '가장 세게 오른 2주(끝날)': {k: v.strftime('%m/%d') for k, v in pk.items()}})
T = T.sort_values('1개월(%)', ascending=False)
pd.concat([T, R], axis=1).round(1).to_csv(OUT / '2020_섹터_구간별.csv', encoding='utf-8-sig')
# 3) 히트맵
R = R.loc[T.index]
fig, ax = plt.subplots(figsize=(13, 6.5))
im = ax.imshow(R.values, cmap='RdYlGn', vmin=-15, vmax=15, aspect='auto')
ax.set_xticks(range(len(lab))); ax.set_xticklabels([f'{l}\n{a:%m/%d}~{b:%m/%d}' for l, a, b in zip(lab, cuts[:-1], cuts[1:])], fontsize=8.5)
ax.set_yticks(range(len(R))); ax.set_yticklabels(R.index, fontsize=10)
for i in range(R.shape[0]):
    for j in range(R.shape[1]):
        v = R.values[i, j]; top = v == R.iloc[:, j].max()
        ax.text(j, i, f'{v:+.0f}', ha='center', va='center', fontsize=9, color='black', fontweight='bold' if top else 'normal',
                bbox=dict(fc='none', ec='black', lw=1.2) if top else None)
ax.set_title('2020 금 바닥(3/19) 뒤 구간별 상승률(%) — 네모 = 그 구간 1등', loc='left', fontsize=12)
fig.savefig(OUT / '2020_섹터_구간별_히트맵.png', dpi=160, bbox_inches='tight'); plt.close(fig)
print(T.round(1).to_string())
print(R.round(1).to_string())
print('구간 1등:', {c: R[c].idxmax() for c in R})
print('구간 2등:', {c: R[c].nlargest(2).index[1] for c in R})

# 4) 구간 1등을 차례로 산 경우(사후 계산) vs 지수
lead = [R[c].idxmax() for c in R]; inv = {v: k for k, v in S.items()}
acc = 1.0
for c, nm in zip(R.columns, lead):
    acc *= 1 + R.loc[nm, c] / 100
print(f'구간 1등을 차례로(사후): {(acc - 1) * 100:+.1f}%  /  S&P {(P["^GSPC"].asof(cuts[-1]) / P["^GSPC"].loc[g] - 1) * 100:+.1f}%  나스닥100 {(P["^NDX"].asof(cuts[-1]) / P["^NDX"].loc[g] - 1) * 100:+.1f}%  코스피 {(P["^KS11"].asof(cuts[-1]) / P["^KS11"].loc[g] - 1) * 100:+.1f}%')
