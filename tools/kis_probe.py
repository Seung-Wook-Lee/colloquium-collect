# 한투 재무 호출 점검(조회만)
import os, sys, json
sys.path.insert(0, 'collect/data'); import kis, requests
tok = kis._token()
def go(name, path, tr, p):
    h = {'content-type': 'application/json; charset=utf-8', 'authorization': f'Bearer {tok}', 'appkey': os.environ['KIS_APP_KEY'],
         'appsecret': os.environ['KIS_APP_SECRET'], 'tr_id': tr, 'custtype': 'P'}
    r = requests.get(f'{kis.BASE}{path}', headers=h, params=p, timeout=15)
    try: j = r.json()
    except Exception: j = {'raw': r.text[:200]}
    o = j.get('output') or j.get('output1') or j.get('output2') or []
    print(name, r.status_code, j.get('rt_cd'), j.get('msg_cd'), j.get('msg1'), len(o) if isinstance(o, list) else 'dict', json.dumps(o[:2] if isinstance(o, list) else o, ensure_ascii=False)[:500])
F = '/uapi/domestic-stock/v1/finance/'
go('손익 연', F + 'income-statement', 'FHKST66430200', {'FID_DIV_CLS_CODE': '0', 'fid_cond_mrkt_div_code': 'J', 'fid_input_iscd': '000270'})
go('재무비율 분기', F + 'financial-ratio', 'FHKST66430300', {'FID_DIV_CLS_CODE': '1', 'fid_cond_mrkt_div_code': 'J', 'fid_input_iscd': '000270'})
go('대차 분기', F + 'balance-sheet', 'FHKST66430100', {'FID_DIV_CLS_CODE': '1', 'fid_cond_mrkt_div_code': 'J', 'fid_input_iscd': '000270'})
go('손익 삼성 분기', F + 'income-statement', 'FHKST66430200', {'FID_DIV_CLS_CODE': '1', 'fid_cond_mrkt_div_code': 'J', 'fid_input_iscd': '005930'})
go('추정실적 기아', '/uapi/domestic-stock/v1/quotations/estimate-perform', 'HHKST668300C0', {'SHT_CD': '000270'})
