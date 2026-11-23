"""좋은 주식을 하락장 '직전 시점 자료만으로' 다시 고른 검정 (11/23 의장 "검정해보세요", 생존 편향 없애기).
좋은 주식 = MSCI Quality Index 방식 품질점수 상위 1/3: Z(ROE) − Z(부채/자본) − Z(이익변동성), 각 ±3에서 자름.
  ROE = 최근 4분기 순이익 합 ÷ 자본, 부채/자본 = (단기부채+장기부채) ÷ 자본, 이익변동성 = 최근 20분기 TTM 순이익 전년 대비 증가율의 표준편차.
  재무는 SEC재무_분기.csv(공시일 기준 point-in-time)에서 S&P 고점일 이전에 공시된 것만 쓴다.
대상: 유니버스 미국 개별주(가격10년에 있는 것). 한국은 공시일 기준 재무 이력이 우리 자료에 없어 뺐다.
하락장·낙폭·반등 정의는 good_stock_fall.py와 같다."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ourdata as O
from good_stock_fall import EP, UNI, dbeta, fwd, mk, px, spx, val  # noqa: E402

OUT = Path('/mnt/project-files/유니버스/start/잔차반전/')
SEC = pd.read_csv('/mnt/project-files/퀀트센터/입력/SEC재무/SEC재무_분기.csv', parse_dates=['분기말', '공시일'])
SEC = SEC[SEC['항목'].isin(['순이익', '자본', '단기부채', '장기부채'])]
US = UNI[UNI['시장'] == '미국']


def quality(t, asof):
    x = SEC[(SEC['ticker'] == t) & (SEC['공시일'] <= asof)]
    if x.empty:
        return None
    w = x.sort_values('공시일').drop_duplicates(['항목', '분기말'], keep='first').pivot(index='분기말', columns='항목', values='값').sort_index()
    if '순이익' not in w or '자본' not in w:
        return None
    ni = w['순이익'].dropna()
    if len(ni) < 8:
        return None
    ttm = ni.rolling(4).sum().dropna()
    eq = w['자본'].dropna()
    if eq.empty or eq.iloc[-1] <= 0:
        return None
    debt = sum(w[c].dropna().iloc[-1] for c in ('단기부채', '장기부채') if c in w and w[c].notna().any())
    g = (ttm / ttm.shift(4).abs() - 1).replace([np.inf, -np.inf], np.nan).dropna().iloc[-20:]
    return dict(ROE=ttm.iloc[-1] / eq.iloc[-1], 부채자본=debt / eq.iloc[-1], 이익변동성=g.std() if len(g) >= 4 else np.nan)


def z(s):
    s = s.clip(s.quantile(.02), s.quantile(.98)); return ((s - s.mean()) / s.std()).clip(-3, 3)


rows = []
for e, (pk, bt) in EP.items():
    pk = pd.Timestamp(pk); bt = O.crash_low(spx, pd.Timestamp(bt))[0]
    Q = {}
    for t in US['yfinance 티커']:
        q = quality(t, pk)
        if q:
            Q[t] = q
    Q = pd.DataFrame(Q).T
    Q['이익변동성'] = Q['이익변동성'].fillna(Q['이익변동성'].median())
    Q['품질점수'] = (z(Q['ROE']) - z(Q['부채자본']) - z(Q['이익변동성'])) / 3
    for t, r in Q.iterrows():
        s = px[t]; m = mk['SPY']; a, b = val(s, pk), val(s, bt)
        if not (a > 0 and b > 0) or s.dropna().index[0] > pk - pd.Timedelta(days=365):
            continue
        row = dict(하락장=e, 티커=t, 품질점수=r['품질점수'], 시장대비낙폭=((b / a) - (val(m, bt) / val(m, pk))) * 100, 하방베타=dbeta(s, m, pk))
        for n in (60, 120, 250):
            f = fwd(bt, n)
            row[f'반등{n}'] = ((val(s, f) / b) - (val(m, f) / val(m, bt))) * 100 if f is not None else np.nan
        rows.append(row)
D = pd.DataFrame(rows)
D['좋은주식(직전 품질 상위1/3)'] = D.groupby('하락장')['품질점수'].rank(pct=True) >= 2 / 3
D.to_csv(OUT / '좋은주식_직전품질_종목별.csv', index=False, encoding='utf-8-sig')

res = []
for (e, g), x in D.groupby(['하락장', '좋은주식(직전 품질 상위1/3)']):
    for n in (60, 120, 250):
        y = x[['시장대비낙폭', '하방베타', f'반등{n}']].dropna()
        q = y['시장대비낙폭'].rank(pct=True)
        res.append({'하락장': e, '묶음': '품질 상위1/3' if g else '나머지', '종목수': len(y), '뒤': f'{n}일',
                    '상관(덜 떨어짐↔반등)': round(y['시장대비낙폭'].rank().corr(y[f'반등{n}'].rank()), 2),
                    '덜 떨어진 1/3 반등': round(y[f'반등{n}'][q >= 2 / 3].mean(), 1),
                    '많이 떨어진 1/3 반등': round(y[f'반등{n}'][q <= 1 / 3].mean(), 1),
                    '묶음 평균 반등': round(y[f'반등{n}'].mean(), 1),
                    '상관(하방베타↔반등)': round(y['하방베타'].rank().corr(y[f'반등{n}'].rank()), 2)})
R = pd.DataFrame(res)
R.to_csv(OUT / '좋은주식_직전품질_요약.csv', index=False, encoding='utf-8-sig')
pd.set_option('display.width', 220)
print(R.to_string(index=False))
print('출처: 재무=퀀트센터/입력/SEC재무/SEC재무_분기.csv(공시일 기준) ·', O.source_line('SPY', 'S&P500'), '· 종목=가격10년_종가.csv.gz')
