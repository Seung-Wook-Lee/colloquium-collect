# ======================================================================
# 회의실 탭 — 위원들이 말풍선으로 대화하는 정례 회의 화면 (2026-10-29 의장)
#   지명     : 위원 버튼을 누르면 "OO 하세요". 제미나이 위원은 07시 원고를 고치지 않고 그대로 읽고,
#              클로드 위원(닉스 팀·리오·포보스)은 07시 수집 숫자로 그 자리에서 발표한다.
#   질문     : 아래 입력창. 첫머리에 위원 이름을 쓰면 그 위원이, 없으면 '질문 받을 위원'이 답한다.
#   모델     : 제미나이 위원 = 제미나이 무료 API(GEMINI_API_KEY), 클로드 위원 = 클로드 하이쿠(ANTHROPIC_API_KEY)
#              모델을 바꾸려면 Secrets에 GEMINI_MODEL · CLAUDE_MODEL
#   기준     : 드라이브 '페르소나 스토리'의 위원총괄·위원별 txt 최신 Ver(없으면 저장소 prompts/위원총괄.txt)
#   기록     : 대본을 txt로 받거나 드라이브 '콜로키움/오늘의 시장해석/회의록_YYYYMMDD_회의실.txt'로 저장
#   금액     : 포트폴리오 금액은 화면·질문 어디에도 넣지 않는다.
# ======================================================================
import os, re, datetime as dt
from pathlib import Path

import requests
import streamlit as st

import drive

ROOT = Path(__file__).resolve().parent.parent
D_PERSONA = '페르소나 스토리'
GEMINI_API = 'https://generativelanguage.googleapis.com/v1beta'
CLAUDE_MODEL = os.environ.get('CLAUDE_MODEL', '').strip() or 'claude-haiku-5-5'
KST = dt.timezone(dt.timedelta(hours=9))

# 이름, 아바타, 색, AI, 07시 원고 키, 읽는 자료(그날 폴더 파일), 위원별 txt(페르소나 스토리)
MEMBERS = [
    ('뉴스 국장', '📰', '#2f6fb0', 'gemini', '뉴스국장', ['브리핑.txt'], []),
    ('리오', '🧭', '#7b4fb5', 'claude', None, ['매크로체크리스트.csv', '매크로.csv', '리스크.csv'], []),
    ('포보스', '😨', '#c0392b', 'claude', None, ['공포탐욕.csv', '추이.csv'], ['공포탐욕_7개지표_공부']),
    ('클로토', '🧵', '#1b8a5a', 'claude', None, ['닉스.csv', '섹터.csv'], ['닉스_공통', '클로토']),
    ('라케시스', '📏', '#0f7c8c', 'claude', None, ['닉스.csv', '섹터.csv'], ['닉스_공통', '라케시스']),
    ('아트로포스', '✂️', '#8d5524', 'claude', None, ['닉스.csv', '섹터.csv'], ['닉스_공통', '아트로포스']),
    ('피터', '📊', '#b5651d', 'gemini', '피터', ['밸류에이션.csv', 'DART실적.csv', 'SEC실적.csv'], []),
    ('미스 세마이', '💾', '#3949ab', 'gemini', '피터', ['밸류에이션.csv', 'DART실적.csv', 'SEC실적.csv'], []),
    ('미스터 빅스', '🚀', '#00838f', 'gemini', '피터', ['밸류에이션.csv', 'SEC실적.csv'], []),
    ('미스 파이낸스', '🏦', '#6d4c41', 'gemini', '피터', ['밸류에이션.csv', 'DART실적.csv', 'SEC실적.csv'], []),
    ('일라이 존슨', '🧪', '#558b2f', 'gemini', '피터', ['밸류에이션.csv', 'DART실적.csv', 'SEC실적.csv'], []),
    ('엘피스', '🌱', '#2e7d32', 'gemini', '엘피스', ['리스크.csv', '공포탐욕.csv'], []),
]
M = {m[0]: m for m in MEMBERS}
CHAIR = ('의장', '🎩', '#1d2330')

# 클로드 위원이 지명받았을 때 하는 발표 (프로젝트 지침 4장)
OPEN_TASK = {
    '리오': '매크로 체크리스트를 보고한다. 먼저 한 줄 판정 "현금 집행 여건 아님/됨", 이어서 국면의 반대 신호(좋을 때는 나빠질 기미, '
           '나쁠 때는 좋아질 기미) n/7과 항목별 근거. 현금·권한 이야기는 하지 않는다.',
    '포보스': 'CNN Fear & Greed를 보고한다. 종합 점수(전일·1주·1개월 대비) → 7지표를 1 Market Momentum ~ 7 Junk Bond Demand 순서로 '
            '지표마다 한 줄 설명·점수 구간 의미·오늘 값·시장 의미 → 마지막에 시장 분위기 해석 2~3줄. '
            '구간: 0~24 Extreme Fear, 25~44 Fear, 45~55 Neutral, 56~75 Greed, 76~100 Extreme Greed.',
    '클로토': '바닥 진입 신호를 보고한다. 한국→미국→일본, 지수 ETF 먼저. 신호 종목마다 지지·저항, 볼린저, RSI, CCI, 스토캐스틱 슬로우, '
            '이격도, 일목균형표를 일봉·주봉으로 읊고 단계·가점·고점 대비 하락률을 말한 뒤 "제가 볼 때는" 한 줄. 신호가 없으면 "오늘 신호 없음" 한 줄. '
            '이어서 섹터 순환에서 반전 후보 섹터가 있으면 한 줄.',
    '라케시스': '추세·비중 확대 신호를 보고한다. 신호 종목마다 지지·저항, 볼린저, RSI, CCI, 스토캐스틱 슬로우, 이격도, 일목균형표를 '
              '일봉·주봉으로 읊고 판단. 넥라인 +5%를 넘은 종목은 "늦은 자리"로 표시. 없으면 "오늘 신호 없음" 한 줄. 섹터 순환에서 추세 강한 섹터 한 줄.',
    '아트로포스': '과열 분할 매도·붕괴 경고를 보고한다. 신호 종목마다 지지·저항, 볼린저, RSI, CCI, 스토캐스틱 슬로우, 이격도, 일목균형표를 '
               '일봉·주봉으로 읊고 판단. 붕괴 신호는 "주의 깊게 지켜봐야 한다"는 경고와 근거로만. 손절가·정리선은 말하지 않는다. '
               '없으면 "오늘 신호 없음" 한 줄. 섹터 순환에서 과열·꺾임 섹터 한 줄.',
}

COMMON = '''너는 '프로젝트 콜로키움' 아침 정례 회의의 위원 {who}이다. 의장은 Tommy다. 지금 회의실 웹 화면에서 의장과 실시간으로 대화한다.
아래 [위원 총괄]의 공통 규칙과 네 위원 카드, [위원별 기준]을 따른다.
- 한국어로 답한다(Fear & Greed 지표명만 영어). 너는 {who}로서 말한다. "클로드", "제미나이", "AI"라고 말하지 않는다.
- 대본 형식이 아니라 말풍선에 들어갈 본문만 쓴다(앞에 "{who}:"를 붙이지 않는다). 인사말 없이 바로 본론.
- 숫자는 [오늘 자료]에 있는 것만 쓴다. 없으면 "데이터 없음". 룰북에 없는 기준은 지어내지 않는다("룰 미정", 제안은 "룰 제안(의장 승인 필요)").
- 자기 영역만 말한다. 다른 위원 영역이면 "그건 OO 위원 영역입니다"라고 한 줄로 넘긴다.
- 매수·매도 결정, 손절가, 금액은 말하지 않는다. "판단은 의장님 몫입니다", "권한은 없습니다" 같은 말은 하지 않는다.
- 의견은 "제가 볼 때는…"처럼 적극적으로 낸다. 통계는 '중앙값'으로 쓴다. 질문에는 짧게(10줄 안쪽) 답한다.
- 오늘 날짜: {day} (한국 시간). 자료 기준: 오늘 07시 자동 수집.
'''


# ---------------------------------------------------------------- 기준·자료
@st.cache_data(ttl=3600, show_spinner=False)
def persona_files():
    """페르소나 스토리 폴더의 txt 이름 목록 (창구가 못 열면 빈 목록)"""
    try:
        return sorted(f['name'] for f in drive.ls(D_PERSONA) if f['name'].endswith('.txt'))
    except Exception:
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def persona(stem):
    """'위원총괄' → 드라이브 최신 '위원총괄_Ver.….txt' 내용 (없으면 저장소 prompts 사본, 그것도 없으면 '')"""
    names = [n for n in persona_files() if n.startswith(f'{stem}_Ver.')]
    if names:
        try:
            b = drive.get(f'{D_PERSONA}/{names[-1]}')
            if b:
                return names[-1], b.decode('utf-8', errors='replace')
        except Exception:
            pass
    p = ROOT / 'prompts' / f'{stem}.txt'
    return (f'prompts/{stem}.txt', p.read_text(encoding='utf-8')) if p.exists() else (stem, '')


def day_text(blob, day, name, limit=25000):
    b = blob(day, name)
    return b.decode('utf-8-sig', errors='replace')[:limit] if b else f'({day}_{name} 없음)'


def script(blob, day, key):
    """07시 제미나이 원고 본문 (머리 3줄 뺌). 없으면 None"""
    b = blob(day, f'위원_{key}.txt')
    if not b:
        return None
    t = b.decode('utf-8', errors='replace').strip()
    return t.split('\n\n', 1)[1].strip() if t.startswith('[') and '\n\n' in t else t


def desk_part(text, name):
    """피터 원고에서 해당 섹터 데스크 문단만"""
    out, on = [], False
    for line in text.splitlines():
        head = re.match(r'\s*\**\s*([가-힣A-Za-z ]+?)\s*\**\s*:', line)
        if head:
            on = head.group(1).strip() == name
        if on:
            out.append(line)
    return '\n'.join(out).strip()


def build_prompt(blob, day, name, transcript, ask):
    _, _, _, ai, key, files, extra = M[name]
    cards_name, cards = persona('위원총괄')
    own = '\n\n'.join(f'[{s}]\n{t}' for s in extra for _, t in [persona(s)] if t)
    data = '\n\n'.join(f'[{f}]\n{day_text(blob, day, f)}' for f in files)
    if ai == 'gemini' and key:
        s = script(blob, day, key)
        if s:
            data += f'\n\n[오늘 07시 내 원고]\n{s}'
    system = (COMMON.format(who=name, day=f'{day[:4]}-{day[4:6]}-{day[6:]}') +
              f'\n[위원 총괄 — {cards_name}]\n{cards}\n\n[위원별 기준]\n{own or "(위원 총괄 카드만)"}\n\n[오늘 자료]\n{data}')
    talk = '\n'.join(f'{w}: {t}' for w, t in transcript[-12:])
    user = (f'[지금까지 회의 대화]\n{talk or "(아직 없음)"}\n\n' if talk else '') + f'[의장]\n{ask}'
    return system, user


# ---------------------------------------------------------------- 모델 부르기
def secret(k):
    v = os.environ.get(k, '').strip()
    if not v:
        try:
            v = str(st.secrets.get(k, '')).strip()
        except Exception:
            v = ''
    return v


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def gemini_model(key):
    """키로 쓸 수 있는 최신 Flash (블록 10-제미나이와 같은 고르기)"""
    if secret('GEMINI_MODEL'):
        return secret('GEMINI_MODEL')
    r = requests.get(f'{GEMINI_API}/models', headers={'x-goog-api-key': key}, params={'pageSize': 1000}, timeout=60)
    r.raise_for_status()
    skip = ('lite', 'image', 'tts', 'audio', 'live', 'exp', 'embedding', 'thinking', 'latest')
    names = [m['name'].split('/')[-1] for m in r.json().get('models', [])
             if 'generateContent' in m.get('supportedGenerationMethods', [])]
    flash = [n for n in names if n.startswith('gemini-') and 'flash' in n and not any(k in n for k in skip)]

    def rank(n):
        ver = re.search(r'gemini-(\d+(?:\.\d+)?)', n)
        return ('preview' not in n, float(ver.group(1)) if ver else 0, -len(n))
    return max(flash, key=rank) if flash else 'gemini-flash-latest'


def ask_gemini(system, user):
    key = secret('GEMINI_API_KEY')
    if not key:
        raise RuntimeError('스트림릿 Secrets에 GEMINI_API_KEY가 없습니다.')
    body = {'systemInstruction': {'parts': [{'text': system}]},
            'contents': [{'role': 'user', 'parts': [{'text': user}]}],
            'generationConfig': {'temperature': 0.4}}
    r = requests.post(f'{GEMINI_API}/models/{gemini_model(key)}:generateContent',
                      headers={'x-goog-api-key': key}, json=body, timeout=180)
    if r.status_code == 429:
        raise RuntimeError('제미나이 무료 한도에 걸렸습니다. 1분쯤 뒤에 다시 물어봐 주세요.')
    r.raise_for_status()
    parts = r.json()['candidates'][0]['content']['parts']
    return ''.join(p.get('text', '') for p in parts).strip()


def ask_claude(system, user):
    if not secret('ANTHROPIC_API_KEY'):
        raise RuntimeError('스트림릿 Secrets에 ANTHROPIC_API_KEY가 없습니다.')
    import anthropic
    client = anthropic.Anthropic(api_key=secret('ANTHROPIC_API_KEY'))
    resp = client.messages.create(
        model=CLAUDE_MODEL, max_tokens=4000,
        system=[{'type': 'text', 'text': system, 'cache_control': {'type': 'ephemeral'}}],   # 룰북·자료는 캐시
        output_config={'effort': 'low'},
        messages=[{'role': 'user', 'content': user}])
    if resp.stop_reason == 'refusal':
        raise RuntimeError('답변이 거절되었습니다. 질문을 바꿔 다시 물어봐 주세요.')
    return ''.join(b.text for b in resp.content if b.type == 'text').strip()


def speak(blob, day, name, ask, transcript):
    system, user = build_prompt(blob, day, name, transcript, ask)
    return (ask_claude if M[name][3] == 'claude' else ask_gemini)(system, user)


def opening(blob, day, name, transcript):
    """지명받았을 때 첫 발표. 제미나이 위원은 07시 원고 그대로."""
    ai, key = M[name][3], M[name][4]
    if ai == 'gemini':
        s = script(blob, day, key)
        if s is None:
            return f'오늘 07시 원고가 없습니다({day}_위원_{key}.txt). 질문을 주시면 바로 답하겠습니다.'
        if name not in ('피터', '뉴스 국장', '엘피스'):
            return desk_part(s, name) or '오늘 담당 종목에 실적·공시·뉴스가 없어 보고할 것이 없습니다.'
        return s
    cache = st.session_state.setdefault('mt_open', {})
    if (day, name) not in cache:            # 같은 날 같은 위원 발표는 한 번만 부른다(비용)
        cache[(day, name)] = speak(blob, day, name, f'{name} 하세요. ' + OPEN_TASK[name], transcript)
    return cache[(day, name)]


# ---------------------------------------------------------------- 화면
CSS = '''<style>
.mt-roster{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 10px}
.mt-tag{display:inline-block;font-size:.72rem;padding:1px 7px;border-radius:9px;margin-left:6px;
  background:rgba(127,127,127,.15);vertical-align:middle}
.mt-name{font-weight:700}
</style>'''


def bubble(who, text):
    av, color, ai = (CHAIR[1], CHAIR[2], '') if who == '의장' else (M[who][1], M[who][2], M[who][3])
    tag = {'claude': '클로드', 'gemini': '제미나이'}.get(ai, '')
    with st.chat_message('user' if who == '의장' else who, avatar=av):
        st.markdown(f'<span class="mt-name" style="color:{color}">{who}</span>'
                    + (f'<span class="mt-tag">{tag}</span>' if tag else ''), unsafe_allow_html=True)
        st.markdown(text)


def who_in(text):
    """질문 첫머리의 위원 이름 (예: '클로토, 삼성전자는?')"""
    t = text.strip()
    for name in sorted(M, key=len, reverse=True):
        for alias in {name, name.replace(' ', '')}:
            if t.startswith(alias):
                return name, t[len(alias):].lstrip(' ,:·님씨은는').strip() or t
    return None, t


def render(day, blob):
    st.markdown(CSS, unsafe_allow_html=True)
    log = st.session_state.setdefault('mt_log', {}).setdefault(day, [])

    st.caption('위원을 누르면 "OO 하세요"로 지명합니다. 질문은 아래 입력창에, 첫머리에 위원 이름을 쓰면 그 위원이 답합니다. '
               '제미나이 위원은 07시 원고를 그대로 읽고, 클로드 위원은 07시 수집 숫자로 그 자리에서 발표합니다.')
    for row in (MEMBERS[:6], MEMBERS[6:]):
        cols = st.columns(len(row))
        for c, (name, av, *_rest) in zip(cols, row):
            if c.button(f'{av} {name}', key=f'mt_btn_{name}', width='stretch'):
                st.session_state['mt_call'] = name

    call = st.session_state.pop('mt_call', None)
    if call:
        log.append(('의장', f'{call} 하세요.'))
        with st.spinner(f'{call} 발표 준비 중…'):
            try:
                log.append((call, opening(blob, day, call, log[:-1])))
            except Exception as e:
                log.append((call, f'(지금 발표를 불러오지 못했습니다: {str(e)[:200]})'))
        st.session_state['mt_to'] = call

    for who, text in log:
        bubble(who, text)
    if not log:
        st.info('아직 발언이 없습니다. 뉴스 국장부터 지명해 보세요.')

    names = [m[0] for m in MEMBERS]
    a, b, c = st.columns([2, 1, 1])
    to = a.selectbox('질문 받을 위원 (질문 첫머리에 이름을 쓰면 그 위원)', names,
                     index=names.index(st.session_state.get('mt_to', '뉴스 국장')), key=f'mt_to_sel_{day}')
    script_txt = '\n\n'.join(f'{w}: "{t}"' for w, t in log)
    head = f'[웹 회의실 대본] {day[:4]}-{day[4:6]}-{day[6:]} 정례 회의\n저장: {dt.datetime.now(KST):%Y-%m-%d %H:%M} KST\n\n'
    b.download_button('대본 txt 받기', (head + script_txt).encode('utf-8'), file_name=f'회의록_{day}_회의실.txt',
                      mime='text/plain', width='stretch', disabled=not log)
    if c.button('드라이브에 회의록 저장', width='stretch', disabled=not log):
        try:
            drive.put(f'콜로키움/오늘의 시장해석/회의록_{day}_회의실.txt', (head + script_txt).encode('utf-8'))
            st.success('드라이브 콜로키움/오늘의 시장해석/ 에 저장했습니다.')
        except Exception as e:
            st.error(f'저장 실패: {e}')

    q = st.chat_input('의장 질문 (예: 클로토, 삼성전자 바닥 신호는?)')
    if q:
        name, body = who_in(q)
        name = name or to
        log.append(('의장', q))
        try:
            with st.spinner(f'{name} 답변 중…'):
                log.append((name, speak(blob, day, name, body, log[:-1])))
        except Exception as e:
            log.append((name, f'(지금 답하지 못했습니다: {str(e)[:200]})'))
        st.session_state['mt_to'] = name
        st.rerun()
