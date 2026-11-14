# 외신 중심 뉴스 수집 시험(2026-11-14 의장 "블룸버그는 제목만 긁고, 내용은 그걸 인용한 다른 보도로 보강할 수 없나")
# 두 가지를 시험한다. 결과는 실행 로그와 research/out/ 파일로 읽는다.
#   (가) 무료 통로 접속 시험: 언론사 RSS, 구글 뉴스 RSS, GDELT, 네이버 검색 API(키 있으면) — 건수·최신 시각·robots.txt 허용 여부
#   (나) 블룸버그 제목 → 인용 보도 매칭: 국내 번역 기사(블룸버그 인용) + 다른 외신 같은 사건 보도를 짝지어 내용 보강
# 기사 본문은 긁지 않는다(제목·요약·링크만). 비용 0원(제미나이 무료 키, 없으면 단어 겹침으로만 짝짓기).
import csv, datetime as dt, html, json, os, re, time, urllib.robotparser as rp
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
import requests

KST = ZoneInfo('Asia/Seoul')
NOW = dt.datetime.now(KST)
SINCE = NOW - dt.timedelta(hours=24)
UA = 'Mozilla/5.0 (compatible; colloquium-research/1.0)'
OUT = 'research/out'
os.makedirs(OUT, exist_ok=True)
DAY = NOW.strftime('%Y%m%d')
GN = 'https://news.google.com/rss/search?hl={hl}&gl={gl}&ceid={gl}:{hl2}&q='

# 의장 허용 매체(11/10·11/11): 국내 연합뉴스·매일경제·조선일보 / 해외 CNBC·CNN·블룸버그 (+일본 닛케이·NHK·닛칸코교)
OK_MEDIA = r'연합뉴스|매일경제|조선일보|조선비즈|Chosun|CNBC|CNN|Bloomberg|블룸버그|Nikkei|닛케이|NHK'


def gn(q, ko=False):
    from urllib.parse import quote
    return (GN.format(hl='ko', gl='KR', hl2='ko') if ko else GN.format(hl='en-US', gl='US', hl2='en')) + quote(q)


FEEDS = [  # (구분, 이름, 주소)
    ('해외', '블룸버그 Markets', 'https://feeds.bloomberg.com/markets/news.rss'),
    ('해외', '블룸버그 Economics', 'https://feeds.bloomberg.com/economics/news.rss'),
    ('해외', '블룸버그 Technology', 'https://feeds.bloomberg.com/technology/news.rss'),
    ('해외', '블룸버그 Politics', 'https://feeds.bloomberg.com/politics/news.rss'),
    ('해외', '블룸버그 Industries', 'https://feeds.bloomberg.com/industries/news.rss'),
    ('해외', 'CNN Money(옛 RSS)', 'http://rss.cnn.com/rss/money_latest.rss'),
    ('해외', 'CNN World(옛 RSS)', 'http://rss.cnn.com/rss/edition_world.rss'),
    ('해외', 'CNBC Top News', 'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114'),
    ('해외', 'CNBC World', 'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362'),
    ('해외', 'CNBC Economy', 'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258'),
    ('해외', 'Nikkei Asia', 'https://asia.nikkei.com/rss/feed/nar'),
    ('해외', 'AP(직접 RSS 시도)', 'https://apnews.com/index.rss'),
    ('해외', '구글뉴스: 블룸버그', gn('site:bloomberg.com when:1d')),
    ('해외', '구글뉴스: AP', gn('site:apnews.com when:1d')),
    ('해외', '구글뉴스: CNN 경제', gn('site:cnn.com business when:1d')),
    ('해외', '구글뉴스: 로이터(참고)', gn('site:reuters.com when:1d')),
    ('해외', 'GDELT: 블룸버그', 'https://api.gdeltproject.org/api/v2/doc/doc?query=domain:bloomberg.com&mode=artlist&format=json&maxrecords=75&timespan=1d'),
    ('국내', '연합뉴스 국제', 'https://www.yna.co.kr/rss/international.xml'),
    ('국내', '연합뉴스 경제', 'https://www.yna.co.kr/rss/economy.xml'),
    ('국내', '매일경제 전체', 'https://www.mk.co.kr/rss/40300001/'),
    ('국내', '매일경제 국제', 'https://www.mk.co.kr/rss/30300018/'),
    ('국내', '조선일보 전체', 'https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml'),
    ('국내', '조선일보 경제', 'https://www.chosun.com/arc/outboundfeeds/rss/category/economy/?outputType=xml'),
    ('국내', '구글뉴스: 블룸버그 인용(한국어)', gn('블룸버그 when:1d', ko=True)),
    ('국내', '구글뉴스: 연합 기획(한국어)', gn('site:yna.co.kr 기획 when:7d', ko=True)),
]


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


ROBOTS = {}


def robots_ok(url):
    host = urlparse(url)
    base = f'{host.scheme}://{host.netloc}'
    if base not in ROBOTS:
        r = rp.RobotFileParser()
        try:
            t = requests.get(base + '/robots.txt', headers={'User-Agent': UA}, timeout=15)
            r.parse(t.text.splitlines() if t.status_code == 200 else [])
        except Exception:
            r.parse([])
        ROBOTS[base] = r
    return ROBOTS[base].can_fetch(UA, url)


def fetch(url, **kw):
    return requests.get(url, headers={'User-Agent': UA}, timeout=25, **kw)


def items(url):
    """RSS/GDELT → [{시각, 제목, 요약, 매체, 링크}]"""
    r = fetch(url)
    r.raise_for_status()
    out = []
    if 'gdeltproject' in url:
        for a in r.json().get('articles', []):
            out.append({'시각': when(a.get('seendate', '')), '제목': clean(a.get('title')), '요약': '',
                        '매체': a.get('domain', ''), '링크': a.get('url', '')})
        return out, r.status_code
    root = ET.fromstring(r.content)
    for it in root.iter('item'):
        title = clean(it.findtext('title'))
        media = clean(it.findtext('source')) or ''
        if 'news.google.com' in url and ' - ' in title:      # 구글 뉴스 제목 끝 ' - 매체' 떼기
            title, media = title.rsplit(' - ', 1)[0], media or title.rsplit(' - ', 1)[1]
        out.append({'시각': when(it.findtext('pubDate') or ''), '제목': title,
                    '요약': '' if 'news.google.com' in url else clean(it.findtext('description'))[:200],
                    '매체': media, '링크': (it.findtext('link') or '').strip()})
    return out, r.status_code


# ---------------------------------------------------------------- (가) 접속 시험
print(f'=== (가) 무료 통로 접속 시험 {NOW:%Y-%m-%d %H:%M} KST (24시간 안 기사 건수) ===')
access, POOL = [], {}
for kind, name, url in FEEDS:
    row = {'구분': kind, '통로': name, '주소': url, '응답': '', 'robots허용': '', '전체건수': 0, '24시간건수': 0, '최신시각': '', '보기': ''}
    try:
        row['robots허용'] = 'O' if robots_ok(url) else 'X'
        got, code = items(url)
        row['응답'] = code
        fresh = [x for x in got if x['시각'] and x['시각'] >= SINCE]
        row.update({'전체건수': len(got), '24시간건수': len(fresh),
                    '최신시각': max([x['시각'] for x in got if x['시각']], default=None),
                    '보기': ' | '.join(x['제목'][:60] for x in (fresh or got)[:3])})
        row['최신시각'] = row['최신시각'].strftime('%m-%d %H:%M') if row['최신시각'] else ''
        POOL[name] = fresh
    except Exception as e:
        row['응답'] = f'실패 {type(e).__name__}: {str(e)[:80]}'
    access.append(row)
    print(f"[{row['구분']}] {name}: 응답 {row['응답']}, robots {row['robots허용']}, 24시간 {row['24시간건수']}건/전체 {row['전체건수']}, 최신 {row['최신시각']}\n     {row['보기'][:200]}")
    if 'gdeltproject' in url:
        time.sleep(6)    # GDELT는 5초에 1번

# 네이버 검색 API(키가 있을 때만): 국내 언론의 블룸버그 인용 번역 기사 찾기
NAVER = []
nid, nsec = os.environ.get('NAVER_CLIENT_ID'), os.environ.get('NAVER_CLIENT_SECRET')
if nid and nsec:
    for base, hdr in [('https://naverapihub.apigw.ntruss.com/search/v1/news', {'X-NCP-APIGW-API-KEY-ID': nid, 'X-NCP-APIGW-API-KEY': nsec}),
                      ('https://openapi.naver.com/v1/search/news.json', {'X-Naver-Client-Id': nid, 'X-Naver-Client-Secret': nsec})]:
        try:
            r = requests.get(base, headers=hdr, params={'query': '블룸버그', 'display': 100, 'sort': 'date'}, timeout=20)
            print(f'[국내] 네이버 검색 API {base.split("/")[2]}: 응답 {r.status_code}')
            if r.ok:
                for a in r.json().get('items', []):
                    t = when(a.get('pubDate', ''))
                    if t and t >= SINCE:
                        NAVER.append({'시각': t, '제목': clean(a['title']), '요약': clean(a.get('description'))[:200],
                                      '매체': urlparse(a.get('originallink') or a['link']).netloc, '링크': a.get('link')})
                print(f'     24시간 안 블룸버그 인용 {len(NAVER)}건')
                break
        except Exception as e:
            print(f'[국내] 네이버 검색 API 실패 {type(e).__name__}')
else:
    print('[국내] 네이버 검색 API: 키 없음(NAVER_CLIENT_ID·NAVER_CLIENT_SECRET) → 건너뜀')
access.append({'구분': '국내', '통로': '네이버 검색 API(블룸버그)', '주소': 'naver search api', '응답': 'O' if NAVER else ('키 없음' if not nid else '실패'),
               'robots허용': 'API', '전체건수': len(NAVER), '24시간건수': len(NAVER), '최신시각': '', '보기': ' | '.join(x['제목'][:60] for x in NAVER[:3])})

with open(f'{OUT}/news_probe_{DAY}_통로.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(access[0]))
    w.writeheader()
    w.writerows(access)

# ---------------------------------------------------------------- (나) 블룸버그 제목 → 인용 보도 매칭
print('\n=== (나) 블룸버그 제목 → 인용 보도 매칭 ===')
bb, seen = [], set()
for k, v in POOL.items():
    if k.startswith('블룸버그') or k == '구글뉴스: 블룸버그':
        for x in v:
            key = re.sub(r'\W+', '', x['제목'].lower())[:50]
            if key and key not in seen:
                seen.add(key)
                bb.append(x)
bb = sorted(bb, key=lambda x: x['시각'], reverse=True)[:20]
print(f'블룸버그 제목 {len(bb)}건(24시간, 최대 20)')

# 국내 번역·인용 후보: 구글 뉴스(한국어) '블룸버그' + 네이버
ko = POOL.get('구글뉴스: 블룸버그 인용(한국어)', []) + NAVER
for q in ['블룸버그통신', '블룸버그에 따르면']:
    try:
        got, _ = items(gn(f'"{q}" when:1d', ko=True))
        ko += got
    except Exception:
        pass
kseen, kos = set(), []
for x in ko:
    key = re.sub(r'\W+', '', x['제목'])[:40]
    if key not in kseen:
        kseen.add(key)
        kos.append(x)
print(f'국내 블룸버그 인용 후보 {len(kos)}건(그중 허용 매체 {sum(bool(re.search(OK_MEDIA, x["매체"])) for x in kos)}건)')

STOP = set('the a an of to in on for and or as at by with from is are be after amid over its it this that says said new up down more than into how why what who will may could'.split())


def words(t):
    return [w for w in re.findall(r"[A-Za-z0-9$%.']+", t) if w.lower() not in STOP and len(w) > 2]


# 다른 외신 같은 사건: 블룸버그 제목 핵심 단어로 구글 뉴스 검색(블룸버그 제외)
en = {}
for i, x in enumerate(bb):
    key = ' '.join(sorted(words(x['제목']), key=lambda w: (not w[0].isupper(), -len(w)))[:5])
    try:
        got, _ = items(gn(f'{key} -site:bloomberg.com when:2d'))
        en[i] = [g for g in got if 'bloomberg' not in g['매체'].lower()][:8]
    except Exception:
        en[i] = []
    time.sleep(1)


def overlap(a, b):
    A, B = {w.lower() for w in words(a)}, {w.lower() for w in words(b)}
    return len(A & B) / max(1, min(len(A), len(B)))


# 제미나이로 짝짓기(같은 사건인지). 키 없으면 영어는 단어 겹침 0.5 이상, 한국어는 짝짓지 않음
gkey = os.environ.get('GEMINI_API_KEY')
pairs = {}
if gkey and bb:
    try:
        API = 'https://generativelanguage.googleapis.com/v1beta'
        prompt = ('아래 [B]는 블룸버그 기사 제목, [K]는 국내 기사 제목, [E숫자]는 그 블룸버그 기사와 같은 사건일지 모르는 다른 외신 제목이다.\n'
                  '각 B에 대해 같은 사건(같은 회사·같은 발표·같은 숫자)을 다룬 K 번호와 E 번호만 고른다. 비슷한 주제일 뿐이면 고르지 않는다.\n'
                  'JSON 하나로만 답하라: {"0": {"K": [3, 7], "E": [0, 2]}, "1": {"K": [], "E": []}, ...}\n\n')
        prompt += '\n'.join(f'[B{i}] {x["제목"]}' for i, x in enumerate(bb)) + '\n\n'
        prompt += '\n'.join(f'[K{j}] {x["제목"]} ({x["매체"]})' for j, x in enumerate(kos[:150])) + '\n\n'
        for i, lst in en.items():
            prompt += '\n'.join(f'[E{i}-{j}] {g["제목"]} ({g["매체"]})' for j, g in enumerate(lst)) + '\n'
        model = 'gemini-2.5-flash'
        for m in ['gemini-2.5-flash', 'gemini-flash-latest', 'gemini-2.5-flash-lite']:
            r = requests.post(f'{API}/models/{m}:generateContent', headers={'x-goog-api-key': gkey},
                              json={'contents': [{'parts': [{'text': prompt}]}],
                                    'generationConfig': {'responseMimeType': 'application/json', 'temperature': 0}}, timeout=180)
            if r.ok:
                model = m
                break
            time.sleep(5)
        txt = r.json()['candidates'][0]['content']['parts'][0]['text']
        pairs = {int(k): v for k, v in json.loads(txt).items()}
        print(f'제미나이 짝짓기 완료({model})')
    except Exception as e:
        print(f'제미나이 짝짓기 실패 {type(e).__name__}: {str(e)[:120]} → 단어 겹침으로만')

rows = []
for i, x in enumerate(bb):
    p = pairs.get(i, {})
    kk = [kos[j] for j in p.get('K', []) if isinstance(j, int) and j < len(kos)]
    ee = [en[i][j] for j in p.get('E', []) if isinstance(j, int) and j < len(en[i])] if p else \
         [g for g in en[i] if overlap(x['제목'], g['제목']) >= 0.5]
    rows.append({'블룸버그시각': x['시각'].strftime('%m-%d %H:%M'), '블룸버그제목': x['제목'], '블룸버그요약': x['요약'],
                 '국내인용건수': len(kk), '국내허용매체': ' / '.join(f'{k["매체"]}: {k["제목"]}' for k in kk if re.search(OK_MEDIA, k['매체'])),
                 '국내기타매체': ' / '.join(f'{k["매체"]}: {k["제목"]}' for k in kk if not re.search(OK_MEDIA, k['매체'])),
                 '외신같은사건건수': len(ee), '외신같은사건': ' / '.join(f'{g["매체"]}: {g["제목"]}' for g in ee),
                 '링크': x['링크']})
    print(f"\n[B{i}] {x['시각']:%H:%M} {x['제목']}\n     요약: {x['요약'][:120] or '(없음)'}")
    for k in kk:
        print(f"     ↳ 국내 {'★' if re.search(OK_MEDIA, k['매체']) else ' '} {k['매체']}: {k['제목']}")
    for g in ee:
        print(f"     ↳ 외신 {g['매체']}: {g['제목']}")

if rows:
    with open(f'{OUT}/news_probe_{DAY}_블룸버그매칭.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
n = len(rows)
print(f"\n=== 요약: 블룸버그 {n}건 중 국내 인용 찾음 {sum(r['국내인용건수'] > 0 for r in rows)}건"
      f"(허용 매체 {sum(bool(r['국내허용매체']) for r in rows)}건), 다른 외신 같은 사건 {sum(r['외신같은사건건수'] > 0 for r in rows)}건,"
      f" 요약(블룸버그 RSS 설명) 있음 {sum(bool(r['블룸버그요약']) for r in rows)}건 ===")
