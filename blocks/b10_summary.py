# ======================================================================
# [블록 10] 점검 요약·드라이브에 올리기 — 항상 맨 마지막 (새 블록은 이 위에 끼워 넣는다)
#   하는 일  : 블록별 성공·실패 요약을 점검 파일에 적는다.
#              GitHub에서 돌 때는 오늘 폴더의 파일 전부와 00_누적에서 바뀐 파일만 드라이브에 올린다.
#              클로드는 이 점검 파일을 드라이브에서 읽어 수집 상태를 확인한다.
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_수집점검.txt (같은 날 여러 번 돌리면 아래에 이어 씀)
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


if not IN_COLAB:
    # 점검 파일을 먼저 쓰고(올리기 결과 줄은 다음 실행 때 GitHub 로그에서 확인), 전부 올린다
    with open(f'{DAY}/{TODAY}_수집점검.txt', 'a', encoding='utf-8') as f:
        f.write('\n'.join(LOG) + '\n\n')
    n_up, n_fail = _upload()
    print(f'[드라이브 올리기] {n_up}개 | 실패: {", ".join(n_fail) or "없음"}')
    if n_fail:
        FATAL = True        # GitHub 실행 화면에 빨간 X로 보이게
else:
    with open(f'{DAY}/{TODAY}_수집점검.txt', 'a', encoding='utf-8') as f:
        f.write('\n'.join(LOG) + '\n\n')
print('\n=== 점검 요약 ===')
print('\n'.join(LOG))
