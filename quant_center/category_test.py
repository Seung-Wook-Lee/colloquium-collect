"""기업 범주 비교 (11/20 의장: "기업을 범주화하는 인사이트가 가장 중요. 섹터? 층? 가로·세로? 어떤 열을 넣을까").

재무블록_주별.csv.gz(fund_test.py)에 범주 열을 붙이고, 범주마다 두 가지를 잰다.
1) 설명력: 매주 그 범주로 묶었을 때 뒤 12주 수익률 차이를 얼마나 설명하나(조정 R², 무리 수 많을수록 깎음) → 주별 평균.
2) 바닥에서 갈림: 준비(나스닥100 바닥 근접도 ≥ 0.5)+떨어짐(52주 고점 −10%) 주에 무리별 뒤 26주 평균 → 가장 좋은 무리와 나쁜 무리 차이, 설명 비율(eta²).
범주 열:
- 섹터: GICS 11개(S&P500 표) / 층: 콜로키움 S0~S6(유니버스만)
- 숫자 5분위(그 주 단면): 성장(매출 전년비), 수익성(ROE), 자본집약(설비투자÷매출), 빚(차입÷EBITDA), 베타, 크기(시가총액), 밸류(PER)
- 같이 움직이는 무리: 지난 52주 주간 수익률 상관으로 11무리(해마다 그해 앞 자료로만 다시 나눔)
- 겹친 범주: 섹터 × 베타 3분위, 섹터 × 수익성 3분위
출력: 범주_설명력.csv, 범주_바닥갈림.csv, 범주_바닥_무리별.csv
"""
import sys

import numpy as np
import pandas as pd

Q5 = {'성장(매출 전년비)': 'rev_yoy', '수익성(ROE)': 'roe', '자본집약(설비투자÷매출)': 'capex_int', '빚(차입÷EBITDA)': 'debt_ebitda',
      '베타': '베타', '크기(시가총액)': 'mcap', '밸류(PER)': 'per'}


def bucket(X, col, n=5):
    return X.groupby('날짜')[col].transform(lambda s: pd.qcut(s.rank(method='first'), n, labels=False) + 1 if s.notna().sum() >= n * 5 else np.nan)


def corr_clusters(X, k=11):
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform
    P = X.pivot_table(index='날짜', columns='ticker', values='px')
    R = P.pct_change(fill_method=None)
    lab = pd.Series(np.nan, index=X.index)
    for y in sorted(X['날짜'].dt.year.unique()):
        past = R[(R.index < pd.Timestamp(f'{y}-01-01')) & (R.index >= pd.Timestamp(f'{y - 1}-01-01'))]
        past = past.loc[:, past.notna().sum() >= 40]
        if past.shape[1] < k * 3:
            continue
        C = past.corr().fillna(0).values
        D = np.clip(1 - C, 0, 2); np.fill_diagonal(D, 0)
        L = fcluster(linkage(squareform(D, checks=False), 'average'), k, 'maxclust')
        m = dict(zip(past.columns, L))
        sel = X['날짜'].dt.year == y
        lab[sel] = X.loc[sel, 'ticker'].map(m)
    return lab


def adj_r2(g, cat, y):
    g = g[[cat, y]].dropna()
    n, k = len(g), g[cat].nunique()
    if n < 50 or k < 2:
        return np.nan
    m = g.groupby(cat)[y].transform('mean')
    ss_t = ((g[y] - g[y].mean()) ** 2).sum()
    r2 = 1 - ((g[y] - m) ** 2).sum() / ss_t
    return 1 - (1 - r2) * (n - 1) / (n - k)


def run(W, panel_gz, start='2015-01-01'):
    X = pd.read_csv(panel_gz, encoding='utf-8-sig', parse_dates=['날짜'])
    X = X[X['날짜'] >= pd.Timestamp(start) - pd.DateOffset(years=1)]
    cats = {'섹터(GICS 11)': X['섹터'], '층(S0~S6)': X['층']}
    for k, c in Q5.items():
        cats[k] = bucket(X, c)
    cats['같이 움직이는 무리(상관 11)'] = corr_clusters(X)
    b3 = bucket(X, '베타', 3); p3 = bucket(X, 'roe', 3)
    cats['섹터 × 베타3'] = X['섹터'].astype(str) + '|' + b3.astype(str)
    cats['섹터 × 수익성3'] = X['섹터'].astype(str) + '|' + p3.astype(str)
    for k, v in cats.items():
        X[k] = v
    X.loc[b3.isna(), '섹터 × 베타3'] = np.nan; X.loc[p3.isna(), '섹터 × 수익성3'] = np.nan
    X = X[X['날짜'] >= start]
    bot = X[(X['나스닥점수'] >= 0.5) & (X['고점대비'] <= -0.10)]
    rows, brows, grp = [], [], []
    for scope, S, B in (('S&P500+유니버스', X, bot), ('유니버스 미국', X[X['층'].notna()], bot[bot['층'].notna()])):
        for k in cats:
            if scope == 'S&P500+유니버스' and k == '층(S0~S6)':
                continue
            r = S.groupby('날짜').apply(lambda g: adj_r2(g, k, '12주')).dropna()
            rows.append({'대상': scope, '범주': k, '무리 수': S[k].nunique(), '주수': len(r), '설명력_조정R²_평균%': round(r.mean() * 100, 2),
                         '설명력_중앙%': round(r.median() * 100, 2)})
            b = B[[k, '26주', 'ticker']].dropna()
            if b.empty:
                continue
            gm = b.groupby(k)['26주'].agg(['count', 'mean', lambda v: (v > 0).mean() * 100])
            gm = gm[gm['count'] >= 30]
            if len(gm) < 2:
                continue
            ss_t = ((b['26주'] - b['26주'].mean()) ** 2).sum()
            eta = 1 - ((b['26주'] - b.groupby(k)['26주'].transform('mean')) ** 2).sum() / ss_t
            best, worst = gm['mean'].idxmax(), gm['mean'].idxmin()
            brows.append({'대상': scope, '범주': k, '바닥 건수': len(b), '무리 수(30건↑)': len(gm), '설명비율_eta²%': round(eta * 100, 2),
                          '최고 무리': best, '최고_26주%': round(gm.at[best, 'mean'], 1), '최저 무리': worst, '최저_26주%': round(gm.at[worst, 'mean'], 1),
                          '차이%p': round(gm['mean'].max() - gm['mean'].min(), 1)})
            gm = gm.reset_index().rename(columns={k: '무리', 'count': '건수', 'mean': '26주_평균%', '<lambda_0>': '승률%'})
            grp.append(gm.round(1).assign(대상=scope, 범주=k))
    A = pd.DataFrame(rows).sort_values(['대상', '설명력_조정R²_평균%'], ascending=[True, False])
    Bt = pd.DataFrame(brows).sort_values(['대상', '설명비율_eta²%'], ascending=[True, False])
    G = pd.concat(grp, ignore_index=True)[['대상', '범주', '무리', '건수', '26주_평균%', '승률%']]
    for k, v in (('범주_설명력', A), ('범주_바닥갈림', Bt), ('범주_바닥_무리별', G)):
        v.to_csv(f'{W}/{k}.csv', index=False, encoding='utf-8-sig')
    return A, Bt, G


if __name__ == '__main__':
    # python category_test.py <출력폴더> <재무블록_주별.csv.gz>
    pd.set_option('display.width', 250)
    A, B, G = run(*sys.argv[1:3])
    print(A.to_string()); print(B.to_string())
