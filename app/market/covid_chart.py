"""코로나 폭락 2/18~4/30: S&P500·금(GLD)·장기채(TLT) 겹친 그래프 + 사건 표시 (11/23 의장).
연준 날짜는 연준 발표 기록(2020-03-03 긴급 -0.50%p, 2020-03-15 일요일 긴급 -1.00%p·7000억 달러 매입, 2020-03-23 무제한 매입)."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import pandas as pd
import yfinance as yf

OUT = Path('/mnt/project-files/유니버스/start/covid_rotation/')
fm.fontManager.addfont('/root/.fonts/NanumGothic.ttf'); plt.rcParams['font.family'] = 'NanumGothic'; plt.rcParams['axes.unicode_minus'] = False
P = yf.download(['^GSPC', 'GLD', 'TLT', '^IRX'], start='2020-02-10', end='2020-05-01', auto_adjust=True, progress=False)['Close']
base = P.loc['2020-02-19']
N = P[['^GSPC', 'GLD', 'TLT']].div(base[['^GSPC', 'GLD', 'TLT']]) * 100
s, g, t = P['^GSPC'], P['GLD'], P['TLT']
EV = [('2020-02-19', 'S&P 고점', '#333'), ('2020-02-24', 'S&P 첫 폭락(-3.4%)', '#333'),
      ('2020-03-03', '연준 긴급 인하 -0.50%p\n(1.00~1.25%)', '#c8372d'), ('2020-03-09', '금·장기채 고점\n(같이 팔리기 시작)', '#e08a00'),
      ('2020-03-16', '연준 일요일(3/15) 긴급 인하 -1.00%p\n(0~0.25%)+7000억 달러 매입 → 첫 거래일', '#c8372d'),
      ('2020-03-18', '장기채 바닥', '#1f5fa8'), ('2020-03-19', '금 바닥', '#b8860b'),
      ('2020-03-23', 'S&P 바닥 / 연준 무제한 매입', '#c8372d'), ('2020-04-09', '금, 3월 고점 넘음', '#b8860b')]
fig, ax = plt.subplots(figsize=(13, 7))
ax.plot(N.index, N['^GSPC'], color='#222', lw=2.2, label='S&P500')
ax.plot(N.index, N['GLD'], color='#d4a017', lw=2, label='금(GLD)')
ax.plot(N.index, N['TLT'], color='#1f5fa8', lw=2, label='미국 장기채(TLT)')
ymin, ymax = 60, 128
for i, (d, txt, col) in enumerate(EV):
    d = pd.Timestamp(d)
    ax.axvline(d, color=col, lw=1.1, ls='--' if col != '#c8372d' else '-', alpha=0.8)
    ax.text(d, ymax - 2.2 - (i % 4) * 5.2, txt, fontsize=8.3, color=col, ha='left', va='top', bbox=dict(fc='white', ec='none', alpha=0.85, pad=1))
for nm, col in (('^GSPC', '#222'), ('GLD', '#d4a017'), ('TLT', '#1f5fa8')):
    lo = N[nm]['2020-03-01':'2020-04-15'].idxmin()
    ax.scatter([lo], [N[nm][lo]], color=col, s=40, zorder=5); ax.annotate(f'{N[nm][lo]:.1f}', (lo, N[nm][lo]), textcoords='offset points', xytext=(4, -12), fontsize=8.5, color=col)
ax.set_ylim(ymin, ymax); ax.axhline(100, color='#999', lw=0.7)
ax.set_title('코로나 폭락 2020-02~04: S&P500·금·장기채 (2/19 = 100) 와 연준 긴급 조치', fontsize=13, loc='left', fontweight='bold')
ax.legend(loc='lower left', fontsize=10); ax.grid(alpha=0.25)
ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%m/%d')); ax.xaxis.set_major_locator(matplotlib.dates.WeekdayLocator(byweekday=0))
fig.savefig(OUT / '코로나_SP_금_장기채_연준.png', dpi=160, bbox_inches='tight')
ev = pd.DataFrame([(d, x.replace('\n', ' '), round(s.asof(pd.Timestamp(d)), 1), round(g.asof(pd.Timestamp(d)), 2), round(t.asof(pd.Timestamp(d)), 2), round(P['^IRX'].asof(pd.Timestamp(d)), 2)) for d, x, _ in EV],
                  columns=['날짜', '사건', 'S&P500', 'GLD', 'TLT', '미국 3개월 국채 금리(%)'])
ev.to_csv(OUT / '코로나_사건기록.csv', index=False, encoding='utf-8-sig')
print(ev.to_string(index=False))
