# 콜로키움 자료수집 — GitHub Actions에서 매일 실행하는 시작 파일
#   blocks/ 폴더의 블록 파일(b00 ~ b10)을 번호 순서대로 한 공간에서 실행한다(코랩에서 칸을 위에서부터 돌리는 것과 같음).
#   한 블록이 실패해도 다음 블록은 계속 돈다. 블록 0(준비)이 실패하면 거기서 멈춘다.
#   일부만 돌리기: python run.py 0 1 3 4   (블록 0과 10은 항상 포함)
import glob, os, re, sys, traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

only = {int(a) for a in sys.argv[1:] if a.isdigit()}
G = {'__name__': '__colloquium__'}
for path in sorted(glob.glob('blocks/b[0-9][0-9]_*.py')):
    no = int(re.search(r'b(\d\d)_', path).group(1))
    if only and no not in only | {0, 10}:
        continue
    print(f'\n===== {os.path.basename(path)} =====', flush=True)
    try:
        exec(compile(open(path, encoding='utf-8').read(), path, 'exec'), G)
    except Exception as e:
        traceback.print_exc()
        if no == 0:
            sys.exit(f'블록 0(준비) 실패로 중단: {e}')
        if 'log' in G:
            G['log'](f'[{no} {os.path.basename(path)}] 블록 전체 실패: {type(e).__name__} {e}')

sys.exit(1 if G.get('FATAL') else 0)
