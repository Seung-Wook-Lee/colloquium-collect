"""미국 개별주 공매도 잔고 과거 기록 (11/24 의장 "공매도와 수급 DATA가 없다고?" → B22 과거 값).
FINRA 공개 API(consolidatedShortInterest, 월 2회 결제일 기준)에서 유니버스 미국 개별주의 전체 이력을 받는다.
출력: <폴더>/가격10년_공매도.csv.gz(10년치 저장본 칸) (결제일, ticker, 공매도주식, 전기공매도주식, 일평균거래량, 커버일수)
실행: python collect/data/hist_short.py <유니버스.csv 있는 폴더>"""
import gzip
import os
import sys
import time

import pandas as pd
import requests

d = sys.argv[1] if len(sys.argv) > 1 else 'in'
U = pd.read_csv(f'{d}/유니버스.csv', encoding='utf-8-sig', dtype=str)
tk = sorted(U[(U['시장'] == '미국') & (U['구분'] == '개별주')]['yfinance 티커'].dropna().str.upper().unique())
URL = 'https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest'
H = {'Accept': 'application/json', 'Content-Type': 'application/json'}
F = ['settlementDate', 'symbolCode', 'currentShortPositionQuantity', 'previousShortPositionQuantity', 'averageDailyVolumeQuantity', 'daysToCoverQuantity']
rows, rep = [], []
for t in tk:
    sym = t.replace('-', '.')   # BRK-B → BRK.B
    got, off = 0, 0
    while True:
        body = {'fields': F, 'limit': 5000, 'offset': off, 'compareFilters': [{'compareType': 'equal', 'fieldName': 'symbolCode', 'fieldValue': sym}]}
        for n in range(3):
            try:
                r = requests.post(URL, json=body, headers=H, timeout=60)
                j = r.json() if r.status_code == 200 and r.text.strip() else []
                break
            except Exception as e:   # noqa: BLE001
                j = []; print(t, '재시도', e); time.sleep(2 + 3 * n)
        if not j:
            break
        for o in j:
            rows.append(dict(결제일=o.get('settlementDate'), ticker=t, 공매도주식=o.get('currentShortPositionQuantity'),
                             전기공매도주식=o.get('previousShortPositionQuantity'), 일평균거래량=o.get('averageDailyVolumeQuantity'), 커버일수=o.get('daysToCoverQuantity')))
        got += len(j); off += len(j)
        if len(j) < 5000:
            break
    rep.append(f'{t} {got}')
    time.sleep(0.2)
S = pd.DataFrame(rows)
if len(S):
    S = S.drop_duplicates(['결제일', 'ticker']).sort_values(['ticker', '결제일'])
    open(f'{d}/가격10년_공매도.csv.gz', 'wb').write(gzip.compress(S.to_csv(index=False).encode('utf-8')))
print(f'공매도 이력 {len(tk)}종목, {len(S)}줄', (S['결제일'].min(), S['결제일'].max()) if len(S) else '', '|', ' · '.join(rep[:40]))
