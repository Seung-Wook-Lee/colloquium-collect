"""재무 블록 과거 검정 (11/20 의장: "SEC 10년치 재무로, 최대한 Quant로").

SEC재무_분기.csv(sec_fund.py, 공시일 기준)로 매주, 그 주에 알 수 있던 재무만으로 블록33의 기업 블록을 다시 계산하고
뒤 12·26주 절대 수익률과 맞춰 본다.
- B23 이익 거르기: 분기 영업이익 전년비 증가 또는 매출 전년비 증가(추정치 상향 구제는 추정치 이력이 없어 뺌).
- B25 돈 잘 버나: F-Score ≥ 7, FCF(4분기) > 0, ROE ≥ 10% → 예 비율.
- B26 빚: Altman Z ≥ 1.8, 총차입 ÷ EBITDA ≤ 3 → 예 비율.
- 우량 = B23 통과 + (B25·B26 평균) ≥ 0.5 (blocks.yaml 원칙과 같은 문턱).
- B15 싼가: PER 섹터 안 하위 절반, PBR 섹터 안 하위 절반, FCF 수익률 ≥ 5%, 자기 3년 PER 하위 절반 → 예 비율
  (선행 PER 두 공식은 추정치 이력이 없어 뺌).
- B24 이익 전망(추정치 상향)은 무료 과거 자료가 없어 시험 못 함.
- 떨어짐 = 52주 고점 대비 −10% 이하(B29), 준비 = 나스닥100 바닥 근접도 원점수 ≥ 0.5, 베타 = 1년 나스닥100 대비.
- 대상 = S&P500 오늘 구성 + 유니버스 미국 개별주 → 생존 편향(망해서 빠진 회사 없음, 절대 수익률 부풀림).
출력: 재무블록_검정(묶음별), 재무블록_IC(블록·지표별 순위 상관), 재무블록_연도별, 재무블록_주별(패널, gz)
"""
import sys

import numpy as np
import pandas as pd


def prices(tickers, start='2012-01-01', idx='^NDX'):
    import yfinance as yf
    P = yf.download(sorted(set(tickers) | {idx}), start=start, auto_adjust=True, progress=False, threads=True)['Close']
    P = P.dropna(axis=1, how='all')
    R = P.pct_change(fill_method=None)
    m = R[idx]
    beta = R.drop(columns=idx).rolling(252, min_periods=120).cov(m).div(m.rolling(252, min_periods=120).var(), axis=0)
    hi = P / P.rolling(252, min_periods=120).max() - 1
    W = P.resample('W-FRI').last()
    return W, beta.resample('W-FRI').last(), hi.resample('W-FRI').last()


def quarterly(D):
    """티커·분기 표: 흐름 4분기 합(TTM), 전년 같은 분기 비교, 잔액. 이용 가능일 = 그 분기 항목들 공시일 중 가장 늦은 날."""
    D = D.copy()
    D['분기말'] = pd.to_datetime(D['분기말']); D['공시일'] = pd.to_datetime(D['공시일'])
    sh = D[D['항목'] == '주식수'][['ticker', '공시일', '값']].rename(columns={'값': '주식수'})
    D = D[D['항목'] != '주식수']
    D['분기'] = D['분기말'].dt.to_period('Q')
    V = D.pivot_table(index=['ticker', '분기'], columns='항목', values='값', aggfunc='last')
    A = D.groupby(['ticker', '분기'])['공시일'].max().rename('이용일')
    Q = V.join(A).reset_index().sort_values(['ticker', '분기'])
    out = []
    for t, g in Q.groupby('ticker'):
        g = g.set_index('분기').reindex(pd.period_range(g['분기'].min(), g['분기'].max(), freq='Q'))
        g['ticker'] = t
        ttm = lambda c: g[c].rolling(4, min_periods=4).sum() if c in g else np.nan
        col = lambda c: g[c] if c in g else pd.Series(np.nan, index=g.index)
        f = pd.DataFrame(index=g.index)
        f['ticker'] = t; f['이용일'] = g['이용일']
        rev, ni = col('매출'), col('순이익')
        op = col('영업이익').combine_first(col('세전이익') + col('이자비용').fillna(0))   # 영업이익을 따로 안 내는 회사(머크 등)는 세전이익+이자비용
        g['영업이익'] = op
        f['rev_yoy'] = rev / rev.shift(4) - 1
        f['op_yoy'] = np.where(op.shift(4).abs() > 0, (op - op.shift(4)) / op.shift(4).abs(), np.nan)
        opm = op / rev
        f['opm_yoy'] = opm - opm.shift(4)
        f['earn_ok'] = ((f['op_yoy'] > 0) | (f['rev_yoy'] > 0)).astype(float).where(f['op_yoy'].notna() | f['rev_yoy'].notna())
        f['rev_ttm'], f['op_ttm'], f['ni_ttm'] = ttm('매출'), ttm('영업이익'), ttm('순이익')
        f['ocf_ttm'], f['capex_ttm'], f['dna_ttm'] = ttm('영업현금흐름'), ttm('설비투자'), ttm('감가상각')
        f['gp_ttm'] = ttm('매출총이익')
        f['fcf'] = f['ocf_ttm'] - f['capex_ttm'].fillna(0)
        eq, ta = col('자본'), col('자산')
        f['equity'], f['assets'] = eq, ta
        f['roe'] = f['ni_ttm'] / ((eq + eq.shift(4)) / 2).where(lambda s: s > 0) * 100
        debt = pd.concat([col('장기부채'), col('단기부채')], axis=1)
        f['debt'] = debt.sum(axis=1, min_count=1)
        f['ebitda'] = f['op_ttm'] + f['dna_ttm'].fillna(0)
        f['debt_ebitda'] = np.where(f['ebitda'] > 0, f['debt'].fillna(0) / f['ebitda'], np.where(f['ebitda'].notna(), 99, np.nan))
        f['liab'] = col('부채').combine_first(ta - eq)
        f['wc'] = col('유동자산') - col('유동부채')
        f['re'] = col('이익잉여금')
        f['capex_int'] = f['capex_ttm'] / f['rev_ttm']
        # Piotroski F-Score (9개, 4분기 전과 비교)
        roa = f['ni_ttm'] / ta
        cr = col('유동자산') / col('유동부채')
        lev = col('장기부채') / ta
        gm = f['gp_ttm'] / f['rev_ttm']
        at = f['rev_ttm'] / ta
        comp = pd.DataFrame({
            'roa': roa > 0, 'cfo': f['ocf_ttm'] > 0, 'droa': roa > roa.shift(4), 'accr': f['ocf_ttm'] > f['ni_ttm'],
            'dlev': lev < lev.shift(4), 'dcr': cr > cr.shift(4), 'dgm': gm > gm.shift(4), 'dat': at > at.shift(4)})
        have = pd.DataFrame({'roa': roa, 'cfo': f['ocf_ttm'], 'droa': roa.shift(4), 'accr': f['ni_ttm'],
                             'dlev': lev.shift(4), 'dcr': cr.shift(4), 'dgm': gm.shift(4), 'dat': at.shift(4)}).notna()
        n = have.sum(axis=1)
        f['fscore_8'] = (comp & have).sum(axis=1).where(n >= 6)
        f['fscore_n'] = n
        out.append(f.reset_index().rename(columns={'index': '분기'}))
    Q = pd.concat(out, ignore_index=True)
    return Q[Q['이용일'].notna()], sh


def panel(Q, sh, W, beta, hi, sector, layer, raw):
    """주별 패널: 그 주까지 공시된 마지막 분기 값."""
    wk = W.stack().rename('px').reset_index()
    wk.columns = ['날짜', 'ticker', 'px']
    wk = wk.sort_values('날짜')
    Q = Q.sort_values('이용일')
    wk['날짜'] = wk['날짜'].astype('datetime64[ns]'); Q = Q.assign(이용일=Q['이용일'].astype('datetime64[ns]'))
    sh = sh.assign(공시일=sh['공시일'].astype('datetime64[ns]'))
    X = pd.merge_asof(wk, Q.drop(columns='분기'), left_on='날짜', right_on='이용일', by='ticker', direction='backward', tolerance=pd.Timedelta(days=200))
    sh = sh.sort_values('공시일').drop_duplicates(['ticker', '공시일'], keep='last')
    X = pd.merge_asof(X.sort_values('날짜'), sh, left_on='날짜', right_on='공시일', by='ticker', direction='backward', tolerance=pd.Timedelta(days=200))
    # 주식 분할 뒤 주식수 공시가 늦으면 시가총액이 틀어지므로, 시가총액 = 종가 × 주식수 (공시일 이후 분할은 가격이 보정돼 대체로 맞음)
    X['mcap'] = X['px'] * X['주식수']
    look = lambda T, d, t: T.at[d, t] if (d in T.index and t in T.columns) else np.nan
    X['베타'] = [look(beta, d, t) for d, t in zip(X['날짜'], X['ticker'])]
    X['고점대비'] = [look(hi, d, t) for d, t in zip(X['날짜'], X['ticker'])]
    for h in (12, 26):
        f = (W.shift(-h) / W - 1) * 100
        X[f'{h}주'] = [look(f, d, t) for d, t in zip(X['날짜'], X['ticker'])]
    X['섹터'] = X['ticker'].map(sector).fillna('S&P500 밖')
    X['층'] = X['ticker'].map(layer)
    raw = raw.copy(); raw.index = pd.to_datetime(raw.index).to_period('W-FRI').to_timestamp('W-FRI')
    X['나스닥점수'] = X['날짜'].map(raw[~raw.index.duplicated(keep='last')])
    # 밸류
    X['per'] = np.where(X['ni_ttm'] > 0, X['mcap'] / X['ni_ttm'], np.nan)
    X['pbr'] = np.where(X['equity'] > 0, X['mcap'] / X['equity'], np.nan)
    X['fcf_yield'] = X['fcf'] / X['mcap'] * 100
    X['per_rank'] = X.groupby(['날짜', '섹터'])['per'].rank(pct=True)
    X['pbr_rank'] = X.groupby(['날짜', '섹터'])['pbr'].rank(pct=True)
    X = X.sort_values(['ticker', '날짜'])
    X['per_pct3'] = X.groupby('ticker')['per'].transform(lambda s: s.rolling(156, min_periods=52).rank(pct=True))
    # Altman Z (원래 식: 1.2 WC/TA + 1.4 RE/TA + 3.3 EBIT/TA + 0.6 MVE/TL + 1.0 Sales/TA)
    ta = X['assets']
    X['z'] = (1.2 * X['wc'] / ta + 1.4 * X['re'] / ta + 3.3 * X['op_ttm'] / ta + 0.6 * X['mcap'] / X['liab'] + X['rev_ttm'] / ta)
    yes = lambda c, ok: ok.astype(float).where(X[c].notna())
    X['B23'] = X['earn_ok']
    b25 = pd.concat([yes('fscore_8', X['fscore_8'] >= 6), yes('fcf', X['fcf'] > 0), yes('roe', X['roe'] >= 10)], axis=1)   # F-Score 9개 중 8개만 계산(증자 여부 빠짐) → 7/9 대신 6/8
    X['B25'] = b25.mean(axis=1).where(b25.notna().sum(axis=1) >= 2)
    b26 = pd.concat([yes('z', X['z'] >= 1.8), yes('debt_ebitda', X['debt_ebitda'] <= 3)], axis=1)
    X['B26'] = b26.mean(axis=1).where(b26.notna().sum(axis=1) >= 1)
    b15 = pd.concat([yes('per_rank', X['per_rank'] <= 0.5), yes('pbr_rank', X['pbr_rank'] <= 0.5),
                     yes('fcf_yield', X['fcf_yield'] >= 5), yes('per_pct3', X['per_pct3'] < 0.5)], axis=1)
    X['B15'] = b15.mean(axis=1).where(b15.notna().sum(axis=1) >= 2)
    X['우량'] = ((X['B23'] == 1) & (X[['B25', 'B26']].mean(axis=1) >= 0.5)).astype(float).where(X['B23'].notna() & X['B25'].notna())
    X['떨어짐'] = X['고점대비'] <= -0.10
    X['준비'] = X['나스닥점수'] >= 0.5
    return X


def stats(x):
    r = {'건수': len(x), '주수': x['날짜'].nunique(), '종목수': x['ticker'].nunique()}
    for h in (12, 26):
        v = x[f'{h}주'].dropna()
        r.update({f'{h}주_평균%': round(v.mean(), 1), f'{h}주_중앙%': round(v.median(), 1), f'{h}주_승률%': round((v > 0).mean() * 100, 1)})
    return r


def groups(X, start):
    X = X[(X['날짜'] >= start)]
    q, nq, cheap = X['우량'] == 1, X['우량'] == 0, X['B15'] >= 0.5
    f, rd, hb = X['떨어짐'], X['준비'], X['베타'] >= 1
    G = [('전체 주(기준)', X['날짜'].notna()), ('떨어짐', f), ('떨어짐 + 우량', f & q), ('떨어짐 + 우량 아님', f & nq),
         ('떨어짐 + 우량 + 싼가(B15≥0.5)', f & q & cheap), ('떨어짐 + 우량 + 비쌈', f & q & ~cheap),
         ('떨어짐 + 우량 + 베타≥1', f & q & hb)]
    if rd.any():
        G += [('준비', rd), ('준비 + 떨어짐', rd & f), ('준비 + 떨어짐 + 우량', rd & f & q), ('준비 + 떨어짐 + 우량 아님', rd & f & nq),
              ('준비 + 떨어짐 + 우량 + 싼가', rd & f & q & cheap), ('준비 + 떨어짐 + 우량 + 비쌈', rd & f & q & ~cheap),
              ('준비 + 떨어짐 + 우량 + 베타≥1', rd & f & q & hb), ('준비 + 떨어짐 + 우량 아님 + 베타≥1', rd & f & nq & hb),
              ('준비 + 떨어짐 + 우량 + 싼가 + 베타≥1', rd & f & q & cheap & hb)]
    return pd.DataFrame([{'묶음': k, **stats(X[m.fillna(False)])} for k, m in G])


def ic(X, cols, start, h=26):
    from scipy.stats import spearmanr
    X = X[X['날짜'] >= start]
    rows = []
    for c, sign in cols:
        e = X[X[c].notna() & X[f'{h}주'].notna()]
        s = e.groupby('날짜').apply(lambda g: spearmanr(sign * g[c], g[f'{h}주']).statistic if len(g) > 30 and g[c].nunique() > 1 else np.nan).dropna()
        if s.empty:
            continue
        e = e.assign(분위=e.groupby('날짜')[c].transform(lambda v: pd.qcut((sign * v).rank(method='first'), 5, labels=False) if v.notna().sum() >= 25 else np.nan))
        qm = e.groupby('분위')[f'{h}주'].mean()
        rows.append({'블록·지표': c, '방향': '클수록 좋음' if sign > 0 else '작을수록 좋음', '주수': len(s), f'IC_{h}주': round(s.mean(), 3),
                     't값(겹침 보정)': round(s.mean() / s.std() * np.sqrt(len(s) / h), 2), 'IC>0 비율%': round((s > 0).mean() * 100, 1),
                     '상위1/5_평균%': round(qm.get(4, np.nan), 1), '하위1/5_평균%': round(qm.get(0, np.nan), 1)})
    return pd.DataFrame(rows)


def yearly(X, start):
    X = X[(X['날짜'] >= start) & X['떨어짐']]
    rows = []
    for y, g in X.groupby(X['날짜'].dt.year):
        a, b = g[g['우량'] == 1]['26주'].dropna(), g[g['우량'] == 0]['26주'].dropna()
        rows.append({'해': y, '떨어짐+우량_26주%': round(a.mean(), 1), '승률%': round((a > 0).mean() * 100, 1), '건수': len(a),
                     '떨어짐+우량아님_26주%': round(b.mean(), 1), '승률%_': round((b > 0).mean() * 100, 1), '건수_': len(b)})
    return pd.DataFrame(rows)


COLS = [('B23', 1), ('B25', 1), ('B26', 1), ('B15', 1), ('우량', 1), ('roe', 1), ('fscore_8', 1), ('z', 1), ('debt_ebitda', -1),
        ('fcf_yield', 1), ('per', -1), ('pbr', -1), ('per_pct3', -1), ('rev_yoy', 1), ('op_yoy', 1), ('opm_yoy', 1), ('capex_int', -1), ('베타', 1)]


def run(W_out, sec_dir, univ_csv, raw_csv, start='2014-01-01'):
    D = pd.read_csv(f'{sec_dir}/SEC재무_분기.csv', encoding='utf-8-sig')
    D['ticker'] = D['ticker'].str.replace('.', '-', regex=False)   # BRK.B → BRK-B (야후 표기)
    sec = pd.read_csv(f'{sec_dir}/SEC_섹터.csv', encoding='utf-8-sig')
    sector = dict(zip(sec['ticker'].str.replace('.', '-', regex=False), sec['섹터']))
    U = pd.read_csv(univ_csv, encoding='utf-8-sig')
    U = U[(U['시장'] == '미국') & (U['구분'] == '개별주')]
    layer = dict(zip(U['yfinance 티커'].astype(str).str.upper(), U['층']))
    raw = pd.read_csv(raw_csv, encoding='utf-8-sig', index_col=0)['원점수']
    Q, sh = quarterly(D)
    import os, pickle
    pk = f'{W_out}/_가격.pkl'
    if os.path.exists(pk):
        W, beta, hi = pickle.load(open(pk, 'rb'))
    else:
        W, beta, hi = prices(Q['ticker'].unique())
        pickle.dump((W, beta, hi), open(pk, 'wb'))
    X = panel(Q, sh, W, beta, hi, sector, layer, raw)
    G = groups(X, start); G.insert(0, '대상', 'S&P500+유니버스')
    Gu = groups(X[X['층'].notna()], start); Gu.insert(0, '대상', '유니버스 미국')
    G = pd.concat([G, Gu], ignore_index=True)
    G['시험 못 한 것'] = 'B24 이익 전망(추정치 이력 없음), B23 추정치 구제, B15 선행 PER. 생존 편향 있음'
    I = pd.concat([ic(X, COLS, start, 26).rename(columns={'IC_26주': 'IC'}).assign(기간='26주'), ic(X, COLS, start, 12).rename(columns={'IC_12주': 'IC'}).assign(기간='12주')], ignore_index=True)
    Y = yearly(X, start)
    for k, v in (('재무블록_검정', G), ('재무블록_IC', I), ('재무블록_연도별', Y)):
        v.to_csv(f'{W_out}/{k}.csv', index=False, encoding='utf-8-sig')
    keep = ['날짜', 'ticker', '섹터', '층', 'px', 'mcap', '베타', '고점대비', '나스닥점수', 'B15', 'B23', 'B25', 'B26', '우량', 'roe', 'fscore_8', 'z',
            'debt_ebitda', 'fcf', 'fcf_yield', 'per', 'pbr', 'per_pct3', 'rev_yoy', 'op_yoy', 'opm_yoy', 'capex_int', '12주', '26주']
    X[keep].to_csv(f'{W_out}/재무블록_주별.csv.gz', index=False, encoding='utf-8-sig', compression='gzip')
    cov = X[X['날짜'] >= start][['B23', 'B25', 'B26', 'B15', '우량']].notna().mean().round(3)
    print('[재무블록] 채움률(2014~):', cov.to_dict())
    return G, I, Y, X


if __name__ == '__main__':
    # python fund_test.py <출력폴더> <SEC폴더> <유니버스.csv> <바닥근접도_이력_나스닥100.csv>
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
    G, I, Y, X = run(*sys.argv[1:5])
    print(G.drop(columns='시험 못 한 것').to_string()); print(I.to_string()); print(Y.to_string())
