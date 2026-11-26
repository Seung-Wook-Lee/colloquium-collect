"""공포탐욕 스캔 — "공포탐욕이 N 이하였던 날 샀다면" 유니버스 전 종목 1달·반년·1년 뒤(11/21 의장).

쓰기: python app/diagnose/fear_scan.py --fg 12 [--market 미국] [--kind 개별주] [--universe 유니버스.csv] [--out 폴더]
  --universe 없으면 10년치 데이터베이스 유니버스 칸(11/26 하나로 통일).
출력: <out>/공탐{N}이하_{시장}_{구분}_YYYYMMDD.csv + 화면 상위 표.

틀리지 않게(11/21 의장 "이런 실수가 왜 나오니, 코딩으로"):
  · 가격은 시장(미국·한국)별로 따로 받고, 종목마다 자기 거래일만 쓴다(빈 날 채우기 없음).
  · 앞날 계산 전에 run.check_calendar 로 달력 검사 — 252거래일이 달력 340~380일이 아니면 멈춤.
  · 앞날 계산은 run.forward 하나만 쓴다(종목 진단과 같은 함수).
  · 마지막에 기준 종목(SPY 또는 첫 종목)을 같은 함수로 따로 계산해 표의 값과 같은지 대조한다.
"""
import argparse
import datetime as dt
import io
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
sys.path[:0] = [HERE, APP, os.path.join(APP, 'market'), os.path.join(os.path.dirname(APP), 'collect')]
import fear_greed as FGM  # noqa: E402
import run as RUN  # noqa: E402


def universe(path=None):
    if path:
        return pd.read_csv(path)
    import drive
    sys.path.insert(0, os.path.join(os.path.dirname(APP), 'collect', 'data'))
    import px_store as PS   # 11/26 의장 "하나로 통일해": 유니버스 = 10년치 데이터베이스 칸
    return PS.universe(drive)


def prices(tickers):
    import yfinance as yf
    P = yf.download(sorted(tickers), start='2010-06-01', auto_adjust=True, progress=False, threads=True)['Close']
    return P if isinstance(P, pd.DataFrame) else P.to_frame(tickers[0])


REF = {'미국': 'SPY', '한국': '^KS11'}   # 시장별 기준 거래일


def one(s, days, first, ref=None):
    """한 종목: 공포 날(days) 앞날 통계 + 사건(first)별 1년 이익 횟수"""
    s = s.dropna()
    RUN.check_calendar(s, s.name, ref)
    F = RUN.forward(s)
    end = s.index[-1] - pd.Timedelta(days=366)
    d = days[(days >= s.index[0]) & (days <= end)]
    i = s.index.get_indexer(d, method='bfill'); i = i[i >= 0]
    x = F.iloc[i]
    fe = first[(first >= s.index[0]) & (first <= end)]
    j = s.index.get_indexer(fe, method='bfill'); e = F['f52'].iloc[j[j >= 0]].dropna()
    r = {'사건수': len(e), '날수': len(x), '사건별_1년_이익': int((e > 0).sum())}
    for c, n in (('f4', '1달'), ('f26', '반년'), ('f52', '1년')):
        v = x[c].dropna()
        r[f'{n}_중앙값%'] = v.median() * 100; r[f'{n}_승률%'] = (v > 0).mean() * 100
    r['반년안_추가하락_중앙값'] = x['lo26'].median() * 100
    r['반년안_추가하락_하위25'] = x['lo26'].quantile(0.25) * 100
    r['고점대비'] = (s.iloc[-1] / s.tail(252).max() - 1) * 100
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fg', type=float, default=12)
    ap.add_argument('--market', default=None, help='미국 / 한국 (비우면 전부)')
    ap.add_argument('--kind', default=None, help='개별주 / ETF (비우면 전부)')
    ap.add_argument('--universe', default=None)
    ap.add_argument('--min-events', type=int, default=10)
    ap.add_argument('--out', default=os.path.join(HERE, 'out'))
    a = ap.parse_args()
    U = universe(a.universe)
    U = U[U['yfinance 티커'].notna()].drop_duplicates('yfinance 티커')
    if a.market:
        U = U[U['시장'] == a.market]
    if a.kind:
        U = U[U['구분'] == a.kind]
    H = FGM.history()
    if not len(H):
        raise SystemExit('공포탐욕 이력을 못 받음')
    days = H.index[H <= a.fg]
    first = pd.Series(days).groupby((pd.Series(days).diff().dt.days > 30).cumsum()).first()
    rows, bad = [], []
    for mk, G in U.groupby('시장'):   # 시장별로 따로 받음(다른 나라 거래일 섞임 방지)
        P = prices(G['yfinance 티커'].astype(str).tolist() + [REF[mk]])
        ref = P[REF[mk]].dropna().index
        for _, u in G.iterrows():
            t = str(u['yfinance 티커'])
            if t not in P or P[t].dropna().shape[0] < 300:
                continue
            try:
                r = one(P[t].rename(t), days, first, ref)
            except ValueError as e:
                bad.append(str(e)); continue
            rows.append({'티커': t, '이름': u.get('정식 종목명'), '시장': mk, '구분': u.get('구분'), **r})
    if bad:
        print('달력 검사에서 뺀 종목:', *bad, sep='\n  ')
    R = pd.DataFrame(rows)
    R = R[R['사건수'] >= a.min_events].sort_values(['1년_승률%', '1년_중앙값%'], ascending=False).round(1)
    # 대조: 표의 첫 종목을 따로 받아 같은 함수로 다시 계산 → 같아야 함
    t0 = R['티커'].iloc[0]
    m0 = R['시장'].iloc[0]
    Q = prices([t0, REF[m0]])
    chk = one(Q[t0].rename(t0), days, first, Q[REF[m0]].dropna().index)
    if abs(round(chk['1년_중앙값%'], 1) - R.iloc[0]['1년_중앙값%']) > 0.05:
        raise SystemExit(f'대조 실패: {t0} 표 {R.iloc[0]["1년_중앙값%"]} vs 따로 {chk["1년_중앙값%"]:.1f}')
    day = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime('%Y%m%d')
    os.makedirs(a.out, exist_ok=True)
    fn = os.path.join(a.out, f"공탐{a.fg:g}이하_{a.market or '전체'}_{a.kind or '전체'}_{day}.csv")
    R.to_csv(fn, index=False, encoding='utf-8-sig')
    print(f'공포탐욕 {a.fg:g} 이하: {len(days)}일, 사건 {len(first)}번 · 종목 {len(R)}개 · 대조 통과({t0}) → {fn}')
    print(R.head(25).to_string(index=False))


if __name__ == '__main__':
    main()
