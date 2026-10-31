# ======================================================================
# [블록 10-제미나이] 제미나이 위원 보고서 — 브리핑(블록 10) 바로 뒤, 올리기(블록 11) 앞
#   하는 일  : 제미나이 무료 API로 제미나이 쪽 위원(뉴스 국장, 피터·섹터 데스크, 엘피스)의 오늘 발언을 미리 써 둔다.
#              회의실(클로드)은 이 파일을 고치지 않고 그대로 대독한다(2026-10-29 의장).
#              뉴스 국장만 구글 검색을 켠다(웹 검색은 뉴스 국장만 허용). 나머지는 그날 수집 파일만 본다.
#   읽는 것  : 오늘 _브리핑.txt, _밸류에이션.csv, _DART실적.csv, _SEC실적.csv
#              위원 기준: 드라이브 '페르소나 스토리/위원총괄_Ver.….txt' 최신(창구가 못 열면 저장소 prompts/위원총괄.txt)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_위원_뉴스국장.txt · _위원_피터.txt · _위원_엘피스.txt
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
3) 간밤 국제 뉴스: 브리핑 '간밤 국제 뉴스'·'간밤 종목 뉴스'·'간밤 미국 뉴스'·'간밤 한국 종목 뉴스'·'간밤 일본 종목 뉴스'·'아침 정리 기사'에서 시장에 중요한 것 3~5개, 끝에 (매체, 시각) 표기. 목록에 없는 큰 뉴스는 구글 검색으로 보충하되 출처와 시각(한국 시간)을 붙인다.
4) 스페이스X·테슬라 뉴스가 있으면 두 종목과 일론 머스크 발언(X 포함)을 함께 확인한다.
5) 오늘의 한 종목(2026-10-31 의장, 매일): 맨 끝에 뉴스 국장: "[주목] 종목명 — 간밤 뉴스·일정에서 고른 이유 2줄(매체, 시각)" 한 종목. 콜로키움 100 안에서.
밸류에이션 판단과 매매 의견은 하지 않는다. 15줄 안팎.'''

PETER_TASK = '''피터(산업분석 데스크장)로 밸류에이션 보고를 쓰고, 이어서 섹터 데스크 발언을 쓴다.
1) 피터: 눈에 띄는 종목 3~5개를 한 줄씩. 선정 기준은 PER·PBR의 큰 변화, 실적 발표 직후, 업종 대비 눈에 띄는 수준. PER은 TTM / 최근 분기×4 / 선행 세 칸을 구분해 말한다. 역사적 밴드 데이터는 아직 없으니 "밴드 하단" 같은 말은 쓰지 않는다. 해당이 없으면 "특이 밸류에이션 변화 없음".
   이어서 "데스크 보고 있음/없음" 한 줄.
2) 섹터 데스크 6곳(반도체·하드웨어 = 미스 세마이, 빅테크·AI 플랫폼(애플 포함) = 미스터 빅스, 로봇·모빌리티·우주·배터리(테슬라·스페이스X·현대차·현대모비스·삼성SDI·2차전지, 피지컬 AI) = 미스터 로보, 금융·지주 = 미스 파이낸스, 전력·원전·조선·방산 = 마담 중공업, 소재·바이오·소비재 = 일라이 존슨):
   담당 종목에 오늘 실적·공시·뉴스(잠정실적 공시 포함)가 브리핑에 있을 때만 그 위원 이름으로 2~3줄. 없으면 그 위원은 이 칸을 쓰지 않는다.
   담당이 아닌 종목은 말하지 않는다(예: 현대모비스는 미스터 로보, 애플은 미스터 빅스).
   실적이 나온 종목은 무엇이 좋았고 무엇이 나빴는지를 숫자로 한 줄씩 말한다(발표 다음 날부터 한 달 추적 대상).
3) 오늘의 한 종목(2026-10-31 의장, 매일): 피터와 다섯 데스크가 각자 자기 측면(피터 = 밸류에이션, 데스크 = 담당 업황)에서 한 종목씩 고른다.
   형식: 위원명: "[추천/선호/주목 중 하나] 종목명 — 고른 이유 2~3줄(숫자 포함), 다음에 볼 것 1줄". 콜로키움 100 안에서, 데스크는 담당 범위 안에서 고른다. 위원끼리 겹쳐도 되고 종합하지 않는다.
웹 검색 없이 오늘 자료(자기 DB)만으로 판단한다. 인터넷 수치가 필요하면 "뉴스 국장 확인 필요"라고만 적는다.'''

ELPIS_TASK = '''엘피스(리오팀, 기회 종합)로 쓴다. 아래 뉴스 국장·피터 보고와 브리핑의 공포탐욕·리스크를 보고
"공포 속에 살 만한 기회가 있는가"를 2~3줄로 말한다. 유가·금·환율처럼 사건 판단이 섞인 리스크 항목을 한 줄 덧붙인다.
이어서 오늘의 한 종목(2026-10-31 의장, 매일): 엘피스: "[추천/선호/주목 중 하나] 종목명 — 바깥 위원(기관·외국인·내부자) 매매 측면의 이유 2줄". 자료에 매매 기록이 없으면 '자료에 없음'이라고 쓰고 고른 근거를 밝힌다.
클로토(닉스 팀) 보고는 회의에서 듣고 덧붙이므로 여기서는 닉스 판단을 추측하지 않는다.
웹 검색 없이 오늘 자료와 두 위원 원고만 본다.'''

SUNDAY_TASK = '''

[오늘은 일요일: 다음 주 전략 회의]
위 할 일 대신(또는 짧게 줄이고) 다음 세 가지를 쓴다. 각 위원 이름으로, 자기 측면에서만.
① 이번 주 복기 한 줄: 이번 주 자기 판단(또는 자료가 보여 준 것)이 맞았나.
② 다음 주 일정·변수: 실적 발표·경제지표·FOMC 등 브리핑 '일정'에 있는 것(뉴스 국장은 날짜·시각 순 목록, 다른 위원은 자기 담당 종목 일정만).
③ 다음 주 한 종목: [추천/선호/주목] 종목명 — 이유 2~3줄, 다음 주에 볼 것 1줄.'''

if not GEMINI_KEY:
    log('[10 제미나이 위원] 건너뜀: GEMINI_API_KEY 없음')
else:
    if not GEMINI_MODEL:
        GEMINI_MODEL = _pick_model()
    print(f'  제미나이 모델: {GEMINI_MODEL}')
    CARDS_NAME, CARDS = _cards()
    brief = _txt('브리핑.txt')
    done, fail, out = [], [], {}
    plan = [('뉴스국장', '뉴스 국장', NEWS_TASK, lambda: brief, True),
            ('피터', '피터 + 섹터 데스크', PETER_TASK,
             lambda: brief + '\n\n[밸류에이션.csv]\n' + _txt('밸류에이션.csv', 30000) +
             '\n\n[DART실적.csv]\n' + _txt('DART실적.csv', 15000) + '\n\n[SEC실적.csv]\n' + _txt('SEC실적.csv', 20000), False),
            ('엘피스', '엘피스', ELPIS_TASK,
             lambda: brief + '\n\n[뉴스 국장 보고]\n' + out.get('뉴스국장', '(없음)') +
             '\n\n[피터 보고]\n' + out.get('피터', '(없음)'), False)]
    # 일요일 = 다음 주 전략 회의(2026-10-31 의장 "내일 회의는 다음주 전략을 짜는 쪽으로")
    import datetime as _dt
    if _dt.date(int(TODAY[:4]), int(TODAY[4:6]), int(TODAY[6:])).weekday() == 6:
        plan = [(k, w, t + SUNDAY_TASK, d, s) for k, w, t, d, s in plan]
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
                    f'회의실은 이 원고를 고치지 않고 그대로 읽는다.\n\n')
            with open(f'{DAY}/{TODAY}_위원_{key}.txt', 'w', encoding='utf-8') as f:
                f.write(head + text + '\n')
            done.append(key)
        except Exception as e:
            fail.append(f'{key}({e})')
        _time.sleep(5)                     # 무료 등급 분당 한도 여유
    log(f'[10 제미나이 위원] 완료 {len(done)}명({", ".join(done) or "없음"})' + (f' | 실패: {", ".join(fail)}' if fail else ''))
