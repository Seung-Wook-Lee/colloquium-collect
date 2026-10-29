# ======================================================================
# [블록 10-제미나이] 제미나이 위원 보고서 — 브리핑(블록 10) 바로 뒤, 올리기(블록 11) 앞
#   하는 일  : 제미나이 무료 API에 "단순하고 양이 많은 일"만 맡긴다(2026-10-29 21:44 의장 "분석은 클로드").
#              ① 뉴스 국장 원고: 수집 뉴스 피드를 사실·출처·시각으로 요약 → 회의실은 고치지 않고 그대로 읽는다.
#              ② 데스크 자료: 섹터 데스크별 실적·뉴스·가격 사실 목록(판단 없음) → 피터·섹터 데스크·엘피스(클로드)가 이걸 읽고 분석한다.
#              구글 검색은 쓰지 않는다(무료 등급 검색 한도 429가 잦음, 2026-10-29 의장 "자동화 대안").
#              뉴스 국장도 그날 수집한 뉴스 피드(연합뉴스 국제·야후 종목별·CNBC)만 보고 쓴다.
#   읽는 것  : 오늘 _브리핑.txt, _밸류에이션.csv, _DART실적.csv, _SEC실적.csv, _뉴스.csv
#              위원 기준: 드라이브 '페르소나 스토리/위원총괄_Ver.….txt' 최신(창구가 못 열면 저장소 prompts/위원총괄.txt)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_위원_뉴스국장.txt · YYYYMMDD_위원_데스크자료.txt
#   비밀값   : GEMINI_API_KEY (없으면 이 블록은 건너뛴다). 모델을 바꾸려면 GEMINI_MODEL
# ======================================================================
import re, time as _time

GEMINI_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', '').strip()      # 비우면 키로 쓸 수 있는 최신 Flash 모델을 고른다
API = 'https://generativelanguage.googleapis.com/v1beta'
D_PERSONA = '페르소나 스토리'


def _txt(name, limit=60000):
    p = f'{DAY}/{TODAY}_{name}'
    if not os.path.exists(p):
        return f'({TODAY}_{name} 없음)'
    return open(p, encoding='utf-8-sig').read()[:limit]


def _cards():
    """위원총괄 최신 버전 (드라이브 → 저장소 사본 순)"""
    if not IN_COLAB and gdrive.ready():
        try:
            names = sorted(f['name'] for f in gdrive.ls(D_PERSONA)
                           if f['name'].startswith('위원총괄_Ver.') and f['name'].endswith('.txt'))
            if names:
                return names[-1], gdrive.get(f'{D_PERSONA}/{names[-1]}').decode('utf-8')
        except Exception as e:
            print(f'  위원총괄 드라이브 읽기 실패 → 저장소 사본 사용: {e}')
    return 'prompts/위원총괄.txt', open('prompts/위원총괄.txt', encoding='utf-8').read()


def _pick_model():
    """키로 쓸 수 있는 모델 중 최신 Flash(정식판 우선). 모델 이름이 해마다 바뀌어 고정하지 않는다."""
    r = requests.get(f'{API}/models', headers={'x-goog-api-key': GEMINI_KEY}, params={'pageSize': 1000}, timeout=60)
    r.raise_for_status()
    skip = ('lite', 'image', 'tts', 'audio', 'live', 'exp', 'embedding', 'thinking', 'latest')
    names = [m['name'].split('/')[-1] for m in r.json().get('models', [])
             if 'generateContent' in m.get('supportedGenerationMethods', [])]
    flash = [n for n in names if n.startswith('gemini-') and 'flash' in n and not any(k in n for k in skip)]

    def key(n):
        ver = re.search(r'gemini-(\d+(?:\.\d+)?)', n)
        return ('preview' not in n, float(ver.group(1)) if ver else 0, -len(n))
    if flash:
        return max(flash, key=key)
    return 'gemini-flash-latest' if 'gemini-flash-latest' in names else names[0]


def _ask(prompt, search=False):
    body = {'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': 0.3}}
    if search:
        body['tools'] = [{'google_search': {}}]
    url = f'{API}/models/{GEMINI_MODEL}:generateContent'
    for n in range(4):
        try:
            r = requests.post(url, headers={'x-goog-api-key': GEMINI_KEY}, json=body, timeout=180)
            if r.status_code in (429, 500, 503) and n < (1 if search else 3):
                _time.sleep(20 * (n + 1))
                continue
            if 400 <= r.status_code < 500:              # 키·모델 이름 문제는 다시 해도 같다
                raise RuntimeError(f'{r.status_code} {r.text[:150]}')
            r.raise_for_status()
            parts = r.json()['candidates'][0]['content']['parts']
            return ''.join(p.get('text', '') for p in parts).strip()
        except Exception as e:
            if n == 3 or str(e)[:1] == '4' or (search and '429' in str(e)):
                raise RuntimeError(str(e)[:200]) from None
            _time.sleep(10)


COMMON = '''너는 '프로젝트 콜로키움' 아침 정례 회의의 위원이다. 의장은 Tommy다.
아래 [위원 총괄]의 공통 규칙과 네 위원 카드를 따른다. 한국어로 쓰되 Fear & Greed 지표명은 영어 그대로 쓴다.
- 위원은 자기 이름으로 말한다. "제미나이"나 "AI"로 말하지 않는다. 대본 형식: 위원이름: "…"
- 룰 충족/미충족과 근거만 말한다. 매수·매도 결정, 손절가, 금액은 말하지 않는다. "판단은 의장님 몫입니다" 같은 맺음말은 쓰지 않는다.
- 숫자는 아래 오늘 자료에 있는 것만 쓴다. 없으면 "데이터 없음". 룰북에 없는 기준은 지어내지 않는다("룰 미정", 제안은 "룰 제안(의장 승인 필요)").
- 통계는 '중앙값'으로 쓴다. 군더더기 인사말 없이 바로 본론.
- 외부 자문사(자문사 C = 체슬리, 자문사 S = 서재형투자학교) 의견을 쓸 때는 "자문사 C는 ~라고 봅니다"로 출처를 붙이고 자기 의견("제가 볼 때는…")과 나눈다.
- 오늘 날짜: {day} (한국 시간). 자료 기준: 오늘 07시 자동 수집.
'''


def _member(who, task, data, search=False):
    prompt = (COMMON.format(day=f'{TODAY[:4]}-{TODAY[4:6]}-{TODAY[6:]}') +
              f'\n[이번에 쓸 위원] {who}\n[할 일]\n{task}\n\n[위원 총괄 — {CARDS_NAME}]\n{CARDS}\n\n[오늘 자료]\n{data}')
    return _ask(prompt, search)


NEWS_TASK = '''뉴스 국장으로 오늘 회의 첫 발언을 쓴다.
1) 간밤 미국·일본 마감, 금리·환율·원자재(유가·금 등) — 브리핑 숫자 그대로.
2) 오늘의 주요 일정: 브리핑 '오늘 일정'에서 오늘·내일 것을 시각 순으로. 보유 종목은 (보유)를 붙인다.
3) 간밤 뉴스: 브리핑의 연합뉴스 국제·야후 종목별·CNBC 목록에서 시장에 중요한 것 3~5개, 크게 오르내린 보유·관심 종목은 왜 움직였는지.
   사실마다 끝에 (매체, 시각 KST)를 붙인다. 목록에 없는 것은 지어내지 말고 "피드에 없음"이라고 쓴다.
4) 스페이스X·테슬라 뉴스가 있으면 두 종목과 일론 머스크 발언을 함께 본다(피드에 있는 것만).
밸류에이션 판단과 매매 의견은 하지 않는다. 15줄 안팎.'''

DESK_TASK = '''너는 위원이 아니라 자료 정리 담당이다. 판단·의견·평가는 쓰지 않는다(분석은 회의실 위원이 한다, 2026-10-29 의장).
오늘 자료에서 섹터 데스크별로 사실만 모아 목록으로 정리한다.
데스크와 담당 종목은 [위원 총괄]의 9장(조직)을 따른다: 미스 세마이(반도체·하드웨어), 미스터 빅스(빅테크·AI 플랫폼·모빌리티·우주),
미스 파이낸스(금융·지주·전력·산업재·방산), 일라이 존슨(소재·바이오·소비재).
데스크마다:
1) 실적: DART실적·SEC실적·잠정실적 공시에 오늘 새로 나온 담당 종목의 숫자(매출·영업이익·순이익·EPS, 예상치가 있으면 함께)
2) 뉴스: 브리핑의 야후 종목별·CNBC·연합뉴스에서 담당 종목 기사 제목 요약 한 줄씩 (매체, 시각 KST)
3) 가격: 시세에서 담당 종목 중 하루 ±5% 넘게 움직인 것과 52주 고점 대비 -30% 이하인 것
해당이 없으면 그 데스크는 "오늘 자료 없음" 한 줄. 자료에 없는 숫자는 쓰지 않는다. 대본 형식(이름: "…")을 쓰지 않는다.'''

if not GEMINI_KEY:
    log('[10 제미나이 위원] 건너뜀: GEMINI_API_KEY 없음')
else:
    if not GEMINI_MODEL:
        GEMINI_MODEL = _pick_model()
    print(f'  제미나이 모델: {GEMINI_MODEL}')
    CARDS_NAME, CARDS = _cards()
    brief = _txt('브리핑.txt')
    done, fail, out = [], [], {}
    plan = [('뉴스국장', '뉴스 국장', NEWS_TASK, lambda: brief, False),
            ('데스크자료', '자료 정리(섹터 데스크별 사실 목록)', DESK_TASK,
             lambda: brief + '\n\n[밸류에이션.csv]\n' + _txt('밸류에이션.csv', 30000) +
             '\n\n[DART실적.csv]\n' + _txt('DART실적.csv', 15000) + '\n\n[SEC실적.csv]\n' + _txt('SEC실적.csv', 20000) +
             '\n\n[뉴스.csv]\n' + _txt('뉴스.csv', 30000), False)]
    for key, who, task, data, search in plan:
        try:
            note = ''
            try:
                text = _member(who, task, data(), search)
            except RuntimeError as e:
                if not (search and '429' in str(e)):
                    raise
                # 무료 등급은 구글 검색 한도가 작다 → 검색 없이 연합뉴스 목록만으로 다시 쓴다
                note = '(오늘은 웹 검색 한도에 걸려 연합뉴스 목록만으로 썼습니다)\n'
                text = _member(who, task + '\n웹 검색은 오늘 쓸 수 없다. 브리핑의 연합뉴스 목록만 쓴다.', data(), False)
            text = note + text
            out[key] = text
            head = (f'[{who}] {TODAY[:4]}-{TODAY[4:6]}-{TODAY[6:]} 정례 회의 발언 원고\n'
                    f'작성: {stamp()} KST · 제미나이({GEMINI_MODEL}) · 기준 {CARDS_NAME}\n'
                    + ('회의실은 이 원고를 고치지 않고 그대로 읽는다.\n\n' if key == '뉴스국장'
                       else '판단 없는 사실 목록. 피터·섹터 데스크·엘피스(클로드)가 읽고 분석한다.\n\n'))
            with open(f'{DAY}/{TODAY}_위원_{key}.txt', 'w', encoding='utf-8') as f:
                f.write(head + text + '\n')
            done.append(key)
        except Exception as e:
            fail.append(f'{key}({e})')
        _time.sleep(5)                     # 무료 등급 분당 한도 여유
    log(f'[10 제미나이 위원] 완료 {len(done)}명({", ".join(done) or "없음"})' + (f' | 실패: {", ".join(fail)}' if fail else ''))
