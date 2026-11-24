"""B20 ETF 자금 과거값 출처 점검(수동): 2017년부터 일별 좌수(설정·환매)를 받을 수 있는 곳을 확인한다."""
import io, os, requests, pandas as pd
UA = {'User-Agent': 'Mozilla/5.0'}


def show(name, f):
    try:
        print(f'[{name}]', f(), flush=True)
    except Exception as e:  # noqa: BLE001
        print(f'[{name}] 실패 {type(e).__name__}: {str(e)[:200]}', flush=True)


def krx():
    r = requests.post('https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd', timeout=30,
                      headers={**UA, 'Referer': 'https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd'},
                      data={'bld': 'dbms/MDC/STAT/standard/MDCSTAT04501', 'locale': 'ko_KR', 'isuCd': 'KR7069500007',
                            'strtDd': '20180102', 'endDd': '20180110', 'share': '1', 'money': '1', 'csvxls_isNo': 'false'})
    return r.status_code, r.text[:600]


def kis():
    K = 'https://openapi.koreainvestment.com:9443'
    t = requests.post(f'{K}/oauth2/tokenP', json={'grant_type': 'client_credentials', 'appkey': os.environ['KIS_APP_KEY'],
                                                    'appsecret': os.environ['KIS_APP_SECRET']}, timeout=10).json()['access_token']
    h = {'authorization': f'Bearer {t}', 'appkey': os.environ['KIS_APP_KEY'], 'appsecret': os.environ['KIS_APP_SECRET'],
         'tr_id': 'FHPST02440200', 'custtype': 'P'}
    j = requests.get(f'{K}/uapi/etfetn/v1/quotations/nav-comparison-daily-trend', headers=h, timeout=10,
                     params={'FID_COND_MRKT_DIV_CODE': 'J', 'FID_INPUT_ISCD': '069500', 'FID_INPUT_DATE_1': '20180102',
                             'FID_INPUT_DATE_2': '20180131'}).json()
    o = j.get('output') or j.get('output1') or j
    return str(o)[:800]


def ishares():
    r = requests.get('https://www.ishares.com/us/products/239705/ishares-phlx-semiconductor-etf/1467271812596.ajax',
                     params={'fileType': 'xls', 'fileName': 'SOXX_fund', 'dataType': 'fund'}, headers=UA, timeout=60)
    t = r.content.decode('utf-8-sig', 'ignore')
    i = t.find('ss:Name="Historical"')
    import re
    rows = re.findall(r'<ss:Row>(.*?)</ss:Row>', t[i:], flags=re.S)
    cell = lambda x: re.findall(r'<ss:Data[^>]*>(.*?)</ss:Data>', x, flags=re.S)
    return r.status_code, i, len(rows), [cell(x) for x in rows[:3]], [cell(x) for x in rows[-2:]]


def ssga():
    r = requests.get('https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/navhist-us-en-xlk.xlsx',
                     headers=UA, timeout=60)
    d = pd.read_excel(io.BytesIO(r.content), header=None)
    return r.status_code, d.shape, d.iloc[:6, :4].values.tolist(), d.iloc[-2:, :4].values.tolist()


def invesco():
    r = requests.get('https://www.invesco.com/us/financial-products/etfs/holdings/main/holdings/0?audienceType=Investor&action=download&ticker=QQQ',
                     headers=UA, timeout=60)
    return r.status_code, r.text[:300]


import time; time.sleep(65)   # 한투 토큰은 1분에 1번
for n, f in [('한투 NAV 비교추이(일)', kis), ('iShares 과거(좌수)', ishares)]:
    show(n, f)
