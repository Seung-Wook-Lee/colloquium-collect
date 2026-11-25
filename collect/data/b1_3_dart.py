"""1-3 한국 재무(DART, 공시일 기준): 팀Q 수집(kr_standardized_pit)을 SEC와 같은 꼴(ticker·항목·분기말·공시일·값)로.
첫 공시값만 쓴다(나중 정정은 그때 몰랐음). 주식수 = DART 주식총수(있으면)."""
import os

import pandas as pd

from . import px_store as PS
from .common import read, universe, write

MAP = {'revenue': '매출', 'operating_income': '영업이익', 'net_income': '순이익', 'pretax_income': '세전이익', 'gross_profit': '매출총이익',
       'cfo': '영업현금흐름', 'capex': '설비투자', 'equity': '자본', 'total_assets': '자산', 'total_liabilities': '부채',
       'long_term_debt': '장기부채', 'short_term_debt': '단기부채', 'cash': '현금', 'eps_diluted': '희석EPS'}


def _load(ctx, rel, local):
    p = os.path.join(ctx['in'], local)
    if os.path.exists(p):
        return pd.read_parquet(p)
    try:   # 팀Q 드라이브(TEAMQ_DRIVE_URL·TOKEN)에 남은 표준 재무 파일을 읽기만 함(11/26 옛 팀Q 수집 코드 지움)
        import base64
        import requests
        url, tok = os.environ.get('TEAMQ_DRIVE_URL'), os.environ.get('TEAMQ_DRIVE_TOKEN')
        if not (url and tok):
            raise RuntimeError('TEAMQ_DRIVE_URL·TOKEN 없음')
        b = requests.post(url, json={'token': tok, 'action': 'get', 'path': f'Team_Q__chatgpt/{rel}'}, timeout=600).json()
        if not b.get('found'):
            raise RuntimeError(f'{rel} 없음')
        p = os.path.join(ctx['tmp'], local)
        open(p, 'wb').write(base64.b64decode(b['data']))
        return pd.read_parquet(p)
    except Exception as e:   # noqa: BLE001
        print(f'[1-3] 팀Q 드라이브 실패: {e}')
        return None


# 공시 마감일(법정): 실제 공시는 이날이거나 더 이르다 → 공시일로 마감일을 쓰면 미래 정보가 섞이지 않음
_DUE = {'03-31': (5, 15, 0), '06-30': (8, 14, 0), '09-30': (11, 14, 0), '12-31': (3, 31, 1)}


def _add_new(D, yt):
    """저장본 칸에서 종목마다 마지막 분기 뒤의 분기(매출·영업이익·순이익)를 DART 정기보고서(dart_q)로 덧붙인다. 키 없으면 그대로."""
    import datetime as dt
    try:
        from . import dart_q
    except ImportError:
        import dart_q
    if not dart_q.ready():
        print('[1-3] DART_KEY 없음 — 새 분기 덧붙이기 건너뜀')
        return D
    E = D[D['항목'].isin(['매출', '영업이익'])]   # 주식수 줄은 분기말 칸에 공시 날짜가 들어 있어 빼야 함
    last = pd.to_datetime(E['분기말']).groupby(E['ticker']).max() if len(E) else pd.Series(dtype='datetime64[ns]')
    rows = []
    for code, t in yt.items():
        lq = last.get(t)
        for q, rev, op, ni in dart_q.quarterly(str(code).zfill(6), years=2):
            if lq is not None and pd.Timestamp(q) <= lq:
                continue
            m, d_, y1 = _DUE[q[5:]]
            filed = min(dt.date(int(q[:4]) + y1, m, d_), dt.date.today())
            for item, v in (('매출', rev), ('영업이익', op), ('순이익', ni)):
                if v is not None:
                    rows.append({'ticker': t, '항목': item, '분기말': q, '공시일': filed.isoformat(), '값': v})
    ctx_n = len({(r['ticker'], r['분기말']) for r in rows})
    print(f'[1-3] DART 새 분기 {ctx_n}개(종목·분기) 덧붙임 | 회사번호 찾음 {sum(1 for c in yt if dart_q.corp(str(c).zfill(6)))}/{len(yt)} | '
          f'에이피알 마지막 분기 {last.get("278470.KS")} | DART 오류 {dart_q.ERR[:3]}')
    return pd.concat([D, pd.DataFrame(rows)], ignore_index=True) if rows else D


def run(ctx, c):
    if ctx.get('drive'):   # 11/26 의장: 과거 자료는 10년치 저장본 칸 — 칸이 아직 없으면 옛 파일을 칸으로 옮기고 휴지통
        import drive
        PS.fetch(drive, 'DART재무', ctx['out'])
    U = universe(ctx)
    U = U[U['시장'] == '한국']
    yt = dict(zip(U['코드'], U['yfinance 티커']))
    k = _load(ctx, 'processed/fundamentals/kr_standardized_pit.parquet', 'kr_standardized_pit.parquet')
    old = read(ctx, PS.name('DART재무'), dtype={'ticker': str})   # 지금 저장본 칸
    if k is None:   # 11/26: 팀Q 표준 재무는 더 이상 새로 쌓이지 않음 → 저장본 칸에 DART 새 분기만 덧붙임
        if old is None or not len(old):
            raise RuntimeError('DART 표준 재무(kr_standardized_pit)도 저장본 칸도 없음')
        D = _add_new(old, yt)
        write(ctx, PS.name('DART재무'), D); ctx['DART'] = D
        return {'종목': int(D['ticker'].nunique()), '행': len(D), '시작': str(D['분기말'].min())[:10], '끝': str(D['분기말'].max())[:10]}
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
    D = _add_new(D, yt)   # 팀Q 표준 재무에 아직 없는 새 분기는 DART에서 바로(11/26 에이피알 3분기 빠짐 발견)
    write(ctx, PS.name('DART재무'), D)   # 10년치 저장본 칸(옛 1_data/DART재무_분기)
    ctx['DART'] = D
    return {'종목': int(D['ticker'].nunique()), '행': len(D), '시작': str(D['분기말'].min())[:10], '끝': str(D['분기말'].max())[:10],
            '주식수': int((D['항목'] == '주식수').sum())}
