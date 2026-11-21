# 한투 분기 손익 호출 형태 점검(조회만): 어떤 파라미터 이름이 통하는지 찍어 본다
import os, sys, json
sys.path.insert(0, 'collect/data'); import kis, requests
tok = kis._token()
h = {'content-type': 'application/json; charset=utf-8', 'authorization': f'Bearer {tok}', 'appkey': os.environ['KIS_APP_KEY'],
     'appsecret': os.environ['KIS_APP_SECRET'], 'tr_id': 'FHKST66430200', 'custtype': 'P'}
url = f'{kis.BASE}/uapi/domestic-stock/v1/finance/income-statement'
for name, p in [('소문자 섞임', {'FID_DIV_CLS_CODE': '1', 'fid_cond_mrkt_div_code': 'J', 'fid_input_iscd': '000270'}),
                ('대문자', {'FID_DIV_CLS_CODE': '1', 'FID_COND_MRKT_DIV_CODE': 'J', 'FID_INPUT_ISCD': '000270'}),
                ('소문자', {'fid_div_cls_code': '1', 'fid_cond_mrkt_div_code': 'J', 'fid_input_iscd': '000270'})]:
    for hh in (h, {k: v for k, v in h.items() if k != 'content-type'}):
        r = requests.get(url, headers=hh, params=p, timeout=15)
        j = r.json() if r.headers.get('content-type', '').startswith('application/json') else {'raw': r.text[:200]}
        out = j.get('output') or []
        print(name, 'ct' if 'content-type' in hh else 'no-ct', r.status_code, j.get('rt_cd'), j.get('msg_cd'), j.get('msg1'), len(out), json.dumps(out[:2], ensure_ascii=False)[:400])
