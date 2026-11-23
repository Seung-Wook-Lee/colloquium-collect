"""블록점수이력용 과거 재무 칸 (11/23 의장: "24개 블록의 과거 값부터 채워. 안 되는 블록은 버려").
backtest.py는 그 주까지의 가격만 다시 계산하고, 재무 칸(B15·B23·B25·B26)은 오늘 값으로 고정돼 비워 왔다.
여기서는 우리 1_data의 SEC재무_분기·DART재무_분기(공시일 기준)와 PER_EPS_주별(공시일 기준 주별 PER)로
'그 주에 공시돼 있던 분기'만 써서 엔진과 같은 칸을 다시 만든다.
  B23: op_yoy·rev_yoy·opm_yoy·opm2·earn_ok (분기 전년 같은 분기 대비, 영업이익 없으면 순이익)
  B25: fscore(피오트로스키 9항목, 4분기 합 기준)·fcf(영업현금흐름−설비투자, 4분기 합)·roe(순이익 4분기 합÷자본)
  B26: z(알트만: 1.2 운전자본/자산 + 1.4 이익잉여금/자산 + 3.3 영업이익/자산 + 0.6 시총/부채 + 1.0 매출/자산)·debt_ebitda
  B15: per_ttm·pbr(층 안 순위)·fcf_yield·per_pct3 (fper·peer_fper는 과거 추정치가 없어 비움 → 공식 6개 중 4개)
쓰는 곳: backtest._one → apply(f, t, close)"""
import os

import numpy as np
import pandas as pd

VARS = {'op_yoy', 'opm_yoy', 'opm2', 'rev_yoy', 'earn_ok', 'roe', 'fcf', 'fcf_yield', 'debt_ebitda', 'z', 'fscore',
        'per_ttm', 'pbr', 'per_rank', 'pbr_rank', 'per_pct3'}
_EV = None


def _load(d):
    src = [p for p in (f'{d}/장기/SEC재무_분기.csv.gz', f'{d}/장기/DART재무_분기.csv.gz') if os.path.exists(p)]
    if not src:
        return None, None
    D = pd.concat([pd.read_csv(p) for p in src], ignore_index=True)
    D['분기말'] = pd.to_datetime(D['분기말'], errors='coerce'); D['공시일'] = pd.to_datetime(D['공시일'], errors='coerce')
    D['값'] = pd.to_numeric(D['값'], errors='coerce')
    D = D.dropna(subset=['분기말', '공시일', '값']).sort_values('공시일').drop_duplicates(['ticker', '항목', '분기말'], keep='first')
    ev = []
    for tk, g in D.groupby('ticker'):
        q = g['분기말'].dt.to_period('Q'); main = g['항목'] != '주식수'   # 주식수는 표지 날짜(다음 분기)로 찍혀 와서 분기를 새로 만들지 않게
        if not main.any(): continue
        W = g.pivot_table(index=q, columns='항목', values='값', aggfunc='first').sort_index()
        av = g[main].groupby(q[main])['공시일'].min()
        W = W.loc[W.index.isin(av.index) | (W.index < av.index.max())]
        W = W.reindex(pd.period_range(W.index.min(), W.index.max(), freq='Q'))
        c = lambda k: W[k] if k in W else pd.Series(np.nan, index=W.index)
        s4 = lambda k: c(k).rolling(4, min_periods=4).sum()
        kind = np.where(c('영업이익').notna(), '영업이익', '순이익')
        op = c('영업이익').combine_first(c('순이익')); rev = c('매출')
        yoy = lambda x: (x - x.shift(4)) / x.shift(4).abs()
        opm = op / rev.where(rev > 0)
        ni4, op4, ocf4, cap4, da4, rev4 = s4('순이익'), op.rolling(4, min_periods=4).sum(), s4('영업현금흐름'), s4('설비투자'), s4('감가상각'), rev.rolling(4, min_periods=4).sum()
        ta, tl, eq = c('자산'), c('부채'), c('자본')
        tl = tl.combine_first(ta - eq)
        debt = (c('단기부채').fillna(0) + c('장기부채').fillna(0)).where(c('단기부채').notna() | c('장기부채').notna()).combine_first(tl)
        roa = ni4 / ta; cr = c('유동자산') / c('유동부채'); lev = c('장기부채') / ta
        gm = s4('매출총이익') / rev4; at = rev4 / ta
        F = pd.concat([roa > 0, ocf4 > 0, roa > roa.shift(4), ocf4 > ni4, lev < lev.shift(4), cr > cr.shift(4),
                       c('주식수') <= c('주식수').shift(4), gm > gm.shift(4), at > at.shift(4)], axis=1)
        okF = pd.concat([roa, ocf4, roa.shift(4), ni4, lev.shift(4), cr.shift(4), c('주식수').shift(4), gm.shift(4), at.shift(4)], axis=1).notna()
        fscore = (F & okF).sum(axis=1).where(okF.sum(axis=1) >= 6) * 9 / okF.sum(axis=1).clip(lower=1)
        E = pd.DataFrame({'ticker': tk, '이용일': av.reindex(W.index).values, 'kind': kind,
                          'op_yoy': yoy(op).values, 'rev_yoy': yoy(rev).values, 'opm_yoy': (opm - opm.shift(4)).values,
                          'roe': (ni4 / eq.where(eq > 0) * 100).values, 'fcf': (ocf4 - cap4.abs()).values,
                          'ebitda': (op4 + da4.fillna(0)).values, 'debt': debt.values, 'eq': eq.values, 'ta': ta.values, 'tl': tl.values,
                          'wc': (c('유동자산') - c('유동부채')).values, 're': c('이익잉여금').values, 'op4': op4.values, 'rev4': rev4.values,
                          'sh': c('주식수').ffill().values, 'fscore': fscore.values})
        E['opm2'] = ((E['opm_yoy'] > 0) & (E['opm_yoy'].shift(1) > 0)).astype(float).where(E['opm_yoy'].notna())
        ev.append(E.dropna(subset=['이용일']))
    E = pd.concat(ev, ignore_index=True).sort_values('이용일')
    E['이용일'] = E['이용일'].astype('datetime64[ns]')
    P = None
    pp = f'{d}/장기/PER_EPS_주별.csv.gz'
    if os.path.exists(pp):
        P = pd.read_csv(pp, usecols=['날짜', 'ticker', 'PER', 'PER_3년백분위'], parse_dates=['날짜']).sort_values('날짜')
        P['날짜'] = P['날짜'].astype('datetime64[ns]')
    return E, P


def apply(f, t, close, d, mem=()):
    """f: 그 주 엔진 칸(feats), t: 기준일, close: {ticker: 그날 종가}. 재무 칸을 그 주에 알 수 있던 값으로 바꿔 넣는다."""
    global _EV
    if _EV is None:
        _EV = _load(d)
    E, P = _EV
    if E is None:
        return f
    t = pd.Timestamp(t)
    e = E[(E['이용일'] <= t) & (E['이용일'] >= t - pd.Timedelta(days=200))].drop_duplicates('ticker', keep='last').set_index('ticker')
    g = lambda k: f['ticker'].map(e[k]) if k in e else pd.Series(np.nan, index=f.index)
    px = f['ticker'].map(close)
    mcap = px * g('sh')
    f = f.copy()
    for k in ('op_yoy', 'rev_yoy', 'opm_yoy', 'opm2', 'roe', 'fcf', 'fscore'):
        f[k] = g(k).values
    f['kind'] = g('kind').values
    eb = g('ebitda')
    f['debt_ebitda'] = np.where(eb > 0, g('debt') / eb, np.where(eb.notna(), 99, np.nan))
    f['fcf_yield'] = (g('fcf') / mcap * 100).values
    ta = g('ta')
    f['z'] = (1.2 * g('wc') / ta + 1.4 * g('re').fillna(0) / ta + 3.3 * g('op4') / ta + 0.6 * mcap / g('tl') + 1.0 * g('rev4') / ta).values
    f['pbr'] = (mcap / g('eq').where(g('eq') > 0)).values
    if P is not None:
        p = P[(P['날짜'] <= t) & (P['날짜'] >= t - pd.Timedelta(days=10))].drop_duplicates('ticker', keep='last').set_index('ticker')
        f['per_ttm'] = f['ticker'].map(p['PER']).values
        f['per_pct3'] = f['ticker'].map(p['PER_3년백분위']).values
    else:
        f['per_ttm'] = np.nan; f['per_pct3'] = np.nan
    for k in ('per_ttm', 'pbr'):
        v = f[k].where(f[k] > 0)
        f[f'{k.split("_")[0]}_rank'] = v.groupby(f['layer']).rank(pct=True)
    # B23 거르기(엔진 features와 같은 식, 추정치 봐주기는 과거 자료가 없어 뺌)
    f['earn_ok'] = ((f['op_yoy'] > 0) | (f['rev_yoy'] > 0)).astype(float).where(f['op_yoy'].notna())
    m = f['번호'].isin(mem)
    f.loc[m, 'earn_ok'] = (f.loc[m, 'op_yoy'] < 0).astype(float).where(f.loc[m, 'op_yoy'].notna())
    return f
