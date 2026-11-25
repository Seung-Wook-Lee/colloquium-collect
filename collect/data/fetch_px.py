"""회의 직전 가격: 드라이브 저장본(1_data/가격10년_*, in/에 받아 둠)에 그날 새 날짜만 받아 덧붙인다(11/25 의장).
규칙은 px_store.py. 새 종목만 그 종목 과거치를 받는다. 저장본이 아예 없을 때만 전부 받는다.
결과: in/가격10년_*.csv.gz(드라이브에 다시 올림) + 회의용 in/가격2년·고가2년·저가2년·거래량2년.csv(저장본에서 잘라 만듦)."""
import datetime as dt
import os
import sys

import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import px_store as PS  # noqa: E402

N = pd.read_csv('in/닉스.csv', encoding='utf-8-sig')
t = [x for x in N['yfinance 티커'].dropna().astype(str).unique()]
B = PS.load('in')
S0 = PS.start(B)
NEW = PS.missing(B, t)
OLDT = [x for x in t if x not in NEW]
DAYS = 730 if S0 is None else (dt.date.today() - S0).days + 1
print('가격 받기', '저장본 없음 → 전부 10년' if S0 is None else f'저장본 {S0 + dt.timedelta(days=PS.OVERLAP_DAYS)}까지 + 그 뒤 {DAYS}일만 {len(OLDT)}종목' + (f' · 저장본에 없는 새 종목 {NEW}' if NEW else ''))

D = yf.download(OLDT, start=str(S0), auto_adjust=True, progress=False, threads=True) if OLDT and S0 else None
if NEW:   # 저장본에 없는 종목만 과거치
    D2 = yf.download(NEW, period='10y', auto_adjust=True, progress=False, threads=True)
    D = D2 if D is None else pd.concat([D, D2], axis=1, sort=True)


def _col(D, k, x):
    try:
        return D[(k, x)]
    except Exception:
        return None


# 11/21 의장: 한국 종목은 전부 한투 일봉, 미국은 야후가 빈 것만 한투. 받는 날 수는 저장본 뒤 며칠뿐(새 종목만 2년).
try:
    import kis
    print('한투 키', '있음' if kis.ready() else '없음')
    if kis.ready():
        M = N.dropna(subset=['yfinance 티커']).drop_duplicates('yfinance 티커').set_index('yfinance 티커')
        kr = [x for x in t if M.loc[x].get('시장') == '한국']
        bad = kr + [x for x in t if x not in kr and (_col(D, 'Close', x) is None or _col(D, 'Close', x).tail(5).isna().all())]
        got = []
        for x in bad:
            r = M.loc[x]
            mk = r.get('시장')
            if mk == '한국':
                k = kis.daily_kr(str(r.get('코드') or x).split('.')[0], days=730 if x in NEW else DAYS)
            elif mk == '미국':
                k = kis.daily_us(r.get('코드') or x, r.get('거래소'), days=730 if x in NEW else DAYS, pages=8 if x in NEW else 1)
            else:
                continue
            if not len(k):
                continue
            k.index = pd.to_datetime(k.index)
            D = pd.DataFrame(index=k.index) if D is None else D.reindex(D.index.union(k.index))
            for col in ('Close', 'High', 'Low', 'Volume'):
                D[(col, x)] = k[col].reindex(D.index)
            if ('Open', x) in D.columns:   # 한투 일봉에 시가 없음 → 받은 날 시가는 비움(저장본 값 유지)
                D[('Open', x)] = D[('Open', x)].where(~D.index.isin(k.index))
            got.append(x)
        print('한투 일봉', len(got), '/', len(bad), '| 못 받음', [x for x in bad if x not in got])
except Exception as e:
    print('한투 일봉 보충 실패', e)

NEWD = {}
if D is not None and len(D):
    D.columns = pd.MultiIndex.from_tuples(D.columns) if not isinstance(D.columns, pd.MultiIndex) else D.columns
    for k in PS.F:
        if k in D.columns.get_level_values(0):
            NEWD[k] = D[k].dropna(how='all')
B = PS.merge(B, NEWD)
saved = PS.save(B, 'in')
two = PS.two_years(B, 'in', t)
c = B['Close']
print('저장본', c.shape, '마지막 날', c.index[-1].date(), '| 저장', saved, two)
