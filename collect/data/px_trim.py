"""11/25 의장 "이제 유니버스와 10년치 자료를 매칭시켜. 10년치 자료에서 유니버스에 없는 종목의 기록들은 모두 삭제해."
드라이브 1_data/가격10년_{시가,고가,저가,종가,거래량}.csv.gz에서 최신 유니버스(콜로키움/포트폴리오)에 없는 종목 칸을 지운다.
지수(^GSPC 등, 종목 아님)는 남긴다. 결과 표는 로그에 찍는다. (Actions px_trim.yml, DRIVE_URL·DRIVE_TOKEN)"""
import io
import os
import sys
import tempfile

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import drive  # noqa: E402
import px_store as PS  # noqa: E402

P, D = '콜로키움/포트폴리오', '콜로키움 수집데이터/1_data'
names = sorted(f['name'] for f in drive.ls(P) if f['name'].startswith('콜로키움100_유니버스_') and f['name'].endswith('.csv'))
U = pd.read_csv(io.BytesIO(drive.get(f'{P}/{names[-1]}')), dtype=str, encoding='utf-8-sig')
T = set(U['yfinance 티커'].dropna().astype(str))
print(f'유니버스 {names[-1]}: {len(U)}줄, 티커 {len(T)}개')
tmp = tempfile.mkdtemp()
for k in PS.F:
    b = drive.get(f'{D}/{PS.name(k)}')
    if b:
        open(f'{tmp}/{PS.name(k)}', 'wb').write(b)
B = PS.load(tmp)
before = {k: d.shape[1] for k, d in B.items()}
B2, drop = PS.keep(B, T)
c = B2['Close']
miss = sorted(T - set(c.columns))
print('\n| 파일 | 지우기 전 칸 | 지운 뒤 칸 |')
print('|---|---|---|')
for k in PS.F:
    if k in B:
        print(f'| {PS.name(k)} | {before[k]} | {B2[k].shape[1]} |')
print(f'\n지운 종목 {len(drop)}개: {" ".join(drop)}')
print(f'남은 지수 {[x for x in c.columns if str(x).startswith("^")]}')
print(f'유니버스에 있는데 10년치에 없는 티커 {len(miss)}개: {" ".join(miss)}')
if os.environ.get('DRY') == '1' or not drop:
    print('저장 안 함(DRY 또는 지울 것 없음)')
    sys.exit(0)
for nm in PS.save(B2, tmp):
    drive.put(f'{D}/{nm}', open(f'{tmp}/{nm}', 'rb').read())
    print('드라이브 저장', nm)
