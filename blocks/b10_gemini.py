# ======================================================================
# [블록 10-제미나이] 제미나이 위원 보고서 — 브리핑(블록 10) 바로 뒤, 올리기(블록 11) 앞
#   하는 일  : 제미나이 무료 API로 제미나이 쪽 위원(국장(밤새 경제 브리핑, 11/5 의장), 미스 밸류(옛 피터)·섹터 데스크, 엘피스)의 오늘 발언을 미리 써 둔다.
#              회의실(클로드)은 이 파일을 고치지 않고 그대로 대독한다(2026-10-29 의장).
#              구글 검색은 쓰지 않는다(무료 한도 429가 잦음, 2026-10-29 의장). 모든 위원이 그날 수집 파일(뉴스 피드 포함)만 본다.
#   읽는 것  : 오늘 _브리핑.txt, _밸류에이션.csv, _DART실적.csv, _SEC실적.csv
#              위원 기준: 드라이브 '페르소나 스토리/위원총괄_Ver.….txt' 최신(창구가 못 열면 저장소 prompts/위원총괄.txt)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_위원_경제브리핑.txt · _위원_피터.txt · _위원_엘피스.txt
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


def _pick_model(exclude=None):
    """키로 쓸 수 있는 모델 중 최신 Flash(정식판 우선). 모델 이름이 해마다 바뀌어 고정하지 않는다.
    exclude를 주면 그 모델을 뺀 다음 후보(과부하 예비, lite도 허용)를 돌려준다."""
    r = requests.get(f'{API}/models', headers={'x-goog-api-key': GEMINI_KEY}, params={'pageSize': 1000}, timeout=60)
    r.raise_for_status()
    skip = ('image', 'tts', 'audio', 'live', 'exp', 'embedding', 'thinking', 'latest') + (() if exclude else ('lite',))
    names = [m['name'].split('/')[-1] for m in r.json().get('models', [])
             if 'generateContent' in m.get('supportedGenerationMethods', [])]
    flash = [n for n in names if n.startswith('gemini-') and 'flash' in n and not any(k in n for k in skip) and n != exclude]

    def key(n):
        ver = re.search(r'gemini-(\d+(?:\.\d+)?)', n)
        return ('preview' not in n, float(ver.group(1)) if ver else 0, -len(n))
    if flash:
        return max(flash, key=key)
    if exclude:
        return None
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
    global GEMINI_MODEL
    prompt = (COMMON.format(day=f'{TODAY[:4]}-{TODAY[4:6]}-{TODAY[6:]}') +
              f'\n[이번에 쓸 위원] {who}\n[할 일]\n{task}\n\n[위원 총괄 — {CARDS_NAME}]\n{CARDS}\n\n[오늘 자료]\n{data}')
    try:
        return _ask(prompt, search)
    except RuntimeError as e:
        # 11/3: 503(수요 과다)로 원고 셋이 모두 빠짐 → 다시 해도 안 되면 다른 Flash 모델로 한 번 더
        if not any(c in str(e) for c in ('503', '500', '429', 'UNAVAILABLE', 'overloaded')) or search:
            raise
        alt = _pick_model(exclude=GEMINI_MODEL)
        if not alt:
            raise
        print(f'  {who}: {GEMINI_MODEL} 실패({str(e)[:60]}) → {alt}로 다시')
        main, GEMINI_MODEL = GEMINI_MODEL, alt
        try:
            return _ask(prompt, search) + f'\n\n(오늘은 {main} 과부하로 {alt}가 썼습니다)'
        finally:
            GEMINI_MODEL = main


NEWS_TASK = '''국장(밤새 경제 브리핑)으로 오늘 회의 첫 발언을 쓴다(2026-11-05 의장: 이름은 그냥 '국장', 수치만 모은다. 뉴스는 의장이 직접 본다).
뉴스·기사·사건 해석은 쓰지 않는다. 브리핑에 있는 수치만 옮긴다. 판정 말·매매 의견도 쓰지 않는다.

형식: 번호 줄마다 짧은 제목, 번호 사이는 빈 줄 두 개.
국장: "
1. 미국 지수: S&P500·나스닥·다우·SOX 종가와 등락률

2. 아시아 지수: 코스피·코스닥·닛케이 (전일)

3. 금리: 미국 2년·10년, 하이일드 스프레드·하이일드 실효수익률

4. 환율: 원달러·엔달러·달러인덱스

5. 원자재: WTI·금·구리

6. 심리: 공포탐욕·VIX

7. 돈의 흐름: ETF 자금 쏠림 상위·하위, 국내 외국인 5일 순매수 상위·하위, MMF 잔고(있으면)

8. 오늘 일정: 브리핑 '일정' 표의 오늘·내일 것만, 확인 칸 그대로
"
브리핑에 없는 수치는 "자료 없음"이라고 쓴다. 지어내지 않는다.'''

PETER_TASK = '''미스 밸류(가치 평가 담당, 2026-11-15 피터에서 개명)로 밸류에이션 보고를 쓰고, 이어서 섹터 데스크 발언을 쓴다.
1) 미스 밸류: 눈에 띄는 종목 3~5개를 한 줄씩. 선정 기준은 PER·PBR의 큰 변화, 실적 발표 직후, 업종 대비 눈에 띄는 수준. PER은 TTM / 최근 분기×4 / 선행 세 칸을 구분해 말한다. 역사적 밴드 데이터는 아직 없으니 "밴드 하단" 같은 말은 쓰지 않는다. 해당이 없으면 "특이 밸류에이션 변화 없음".
   이어서 "데스크 보고 있음/없음" 한 줄.
2) 섹터 데스크 6곳(책임자 미스 세마이, 2026-11-15 의장. 반도체·하드웨어 = 미스 세마이, 빅테크·AI 플랫폼(애플 포함) = 미스터 빅스, 로봇·모빌리티·우주·배터리(테슬라·스페이스X·현대차·현대모비스·삼성SDI·2차전지, 피지컬 AI) = 미스터 로보, 금융·지주 = 미스 파이낸스, 전력·원전·조선·방산 = 마담헤비, 소재·바이오·소비재 = 일라이 존슨):
   담당 종목에 오늘 실적·공시·뉴스(잠정실적 공시 포함)가 브리핑에 있을 때만 그 위원 이름으로 2~3줄. 없으면 그 위원은 이 칸을 쓰지 않는다.
   담당이 아닌 종목은 말하지 않는다(예: 현대모비스는 미스터 로보, 애플은 미스터 빅스).
   실적이 나온 종목은 무엇이 좋았고 무엇이 나빴는지를 숫자로 한 줄씩 말한다(발표 다음 날부터 한 달 추적 대상).
3) 오늘의 한 종목(2026-10-31 의장, 매일): 미스 밸류와 여섯 데스크가 각자 자기 측면(미스 밸류 = 밸류에이션, 데스크 = 담당 업황)에서 한 종목씩 고른다.
   형식: 위원명: "[추천/선호/주목 중 하나] 종목명 — 고른 이유 2~3줄(숫자 포함), 다음에 볼 것 1줄". 콜로키움 100 안에서, 데스크는 담당 범위 안에서 고른다. 위원끼리 겹쳐도 되고 종합하지 않는다.
웹 검색 없이 오늘 자료(자기 DB)만으로 판단한다. 인터넷 수치가 필요하면 "의장 자료 확인 필요"라고만 적는다.'''

ELPIS_TASK = '''엘피스(리오팀, 기회 종합)로 쓴다. 아래 밤새 경제 브리핑·미스 밸류 보고와 브리핑의 공포탐욕·리스크를 보고
"공포 속에 살 만한 기회가 있는가"를 2~3줄로 말한다. 유가·금·환율처럼 사건 판단이 섞인 리스크 항목을 한 줄 덧붙인다.
이어서 오늘의 한 종목(2026-10-31 의장, 매일): 엘피스: "[추천/선호/주목 중 하나] 종목명 — 바깥 위원(기관·외국인·내부자) 매매 측면의 이유 2줄". 자료에 매매 기록이 없으면 '자료에 없음'이라고 쓰고 고른 근거를 밝힌다.
미스 차트(닉스 팀) 보고는 회의에서 듣고 덧붙이므로 여기서는 닉스 판단을 추측하지 않는다.
웹 검색 없이 오늘 자료와 두 위원 원고만 본다.'''

SUNDAY_TASK = '''

[오늘은 일요일: 다음 주 전략 회의]
위 할 일 대신(또는 짧게 줄이고) 다음 세 가지를 쓴다. 각 위원 이름으로, 자기 측면에서만.
① 이번 주 복기 한 줄: 이번 주 자기 판단(또는 자료가 보여 준 것)이 맞았나.
② 다음 주 일정·변수: 실적 발표·경제지표·FOMC 등 브리핑 '일정'에 있는 것(국장은 날짜·시각 순 목록, 다른 위원은 자기 담당 종목 일정만).
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
    plan = [('경제브리핑', '국장', NEWS_TASK, lambda: brief, False),
            ('피터', '미스 밸류 + 섹터 데스크', PETER_TASK,
             lambda: brief + '\n\n[밸류에이션.csv]\n' + _txt('밸류에이션.csv', 30000) +
             '\n\n[DART실적.csv]\n' + _txt('DART실적.csv', 15000) + '\n\n[SEC실적.csv]\n' + _txt('SEC실적.csv', 20000), False),
            ('엘피스', '엘피스', ELPIS_TASK,
             lambda: brief + '\n\n[밤새 경제 브리핑]\n' + out.get('경제브리핑', '(없음)') +
             '\n\n[미스 밸류 보고]\n' + out.get('피터', '(없음)'), False)]
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
