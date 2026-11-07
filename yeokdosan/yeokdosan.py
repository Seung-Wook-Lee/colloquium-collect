# 미스터 역도산(2026-11-07 신설) 공용 계산 — 매일 수집 블록(b09_yeokdosan)과 과거 자료 채우기(research/yeokdosan_backfill.py)가 같이 쓴다.
#   자료 창고 : 드라이브 '콜로키움 수집데이터/00_누적/00_역도산_주봉.csv' (한투 해외 주봉, 수정주가, 긴 표: 티커,날짜,시가,고가,저가,종가,거래량)
#              날짜는 그 주 금요일. 진행 중인 주는 매일 덮어써서 금요일 종가로 굳는다.
#   종목 목록 : yeokdosan/holdings_top10.csv (SPDR 섹터 ETF 11개 × 상위 10, 의장이 바꾸면 여기만 고친다)
#   기준      : 아래 CFG. 이론을 바꾸면 CFG만 고치고, 백테스트(Team_Q contrarian/)도 같은 CFG 숫자로 다시 돌린다(룰 변경은 의장 승인 뒤).
import time, requests, pandas as pd, numpy as np

CFG = dict(
    선=(60, 20),            # 60주선이 본 신호, 20주선은 참고
    터치_저가=1.01,          # 그 주 저가 <= 선 x1.01
    터치_종가=0.97,          # 그 주 종가 >= 선 x0.97
    추세_기울기주=13,        # 선이 13주 전보다 높음
    추세_위비율=0.8,         # 지난 52주 중 80% 이상 종가가 선 위
    첫터치_간격주=13,        # 직전 13주 안에 같은 터치 없음
    RSI_n=14, RSI_바닥=40,   # 주봉 와일더 RSI
    MACD=(12, 26, 9),
)
BASE = 'https://openapi.koreainvestment.com:9443'
COLS = ['티커', '날짜', '시가', '고가', '저가', '종가', '거래량']


def fri(d):  # 그 주 금요일
    d = pd.to_datetime(d)
    return (d + pd.to_timedelta((4 - d.dt.weekday) % 7, unit='D')).dt.normalize()


def kis_week_page(token, key, secret, ex, sym, bymd=''):
    """한투 해외주식 기간별시세(HHDFS76240000) 주봉 100줄. 실패면 예외."""
    h = {'content-type': 'application/json; charset=utf-8', 'authorization': f'Bearer {token}', 'appkey': key,
         'appsecret': secret, 'tr_id': 'HHDFS76240000', 'custtype': 'P'}
    err = ''
    for n in range(3):
        try:
            time.sleep(0.25)
            j = requests.get(f'{BASE}/uapi/overseas-price/v1/quotations/dailyprice', headers=h, timeout=15,
                             params={'AUTH': '', 'EXCD': ex, 'SYMB': sym, 'GUBN': '1', 'BYMD': bymd, 'MODP': '1'}).json()
            if j.get('rt_cd') == '0':
                return [r for r in (j.get('output2') or []) if r.get('xymd') and r.get('clos') not in (None, '', '0')]
            err = f"{j.get('msg_cd')} {j.get('msg1')}"
        except Exception as e:
            err = str(e)[:80]
        time.sleep(1 + 2 * n)
    raise RuntimeError(err)


def to_frame(tk, rows):
    d = pd.DataFrame(rows).drop_duplicates('xymd')
    out = pd.DataFrame({'티커': tk, '날짜': fri(pd.to_datetime(d.xymd)), '시가': pd.to_numeric(d.open, errors='coerce'),
                        '고가': pd.to_numeric(d.high, errors='coerce'), '저가': pd.to_numeric(d.low, errors='coerce'),
                        '종가': pd.to_numeric(d.clos, errors='coerce'), '거래량': pd.to_numeric(d.tvol, errors='coerce')})
    return out[out.종가 > 0].drop_duplicates('날짜', keep='first').sort_values('날짜')


def find_exchange(token, key, secret, tk):
    """(거래소, 한투 코드, 첫 페이지 rows). BRK-B 같은 이름은 BRK/B·BRK.B 도 시도."""
    names = [tk, tk.replace('-', '/'), tk.replace('-', '.')] if '-' in tk else [tk]
    for ex in ('NYS', 'NAS', 'AMS'):
        for nm in names:
            try:
                rows = kis_week_page(token, key, secret, ex, nm)
            except Exception:
                rows = []
            if rows:
                return ex, nm, rows
    return None, None, []


def merge(store, new):
    """창고에 새 주봉을 덮어 넣는다(같은 티커·날짜는 새 값)."""
    if store is None or store.empty:
        return new.reset_index(drop=True)
    x = pd.concat([store, new]).drop_duplicates(['티커', '날짜'], keep='last')
    return x.sort_values(['티커', '날짜']).reset_index(drop=True)


def rsi(c, n):
    d = c.diff(); u = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + u / dn)


def signals(w):
    """w: 한 종목 주봉(날짜 색인, 시가·고가·저가·종가). 선마다 터치·하향돌파 뒤 상향돌파와 보조 값."""
    c, l = w.종가, w.저가; out = {}
    R = rsi(c, CFG['RSI_n']); f, s_, g = CFG['MACD']
    macd = c.ewm(span=f, adjust=False).mean() - c.ewm(span=s_, adjust=False).mean(); hist = macd - macd.ewm(span=g, adjust=False).mean()
    turn = (hist > hist.shift(1)) & (hist.shift(1) <= hist.shift(2))
    for n in CFG['선']:
        m = c.rolling(n).mean()
        up = (m > m.shift(CFG['추세_기울기주'])) & ((c > m).astype(float).rolling(52).mean() >= CFG['추세_위비율'])
        t = (l <= m * CFG['터치_저가']) & (c >= m * CFG['터치_종가']) & up
        t = t & ~t.shift(1).rolling(CFG['첫터치_간격주'], min_periods=1).max().fillna(0).astype(bool)
        below = c < m
        cu = (~below) & below.shift(1).fillna(False).astype(bool)
        out[n] = dict(선=m, 이격=c / m * 100, 저가이격=l / m * 100, 상승추세=up, 터치=t, 상향돌파=cu)
    return out, dict(RSI=R, 오실레이터=hist, 오실레이터상승전환=turn, MACD음수=macd < 0)


def now_table(store, holdings):
    """지금판: ETF와 상위 10의 마지막 주 상태. 끼어들기 = ETF 60주선 첫 터치."""
    rows = []
    g = {t: x.set_index('날짜').sort_index() for t, x in store.groupby('티커')}
    r26 = {t: (w.종가.iloc[-1] / w.종가.iloc[-27] - 1) * 100 for t, w in g.items() if len(w) > 27}
    for e in dict.fromkeys(holdings.ETF):
        for tk, kind, rank in [(e, 'ETF', 0)] + [(r.티커, '종목', r.순위) for r in holdings[holdings.ETF == e].itertuples()]:
            w = g.get(tk)
            if w is None or len(w) < 80:
                rows.append(dict(ETF=e, 구분=kind, 순위=rank, 티커=tk, 상태='자료 부족')); continue
            sg, ind = signals(w); i = -1
            r = dict(ETF=e, 구분=kind, 순위=rank, 티커=tk, 주=w.index[i].date(), 종가=round(w.종가.iloc[i], 2),
                     고점대비52주=round((w.종가.iloc[i] / w.고가.iloc[-52:].max() - 1) * 100, 1),
                     ETF대비26주=round(r26.get(tk, np.nan) - r26.get(e, np.nan), 1) if kind == '종목' else np.nan,
                     RSI=round(ind['RSI'].iloc[i], 1), MACD음수='예' if ind['MACD음수'].iloc[i] else '',
                     오실레이터상승전환_3주안='예' if ind['오실레이터상승전환'].iloc[-3:].any() else '')
            for n, s in sg.items():
                r[f'{n}주 이격'] = round(s['이격'].iloc[i], 1); r[f'{n}주 저가이격'] = round(s['저가이격'].iloc[i], 1)
                r[f'{n}주 상승추세'] = '예' if s['상승추세'].iloc[i] else ''
                r[f'{n}주 첫터치'] = '예' if s['터치'].iloc[i] else ''
                r[f'{n}주 상향돌파'] = '예' if s['상향돌파'].iloc[i] else ''
            rows.append(r)
    T = pd.DataFrame(rows)
    cut = T[(T.구분 == 'ETF') & (T.get('60주 첫터치') == '예')].ETF.tolist() if '60주 첫터치' in T else []
    return T, cut
