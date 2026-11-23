"""위기 때 금·장기채가 주가보다 먼저 바닥을 찍나 — 선행성 정확도 (11/23 의장).
하락 구간 = S&P500 고점 대비 −15% 이상 빠진 구간(2000~). 구간마다 S&P 바닥일, 그 구간(고점~S&P 바닥+20거래일) 안 금·장기채 저점일, 차이(거래일).
신호 검정: '주가가 고점 −10% 아래인데 금(장기채)이 구간 저점에서 +5% 오른 첫날' → 그날부터 S&P 바닥까지 며칠, 그날 산 S&P 63일 뒤 수익 vs 같은 낙폭 아무 날."""
from pathlib import Path
import pandas as pd
import yfinance as yf

OUT = Path('/mnt/project-files/유니버스/start/covid_rotation/')
P = yf.download(['^GSPC', 'GC=F', 'ZB=F', '^NDX', '^KS11'], start='1999-01-01', auto_adjust=True, progress=False)['Close'].ffill()
s = P['^GSPC'].dropna()
dd = s / s.cummax() - 1
eps, i = [], 0
idx = s.index
while i < len(s):
    if dd.iloc[i] <= -0.15:
        pk = s[:idx[i]].idxmax()
        j = i
        while j < len(s) and dd.iloc[j] < 0:
            j += 1
        seg = s[pk:idx[min(j, len(s) - 1)]]
        eps.append((pk, seg.idxmin(), seg.min() / s[pk] - 1)); i = j
    i += 1
rows, sig = [], []
for pk, bt, d in eps:
    end = idx[min(idx.get_loc(bt) + 20, len(idx) - 1)]
    r = {'S&P 고점': pk.date(), 'S&P 바닥': bt.date(), 'S&P 낙폭(%)': round(d * 100, 1)}
    for t, nm in (('GC=F', '금'), ('ZB=F', '장기채')):
        c = P[t][pk:end].dropna(); lo = c.idxmin()
        lag = idx.get_loc(bt) - idx.get_indexer([lo], method='nearest')[0]
        r[f'{nm} 저점'] = lo.date(); r[f'{nm} 낙폭(%)'] = round((c.min() / P[t].asof(pk) - 1) * 100, 1)
        r[f'{nm}가 먼저(거래일)'] = lag
        r[f'{nm} 저점~S&P 바닥 사이 {nm}(%)'] = round((P[t].asof(bt) / c.min() - 1) * 100, 1)
        # 신호: 주가 −10% 아래 & 금(장기채) 구간 저점 대비 +5% 첫날
        cc = P[t][pk:bt]; mn = cc.cummin(); hit = cc[(cc / mn - 1 >= 0.05) & (dd.reindex(cc.index) <= -0.10)]
        if len(hit):
            h = hit.index[0]; f = s.asof(h + pd.Timedelta(days=91)) / s.asof(h) - 1
            sig.append({'자산': nm, 'S&P 바닥': bt.date(), '신호일': h.date(), '신호 뒤 S&P 바닥까지(거래일)': idx.get_loc(bt) - idx.get_indexer([h], method='nearest')[0],
                        '신호일 뒤 S&P 추가 하락(%)': round((s[bt] / s.asof(h) - 1) * 100, 1), '신호일 산 S&P 3개월 뒤(%)': round(f * 100, 1)})
    rows.append(r)
E1 = pd.DataFrame(rows); E2 = pd.DataFrame(sig)
E1.to_csv(OUT / '선행성_구간별.csv', index=False, encoding='utf-8-sig'); E2.to_csv(OUT / '선행성_신호.csv', index=False, encoding='utf-8-sig')
pd.set_option('display.width', 250)
print(E1.to_string(index=False)); print(E2.to_string(index=False))
for nm in ('금', '장기채'):
    x = E1[f'{nm}가 먼저(거래일)']
    print(nm, '먼저 바닥 비율', f'{(x > 0).mean() * 100:.0f}% ({(x > 0).sum()}/{len(x)})', '중앙값', x.median())
base = s.pct_change(63).shift(-63)[dd <= -0.10].dropna()
print('같은 낙폭(−10% 아래) 아무 날 S&P 63일 뒤', f'{base.mean() * 100:+.1f}%', f'{(base > 0).mean() * 100:.0f}%')
