"""1-4 과거 PER·EPS: 정제 가격(1-6) + 재무(1-2 SEC·1-3 DART), 공시일 기준(그날 알 수 있던 값만).
주별(금): 순이익 4분기 합(TTM), 주식수, 시가총액 = 종가 × 주식수, PER = 시가총액 ÷ 순이익 TTM(적자면 비움),
EPS TTM = 순이익 TTM ÷ 주식수, PER 52주 중앙값(비쌈 관문), PER 3년 백분위(B15)."""
import numpy as np
import pandas as pd

from .common import need, write


def _ttm(D):
    D = D.copy()
    D['분기말'] = pd.to_datetime(D['분기말']); D['공시일'] = pd.to_datetime(D['공시일'])
    ni = D[D['항목'] == '순이익'].sort_values('공시일').drop_duplicates(['ticker', '분기말'], keep='first')
    out = []
    for t, g in ni.groupby('ticker'):
        g = g.set_index(g['분기말'].dt.to_period('Q')).sort_index()
        g = g[~g.index.duplicated(keep='first')]
        full = g.reindex(pd.period_range(g.index.min(), g.index.max(), freq='Q'))
        s = pd.to_numeric(full['값'], errors='coerce').rolling(4, min_periods=4).sum()
        avail = full['공시일']   # TTM은 가장 최근 분기 공시일부터 알 수 있음
        out.append(pd.DataFrame({'ticker': t, '이용일': avail.values, 'ni_ttm': s.values}).dropna())
    T = pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=['ticker', '이용일', 'ni_ttm'])
    sh = D[D['항목'] == '주식수'][['ticker', '공시일', '값']].rename(columns={'값': '주식수'})
    sh['주식수'] = pd.to_numeric(sh['주식수'], errors='coerce')
    return T, sh.dropna()


def run(ctx, c):
    P = need(ctx, 'P', '가격10년_정제.csv.gz', index_col=0, parse_dates=True)
    need(ctx, 'SEC', 'SEC재무_분기.csv.gz'); need(ctx, 'DART', 'DART재무_분기.csv.gz')
    if P is None:
        raise RuntimeError('1-6 정제 가격이 먼저 있어야 함')
    D = pd.concat([x for x in (ctx.get('SEC'), ctx.get('DART')) if x is not None and len(x)], ignore_index=True)
    T, sh = _ttm(D)
    W = P.resample('W-FRI').last()
    wk = W.stack().rename('종가').reset_index(); wk.columns = ['날짜', 'ticker', '종가']
    wk = wk[wk['ticker'].isin(set(T['ticker']))].sort_values('날짜')
    wk['날짜'] = wk['날짜'].astype('datetime64[ns]')
    T = T.assign(이용일=pd.to_datetime(T['이용일']).astype('datetime64[ns]')).sort_values('이용일')
    X = pd.merge_asof(wk, T, left_on='날짜', right_on='이용일', by='ticker', direction='backward', tolerance=pd.Timedelta(days=200))
    sh = sh.assign(공시일=pd.to_datetime(sh['공시일']).astype('datetime64[ns]')).sort_values('공시일').drop_duplicates(['ticker', '공시일'], keep='last')
    X = pd.merge_asof(X.sort_values('날짜'), sh, left_on='날짜', right_on='공시일', by='ticker', direction='backward')   # 주식수는 마지막으로 알려진 값
    X['시가총액'] = X['종가'] * X['주식수']
    X['PER'] = np.where(X['ni_ttm'] > 0, X['시가총액'] / X['ni_ttm'], np.nan)
    X['EPS_TTM'] = X['ni_ttm'] / X['주식수']
    X = X.sort_values(['ticker', '날짜'])
    g = X.groupby('ticker')['PER']
    X['PER_52주중앙'] = g.transform(lambda s: s.rolling(52, min_periods=26).median())
    X['PER_3년백분위'] = g.transform(lambda s: s.rolling(156, min_periods=52).rank(pct=True))
    keep = ['날짜', 'ticker', '종가', 'ni_ttm', '주식수', '시가총액', 'EPS_TTM', 'PER', 'PER_52주중앙', 'PER_3년백분위']
    write(ctx, 'PER_EPS_주별.csv.gz', X[keep])
    ctx['PER'] = X[keep]
    have = X.dropna(subset=['PER'])
    return {'종목': int(have['ticker'].nunique()), '주': int(have['날짜'].nunique()), '시작': str(have['날짜'].min())[:10],
            '주식수_없음_종목': int(X.groupby('ticker')['주식수'].apply(lambda s: s.isna().all()).sum())}
