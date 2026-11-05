# 일회성 시험(2026-11-05): 새 블록 8-MMF·9-국내수급과 주지사 데이터센터 구글 뉴스 검색이 Actions에서 되는지 본다.
# 드라이브 없이 블록 0의 필요한 것만 흉내 낸다. 결과는 research/out/test_mmf_kflow/ 에 저장.
import os, time, json, datetime as dt, requests, pandas as pd, xml.etree.ElementTree as ET
KST = dt.timezone(dt.timedelta(hours=9)); NOW = dt.datetime.now(KST); TODAY = NOW.strftime('%Y%m%d')
OUT = 'research/out/test_mmf_kflow'; DAY = f'{OUT}/{TODAY}'; KEEP = f'{OUT}/keep'
os.makedirs(DAY, exist_ok=True); os.makedirs(KEEP, exist_ok=True)
BASE = 'https://openapi.koreainvestment.com:9443'
SEC = {'KIS_APP_KEY': os.environ['KIS_APP_KEY'], 'KIS_APP_SECRET': os.environ['KIS_APP_SECRET']}
TOKEN = requests.post(f'{BASE}/oauth2/tokenP', timeout=10, json={'grant_type': 'client_credentials',
                      'appkey': SEC['KIS_APP_KEY'], 'appsecret': SEC['KIS_APP_SECRET']}).json()['access_token']
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36'}


def log(m): print(m, flush=True)


def get(url, retry=2, **kw):
    for n in range(retry + 1):
        try:
            r = requests.get(url, headers=UA, timeout=30, **kw); r.raise_for_status(); return r
        except Exception as e:
            if n == retry: print('실패', url, e); return None
            time.sleep(3)


def kis_get(path, tr_id, params, retry=2):
    h = {'content-type': 'application/json; charset=utf-8', 'authorization': f'Bearer {TOKEN}',
         'appkey': SEC['KIS_APP_KEY'], 'appsecret': SEC['KIS_APP_SECRET'], 'tr_id': tr_id, 'custtype': 'P'}
    for n in range(retry + 1):
        time.sleep(0.1)
        out = requests.get(f'{BASE}{path}', headers=h, params=params, timeout=10).json()
        if out.get('rt_cd') == '0' and out.get('output'):
            return out['output']
        print('KIS', tr_id, out.get('msg_cd'), out.get('msg1'))
    return None


u = pd.DataFrame([dict(번호=i + 1, 정식종목명=n, 코드=c) for i, (n, c) in enumerate(
    [('삼성전자', '005930'), ('SK하이닉스', '000660'), ('KB금융', '105560'), ('효성중공업', '298040'), ('SK텔레콤', '017670')])])
u = u.rename(columns={'정식종목명': '정식 종목명'}); u['시장'] = '한국'; u['구분'] = '개별주'
raw = kis_get('/uapi/domestic-stock/v1/quotations/inquire-investor', 'FHKST01010900', {'FID_COND_MRKT_DIV_CODE': 'J', 'FID_INPUT_ISCD': '005930'})
print('RAW rows', len(raw or []), json.dumps((raw or [{}])[:3], ensure_ascii=False))
G = dict(globals())
for b in ('blocks/b08_mmf.py', 'blocks/b09_kflow.py'):
    exec(compile(open(b, encoding='utf-8').read(), b, 'exec'), G)
for f in sorted(os.listdir(DAY)):
    print('==', f); print(open(f'{DAY}/{f}', encoding='utf-8-sig').read())
# 주지사 데이터센터 구글 뉴스(최근 2일)
for q in ['Texas governor data center', 'Hinojosa data center', 'Iowa governor data center', 'Georgia governor data center']:
    r = get('https://news.google.com/rss/search', params={'q': f'{q} when:2d', 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'})
    items = ET.fromstring(r.content).findall('.//item') if r is not None else []
    print('GNEWS', q, len(items))
    for it in items[:4]:
        print('   ', it.findtext('pubDate'), '|', it.findtext('title'))
