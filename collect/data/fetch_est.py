"""미국 종목 애널리스트 이익 추정치(야후 eps_trend·eps_revisions) — 매일 아침 8시 수집이 그날 값만 받아
10년치 데이터베이스 칸 '이익추정'(1_data/가격10년_이익추정.csv.gz)에 날짜 줄로 덧붙인다(새 파일 없음).
11/26 의장 "11월 26일 전망을 10월 30일 거를 가지고 한다고?", "최근 일주일 보고서만 참고해", "하나로 통일해".
칸: 날짜, 번호, ticker, 추정_7일·추정_30일·추정_90일(%, 1년 뒤 EPS 추정 변화), 상향7·하향7·상향30·하향30(애널리스트 수).
한국 종목은 한투 증권사 투자의견 칸(kis_opinion.py)을 쓴다."""
import datetime as dt
import os
import sys
import warnings

import pandas as pd

warnings.filterwarnings('ignore')
sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), os.path.dirname(os.path.abspath(__file__))]
import drive  # noqa: E402
import px_store as PS  # noqa: E402

KAN = '이익추정'


def one(tk):
    import yfinance as yf
    r = {}
    T = yf.Ticker(tk)
    tr = T.eps_trend
    row = tr.loc['+1y'] if '+1y' in tr.index else tr.iloc[-1]
    cur = row['current']
    for k, c in (('추정_7일', '7daysAgo'), ('추정_30일', '30daysAgo'), ('추정_90일', '90daysAgo')):
        r[k] = (cur / row[c] - 1) * 100 if row.get(c) else None
    rv = T.eps_revisions
    rr = rv.loc['+1y'] if '+1y' in rv.index else rv.iloc[-1]
    r['상향7'], r['하향7'] = rr.get('upLast7days'), rr.get('downLast7Days', rr.get('downLast7days'))
    r['상향30'], r['하향30'] = rr.get('upLast30days'), rr.get('downLast30days')
    return r


def main():
    U = PS.universe(drive)
    U = U[(U['시장'] == '미국') & (U['구분'] == '개별주')]
    day = dt.date.today().isoformat()
    rows, bad = [], []
    for no, tk in zip(U['번호'], U['yfinance 티커']):
        try:
            rows.append(dict(날짜=day, 번호=no, ticker=tk, **one(tk)))
        except Exception:   # noqa: BLE001 — 추정치 없는 종목은 건너뜀
            bad.append(tk)
    new = pd.DataFrame(rows)
    old = PS.rows(drive, KAN)
    D = new if old.empty else pd.concat([old[old['날짜'].astype(str) != day], new.astype(str)], ignore_index=True)
    PS.put_rows(drive, KAN, D)
    print(f'[이익추정] {day} {len(new)}종목(못 받음 {len(bad)}) → {PS.name(KAN)} 전체 {len(D)}줄')


if __name__ == '__main__':
    main()
