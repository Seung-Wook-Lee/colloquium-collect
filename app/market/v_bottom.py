"""V자 바닥 그래프: 2018-12, 2020-03, 2025-04 (S&P 바닥일 = 100, 앞뒤 40거래일) 코스피·나스닥100·XLK·금·장기채 (11/23 의장)."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import pandas as pd
import yfinance as yf

OUT = Path('/mnt/project-files/유니버스/start/covid_rotation/')
fm.fontManager.addfont('/root/.fonts/NanumGothic.ttf'); plt.rcParams['font.family'] = 'NanumGothic'; plt.rcParams['axes.unicode_minus'] = False
A = {'^KS11': ('코스피', '#00897b', 2.6), '^NDX': ('나스닥100', '#7b1fa2', 2.6), 'XLK': ('XLK 기술', '#1f77b4', 2.6),
     'GC=F': ('금', '#d4a017', 1.4), 'ZB=F': ('장기채', '#1f5fa8', 1.4), '^GSPC': ('S&P500', '#222', 1.2)}
P = yf.download(list(A), start='2018-06-01', auto_adjust=True, progress=False)['Close'].ffill()
B = [('2018-12-24', '2018 4분기'), ('2020-03-23', '2020 코로나'), ('2025-04-08', '2025 관세')]
fig, axs = plt.subplots(1, 3, figsize=(17, 6), sharey=True)
rows = []
for ax, (d, ttl) in zip(axs, B):
    d = pd.Timestamp(d); i = P.index.get_indexer([d], method='nearest')[0]; W = P.iloc[max(0, i - 40): i + 41]
    for t, (nm, col, lw) in A.items():
        y = W[t] / W[t].asof(d) * 100
        ax.plot(y.index, y, color=col, lw=lw, ls='--' if t in ('GC=F', 'ZB=F') else '-', label=nm)
        lo = W[t].iloc[:60].idxmin()
        if t in ('^KS11', '^NDX', 'XLK', 'GC=F', 'ZB=F'):
            ax.scatter([lo], [y[lo]], color=col, s=35, zorder=5)
        rows.append({'구간': ttl, '대상': nm, '저점일': lo.date(), 'S&P 바닥과 차이(거래일)': P.index.get_loc(lo) - i,
                     '저점까지 낙폭(40일 전 대비 %)': round((W[t][lo] / W[t].iloc[0] - 1) * 100, 1),
                     '저점 뒤 20거래일(%)': round((W[t].iloc[W.index.get_loc(lo):].iloc[:21].iloc[-1] / W[t][lo] - 1) * 100, 1),
                     '저점 뒤 40거래일(%)': round((W[t].iloc[W.index.get_loc(lo):].iloc[:41].iloc[-1] / W[t][lo] - 1) * 100, 1)})
    ax.axvline(d, color='#222', lw=1); ax.axhline(100, color='#999', lw=0.6); ax.grid(alpha=0.25)
    ax.set_title(f'{ttl}: S&P 바닥 {d:%Y-%m-%d} = 100', loc='left', fontsize=12)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%m/%d'))
axs[0].legend(loc='upper left', fontsize=9)
fig.text(0.01, -0.01, '점 = 각자 저점일. 굵은 선 = 코스피·나스닥100·XLK, 점선 = 금·장기채(선물)', fontsize=9)
fig.tight_layout(); fig.savefig(OUT / 'V자바닥_코스피_나스닥_XLK.png', dpi=160, bbox_inches='tight')
R = pd.DataFrame(rows); R.to_csv(OUT / 'V자바닥_표.csv', index=False, encoding='utf-8-sig'); print(R.to_string(index=False))
