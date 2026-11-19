"""종목 4·8주 전망 점수 (11/20 의장: "블록33으로 돌려 각 종목 점수, 4주·8주 뒤 상승률 전망 높은 순").

블록점수이력(매주 미국 개별주 블록 점수, 가격으로 만들 수 있는 블록만) + 1년 나스닥 베타 + 나스닥100 바닥 근접도(시장 상태)로
뒤 4주·8주 절대 수익률을 예측한다.
- 모형: 그래디언트 부스팅 회귀(sklearn HistGradientBoosting), 해마다 걸어가며 학습(그해 앞 자료만, 정답 겹침 8주 비움).
- 검정: 주마다 예측 순위와 실제 순위의 상관(IC, Spearman) 평균·t값, 예측 5분위별 실제 절대 수익률·승률.
- 오늘: 이력 마지막 주 블록 점수로 4·8주 예상 수익률과 순위.
- 한계: 실적·수급·밸류 블록(B15·B23~B26 등)은 과거 값이 없어 못 씀. 오늘 종목으로 과거를 돌려 생존 편향.
출력: 전망_검정.csv, 전망_5분위.csv, 전망_오늘.csv, 전망_블록중요도.csv
"""
import sys

import numpy as np
import pandas as pd

FEAT = ['B11', 'B12', 'B13', 'B16', 'B17', 'B28', 'B29', 'B30', 'B31', 'B32', 'B33', '베타', '나스닥점수']
H_WEEKS = (4, 8)   # 명령줄 4번째부터 바꿀 수 있음(예: 13 26)


def prices(tickers, start='2016-06-01', idx='^NDX'):
    import yfinance as yf
    P = yf.download(sorted(set(tickers) | {idx}), start=start, auto_adjust=True, progress=False)['Close']
    R = P.pct_change(fill_method=None)
    m = R[idx]
    beta = R.drop(columns=idx).rolling(252, min_periods=120).cov(m).div(m.rolling(252, min_periods=120).var(), axis=0)
    W = P.resample('W-FRI').last()
    fwd = {h: (W.shift(-h) / W - 1) * 100 for h in H_WEEKS}
    return beta.resample('W-FRI').last(), fwd, W


def run(W_out, H, raw, start_year=2021):   # 나스닥 점수(걸어가며 예측)가 2020년부터 있어 학습은 2020~, 검정은 2021~
    from scipy.stats import spearmanr
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.inspection import permutation_importance
    H = H[(H['시장'] == '미국') & (H['구분'] == '개별주')].copy()
    H['날짜'] = pd.to_datetime(H['날짜']).dt.to_period('W-FRI').dt.to_timestamp('W-FRI')
    H = H.drop_duplicates(['날짜', 'ticker'], keep='last')
    beta, fwd, PX = prices(H['ticker'].dropna().unique())
    look = lambda T, d, t: T.at[d, t] if (d in T.index and t in T.columns) else np.nan
    H['베타'] = [look(beta, d, t) for d, t in zip(H['날짜'], H['ticker'])]
    raw = raw.copy(); raw.index = pd.to_datetime(raw.index).to_period('W-FRI').to_timestamp('W-FRI')
    H['나스닥점수'] = H['날짜'].map(raw[~raw.index.duplicated(keep='last')])
    for h in H_WEEKS:
        H[f'뒤{h}주'] = [look(fwd[h], d, t) for d, t in zip(H['날짜'], H['ticker'])]
    last = H['날짜'].max()
    tests, quint, today, imp = [], [], [], []
    for h in H_WEEKS:
        y = f'뒤{h}주'
        pred = pd.Series(np.nan, index=H.index)
        for yr in range(start_year, last.year + 1):
            cut = pd.Timestamp(f'{yr}-01-01')
            tr = H[(H['날짜'] < cut - pd.Timedelta(weeks=h)) & H[y].notna()]
            te = H[(H['날짜'] >= cut) & (H['날짜'] < pd.Timestamp(f'{yr + 1}-01-01'))]
            if (tr['나스닥점수'].notna()).sum() < 2000 or te.empty:
                continue
            tr = tr[tr['나스닥점수'].notna()]
            m = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_depth=3, min_samples_leaf=200, random_state=0)
            m.fit(tr[FEAT], tr[y].clip(-60, 120))
            pred[te.index] = m.predict(te[FEAT])
        H[f'예측{h}주'] = pred
        ev = H[H[f'예측{h}주'].notna() & H[y].notna()]
        ic = ev.groupby('날짜').apply(lambda g: spearmanr(g[f'예측{h}주'], g[y]).statistic if len(g) > 10 else np.nan).dropna()
        tests.append({'기간': f'{h}주', '검정 주수': len(ic), 'IC 평균': round(ic.mean(), 3), 'IC t값': round(ic.mean() / ic.std() * np.sqrt(len(ic) / h), 2),
                      'IC>0 주 비율%': round((ic > 0).mean() * 100, 1), '검정 기간': f'{ev["날짜"].min().date()}~{ev["날짜"].max().date()}'})
        ev = ev.assign(분위=ev.groupby('날짜')[f'예측{h}주'].transform(lambda s: pd.qcut(s.rank(method='first'), 5, labels=[1, 2, 3, 4, 5])))
        q = ev.groupby('분위', observed=True)[y].agg(['count', 'mean', 'median', lambda v: (v > 0).mean() * 100]).round(1)
        q.columns = ['건수', '실제 평균%', '실제 중앙%', '승률%']; q.insert(0, '기간', f'{h}주')
        quint.append(q.reset_index())
        # 오늘: 모든 과거로 학습
        tr = H[(H['날짜'] < last - pd.Timedelta(weeks=h)) & H[y].notna() & H['나스닥점수'].notna()]
        m = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_depth=3, min_samples_leaf=200, random_state=0)
        m.fit(tr[FEAT], tr[y].clip(-60, 120))
        T = H[H['날짜'] == last].copy()
        T[f'전망{h}주%'] = m.predict(T[FEAT]).round(1)
        today.append(T.set_index('ticker')[[f'전망{h}주%']])
        smp = tr.sample(min(20000, len(tr)), random_state=0)
        pi = permutation_importance(m, smp[FEAT], smp[y].clip(-60, 120), n_repeats=3, random_state=0)
        imp.append(pd.Series(pi.importances_mean, index=FEAT, name=f'{h}주'))
    T = H[H['날짜'] == last].set_index('ticker')[['번호', '종목', '층', '베타', '나스닥점수'] + FEAT[:11]]
    for x in today: T = T.join(x)
    T['전망순위'] = T[[f'전망{h}주%' for h in H_WEEKS]].rank(ascending=False).mean(axis=1).rank().astype(int)
    T = T.sort_values('전망순위').reset_index()
    T['베타'] = T['베타'].round(2)
    TS = pd.DataFrame(tests); Q = pd.concat(quint); I = pd.concat(imp, axis=1).round(3).sort_values(f'{H_WEEKS[-1]}주', ascending=False).reset_index().rename(columns={'index': '블록'})
    tag = '_'.join(str(h) for h in H_WEEKS)
    for k, v in (('전망_검정', TS), ('전망_5분위', Q), ('전망_오늘', T), ('전망_블록중요도', I)):
        v.to_csv(f'{W_out}/{k}_{tag}주.csv', index=False, encoding='utf-8-sig')
    return TS, Q, T, I


if __name__ == '__main__':
    # python forecast.py <블록점수이력.csv> <바닥근접도_이력_나스닥100.csv> <출력폴더>
    hist, rawf, W = sys.argv[1:4]
    if len(sys.argv) > 4:
        H_WEEKS = tuple(int(x) for x in sys.argv[4:])
    TS, Q, T, I = run(W, pd.read_csv(hist, encoding='utf-8-sig', low_memory=False),
                      pd.read_csv(rawf, encoding='utf-8-sig', index_col=0)['원점수'])
    pd.set_option('display.width', 250)
    print(TS.to_string()); print(Q.to_string()); print(I.to_string())
    print(T[['ticker', '종목', '층', '베타'] + [f'전망{h}주%' for h in H_WEEKS] + ['전망순위']].head(20).to_string())
