"""1-9 자료 품질 검사(블록 1 검정): 원천마다 종목 수·기간·결측률·이상치 수, 유니버스 중 빠진 종목."""
import pandas as pd

from .common import need, read, write


def run(ctx, c):
    rows = []
    U = ctx.get('U') if ctx.get('U') is not None else need(ctx, 'L', '유니버스_층.csv.gz')
    want = set(U['yfinance 티커'].dropna()) if U is not None else set()
    P = need(ctx, 'P', '가격10년_정제.csv.gz', index_col=0, parse_dates=True)
    need(ctx, 'SEC', '가격10년_SEC재무.csv.gz'); need(ctx, 'DART', '가격10년_DART재무.csv.gz')   # 10년치 저장본 칸
    if ctx.get('PER') is None:   # 11/26 PER은 10년치 데이터베이스(종가 ÷ EPS 칸)에서 읽음
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import px_store as PS
        read(ctx, PS.name('Close'), nrows=1); read(ctx, PS.name('EPS'), nrows=1)   # 없으면 드라이브에서 1_data로 받아 둠
        ctx['PER'] = PS.per_weekly(ctx['out'])
    if ctx.get('정제기록') is None:
        ctx['정제기록'] = need(ctx, '정제기록', '정제_기록.csv.gz')
    if P is not None:
        live = P.loc[:, [t for t in P.columns if t in want]]
        first = pd.to_datetime(live.apply(lambda s: s.first_valid_index()))
        span = (live.index.max() - first).dt.days / 365.25
        after = live.where(live.index.values[:, None] >= first.values[None, :])
        alive = pd.DataFrame(live.index.values[:, None] >= first.values[None, :], index=live.index, columns=live.columns)
        kr = [t for t in live.columns if str(t).endswith(('.KS', '.KQ'))]
        ok_kr = P['^KS11'].notna() if '^KS11' in P else live[kr].notna().any(axis=1)
        ok_us = P['^GSPC'].notna() if '^GSPC' in P else live.notna().any(axis=1)
        alive = alive & pd.DataFrame({t: (ok_kr if t in kr else ok_us) for t in live.columns}, index=live.index)
        miss = (after.isna() & alive).sum() / alive.sum().replace(0, float('nan'))
        L = ctx.get('정제기록', pd.DataFrame(columns=['ticker', '무엇']))
        for t in sorted(want):
            rows.append({'원천': '1-1 가격(정제 뒤)', 'ticker': t, '시작': str(first.get(t))[:10] if t in first else '',
                         '기간(년)': round(float(span.get(t, float('nan'))), 1) if t in span else None,
                         '결측률(%)': round(float(miss.get(t, float('nan'))) * 100, 2) if t in miss else None,
                         '이상치': int(((L['ticker'] == t) & ~L['무엇'].str.startswith('결측')).sum()), '결측채움': int(((L['ticker'] == t) & L['무엇'].str.startswith('결측')).sum()), '없음': t not in P.columns or P[t].notna().sum() == 0})
    for key, name in (('SEC', '1-2 미국 재무'), ('DART', '1-3 한국 재무')):
        D = ctx.get(key)
        if D is None:
            continue
        g = D.groupby('ticker')
        for t, x in g:
            rows.append({'원천': name, 'ticker': t, '시작': str(x['분기말'].min())[:10], '기간(년)': round((pd.to_datetime(x['분기말']).max() - pd.to_datetime(x['분기말']).min()).days / 365.25, 1),
                         '항목수': x['항목'].nunique(), '주식수': bool((x['항목'] == '주식수').any())})
    X = ctx.get('PER')
    if X is not None:
        for t, x in X.groupby('ticker'):
            rows.append({'원천': '1-4 PER·EPS', 'ticker': t, '시작': str(x.dropna(subset=['PER'])['날짜'].min())[:10],
                         'PER_있는주(%)': round(x['PER'].notna().mean() * 100, 1),
                         # 11/22 의장 '우리 자료에 오류 있으면 안 됨'(TSM PER 0.65 = 화폐 단위 섞임): 상식 밖 PER 주 수
                         'PER_상식밖(주)': int(((x['PER'] < 2) | (x['PER'] > 2000)).sum())})
    Q = pd.DataFrame(rows)
    write(ctx, '자료_품질.csv.gz', Q)
    S = Q.groupby('원천').agg(종목=('ticker', 'nunique'), 평균기간=('기간(년)', 'mean')).round(1)
    return S.to_dict('index')
