"""강제 매도(신용 융자) 뒤 반등 검정 — 한국 (11/23 의장 "해봐", Bian·He·Shue·Zhou 'Leverage-Induced Fire Sales' 방식을 우리 자료로).
자료: 신용잔고율_표.csv.gz(한투 FHPST04760000, 종목별 신용 융자 잔고율 %, 2016-11~), 종목 가격 = 가격10년, 시장 = 코스피. 우리 자료(ourdata)만.
하락장 = good_stock_fall.py와 같은 4번(S&P 고점일 → S&P 종가 바닥 앞뒤 15거래일 안 코스피 종가 저점일).
① 고점일 잔고율(빚이 많이 쌓인 종목) 상위 1/3 vs 하위 1/3
② 고점→저점 잔고율 감소(빚을 많이 갚은/털린 종목 = 강제 매도) 상위 1/3 vs 하위 1/3
결과: 시장 대비 낙폭, 저점 뒤 60·120·250거래일 시장 대비 반등."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ourdata as O
from good_stock_fall import EP, val  # noqa: E402

OUT = Path('/mnt/project-files/유니버스/start/잔차반전/')
CR = pd.read_csv('/mnt/project-files/유니버스/코드/신용잔고율_표.csv.gz', index_col=0, parse_dates=True)
UNI = pd.read_csv('/mnt/project-files/유니버스/콜로키움100_유니버스_20261121.csv', dtype={'코드': str})
UNI = UNI[(UNI['시장'] == '한국') & (UNI['구분'] == '개별주')]
code2t = {str(c).zfill(6): t for c, t in zip(UNI['코드'], UNI['yfinance 티커'])}
px = O._px10(); ks = O.get('코스피')['코스피'].dropna(); spx = O.get('S&P500')['S&P500'].dropna()
kd = ks.index


def fwd(d, n):
    j = kd.searchsorted(d) + n
    return kd[j] if j < len(kd) else None


rows = []
for e, (pk, bt) in EP.items():
    pk = pd.Timestamp(pk); bt = O.crash_low(ks, O.crash_low(spx, pd.Timestamp(bt))[0])[0]
    for c in CR.columns:
        t = code2t.get(str(c).zfill(6))
        if t not in px.columns:
            continue
        s = px[t]; a, b = val(s, pk), val(s, bt)
        r0, r1 = val(CR[c], pk), val(CR[c], bt)
        if not (a > 0 and b > 0) or np.isnan(r0):
            continue
        row = dict(하락장=e, 코드=c, 티커=t, 고점잔고율=r0, 잔고율감소=r0 - r1, 시장대비낙폭=((b / a) - (val(ks, bt) / val(ks, pk))) * 100)
        for n in (60, 120, 250):
            f = fwd(bt, n)
            row[f'반등{n}'] = ((val(s, f) / b) - (val(ks, f) / val(ks, bt))) * 100 if f is not None else np.nan
        rows.append(row)
D = pd.DataFrame(rows); D.to_csv(OUT / '신용잔고_하락장_종목별.csv', index=False, encoding='utf-8-sig')
res = []
for e, x in D.groupby('하락장'):
    for key, nm in (('고점잔고율', '① 고점 잔고율'), ('잔고율감소', '② 하락 중 잔고율 감소')):
        q = x[key].rank(pct=True); hi, lo = x[q >= 2 / 3], x[q <= 1 / 3]
        r = {'하락장': e, '기준': nm, '종목수': len(x), '상위1/3 시장대비낙폭': round(hi['시장대비낙폭'].mean(), 1), '하위1/3 시장대비낙폭': round(lo['시장대비낙폭'].mean(), 1)}
        for n in (60, 120, 250):
            r[f'{n}일 반등 상위1/3'] = round(hi[f'반등{n}'].mean(), 1); r[f'{n}일 반등 하위1/3'] = round(lo[f'반등{n}'].mean(), 1)
            r[f'{n}일 상관'] = round(x[key].rank().corr(x[f'반등{n}'].rank()), 2)
        res.append(r)
R = pd.DataFrame(res); R.to_csv(OUT / '신용잔고_하락장_요약.csv', index=False, encoding='utf-8-sig')
pd.set_option('display.width', 250); print(R.to_string(index=False))
last = CR.index[-1]; pk = spx['2026-09-01':].idxmax()
print(f'\n이번: 잔고율 {last:%Y-%m-%d} 평균 {CR.loc[last].mean():.2f}%, S&P 고점 {pk:%m/%d} 때 {val(CR.mean(axis=1), pk):.2f}%')
print('출처: 신용잔고율_표.csv.gz(한투) ·', O.source_line('코스피', 'S&P500'), '· 종목=가격10년_종가.csv.gz')
