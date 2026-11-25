"""11/25 의장 "역도산을 전부 시타델로 바꿔": 드라이브 파일 이름의 역도산을 시타델로 한 번 옮기는 일회용(끝나면 이 파일과 워크플로를 지움).
옛 이름 파일은 새 이름으로 복사만 하고, 옛 파일 휴지통은 따로(드라이브 창구엔 지우기가 없음). 옮긴 목록을 찍는다."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import drive  # noqa: E402

D = '콜로키움 수집데이터'
top = drive._call({'action': 'list', 'path': D})
folders = [D] + [f"{D}/{x['name']}" for x in top.get('folders', [])]
done = []
for fd in folders:
    for f in drive.ls(fd):
        n = f['name']
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
