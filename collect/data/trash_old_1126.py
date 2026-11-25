"""일회용(11/26 의장 "드라이브에 옛 사본 파일 삭제"): 10년치 데이터베이스로 합친 뒤 쓰지 않는 옛 사본 파일을 휴지통으로(30일 뒤 자동으로 비워짐).
드라이브 창구(Apps Script)의 'trash' 기능을 씀. 다 되면 이 파일과 trash_old.yml을 지운다."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import drive  # noqa: E402

D = '콜로키움 수집데이터'
KIS = ['00_한투_일봉.csv', '00_한투_주봉.csv', '00_한투_월봉.csv', '00_한투_밸류이력.csv', '00_한투_창고상태.csv']
PATHS = ([f'{D}/00_누적/{n}' for n in KIS + ['00_한투_창고_안내.txt', '00_가격이력.csv']]
         + [f'{D}/_옛번호_원본_1125/00_누적/{n}' for n in KIS]
         + [f'{D}/00_퀀트입력/{n}' for n in ('가격2년.csv', '지수2년.csv', '고가2년.csv', '저가2년.csv', '거래량2년.csv',
                                           'PER3년.csv', '퀀트자료.csv', 'forward_log.csv', '아침보고.txt')]
         + [f'{D}/_옛번호_원본_1125/00_퀀트입력/PER3년.csv']
         + [f'{D}/1_data/{n}' for n in ('PER_EPS_주별.csv.gz', '수급_퀀트자료.csv.gz')]
         + [f'{D}/{d}/{d}_히트맵.csv' for d in ('20261111', '20261112', '20261113', '20261114', '20261116', '20261119',
                                                '20261120', '20261121', '20261122', '20261123', '20261124', '20261125', '20261126')])
n = 0
for p in PATHS:
    try:
        k = drive.trash(p)
    except Exception as e:   # noqa: BLE001
        k = f'실패 {e}'
    print(f'{p}\t{k}')
    n += k if isinstance(k, int) else 0
print('휴지통에 넣은 파일', n)
