# ======================================================================
# 강의 캡처 받아쓰기 — 유료 강의 슬라이드 캡처(그림) → 위원 검색용 txt (2026-11-14 의장)
#   의장은 드라이브 '페르소나 스토리/강의캡처/받는곳/<위원이름>_<출처>_<강의명>/' 폴더에 캡처를 넣기만 한다.
#     예) 받는곳/미스터로보_자문사S_머스크배런콘퍼런스총정리/ 에 그림 100장
#   제미나이(무료)가 한 장씩 읽어 '[슬라이드 129/194] 단원 > 제목' + [사실]/[의견] 으로 받아쓰고,
#   강의 하나 = txt 하나로 '페르소나 스토리/강의캡처/받아쓰기/' 에 올린다(처리한 그림은 처리목록.csv에 적어 다시 안 함).
#   그 txt를 프로젝트 폴더 위원공부/강의/ 로 옮기면(작업 창이 드라이브 커넥터로) build.py가 슬라이드 한 장 = 문단 하나로 색인.
#
#   python rag/lecture.py --drive                      드라이브 받는곳 전부(Actions '강의 캡처 받아쓰기')
#   python rag/lecture.py --local 그림폴더 --이름 미스터로보_자문사S_강의명   (시험·작업 창용, 결과 txt를 출력 폴더에)
#   유료 자료: 결과는 의장 드라이브·프로젝트 폴더에만. 받아쓴 숫자는 추정치로 표시.
# ======================================================================
import argparse, base64, csv, datetime as dt, glob, io, json, os, re, sys, time
import requests

KST = dt.timezone(dt.timedelta(hours=9))
API = 'https://generativelanguage.googleapis.com/v1beta'
KEY = os.environ.get('GEMINI_API_KEY', '').strip() or 'dummy'
MODEL = os.environ.get('LECTURE_MODEL', '').strip()   # 비우면 키로 쓸 수 있는 최신 Flash(07시 블록과 같은 방식)
D_IN, D_OUT = '페르소나 스토리/강의캡처/받는곳', '페르소나 스토리/강의캡처/받아쓰기'
IMG = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}

PROMPT = """너는 투자 강의 슬라이드 받아쓰기 담당이다. 그림은 유료 강의 슬라이드 한 장(캡처)이다.
아래 형식 그대로, 한국어로만 답한다. 설명·인사·코드블록 금지.

[슬라이드 <오른쪽 아래 쪽 번호, 예: 129/194. 없으면 ?>] <단원 번호와 이름> > <슬라이드 제목> > <소제목>
[사실] 슬라이드에 적힌 사건·숫자·발언을 한 줄에 하나씩. 숫자·고유명사는 슬라이드 표기 그대로.
[의견] 슬라이드(또는 인용된 기사·강사)의 평가·전망·해석을 한 줄에 하나씩. 누구의 의견인지 괄호로(예: (기사 평가), (강사 의견), (머스크 발언)).
[표] 표·그래프가 있으면 핵심 숫자만 '항목: 값' 으로 한 줄씩(그래프에서 읽은 값은 끝에 '(그래프 판독, 추정)').
[출처] 슬라이드에 적힌 출처·기관·날짜(없으면 줄 생략)

규칙: 슬라이드에 없는 내용을 보태지 않는다. 안 보이는 글자는 [?]. 강사 얼굴·화면 장식은 무시."""


def pick_model():
    global MODEL
    if MODEL:
        return MODEL
    r = requests.get(f'{API}/models', headers={'x-goog-api-key': KEY}, params={'pageSize': 1000}, timeout=60)
    r.raise_for_status()
    skip = ('image', 'tts', 'audio', 'live', 'exp', 'embedding', 'thinking', 'latest', 'lite')
    names = [m['name'].split('/')[-1] for m in r.json().get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
    flash = [n for n in names if n.startswith('gemini-') and 'flash' in n and not any(k in n for k in skip)]

    def key(n):
        v = re.search(r'gemini-(\d+(?:\.\d+)?)', n)
        return ('preview' not in n, float(v.group(1)) if v else 0, -len(n))
    order = sorted(flash, key=key, reverse=True)
    lite = sorted([n for n in names if n.startswith('gemini-') and 'flash-lite' in n and 'preview' not in n and not any(k in n for k in ('tts', 'image', 'audio', 'live'))], key=key, reverse=True)
    FALLBACK[:] = order[1:3] + lite[:1]          # 과부하(503) 때 갈아탈 예비
    MODEL = order[0] if order else 'gemini-flash-latest'
    print(f'[모델] {MODEL} (예비 {", ".join(FALLBACK)})', flush=True)
    return MODEL


FALLBACK = []


def gemini_read(img_bytes, mime):
    global MODEL
    pick_model()
    body = {'contents': [{'role': 'user', 'parts': [{'text': PROMPT},
                                                     {'inline_data': {'mime_type': mime, 'data': base64.b64encode(img_bytes).decode()}}]}],
            'generationConfig': {'temperature': 0.1}}
    for n in range(6):
        try:
            r = requests.post(f'{API}/models/{MODEL}:generateContent', headers={'x-goog-api-key': KEY}, json=body, timeout=180)
            if r.status_code in (400, 403, 404):
                raise SystemExit(f'제미나이 거절 {r.status_code}: {r.text[:200]}')
            if r.status_code in (429, 500, 502, 503, 504):
                raise RuntimeError(f'{r.status_code} {r.text[:200]}')
            r.raise_for_status()
            parts = r.json()['candidates'][0]['content']['parts']
            return '\n'.join(p.get('text', '') for p in parts).strip()
        except Exception as e:
            if n == 5:
                raise
            if n % 2 == 1 and FALLBACK:                # 두 번 연속 과부하면 예비 모델로
                MODEL = FALLBACK.pop(0)
                print(f'  예비 모델로: {MODEL}', flush=True)
            print(f'  재시도 {n + 1}: {str(e)[:80]}', flush=True)
            time.sleep(10 * (n + 1))


def slide_no(block):
    m = re.match(r'\[슬라이드\s*(\d+)', block)
    return int(m.group(1)) if m else 10 ** 6


def header(name, n):
    who, _, rest = name.partition('_')
    src, _, title = rest.partition('_')
    now = dt.datetime.now(KST)
    return '\n'.join([
        '강의 자료 받아쓰기 — 유료 구독 자료, 밖으로 내보내지 않음(공부 전용)',
        f'출처: {src} · 강의: {title}',
        f'받아쓴 날: {now:%Y-%m-%d} · 받아쓴 이: 제미나이({MODEL}, 캡처 판독 — 숫자는 추정치) · 슬라이드 {n}장',
        f'담당: {who}',
        '규칙: 슬라이드 한 장 = 문단 하나. [사실]은 자료에 적힌 사건·숫자, [의견]은 자료의 평가·해석.', ''])


def build_txt(name, blocks):
    blocks = sorted(blocks, key=slide_no)
    return header(name, len(blocks)) + '\n' + '\n\n'.join(b.strip() for b in blocks) + '\n'


def out_name(name):
    who, _, rest = name.partition('_')
    return f'{who}_강의_{rest}_{dt.datetime.now(KST):%Y%m%d}.txt'


def run_local(folder, name, out_dir):
    files = sorted(p for p in glob.glob(f'{folder}/*') if os.path.splitext(p)[1].lower() in IMG)
    blocks = []
    for p in files:
        print(f'[받아쓰기] {os.path.basename(p)}', flush=True)
        blocks.append(gemini_read(open(p, 'rb').read(), IMG[os.path.splitext(p)[1].lower()]))
    os.makedirs(out_dir, exist_ok=True)
    path = f'{out_dir}/{out_name(name)}'
    open(path, 'w', encoding='utf-8').write(build_txt(name, blocks))
    print(f'저장: {path}')


def run_drive():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import drive as gd
    if not gd.ready():
        raise SystemExit('DRIVE_URL·DRIVE_TOKEN 없음')
    done_raw = gd.get(f'{D_OUT}/처리목록.csv')
    done = list(csv.DictReader(io.StringIO(done_raw.decode('utf-8-sig')))) if done_raw else []
    seen = {(r['강의'], r['그림']) for r in done}
    j = gd._call({'action': 'list', 'path': D_IN})
    names = [f['name'] for f in j.get('folders', [])]          # 창구(Code.gs)가 하위 폴더도 알려 주면 그대로
    if not names:                                                # 옛 창구면 강의목록.txt에서
        names = [l.strip() for l in (gd.get(f'{D_IN}/강의목록.txt') or b'').decode('utf-8-sig').splitlines() if l.strip() and not l.startswith('#')]
    if not names:
        raise SystemExit(f"'{D_IN}' 아래 강의 폴더가 없습니다(옛 창구라면 '{D_IN}/강의목록.txt'에 폴더 이름을 한 줄씩).")
    for name in names:
        imgs = sorted(f['name'] for f in gd.ls(f'{D_IN}/{name}') if os.path.splitext(f['name'])[1].lower() in IMG)
        new = [n for n in imgs if (name, n) not in seen]
        if not new:
            continue
        prev = gd.get(f'{D_OUT}/{name}_누적.json')
        blocks = json.loads(prev.decode()) if prev else []
        for n in new:
            print(f'[{name}] {n}', flush=True)
            blocks.append(gemini_read(gd.get(f'{D_IN}/{name}/{n}'), IMG[os.path.splitext(n)[1].lower()]))
            done.append({'강의': name, '그림': n, '처리시각': f'{dt.datetime.now(KST):%Y-%m-%d %H:%M}'})
            gd.put(f'{D_OUT}/{name}_누적.json', json.dumps(blocks, ensure_ascii=False).encode())   # 끊겨도 이어서
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=['강의', '그림', '처리시각'])
            w.writeheader(); w.writerows(done)
            gd.put(f'{D_OUT}/처리목록.csv', buf.getvalue().encode('utf-8-sig'))
        gd.put(f'{D_OUT}/{out_name(name)}', build_txt(name, blocks).encode())
        print(f'올림: {D_OUT}/{out_name(name)} (슬라이드 {len(blocks)}장)')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--drive', action='store_true')
    ap.add_argument('--local')
    ap.add_argument('--이름', help='<위원이름>_<출처>_<강의명>')
    ap.add_argument('--출력', default='/mnt/project-files/위원공부/강의')
    a = ap.parse_args()
    if a.drive:
        run_drive()
    elif a.local and a.이름:
        run_local(a.local, a.이름, a.출력)
    else:
        ap.error('--drive 또는 --local 그림폴더 --이름 …')
