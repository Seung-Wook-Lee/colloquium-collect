# 스튜디오 톰앤수 자료수집 — GitHub Actions에서 매일 실행하는 시작 파일
#   blocks/ 폴더의 블록 파일(b00 ~ b11)을 번호 순서대로 한 공간에서 실행한다(코랩에서 칸을 위에서부터 돌리는 것과 같음).
#   한 블록이 실패해도 다음 블록은 계속 돈다. 블록 0(준비)이 실패하면 거기서 멈춘다.
#   일부만 돌리기: python run.py 0 1 3 4   (블록 0과 11은 항상 포함)
#   이름으로 돌리기: python run.py etfcard  (파일 이름에 그 글자가 든 블록만, 블록 0·2·11은 항상 포함)
import glob, os, re, sys, traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

only = {int(a) for a in sys.argv[1:] if a.isdigit()}
names = [a for a in sys.argv[1:] if not a.isdigit()]
G = {'__name__': '__colloquium__', 'ONLY': sorted(only) or ([-1] if names else []), 'ONLY_NAMES': names}   # 이름 실행도 시험 실행으로 본다
# 11/25 의장 "아침 8시 미국 자료, 저녁 8시 한국 자료": 한투 접속 블록은 저녁 8시 수집(kr_evening.yml)에서만 돈다.
#   b02(밸류에이션)는 아침에도 돌되 한투 대신 전날 저녁 한투 값 + 야후(미국) — b02_kis.py KIS_OFF.
KIS_BLOCKS = {'b09_flow', 'b09_zetfcard', 'b09_etfpdf'}   # 11/26 b09_citadel은 데이터베이스만 읽음(한투 접속 없음)
for path in sorted(glob.glob('blocks/b[0-9][0-9]_*.py')):
    no = int(re.search(r'b(\d\d)_', path).group(1))
    if names and not (no in {0, 2, 11} or any(n in os.path.basename(path) for n in names)):
        continue
    if only and not names and no not in only | {0, 11}:
        continue
    if os.environ.get('KIS_OFF') == '1' and os.path.basename(path)[:-3] in KIS_BLOCKS:
        print(f'\n===== {os.path.basename(path)} — 아침엔 한투 접속 안 함(저녁 8시 수집이 받음) =====', flush=True)
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
