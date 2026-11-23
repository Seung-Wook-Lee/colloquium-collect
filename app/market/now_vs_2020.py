"""지금(2026-10 고점 이후) vs 2020 코로나: 금 바닥일 = 100으로 맞춰 자산별 흐름 비교 (11/23 의장 "뭐부터 오르고 뭐부터 사야 할까, 그래프와 함께")."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import pandas as pd
import yfinance as yf

OUT = Path('/mnt/project-files/유니버스/start/covid_rotation/')
fm.fontManager.addfont('/root/.fonts/NanumGothic.ttf'); plt.rcParams['font.family'] = 'NanumGothic'; plt.rcParams['axes.unicode_minus'] = False
A = {'GDX': ('금광주', '#8d6e00'), 'GLD': ('금', '#d4a017'), 'TLT': ('미국 장기채', '#1f5fa8'), '^NDX': ('나스닥100', '#7b1fa2'),
     'ARKK': ('혁신 성장주', '#e91e63'), '^KQ11': ('코스닥', '#00897b'), 'SOXX': ('반도체', '#ef6c00'), '^GSPC': ('S&P500', '#222')}
old = yf.download(list(A), start='2020-02-10', end='2020-05-01', auto_adjust=True, progress=False)['Close']
new = yf.download(list(A), start='2026-09-15', auto_adjust=True, progress=False)['Close']
g0, g1 = pd.Timestamp('2020-03-19'), new['GLD'].dropna()['2026-10-06':].idxmin()
fig, ax = plt.subplots(1, 2, figsize=(15, 6.5), sharey=True)
for a, P, g, ttl in ((ax[0], old, g0, '2020 코로나: 금 바닥 3/19 = 100'), (ax[1], new, g1, f'지금: 금 바닥 {g1:%m/%d} = 100')):
    for t, (nm, col) in A.items():
        c = P[t].dropna(); y = c / c.asof(g) * 100
        a.plot(y.index, y, color=col, lw=2.4 if t in ('GLD', '^GSPC') else 1.4, label=nm)
        a.annotate(nm, (y.index[-1], y.iloc[-1]), xytext=(3, 0), textcoords='offset points', fontsize=8, color=col)
    a.axvline(g, color='#d4a017', ls='--', lw=1); a.axhline(100, color='#999', lw=0.6); a.grid(alpha=0.25)
    a.set_title(ttl, loc='left', fontsize=12); a.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%m/%d'))
ax[0].axvline(pd.Timestamp('2020-03-23'), color='#222', lw=1); ax[0].text(pd.Timestamp('2020-03-23'), 152, ' S&P 바닥 3/23', fontsize=9)
ax[0].axvline(pd.Timestamp('2020-03-16'), color='#c8372d', lw=1); ax[0].text(pd.Timestamp('2020-03-16'), 158, '연준 긴급 인하 ', fontsize=9, color='#c8372d', ha='right')
ax[0].legend(loc='upper left', fontsize=9); ax[0].set_ylim(55, 165)
fig.tight_layout(); fig.savefig(OUT / '지금_vs_2020_금바닥기준.png', dpi=160, bbox_inches='tight')
print('gold low now', g1.date())
