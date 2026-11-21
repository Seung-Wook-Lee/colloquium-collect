# 한투 추정실적(기아) 원문 구조 점검(조회만)
import os, sys, json
sys.path.insert(0, 'collect/data'); import kis, requests
tok = kis._token()
h = {'content-type': 'application/json; charset=utf-8', 'authorization': f'Bearer {tok}', 'appkey': os.environ['KIS_APP_KEY'],
     'appsecret': os.environ['KIS_APP_SECRET'], 'tr_id': 'HHKST668300C0', 'custtype': 'P'}
j = requests.get(f'{kis.BASE}/uapi/domestic-stock/v1/quotations/estimate-perform', headers=h, params={'SHT_CD': '000270'}, timeout=15).json()
for k, v in j.items():
    print(k, json.dumps(v, ensure_ascii=False)[:1500])
