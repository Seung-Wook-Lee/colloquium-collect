# 일회성 조사: 에이피알(278470) 투자자별 매매(외국인·기관·연기금·투신·사모 등) 일별 전 기간 + 외국인 보유율
# 결과는 실행 로그에 csv로 찍는다(회의실이 로그로 읽음). 조회만, 주문 없음.
import os, time, json, requests, sys
BASE='https://openapi.koreainvestment.com:9443'
K,S=os.environ['KIS_APP_KEY'],os.environ['KIS_APP_SECRET']
CODE=sys.argv[1] if len(sys.argv)>1 else os.environ.get('CODE','278470')
tok=requests.post(f'{BASE}/oauth2/tokenP',json={'grant_type':'client_credentials','appkey':K,'appsecret':S},timeout=10).json()['access_token']
def get(path,tr,params):
    h={'content-type':'application/json; charset=utf-8','authorization':f'Bearer {tok}','appkey':K,'appsecret':S,'tr_id':tr,'custtype':'P'}
    for n in range(3):
        time.sleep(0.35)
        try:
            j=requests.get(BASE+path,headers=h,params=params,timeout=15).json()
            if j.get('rt_cd')=='0': return j
            print('ERR',tr,j.get('msg_cd'),j.get('msg1'))
        except Exception as e: print('EXC',tr,e)
        time.sleep(1+n)
    return {}
# 1) 종목별 투자자매매동향(일별) — 기관 세부(투신·사모·연기금 등) 포함
rows={}; d='20261103'; seen=set()
for page in range(40):
    j=get('/uapi/domestic-stock/v1/quotations/investor-trade-by-stock-daily','FHPTJ04160001',
          {'FID_COND_MRKT_DIV_CODE':'J','FID_INPUT_ISCD':CODE,'FID_INPUT_DATE_1':d,'FID_ORG_ADJ_PRC':'','FID_ETC_CLS_CODE':''})
    out=j.get('output2') or []
    if page==0:
        print('KEYS1',json.dumps(j.get('output1',{}),ensure_ascii=False)[:1500])
        print('KEYS2',list(out[0].keys()) if out else None)
    new=[r for r in out if r.get('stck_bsop_date') and r['stck_bsop_date'] not in seen]
    if not new: break
    for r in new: seen.add(r['stck_bsop_date']); rows[r['stck_bsop_date']]=r
    last=min(r['stck_bsop_date'] for r in new)
    if last<='20240227': break
    # 다음 페이지: 마지막 날 하루 전
    import datetime as dt
    d=(dt.datetime.strptime(last,'%Y%m%d')-dt.timedelta(days=1)).strftime('%Y%m%d')
print('ROWS',len(rows))
if rows:
    keys=list(next(iter(rows.values())).keys())
    print('CSV1_BEGIN'); print(','.join(keys))
    for k in sorted(rows): print(','.join(str(rows[k].get(c,'')) for c in keys))
    print('CSV1_END')
# 2) 주식현재가 일자별(외국인 보유율 칸 확인용) 최근 30일
j=get('/uapi/domestic-stock/v1/quotations/inquire-daily-price','FHKST01010400',
      {'FID_COND_MRKT_DIV_CODE':'J','FID_INPUT_ISCD':CODE,'FID_PERIOD_DIV_CODE':'D','FID_ORG_ADJ_PRC':'0'})
o=j.get('output') or []
if o:
    keys=list(o[0].keys()); print('CSV2_BEGIN'); print(','.join(keys))
    for r in o: print(','.join(str(r.get(c,'')) for c in keys))
    print('CSV2_END')
