"""1-3 한국 재무(DART, 공시일 기준): 팀Q 수집(kr_standardized_pit)을 SEC와 같은 꼴(ticker·항목·분기말·공시일·값)로.
첫 공시값만 쓴다(나중 정정은 그때 몰랐음). 주식수 = DART 주식총수(있으면)."""
import os

import pandas as pd

from .common import universe, write

MAP = {'revenue': '매출', 'operating_income': '영업이익', 'net_income': '순이익', 'pretax_income': '세전이익', 'gross_profit': '매출총이익',
       'cfo': '영업현금흐름', 'capex': '설비투자', 'equity': '자본', 'total_assets': '자산', 'total_liabilities': '부채',
       'long_term_debt': '장기부채', 'short_term_debt': '단기부채', 'cash': '현금', 'eps_diluted': '희석EPS'}


def _load(ctx, rel, local):
    p = os.path.join(ctx['in'], local)
    if os.path.exists(p):
        return pd.read_parquet(p)
    try:
        sys_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'teamq')
        import sys
        sys.path.insert(0, sys_path)
        import common as TQ   # 팀Q 드라이브(TEAMQ_DRIVE_URL·TOKEN)
        TQ.OUT = ctx['tmp']
        return TQ.load(rel)
    except Exception as e:   # noqa: BLE001
        print(f'[1-3] 팀Q 드라이브 실패: {e}')
        return None


def run(ctx, c):
    k = _load(ctx, 'processed/fundamentals/kr_standardized_pit.parquet', 'kr_standardized_pit.parquet')
    if k is None:
        raise RuntimeError('DART 표준 재무(kr_standardized_pit)를 못 받음')
    U = universe(ctx)
    U = U[U['시장'] == '한국']
    yt = dict(zip(U['코드'], U['yfinance 티커']))
    k = k[k['ticker'].isin(yt) & k['item'].isin(MAP) & k['period_type'].isin(['Q'])].copy()
    k['ticker'] = k['ticker'].map(yt)
    k['항목'] = k['item'].map(MAP)
    k.loc[k['항목'] == '설비투자', 'value'] = pd.to_numeric(k.loc[k['항목'] == '설비투자', 'value']).abs()
    D = k.rename(columns={'period_end': '분기말', 'filed': '공시일', 'value': '값'})[['ticker', '항목', '분기말', '공시일', '값']]
    D = D.sort_values('공시일').drop_duplicates(['ticker', '분기말', '항목'], keep='first')
    sh = _load(ctx, 'raw/fundamentals/dart_shares_outstanding.parquet', 'dart_shares_outstanding.parquet')
    if sh is not None and len(sh):
        s = sh.copy()
        col = next((x for x in ('istc_totqy', 'shares', 'value') if x in s), None)
        tcol = next((x for x in ('ticker', 'stock_code', 'code') if x in s), None)
        dcol = next((x for x in ('filed', 'rcept_dt', 'date', 'stlm_dt') if x in s), None)
        if col and tcol and dcol:
            s = s[s[tcol].isin(yt)]
            D = pd.concat([D, pd.DataFrame({'ticker': s[tcol].map(yt), '항목': '주식수', '분기말': pd.to_datetime(s[dcol]).dt.date.astype(str),
                                            '공시일': pd.to_datetime(s[dcol]).dt.date.astype(str),
                                            '값': pd.to_numeric(s[col].astype(str).str.replace(',', ''), errors='coerce')})], ignore_index=True)
    if not (D['항목'] == '주식수').any():   # DART 주식총수를 못 받으면 야후 현재 주식수(근사, '주식수_근거'에 표시)
        import yfinance as yf
        rows = []
        for t in D['ticker'].unique():
            try:
                n = yf.Ticker(t).fast_info.get('shares')
            except Exception:   # noqa: BLE001
                n = None
            if n:
                rows.append({'ticker': t, '항목': '주식수', '분기말': '2010-01-01', '공시일': '2010-01-01', '값': float(n)})
        D = pd.concat([D, pd.DataFrame(rows)], ignore_index=True)
        ctx['DART_주식수_근거'] = '야후 현재 주식수(근사)'
    for c_ in ('분기말', '공시일'):
        D[c_] = pd.to_datetime(D[c_]).dt.strftime('%Y-%m-%d')
    write(ctx, 'DART재무_분기.csv.gz', D)
    ctx['DART'] = D
    return {'종목': int(D['ticker'].nunique()), '행': len(D), '시작': str(D['분기말'].min())[:10], '끝': str(D['분기말'].max())[:10],
            '주식수': int((D['항목'] == '주식수').sum())}
