"""11/25 의장 "역도산을 전부 시타델로 바꿔": 드라이브 파일 이름의 역도산을 시타델로 한 번 옮기는 일회용(끝나면 이 파일과 워크플로를 지움).
옛 이름 파일은 새 이름으로 복사만 하고, 옛 파일 휴지통은 따로(드라이브 창구엔 지우기가 없음). 옮긴 목록을 찍는다."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import drive  # noqa: E402

D = '콜로키움 수집데이터'
import datetime as dt
import unicodedata
days = [(dt.date(2026, 11, 7) + dt.timedelta(days=i)).strftime('%Y%m%d') for i in range((dt.date.today() - dt.date(2026, 11, 7)).days + 1)]
folders = [D, f'{D}/00_누적', f'{D}/1_data', f'{D}/1_data/장기', f'{D}/미스터역도산'] + [f'{D}/{d}' for d in days]
done = []
for fd in folders:
    print('폴더', fd, flush=True)
    for f in drive.ls(fd):
        n = unicodedata.normalize('NFC', f['name'])
        if '역도산' not in n:
            continue
        new = n.replace('역도산', '시타델')
        b = drive.get(f'{fd}/{n}')
        if b is None:
            continue
        drive.put(f'{fd}/{new}', b)
        done.append(f'{fd}/{n} -> {new}')
        print('옮김', fd, n, '->', new, flush=True)
print('합계', len(done))
