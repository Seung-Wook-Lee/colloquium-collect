# ======================================================================
# 뉴스 실험실 — 매일 아침 기사 후보를 모아 제미나이가 1차로 고르고, 의장이 스트림릿에서 쓸 것/버릴 것을 표시한다 (2026-11-14 의장)
#   의장 기준(기자 25년): 시장을 움직이는 건 외신. 국내 발생 뉴스는 연합뉴스 하나로 확인. '단독' 표시는 무시.
#                         국내는 깊이 있는 기획 기사만 위원 공부용. 관급 보도자료는 원문으로.
#   순서: ① 무료 통로에서 24시간 기사 모으기(RSS·GDELT·네이버 API, robots.txt가 막은 주소는 건너뜀, 본문은 긁지 않음)
#         ② 제미나이가 룰북 + 의장 판정 사례를 읽고 후보 약 25건을 고름(쓸 것/버릴 것, 이유 한 줄, 같은 사건 다른 보도로 보강)
#            503·429면 기다렸다 다시, 다른 모델로 한 번 더, 그래도 안 되면 키워드 규칙으로 고르고 '제미나이 실패'라고 적음
#         ③ 드라이브 '콜로키움 수집데이터/뉴스실험실/YYYYMMDD_후보.csv' (의장판정·의장이유 칸은 비워 둠)
#         ④ 의장이 스트림릿 '뉴스 고르기' 화면에서 표시 → 'YYYYMMDD_판정.csv' + '00_판정누적.csv'
#         ⑤ 다음 날 ②가 '00_판정누적.csv'의 사례(특히 의장이 제미나이와 다르게 고른 것)를 읽고 따라 함
#   2~3주 쌓이면 클로드가 판정누적의 이유들을 묶어 news_lab/룰북.txt를 고친다(의장 승인 뒤 머지).
#   실행: python news_lab/run.py   (GitHub Actions '뉴스 실험실'이 매일 06:30 한국 시간에 부른다)
# ======================================================================
import csv, html, io, json, os, re, sys, time, datetime as dt
import urllib.robotparser as rp
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlparse

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import drive  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime.now(KST)
DAY = NOW.strftime('%Y%m%d')
SINCE = NOW - dt.timedelta(hours=int(os.environ.get('NEWS_HOURS', '24')))
UA = 'Mozilla/5.0 (compatible; colloquium-newslab/1.0)'
D_OUT = '콜로키움 수집데이터/뉴스실험실'
LOCAL_OUT = os.path.join(HERE, 'out')
PICK_N = 25                     # 후보 건수(쓸 것 15~18 + 경계선 버릴 것 7~10)
PER_SOURCE = 40                 # 통로 하나에서 받는 최대 건수(블룸버그는 전부)
CASES_DAYS = 30                 # 판정 사례로 읽는 기간
CASES_MAX = 60                  # 제미나이에 주는 사례 최대 건수
GEMINI_API = 'https://generativelanguage.googleapis.com/v1beta'


def log(m):
    print(m, flush=True)


def gdelt(q):
    return ('https://api.gdeltproject.org/api/v2/doc/doc?mode=artlist&format=json&maxrecords=75&sort=datedesc&timespan=24h&query='
            + quote(q))


# (분류, 매체, 주소) — 분류: 외신 / 국내 / 국내 기획(조선 기획 면 등). 고칠 곳.
SOURCES = [
    ('외신', 'Bloomberg', 'https://feeds.bloomberg.com/markets/news.rss'),
    ('외신', 'Bloomberg', 'https://feeds.bloomberg.com/economics/news.rss'),
    ('외신', 'Bloomberg', 'https://feeds.bloomberg.com/technology/news.rss'),
    ('외신', 'Bloomberg', 'https://feeds.bloomberg.com/politics/news.rss'),
    ('외신', 'Bloomberg', 'https://feeds.bloomberg.com/industries/news.rss'),
    ('외신', 'CNBC', 'https://www.cnbc.com/id/100003114/device/rss/rss.html'),
    ('외신', 'CNBC', 'https://www.cnbc.com/id/100727362/device/rss/rss.html'),
    ('외신', 'CNBC', 'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114'),  # 위가 막히면 예비(robots 확인)
    ('외신', 'AP', gdelt('domain:apnews.com sourcelang:english')),      # AP는 RSS를 막아 GDELT 색인으로
    ('외신', 'CNN', gdelt('domain:cnn.com sourcelang:english')),        # CNN 옛 RSS는 2023년에 멈춤
    ('국내', '연합뉴스', 'https://www.yna.co.kr/rss/international.xml'),
    ('국내', '연합뉴스', 'https://www.yna.co.kr/rss/economy.xml'),
    ('국내', '연합뉴스', 'https://www.yna.co.kr/rss/market.xml'),
    ('국내', '매일경제', 'https://www.mk.co.kr/rss/30300018/'),
    ('국내', '매일경제', 'https://www.mk.co.kr/rss/30100041/'),
    ('국내', '조선일보', 'https://www.chosun.com/arc/outboundfeeds/rss/category/economy/?outputType=xml'),
    ('국내', '조선일보', 'https://www.chosun.com/arc/outboundfeeds/rss/category/international/?outputType=xml'),
]
# 네이버 검색 API(키 있을 때만): 국내 언론의 외신 번역 기사 → 블룸버그·AP 기사 보강용
NAVER_QUERIES = ['블룸버그통신', '블룸버그에 따르면', 'AP통신', 'CNBC', 'CNN 보도']
DROP = (r'칼럼|인터뷰|기고|사설|포토|화보|\[인사\]|부고|브랜드평판|사회공헌|봉사|후원|기부|캠페인|시상식|축제|'
        r'로또|연예|드라마|예능|스포츠|날씨|운세|\(Podcast\)|Odd Lots|Opinion')


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def when(s):
    try:
        return parsedate_to_datetime(s).astimezone(KST)
    except Exception:
        try:
            return dt.datetime.strptime(s, '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc).astimezone(KST)
        except Exception:
            return None


_ROBOTS = {}


def allowed(url):
    p = urlparse(url)
    base = f'{p.scheme}://{p.netloc}'
    if base not in _ROBOTS:
        r = rp.RobotFileParser()
        try:
            t = requests.get(base + '/robots.txt', headers={'User-Agent': UA}, timeout=15)
            r.parse(t.text.splitlines() if t.status_code == 200 else [])
        except Exception:
            r.parse([])
        _ROBOTS[base] = r
    return _ROBOTS[base].can_fetch(UA, url)


def fetch(url, tries=3):
    for n in range(tries):
        r = requests.get(url, headers={'User-Agent': UA}, timeout=25)
        if r.status_code == 429 and n < tries - 1:        # GDELT는 5초에 1번
            time.sleep(15 * (n + 1))
            continue
        r.raise_for_status()
        return r


def read_source(kind, media, url):
    r = fetch(url)
    out = []
    if 'gdeltproject' in url:
        for a in r.json().get('articles', []):
            out.append({'분류': kind, '매체': media, '시각': when(a.get('seendate', '')), '제목': clean(a.get('title')),
                        '요약': '', '링크': a.get('url', '')})
        return out
    for it in ET.fromstring(r.content).iter('item'):
        out.append({'분류': kind, '매체': media, '시각': when(it.findtext('pubDate') or ''), '제목': clean(it.findtext('title')),
                    '요약': clean(it.findtext('description'))[:220], '링크': (it.findtext('link') or '').strip()})
    return out


def naver():
    nid, nsec = os.environ.get('NAVER_CLIENT_ID'), os.environ.get('NAVER_CLIENT_SECRET')
    if not (nid and nsec):
        log('  네이버 검색 API: 키 없음(NAVER_CLIENT_ID·NAVER_CLIENT_SECRET) → 건너뜀')
        return []
    ends = [('https://naverapihub.apigw.ntruss.com/search/v1/news', {'X-NCP-APIGW-API-KEY-ID': nid, 'X-NCP-APIGW-API-KEY': nsec}),
            ('https://openapi.naver.com/v1/search/news.json', {'X-Naver-Client-Id': nid, 'X-Naver-Client-Secret': nsec})]
    for base, hdr in ends:
        out = []
        try:
            for q in NAVER_QUERIES:
                r = requests.get(base, headers=hdr, params={'query': q, 'display': 50, 'sort': 'date'}, timeout=20)
                r.raise_for_status()
                for a in r.json().get('items', []):
                    link = a.get('originallink') or a.get('link', '')
                    out.append({'분류': '외신 번역', '매체': urlparse(link).netloc.replace('www.', ''), '시각': when(a.get('pubDate', '')),
                                '제목': clean(a.get('title')), '요약': clean(a.get('description'))[:220], '링크': a.get('link', '')})
            log(f'  네이버 검색 API({base.split("/")[2]}): {len(out)}건')
            return out
        except Exception as e:
            log(f'  네이버 검색 API({base.split("/")[2]}) 실패: {type(e).__name__} {str(e)[:80]}')
    return []


def collect():
    pool, seen = [], set()
    for kind, media, url in SOURCES:
        name = f'{media} {urlparse(url).path[:40]}'
        try:
            if not allowed(url):
                log(f'  [건너뜀] {name}: robots.txt가 막음')
                continue
            got = [x for x in read_source(kind, media, url) if x['시각'] and x['시각'] >= SINCE and x['제목']]
            if media != 'Bloomberg':
                got = got[:PER_SOURCE]
            n0 = len(pool)
            for x in got:
                key = re.sub(r'\W+', '', x['제목'].lower())[:40]
                if key in seen or re.search(DROP, x['제목']):
                    continue
                seen.add(key)
                if media == '조선일보' and re.search(r'\[[^\]]*(X파일|기획|심층|추적|리포트|분석)[^\]]*\]', x['제목']):
                    x['분류'] = '국내 기획'
                pool.append(x)
            log(f'  {name}: 24시간 {len(got)}건, 새로 {len(pool) - n0}건')
        except Exception as e:
            log(f'  [실패] {name}: {type(e).__name__} {str(e)[:80]}')
        if 'gdeltproject' in url:
            time.sleep(6)
    for x in naver():
        key = re.sub(r'\W+', '', x['제목'].lower())[:40]
        if x['시각'] and x['시각'] >= SINCE and key not in seen and not re.search(DROP, x['제목']):
            seen.add(key)
            pool.append(x)
    pool.sort(key=lambda x: x['시각'], reverse=True)
    return pool


# ---------------------------------------------------------------- 판정 사례(의장이 표시한 것)
def read_csv_drive(path):
    try:
        b = drive.get(path) if drive.ready() else None
    except Exception as e:
        log(f'  드라이브 읽기 실패 {path}: {e}')
        b = None
    return list(csv.DictReader(io.StringIO(b.decode('utf-8-sig')))) if b else []


def cases():
    rows = read_csv_drive(f'{D_OUT}/00_판정누적.csv')
    cut = (NOW - dt.timedelta(days=CASES_DAYS)).strftime('%Y%m%d')
    rows = [r for r in rows if r.get('날짜', '') >= cut and r.get('의장판정')]
    # 의장이 제미나이와 다르게 고른 것 먼저(최근 것부터), 그다음 같지만 이유를 적은 것
    diff = [r for r in rows if not r.get('제미나이추천', '').startswith(r['의장판정'])]
    same = [r for r in rows if r not in diff and r.get('의장이유')]
    pick = (sorted(diff, key=lambda r: r['날짜'], reverse=True) + sorted(same, key=lambda r: r['날짜'], reverse=True))[:CASES_MAX]
    log(f'  의장 판정 사례: 전체 {len(rows)}건, 제미나이와 다른 것 {len(diff)}건 → {len(pick)}건 전달')
    return pick, rows


# ---------------------------------------------------------------- 제미나이 1차 고르기
def models():
    key = os.environ.get('GEMINI_API_KEY')
    try:
        r = requests.get(f'{GEMINI_API}/models', headers={'x-goog-api-key': key}, params={'pageSize': 1000}, timeout=60)
        names = [m['name'].split('/')[-1] for m in r.json().get('models', [])
                 if 'generateContent' in m.get('supportedGenerationMethods', [])]
    except Exception:
        names = []
    skip = ('image', 'tts', 'audio', 'live', 'exp', 'embedding', 'thinking', 'latest')

    def ver(n):
        m = re.search(r'gemini-(\d+(?:\.\d+)?)', n)
        return float(m.group(1)) if m else 0
    flash = sorted([n for n in names if n.startswith('gemini-') and 'flash' in n and not any(k in n for k in skip)],
                   key=lambda n: ('preview' not in n, 'lite' not in n, ver(n)), reverse=True)
    return flash[:2] + ['gemini-flash-latest'] + flash[2:] + ['gemini-2.5-flash', 'gemini-2.5-flash-lite']


def ask_gemini(prompt):
    """JSON 답. 429·500·503은 20·40초 기다렸다 다시, 그래도 안 되면 다음 모델(최대 4개). 다 안 되면 None"""
    key = os.environ.get('GEMINI_API_KEY')
    if not key:
        log('  제미나이 키 없음 → 키워드 규칙으로')
        return None, ''
    tried = []
    for m in models():
        if m in tried or len(tried) >= 4:
            continue
        tried.append(m)
        for n in range(3):
            try:
                r = requests.post(f'{GEMINI_API}/models/{m}:generateContent', headers={'x-goog-api-key': key}, timeout=150,
                                  json={'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
                                        'generationConfig': {'temperature': 0.2, 'responseMimeType': 'application/json'}})
                if r.status_code in (429, 500, 502, 503, 504) and n < 2:
                    log(f'  제미나이 {m} {r.status_code} → {20 * (n + 1)}초 뒤 다시')
                    time.sleep(20 * (n + 1))
                    continue
                r.raise_for_status()
                txt = ''.join(p.get('text', '') for p in r.json()['candidates'][0]['content']['parts'])
                txt = re.sub(r'^```(json)?|```$', '', txt.strip()).strip()
                return json.loads(txt), m
            except Exception as e:
                log(f'  제미나이 {m} 실패: {type(e).__name__} {str(e)[:120]}')
                break
    return None, ''


PROMPT = '''너는 '프로젝트 콜로키움' 아침 회의의 뉴스 국장이다. 오늘은 의장에게 올릴 기사 후보를 1차로 고른다.
의장은 25년 경력 기자 출신이다. 아래 [룰북]과 [의장 판정 사례]를 그대로 따른다. 사례가 룰북과 다르면 사례(최근 것)를 따른다.

할 일:
1. [기사 목록]에서 후보 {n}건을 고른다. 그중 15~18건은 '쓸 것', 나머지 7~10건은 쓸지 말지 경계선이라 의장 확인이 필요한 '버릴 것'.
   명백한 잡기사(연예·사건사고·홍보)는 후보에 넣지 않는다.
2. 각 후보에 이유 한 줄(30자 안팎, 시장에 어떤 경로로 영향을 주는지 또는 왜 약한지)을 쓴다. 기사에 없는 숫자를 지어내지 않는다.
3. '보강': 같은 사건을 다룬 목록의 다른 기사 번호(다른 외신, 국내 번역 기사, 연합 보도)를 모두 적는다. 같은 회사·같은 발표·같은 숫자일 때만. 주제만 비슷하면 넣지 않는다.
4. '중요도': 1~5(5 = 오늘 회의에서 꼭 말할 것).
5. 분류는 목록에 적힌 것을 그대로 쓰되, 국내 기사가 깊이 있는 기획이면 '국내 기획'으로 바꾼다(아침 보고가 아니라 위원 공부용).

JSON 배열 하나로만 답하라. 예:
[{{"번호": 12, "추천": "쓸 것", "중요도": 5, "분류": "외신", "이유": "엔비디아 CEO 교체설, 반도체 전체 심리", "보강": [40, 77]}}]

[룰북]
{rules}

[의장 판정 사례] (날짜 | 의장판정 | 제미나이추천 | 매체 | 제목 | 의장이유)
{cases}

[기사 목록] (번호 | 분류 | 매체 | 한국 시각 | 제목 | 요약)
{items}
'''


def keyword_pick(pool):
    keep = (r'(?i)Fed|rate|inflation|CPI|PCE|tariff|Nvidia|chip|semiconductor|AI|oil|Iran|Ukraine|Russia|China|yield|bond|'
            r'earnings|data cent|금리|연준|물가|관세|반도체|엔비디아|유가|이란|우크라|중국|환율|실적|데이터센터')
    score = lambda x: (x['분류'] == '외신') * 2 + bool(re.search(keep, x['제목'] + x['요약'])) * 3 + (x['매체'] == 'Bloomberg')
    ranked = sorted(range(len(pool)), key=lambda i: score(pool[i]), reverse=True)[:PICK_N]
    return [{'번호': i, '추천': '쓸 것' if k < 17 else '버릴 것', '중요도': '', '분류': pool[i]['분류'],
             '이유': '제미나이 실패 — 키워드 규칙으로 고름', '보강': []} for k, i in enumerate(ranked)]


def main():
    log(f'=== 뉴스 실험실 {NOW:%Y-%m-%d %H:%M} (기사 {SINCE:%m-%d %H:%M} 이후) ===')
    pool = collect()
    log(f'모은 기사 {len(pool)}건')
    if not pool:
        log('기사가 없습니다. 끝.')
        return
    rules = open(os.path.join(HERE, '룰북.txt'), encoding='utf-8').read()
    pick_cases, _ = cases()
    case_txt = '\n'.join(f"{r['날짜']} | {r['의장판정']} | {r.get('제미나이추천', '')} | {r.get('매체', '')} | {r.get('제목', '')} | {r.get('의장이유', '')}"
                         for r in pick_cases) or '(아직 없음)'
    items = '\n'.join(f"[{i}] {x['분류']} | {x['매체']} | {x['시각']:%m-%d %H:%M} | {x['제목']} | {x['요약'][:160]}"
                      for i, x in enumerate(pool))
    ans, model = ask_gemini(PROMPT.format(n=PICK_N, rules=rules, cases=case_txt, items=items))
    if not isinstance(ans, list) or not ans:
        ans, model = keyword_pick(pool), '키워드 규칙(제미나이 실패)'
    log(f'고른 방식: {model}, 후보 {len(ans)}건')

    rows, used = [], set()
    for a in ans:
        try:
            i = int(a.get('번호'))
        except Exception:
            continue
        if i in used or not 0 <= i < len(pool):
            continue
        used.add(i)
        x = pool[i]
        sup = [pool[j] for j in a.get('보강', []) if isinstance(j, int) and 0 <= j < len(pool) and j != i]
        rows.append({'날짜': DAY, '번호': len(rows) + 1, '분류': a.get('분류') or x['분류'], '매체': x['매체'],
                     '시각': x['시각'].strftime('%m-%d %H:%M'), '제목': x['제목'], '요약': x['요약'],
                     '제미나이추천': a.get('추천', ''), '중요도': a.get('중요도', ''), '제미나이이유': a.get('이유', ''),
                     '보강건수': len(sup), '보강': ' / '.join(f"{s['매체']}: {s['제목']}" for s in sup),
                     '보강링크': ' '.join(s['링크'] for s in sup), '링크': x['링크'], '의장판정': '', '의장이유': ''})
    import ko_translate   # 11/20 의장: 모든 문장은 한글로
    for col in ('제목', '요약'):
        for r, t in zip(rows, ko_translate.translate([r[col] for r in rows], log=log)):
            r[f'{col}(한글)'] = t
    rows.sort(key=lambda r: (r['제미나이추천'] != '쓸 것', -(int(r['중요도']) if str(r['중요도']).isdigit() else 0)))
    for k, r in enumerate(rows, 1):
        r['번호'] = k

    os.makedirs(LOCAL_OUT, exist_ok=True)
    files = {f'{DAY}_후보.csv': rows,
             f'{DAY}_전체.csv': [{'날짜': DAY, '분류': x['분류'], '매체': x['매체'], '시각': x['시각'].strftime('%m-%d %H:%M'),
                                 '제목': x['제목'], '요약': x['요약'], '링크': x['링크']} for x in pool]}
    for name, data in files.items():
        if not data:
            continue
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)
        b = buf.getvalue().encode('utf-8-sig')
        open(os.path.join(LOCAL_OUT, name), 'wb').write(b)
        if drive.ready():
            try:
                drive.put(f'{D_OUT}/{name}', b)
                log(f'  드라이브 올림: {D_OUT}/{name}')
            except Exception as e:
                log(f'  드라이브 올리기 실패 {name}: {e}')
    meta = {'날짜': DAY, '만든시각': NOW.strftime('%Y-%m-%d %H:%M'), '고른방식': model, '모은기사': len(pool),
            '후보': len(rows), '통로별': {}}
    for x in pool:
        meta['통로별'][x['매체']] = meta['통로별'].get(x['매체'], 0) + 1
    b = json.dumps(meta, ensure_ascii=False, indent=1).encode('utf-8')
    open(os.path.join(LOCAL_OUT, f'{DAY}_정보.json'), 'wb').write(b)
    if drive.ready():
        try:
            drive.put(f'{D_OUT}/{DAY}_정보.json', b)
        except Exception as e:
            log(f'  드라이브 올리기 실패 정보: {e}')
    log('\n--- 후보 ---')
    for r in rows:
        log(f"{r['번호']:>2}. [{r['제미나이추천']}·{r['중요도']}] {r['분류']} | {r['매체']} | {r['제목'][:70]}\n      {r['제미나이이유']}"
            + (f"  (보강 {r['보강건수']}건)" if r['보강건수'] else ''))


if __name__ == '__main__':
    main()
