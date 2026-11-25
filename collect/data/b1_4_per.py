"""1-4 EPS 칸: 재무(1-2 SEC·1-3 DART), 공시일 기준(그날 알 수 있던 값만).
11/26 의장 "PER은 10년치 기록에 열을 만들어서 합치면 되지 않나? 데이터베이스를 하나로 통일해":
일별 EPS TTM = 순이익 4분기 합 ÷ 주식수(그날까지 공시된 값) → 10년치 데이터베이스의 한 칸 '가격10년_EPS.csv.gz'(날짜 × 티커).
PER은 따로 저장하지 않고 px_store.per(종가 ÷ EPS, 적자면 빈칸)·per_band·per_weekly로 읽는다. PER_EPS_주별 파일은 없앰."""
import numpy as np
import pandas as pd

import os
import sys

from .common import need, write

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


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
    import px_store as PS
    days = P.index[P.index >= pd.Timestamp('2000-01-01')]
    wk = pd.DataFrame({'날짜': pd.DatetimeIndex(days).astype('datetime64[ns]')})
    wk = wk.merge(pd.DataFrame({'ticker': sorted(set(T['ticker']) & set(P.columns))}), how='cross').sort_values('날짜')
    T = T.assign(이용일=pd.to_datetime(T['이용일']).astype('datetime64[ns]')).sort_values('이용일')
    X = pd.merge_asof(wk, T, left_on='날짜', right_on='이용일', by='ticker', direction='backward', tolerance=pd.Timedelta(days=200))
    sh = sh.assign(공시일=pd.to_datetime(sh['공시일']).astype('datetime64[ns]')).sort_values('공시일').drop_duplicates(['ticker', '공시일'], keep='last')
    X = pd.merge_asof(X.sort_values('날짜'), sh, left_on='날짜', right_on='공시일', by='ticker', direction='backward')   # 주식수는 마지막으로 알려진 값
    X['EPS_TTM'] = X['ni_ttm'] / X['주식수']
    E = X.pivot_table(index='날짜', columns='ticker', values='EPS_TTM', aggfunc='last').sort_index()
    E.index.name = '날짜'
    write(ctx, PS.name('EPS'), E, index=True)
    ctx['EPS'] = E
    ctx['PER'] = PS.per_weekly(ctx['out']) if os.path.exists(os.path.join(ctx['out'], PS.name('Close'))) else None   # 1-9 품질 검사용
    have = E.dropna(how='all', axis=1)
    return {'종목': int(have.shape[1]), '시작': str(E.dropna(how='all').index.min())[:10],
            '주식수_없음_종목': int(X.groupby('ticker')['주식수'].apply(lambda s: s.isna().all()).sum())}
