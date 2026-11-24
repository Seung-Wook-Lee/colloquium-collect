"""노르웨이 국부펀드(NBIM) 주식 보유 이력 (11/24 의장 "확보해보시고" — B21 펀드 자체 공시).
출처: nbim.no 'All investments' 화면이 쓰는 공개 파일 https://www.nbim.no/api/investments/v2/{날짜}.json
  (init.json의 details = 1998년부터 연말 + 반기(H1, 6/30) 31개 시점). 전 세계 상장주식 약 9천 종목.
칸: 날짜, 나라(cc), 회사, 코드(eq.vid = 그 나라 거래소 종목 코드, 한국은 6자리), 지분율(%, 의결권 기준 o), 가치USD, 가치NOK, 업종
공시 시점: NBIM은 반기 자료를 8월, 연말 자료를 다음 해 2~3월에 낸다 → 쓰는 쪽(블록)은 그 시점 이후에만 써야 함(공시일 칸에 보수적으로 연말+75일, 6/30+60일).
실행: python fetch_nbim.py <출력 폴더>  → 노르웨이_보유_이력.csv.gz"""
import os
import sys
import time

import pandas as pd
import requests

B = 'https://www.nbim.no/api/investments/v2/'
H = {'User-Agent': 'Mozilla/5.0'}


def main(out):
    ini = requests.get(B + 'init.json', headers=H, timeout=60).json()['data']
    rows = []
    for d in ini['details']:
        dt = pd.Timestamp(d['date'][:10])
        for k in range(3):
            try:
                r = requests.get(f"{B}{d['fileName']}?v={d['v']}", headers=H, timeout=180); r.raise_for_status(); break
            except Exception as e:  # noqa: BLE001
                print('다시', d['fileName'], e); time.sleep(5)
        else:
            print('건너뜀', d['fileName']); continue
        J = r.json(); L = J.get('data', J)
        n = 0
        for x in L:
            eq = x.get('eq')
            if not eq:
                continue
            a = x.get('a') or {}
            rows.append({'날짜': dt.date(), '나라': x.get('cc'), '회사': x.get('n'), '코드': eq.get('vid'),
                         '지분율': eq.get('v', x.get('o')), '가치USD': a.get('e'), '가치NOK': a.get('n'), '업종': eq.get('s')})
            n += 1
        print(d['label'], n)
    D = pd.DataFrame(rows)
    D['공시일'] = [pd.Timestamp(t) + pd.Timedelta(days=60 if pd.Timestamp(t).month == 6 else 75) for t in D['날짜']]
    D['공시일'] = D['공시일'].dt.date
    p = os.path.join(out, '노르웨이_보유_이력.csv.gz')
    D.to_csv(p, index=False, encoding='utf-8-sig')
    print('저장', p, len(D), '줄', D['날짜'].nunique(), '시점', '한국', (D['나라'] == 'KR').sum())


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
