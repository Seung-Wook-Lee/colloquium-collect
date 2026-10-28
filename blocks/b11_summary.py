# ======================================================================
# [블록 11] 점검 요약·드라이브에 올리기 — 항상 맨 마지막 (새 블록은 이 위에 끼워 넣는다)
#   하는 일  : 블록별 성공·실패 요약을 점검 파일에 적는다.
#              GitHub에서 돌 때는 오늘 폴더의 파일 전부와 00_누적에서 바뀐 파일만 드라이브에 올린다.
#              클로드는 이 점검 파일을 드라이브에서 읽어 수집 상태를 확인한다.
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_수집점검.txt (같은 날 여러 번 돌리면 아래에 이어 씀)
#              수집데이터/최신_브리핑.pdf · 최신_수집점검.txt · 최신_안내.txt — 날짜 없는 이름으로 매일 덮어쓰는 사본.
#              제미나이 같은 외부 AI가 날짜를 몰라도 매일 같은 이름으로 찾게 하려는 것.
# ======================================================================
def _upload():
    up, fail = 0, []
    files = [(f'{DAY}/{n}', f'{D_DATA}/{TODAY}/{n}') for n in sorted(os.listdir(DAY))]
    for n in sorted(os.listdir(KEEP)):
        local = f'{KEEP}/{n}'
        if SYNC.get(local) != _fp(local):           # 새로 생겼거나 바뀐 누적 파일만
            files.append((local, f'{D_DATA}/00_누적/{n}'))
    for local, remote in files:
        try:
            gdrive.put(remote, open(local, 'rb').read())
            up += 1
        except Exception as e:
            fail.append(f'{os.path.basename(local)}({e})')
    return up, fail


def _latest():
    """날짜 없는 '최신_' 사본을 수집데이터 폴더 바로 아래에 덮어쓴다"""
    names = sorted(os.listdir(DAY))
    guide = (f'콜로키움 최신 수집 안내\n'
             f'기준일: {TODAY[:4]}-{TODAY[4:6]}-{TODAY[6:]} (한국 시간)\n'
             f'만든 시각: {stamp()} KST\n'
             f'이 날짜의 자료 폴더: {D_DATA}/{TODAY}/\n'
             f'먼저 읽을 것: 최신_브리핑.pdf (그날 전체 요약), 최신_수집점검.txt (수집 성공·실패)\n'
             f'세부 숫자 파일(같은 폴더):\n' + ''.join(f'  - {n}\n' for n in names))
    copies = [('최신_안내.txt', guide.encode('utf-8'))]
    for src, dst in ((f'{TODAY}_브리핑.pdf', '최신_브리핑.pdf'), (f'{TODAY}_수집점검.txt', '최신_수집점검.txt')):
        if os.path.exists(f'{DAY}/{src}'):
            copies.append((dst, open(f'{DAY}/{src}', 'rb').read()))
    fail = []
    for name, data in copies:
        try:
            gdrive.put(f'{D_DATA}/{name}', data)
        except Exception as e:
            fail.append(f'{name}({e})')
    return fail


if not IN_COLAB:
    # 점검 파일을 먼저 쓰고(올리기 결과 줄은 다음 실행 때 GitHub 로그에서 확인), 전부 올린다
    with open(f'{DAY}/{TODAY}_수집점검.txt', 'a', encoding='utf-8') as f:
        f.write('\n'.join(LOG) + '\n\n')
    n_up, n_fail = _upload()
    if not ONLY:                # 일부 블록만 돌린 시험 실행은 '최신_' 사본을 덮어쓰지 않는다
        n_fail += _latest()
    print(f'[드라이브 올리기] {n_up}개 | 실패: {", ".join(n_fail) or "없음"}')
    if n_fail:
        FATAL = True        # GitHub 실행 화면에 빨간 X로 보이게
else:
    with open(f'{DAY}/{TODAY}_수집점검.txt', 'a', encoding='utf-8') as f:
        f.write('\n'.join(LOG) + '\n\n')
print('\n=== 점검 요약 ===')
print('\n'.join(LOG))
