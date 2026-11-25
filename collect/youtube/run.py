# 유튜브 → 위원 공부자료 txt (2026-11-14 의장: "유튜브 링크를 구글에게 주고 txt로 바꿔 연구 자료로")
#
# 하는 일
#   1) 의장이 넘긴 링크(youtube/링크.txt, 드라이브 '콜로키움 수집데이터/유튜브/링크.txt', 실행 버튼 칸)를 모은다.
#   2) 정기 채널(youtube/채널.csv)의 새 영상을 채널 RSS로 찾는다(최근 3일 안에 올라온 것만).
#   3) 제미나이 API에 유튜브 주소를 그대로 넘겨 받아쓰기·정리를 받는다(영상을 내려받지 않음, 무료 한도 안).
#   4) RAG 형식 이름 `위원_유튜브_채널_제목_YYYYMMDD.txt`(날짜 = 게시일)로
#      드라이브 '콜로키움 수집데이터/유튜브/위원공부_유튜브/'와 저장소 youtube-data 브랜치(youtube/out/)에 둔다.
#      작업 창은 그 txt를 /mnt/project-files/위원공부/유튜브/ 로 옮긴 뒤 `python rag/build.py`.
#   처리한 영상은 '처리목록.csv'에 남겨 두 번 하지 않는다.
#
# 하지 않는 것
#   - 일본 유튜브: 아야카 상 몫이라 제이미가 맡는다. 위원을 아야카상으로 준 링크·일본 채널은 건너뛴다.
#   - 판단·매매 의견을 보태지 않는다. 영상 속 말만 옮기고 [사실]/[의견]을 나눈다.
#
# 비밀값: GEMINI_API_KEY(필수), DRIVE_URL·DRIVE_TOKEN(있으면 드라이브에도)
import csv, datetime as dt, io, json, os, re, sys, time, xml.etree.ElementTree as ET
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import drive  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get('YT_OUT', os.path.join(HERE, 'out'))           # 결과 txt
STATE = os.path.join(OUT, '처리목록.csv')
DRIVE_DIR = '콜로키움 수집데이터/유튜브'
KEY = os.environ.get('GEMINI_API_KEY', '').strip()
API = 'https://generativelanguage.googleapis.com/v1beta'
MODELS = [m for m in os.environ.get('YT_MODELS', 'gemini-3.5-flash-lite,gemini-3-flash-preview').split(',') if m]
MAX_VIDEOS = int(os.environ.get('YT_MAX', '8'))          # 한 번 실행에 최대 몇 개(무료 한도 보호)
RSS_DAYS = int(os.environ.get('YT_DAYS', '3'))
SEG_MIN = 30                                               # 긴 영상은 30분씩 잘라 받음
KST = dt.timezone(dt.timedelta(hours=9))
UA = {'User-Agent': 'Mozilla/5.0 (colloquium-collect)', 'Accept-Language': 'ko-KR,ko;q=0.9'}

PERSONAS = {   # rag/config.py 표기와 같게(띄어쓰기 없음). 아야카상은 일부러 뺌(제이미 몫)
    '공통': '여러 분야에 걸친 시황·경제 전반',
    '국장': '간밤 시황·거시 뉴스·정치·지정학',
    '미스밸류': '밸류에이션·기업 실적 전반',   # 옛 피터(11/15 개명)
    '미스세마이': '반도체·하드웨어·메모리·AI 칩',
    '미스터빅스': '빅테크·AI 플랫폼·소프트웨어',
    '미스터로보': '로봇·모빌리티·우주·배터리·전기차',
    '미스파이낸스': '금융·은행·증권·지주',
    '마담헤비': '전력·원전·조선·방산',
    '일라이존슨': '소재·바이오·헬스케어·소비재',
    '미스차트': '차트·기술적 분석',
    '미스시타델': '수급·포지셔닝·ETF 자금·국내 외국인 수급·계절성',
    '리오': '금리·환율·물가·연준·유동성',
    '포보스': '투자 심리·공포탐욕',
    '엘피스': '전문가·자문사의 매매 의견',
}


def now():
    return dt.datetime.now(KST)


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- 영상 주소
def video_id(s):
    m = re.search(r'(?:v=|youtu\.be/|shorts/|live/|embed/)([A-Za-z0-9_-]{11})', s)
    if m:
        return m.group(1)
    return s if re.fullmatch(r'[A-Za-z0-9_-]{11}', s or '') else None


def watch_url(vid):
    return f'https://www.youtube.com/watch?v={vid}'


def page_info(vid):
    """제목·채널·게시일·길이(초)·언어를 영상 페이지에서. 못 읽으면 빈 칸."""
    info = {'title': '', 'channel': '', 'date': '', 'seconds': 0, 'lang': ''}
    try:
        r = requests.get(f'https://www.youtube.com/oembed?url={watch_url(vid)}&format=json', headers=UA, timeout=30)
        if r.ok:
            j = r.json()
            info['title'], info['channel'] = j.get('title', ''), j.get('author_name', '')
    except Exception as e:
        log('  oembed 실패', str(e)[:80])
    try:
        h = requests.get(watch_url(vid), headers=UA, timeout=30).text
        m = re.search(r'"(?:publishDate|uploadDate)":"(\d{4}-\d{2}-\d{2})', h) or \
            re.search(r'itemprop="(?:datePublished|uploadDate)" content="(\d{4}-\d{2}-\d{2})', h)
        if m:
            info['date'] = m.group(1).replace('-', '')
        m = re.search(r'"lengthSeconds":"(\d+)"', h)
        if m:
            info['seconds'] = int(m.group(1))
        m = re.search(r'"defaultAudioLanguage":"([a-zA-Z-]+)"', h)
        if m:
            info['lang'] = m.group(1)
        if not info['title']:
            m = re.search(r'<meta name="title" content="([^"]+)"', h)
            info['title'] = m.group(1) if m else ''
    except Exception as e:
        log('  영상 페이지 실패', str(e)[:80])
    return info


# ---------------------------------------------------------------- 링크 모으기
def parse_link_lines(text, origin):
    """한 줄에 하나: 주소 [위원] [메모]. #으로 시작하면 무시. 위원은 PERSONAS 이름(없으면 제미나이가 고름)."""
    out = []
    for line in (text or '').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        vid = video_id(line.split()[0])
        if not vid:
            continue
        rest = line.split()[1:]
        who = ''
        if rest and rest[0].replace(' ', '') in PERSONAS | {'아야카상': ''}:
            who = rest.pop(0)
        out.append({'vid': vid, 'who': who, 'memo': ' '.join(rest), 'origin': origin})
    return out


def links_from_everywhere():
    items = []
    p = os.path.join(HERE, '링크.txt')
    if os.path.exists(p):
        items += parse_link_lines(open(p, encoding='utf-8').read(), '링크.txt')
    if drive.ready():
        try:
            b = drive.get(f'{DRIVE_DIR}/링크.txt')
            if b:
                items += parse_link_lines(b.decode('utf-8-sig', 'replace'), '드라이브 링크.txt')
        except Exception as e:
            log('  드라이브 링크.txt 못 읽음:', str(e)[:100])
    extra = os.environ.get('YT_URLS', '')
    if extra.strip():
        items += parse_link_lines(extra.replace(',', '\n'), '실행 버튼')
    return items


def channel_id(c):
    """채널.csv의 채널 칸: UC… id 그대로, 아니면 @핸들·주소에서 id를 찾는다."""
    c = c.strip()
    if re.fullmatch(r'UC[A-Za-z0-9_-]{22}', c):
        return c
    url = c if c.startswith('http') else f'https://www.youtube.com/{c if c.startswith("@") else "@" + c}'
    h = requests.get(url, headers=UA, timeout=30).text
    m = re.search(r'"(?:externalId|channelId)":"(UC[A-Za-z0-9_-]{22})"', h) or \
        re.search(r'channel/(UC[A-Za-z0-9_-]{22})', h)
    if not m:
        raise RuntimeError(f'채널 id 못 찾음: {c}')
    return m.group(1)


def channel_new_videos():
    p = os.path.join(HERE, '채널.csv')
    if not os.path.exists(p):
        return []
    items, since = [], now() - dt.timedelta(days=RSS_DAYS)
    ns = {'a': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}
    for row in csv.DictReader(open(p, encoding='utf-8-sig')):
        ch = (row.get('채널') or '').strip()
        if not ch or ch.startswith('#') or (row.get('켜기') or '예').strip() in ('아니오', 'N', 'n', '0'):
            continue
        if (row.get('위원') or '').strip() == '아야카상':
            log(f'  건너뜀(일본은 제이미 몫): {ch}')
            continue
        try:
            cid = channel_id(ch)
            r = requests.get(f'https://www.youtube.com/feeds/videos.xml?channel_id={cid}', headers=UA, timeout=30)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            must = (row.get('제목에_꼭') or '').strip()
            n = 0
            for e in root.findall('a:entry', ns):
                vid = e.findtext('yt:videoId', '', ns)
                link = (e.find('a:link', ns).get('href') if e.find('a:link', ns) is not None else '')
                pub = dt.datetime.fromisoformat(e.findtext('a:published', '', ns).replace('Z', '+00:00'))
                title = e.findtext('a:title', '', ns)
                if pub < since or '/shorts/' in link:
                    continue
                if must and not any(w in title for w in must.split('|')):
                    continue
                items.append({'vid': vid, 'who': (row.get('위원') or '').strip(), 'memo': (row.get('메모') or '').strip(),
                              'origin': f'채널 {row.get("이름") or ch}', 'title': title,
                              'channel': root.findtext('a:title', '', ns),
                              'date': pub.astimezone(KST).strftime('%Y%m%d')})
                n += 1
            log(f'  채널 {row.get("이름") or ch}: 새 영상 {n}개')
        except Exception as e:
            log(f'  채널 {ch} 실패: {str(e)[:120]}')
    return items


# ---------------------------------------------------------------- 제미나이
class Busy(Exception):
    pass


def _post(model, body):
    """503·429·500은 기다렸다 다시(30·60·120·240초). 4xx는 바로 실패."""
    url = f'{API}/models/{model}:generateContent'
    last = ''
    for n, wait in enumerate([30, 60, 120, 240, 0]):
        try:
            r = requests.post(url, headers={'x-goog-api-key': KEY}, json=body, timeout=600)
        except requests.RequestException as e:
            last = str(e)[:150]
        else:
            if r.ok:
                j = r.json()
                c = (j.get('candidates') or [{}])[0]
                txt = ''.join(p.get('text', '') for p in c.get('content', {}).get('parts', []) if not p.get('thought'))
                if txt.strip():
                    return txt.strip(), j.get('usageMetadata', {})
                last = f'빈 답 finishReason={c.get("finishReason")} {json.dumps(j.get("promptFeedback", {}))[:100]}'
            elif r.status_code in (429, 500, 502, 503, 504):
                last = f'{r.status_code} {r.text[:150]}'
            else:
                raise RuntimeError(f'{r.status_code} {r.text[:300]}')
        if wait:
            log(f'    {model} 다시 시도 {n + 1}/4 ({last[:60]}) {wait}초 뒤')
            time.sleep(wait)
    raise Busy(last)


def ask(parts, temp=0.2):
    body = {'contents': [{'role': 'user', 'parts': parts}], 'generationConfig': {'temperature': temp}}
    err = None
    for m in MODELS:
        try:
            txt, use = _post(m, body)
            return txt, m, use
        except Busy as e:
            err = e
            log(f'    {m} 과부하 → 다음 모델')
    raise RuntimeError(f'모든 모델 실패: {err}')


def transcript(vid):
    """유튜브 자막(사람이 단 것 우선, 없으면 자동 자막). [mm:ss] 줄들과 언어. 없거나 막히면 (None, '')."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return None, ''
    try:
        api = YouTubeTranscriptApi()
        tl = api.list(vid)
        tr = None
        for finder in (tl.find_manually_created_transcript, tl.find_generated_transcript):
            try:
                tr = finder(['ko', 'en', 'en-US', 'en-GB'])
                break
            except Exception:
                pass
        if tr is None:
            tr = next(iter(tl))                 # 다른 언어라도 하나
        lines = [f'[{int(x.start) // 60:02d}:{int(x.start) % 60:02d}] {x.text}' for x in tr.fetch()]
        return '\n'.join(lines), tr.language_code
    except Exception as e:
        log('    자막 못 받음:', type(e).__name__, str(e)[:80])
        return None, ''


def video_part(vid, start=None, end=None):
    meta = {'fps': 0.01}                      # 11/14 의장 "오디오만": 화면은 100초에 한 장(사실상 소리만), 2분 반 영상 3,800토큰
    if start is not None:
        meta.update(startOffset=f'{start}s', endOffset=f'{end}s')
    return {'fileData': {'fileUri': watch_url(vid)}, 'videoMetadata': meta}


PROMPT = '''이 유튜브 영상을 투자 위원회의 공부자료로 받아 적는다. 한국어로 쓴다(영상이 외국어여도 한국어로 옮기고 고유명사·티커는 원어 병기).
규칙
- 영상에서 실제로 나온 말·화면 숫자만 쓴다. 영상에 없는 내용, 네 의견, 매매 권유는 보태지 않는다. 확실치 않은 숫자는 '(잘 안 들림)'.
- 사실(발표된 숫자·사건·일정)과 의견(출연자의 전망·주장·추천)을 나눈다. 의견에는 누가 말했는지 붙인다.
- 숫자에는 단위·기준 시점을 붙인다. 시간 표시는 [mm:ss].
- 줄 맨 앞 '■ ' 소제목 아래에 빈 줄로 단락을 나눈다. 인사말·광고·구독 요청은 뺀다.

형식(그대로):
■ 한 줄 요약
(영상 전체를 한두 문장)

■ 핵심 정리
1. 짧은 제목: 내용
(5~10줄)

■ 사실
- [mm:ss] 내용

■ 출연자 의견
- [mm:ss] 누가: 내용

■ 언급 종목·자산
- 종목명(티커): 무슨 맥락으로 나왔는지 한 줄

■ 주요 발언 받아쓰기
[mm:ss] 발언 요지(시간 순, 중요한 대목은 거의 그대로)
'''

PICK = '''아래 영상 정리를 읽고 이 자료를 가장 먼저 공부할 위원 하나를 고른다. 이름만 한 단어로 답한다.
여러 분야에 걸치거나 애매하면 '공통'.
{table}

[영상 정리]
{text}'''


TOKENS = {'n': 0}


def ask_count(parts, temp=0.2):
    txt, model, use = ask(parts, temp)
    TOKENS['n'] += int(use.get('totalTokenCount') or 0)
    return txt, model, use


def summarize(vid, seconds, script=None):
    if script:
        txt, model, use = ask_count([{'text': PROMPT.replace('이 유튜브 영상을', '아래 유튜브 영상 자막을') +
                                      '\n[자막]\n' + script}])
        log(f'    자막으로 정리, 토큰 {use.get("totalTokenCount")}')
        return txt, model
    if seconds and seconds > (SEG_MIN + 10) * 60:
        pieces, model = [], ''
        for s in range(0, seconds, SEG_MIN * 60):
            e = min(seconds, s + SEG_MIN * 60)
            log(f'    구간 {s // 60}~{e // 60}분')
            txt, model, _ = ask_count([video_part(vid, s, e), {'text': PROMPT + f'\n(이번에는 {s // 60}분~{e // 60}분 구간만 받아 적는다. 시간 표시는 영상 전체 기준.)'}])
            pieces.append(f'[{s // 60}분~{e // 60}분 구간]\n{txt}')
        merged = '\n\n'.join(pieces)
        head, model, _ = ask_count([{'text': '아래는 한 영상을 구간별로 받아 적은 것이다. 영상 전체에 대해 다음 두 칸만 새로 쓴다. 새 내용은 보태지 않는다.\n'
                                       '■ 한 줄 요약\n(한두 문장)\n\n■ 핵심 정리\n1. 짧은 제목: 내용\n(5~10줄)\n\n' + merged}])
        return head + '\n\n■ 구간별 받아쓰기\n\n' + merged, model
    txt, model, use = ask_count([video_part(vid), {'text': PROMPT}])
    log(f'    토큰 {use.get("totalTokenCount")}')
    return txt, model


def pick_persona(text):
    table = '\n'.join(f'- {k}: {v}' for k, v in PERSONAS.items())
    try:
        ans, _, _ = ask_count([{'text': PICK.format(table=table, text=text[:6000])}], temp=0)
        ans = re.sub(r'[\s"\'.:]', '', ans)
        for k in PERSONAS:
            if k in ans:
                return k
    except Exception as e:
        log('    위원 고르기 실패', str(e)[:80])
    return '공통'


# ---------------------------------------------------------------- 저장
def clean(s, n):
    s = re.sub(r'[\\/:*?"<>|\r\n\t#]+', ' ', s or '')
    s = re.sub(r'\s+', '', s.replace('_', ' ').strip())   # 이름 안 칸 구분 '_'와 섞이지 않게 띄어쓰기도 없앰
    return s[:n] or '제목없음'


def load_state():
    rows = {}
    if os.path.exists(STATE):
        for r in csv.DictReader(open(STATE, encoding='utf-8-sig')):
            rows[r['영상id']] = r
    elif drive.ready():
        try:
            b = drive.get(f'{DRIVE_DIR}/처리목록.csv')
            if b:
                for r in csv.DictReader(io.StringIO(b.decode('utf-8-sig'))):
                    rows[r['영상id']] = r
        except Exception as e:
            log('  드라이브 처리목록 못 읽음:', str(e)[:100])
    return rows


COLS = ['영상id', '상태', '시도', '파일', '위원', '채널', '제목', '게시일', '길이분', '방식', '토큰', '받은곳', '처리시각', '모델', '메모']


def save_state(rows):
    os.makedirs(OUT, exist_ok=True)
    buf = io.StringIO()
    w = csv.DictWriter(buf, COLS, extrasaction='ignore')
    w.writeheader()
    for r in sorted(rows.values(), key=lambda r: r.get('처리시각', ''), reverse=True):
        w.writerow(r)
    data = buf.getvalue().encode('utf-8-sig')
    open(STATE, 'wb').write(data)
    if drive.ready():
        try:
            drive.put(f'{DRIVE_DIR}/처리목록.csv', data)
        except Exception as e:
            log('  드라이브 처리목록 올리기 실패:', str(e)[:100])


def main():
    if not KEY:
        log('GEMINI_API_KEY 없음 → 끝')
        return 1
    os.makedirs(OUT, exist_ok=True)
    state = load_state()
    todo, seen = [], set()
    for it in links_from_everywhere() + channel_new_videos():
        st = state.get(it['vid'], {})
        if it['vid'] in seen or st.get('상태') in ('완료', '건너뜀') or int(st.get('시도') or 0) >= 3:
            continue
        seen.add(it['vid'])
        todo.append(it)
    log(f'할 일 {len(todo)}개 (한 번에 최대 {MAX_VIDEOS}개)')
    if not todo:
        return 0                               # 10분마다 돌므로 할 일이 없으면 아무것도 쓰지 않는다
    open(os.path.join(HERE, '.changed'), 'w').write('1')
    done = 0
    for it in todo[:MAX_VIDEOS]:
        vid = it['vid']
        TOKENS['n'] = 0
        log(f'■ {vid} ({it["origin"]})')
        info = page_info(vid)
        title = it.get('title') or info['title']
        channel = it.get('channel') or info['channel']
        if not title or not channel:          # 유튜브 페이지를 못 읽었을 때만: 영상에 보이는 제목·채널을 제미나이에게
            try:
                ans, _, _ = ask_count([video_part(vid), {'text': '이 영상 화면·소리에 나온 제목과 채널(진행자) 이름을 "제목|채널" 한 줄로만. 모르면 빈 칸.'}], temp=0)
                t2, _, c2 = ans.strip().splitlines()[0].partition('|')
                title, channel = title or t2.strip(), channel or c2.strip()
            except Exception as e:
                log('    제목 묻기 실패', str(e)[:80])
        date = it.get('date') or info['date'] or now().strftime('%Y%m%d')
        st = state.get(vid, {})
        row = {'영상id': vid, '채널': channel, '제목': title, '게시일': date, '받은곳': it['origin'],
               '처리시각': now().strftime('%Y-%m-%d %H:%M'), '메모': it.get('memo', ''),
               '시도': str(int(st.get('시도') or 0) + 1)}
        script, slang = transcript(vid)
        if it['who'] == '아야카상' or info['lang'].startswith('ja') or (slang.startswith('ja') and not info['lang']):
            row.update(상태='건너뜀', 메모='일본 유튜브는 제이미 몫')
            state[vid] = row
            log('  일본 → 건너뜀')
            continue
        try:
            body, model = summarize(vid, info['seconds'], script)
        except Exception as e:
            row.update(상태='실패', 메모=str(e)[:150])
            state[vid] = row
            log('  실패:', str(e)[:150])
            save_state(state)
            continue
        who = it['who'].replace(' ', '') or pick_persona(body)
        fname = f'{who}_유튜브_{clean(channel, 20)}_{clean(title, 40)}_{date}.txt'
        mins = f'{info["seconds"] // 60}분 {info["seconds"] % 60}초' if info['seconds'] else '모름'
        head = (f'{title}\n'
                f'출처: 유튜브 {channel} · {watch_url(vid)}\n'
                f'게시일: {date[:4]}-{date[4:6]}-{date[6:]} · 길이: {mins}\n'
                f'정리: {now():%Y-%m-%d %H:%M} KST · 제미나이({model}) {"자막(" + slang + ")" if script else "소리"}로 받아쓰기, 판단 없음\n'
                f'위원: {who}{" (의장 지정)" if it["who"] else " (제미나이가 고름)"} · 종류: 유튜브 · 받은 곳: {it["origin"]}\n'
                + (f'의장 메모: {it["memo"]}\n' if it.get('memo') else '')
                + '주의: 영상 속 숫자·의견은 출연자 말이며 그날 수집 데이터가 아니다. 판정에는 쓰지 않는다.\n\n')
        data = (head + body + '\n').encode('utf-8')
        open(os.path.join(OUT, fname), 'wb').write(data)
        if drive.ready():
            try:
                drive.put(f'{DRIVE_DIR}/위원공부_유튜브/{fname}', data)
            except Exception as e:
                log('  드라이브 올리기 실패:', str(e)[:100])
        row.update(상태='완료', 파일=fname, 위원=who, 모델=model, 토큰=str(TOKENS['n']), 방식='자막' if script else '소리', 길이분=str(round(info['seconds'] / 60)))
        log(f'    이 영상 토큰 합계 {TOKENS["n"]:,}')
        state[vid] = row
        save_state(state)
        done += 1
        log(f'  → {fname}')
    save_state(state)
    left = len(todo) - min(len(todo), MAX_VIDEOS)
    log(f'끝: 새 txt {done}개' + (f', 남은 {left}개는 다음 실행에' if left > 0 else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
