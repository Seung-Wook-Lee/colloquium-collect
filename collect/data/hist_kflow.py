"""한국 개별주 투자자별 일별 순매수 과거 기록 (11/24 의장 "외국인과 기관 수급은 한투에서 받을 수 없나?" → B19·B14·B22 과거 값).
한투 종목별 투자자매매동향(일별) FHPTJ04160001을 기준일을 앞으로 옮겨 가며 2017-11까지 받는다(이미 받은 날 뒤만 새로 받음).
드라이브 10년치 저장본 칸 '콜로키움 수집데이터/1_data/가격10년_국내수급.csv.gz'(옛 1_data/장기/국내수급_일별) (날짜, 코드, 외국인·기관·개인 순매수 거래대금 백만원 + 종가).
실행: python collect/data/hist_kflow.py [시작 YYYYMMDD]"""
import datetime as dt
import gzip
import io
import os
import sys

import pandas as pd

sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), os.path.dirname(os.path.abspath(__file__))]
import drive  # noqa: E402
import kis  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import px_store as PS  # noqa: E402  11/26 의장: 과거 자료는 10년치 저장본 칸으로
PATH = f'{PS.BASE}/1_data/{PS.name("국내수급")}'   # 옛 자리 1_data/장기/국내수급_일별.csv.gz
START = sys.argv[1] if len(sys.argv) > 1 else '20171101'
COLS = {'frgn_ntby_tr_pbmn': '외국인', 'orgn_ntby_tr_pbmn': '기관', 'prsn_ntby_tr_pbmn': '개인', 'stck_clpr': '종가'}
U = PS.universe(drive)   # 11/26 의장 "하나로 통일해": 유니버스 = 10년치 데이터베이스 칸
codes = sorted(U[(U['시장'] == '한국') & (U['구분'] == '개별주')]['코드'].dropna().str.zfill(6).unique())
old = None
import tempfile  # noqa: E402
PS.fetch(drive, '국내수급', tempfile.mkdtemp())   # 칸이 아직 없으면 옛 파일을 칸으로 옮김
b = drive.get(PATH)
if b:
    old = pd.read_csv(io.BytesIO(b), dtype={'코드': str}, compression='gzip')
rows, first, rep = [], None, []
for code in codes:
    have = old[old['코드'] == code]['날짜'].astype(str) if old is not None else pd.Series(dtype=str)
    stop = max(have) if len(have) and min(have) <= START else START   # 앞쪽이 비었으면 처음부터
    end, got, n = dt.date.today().strftime('%Y%m%d'), 0, 0
    while end > stop and n < 200:
        n += 1
        j = kis._get('/uapi/domestic-stock/v1/quotations/investor-trade-by-stock-daily', 'FHPTJ04160001',
                     {'FID_COND_MRKT_DIV_CODE': 'J', 'FID_INPUT_ISCD': code, 'FID_INPUT_DATE_1': end, 'FID_ORG_ADJ_PRC': '', 'FID_ETC_CLS_CODE': ''})
        out = [o for o in ((j or {}).get('output2') or []) if o.get('stck_bsop_date')]
        if first is None and out:
            first = list(out[0].keys()); print('칸:', first)
        if not out:
            break
        for o in out:
            rows.append(dict(날짜=o['stck_bsop_date'], 코드=code, **{v: kis._f(o.get(k)) or 0.0 for k, v in COLS.items()}))
        got += len(out)
        mn = min(o['stck_bsop_date'] for o in out)
        nxt = (dt.datetime.strptime(mn, '%Y%m%d') - dt.timedelta(days=1)).strftime('%Y%m%d')
        if nxt >= end:
            break
        end = nxt
    rep.append(f'{code} {got}일')
print(f'{len(codes)}종목 받음:', ' · '.join(rep[:60]))
new = pd.DataFrame(rows)
A = pd.concat([old, new]) if old is not None else new
A = A[A['날짜'].astype(str) >= START].drop_duplicates(['날짜', '코드'], keep='last').sort_values(['코드', '날짜'])
drive.put(PATH, gzip.compress(A.to_csv(index=False).encode('utf-8')))
print('드라이브 올림', PATH, len(A), '줄', A['날짜'].min(), '~', A['날짜'].max(), '| 실패', len(kis._ERR))
