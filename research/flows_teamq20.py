# 일회성 조사(팀 Q 20기업판): 여러 종목 투자자별 매매(외국인·기관·연기금·투신·사모·개인) 일별, 상장 이후(최대 2015년~)
# 결과는 로그에 압축 csv로 찍는다(단위 억원). 장 마감 뒤(15:40 이후)에만 조회됨. 조회만, 주문 없음.
import os, time, requests, datetime as dt
BASE='https://openapi.koreainvestment.com:9443'
K,S=os.environ['KIS_APP_KEY'],os.environ['KIS_APP_SECRET']
# 팀 Q BLOCK20 B13용: 콜로키움 100의 한국 개별 기업 20개(ETF 제외, 의장 11/10)
CODES=os.environ.get('CODES','').split() or (
 '005930 009150 006400 207940 010140 032830 016360 005380 012330 017670 '
 '000660 055550 105560 316140 278470 003230 079550 298040 034020 033780').split()
tok=requests.post(f'{BASE}/oauth2/tokenP',json={'grant_type':'client_credentials','appkey':K,'appsecret':S},timeout=10).json()['access_token']
H={'content-type':'application/json; charset=utf-8','authorization':f'Bearer {tok}','appkey':K,'appsecret':S,'tr_id':'FHPTJ04160001','custtype':'P'}
C=['frgn_ntby_tr_pbmn','orgn_ntby_tr_pbmn','fund_ntby_tr_pbmn','ivtr_ntby_tr_pbmn','pe_fund_ntby_tr_pbmn','prsn_ntby_tr_pbmn']
os.makedirs('research/out',exist_ok=True); OUT=open('research/out/flows_teamq20.csv','w',encoding='utf-8')
HDR='날짜,코드,종가,외국인,기관계,연기금,투신,사모,개인'; OUT.write(HDR+'\n')
print('FLOWS_BEGIN'); print(HDR)
for code in CODES:
    d=dt.date.today().strftime('%Y%m%d'); seen=set(); n=0
    for page in range(160):
        out=[]
        for t in range(3):
            time.sleep(0.15)
            try:
                j=requests.get(BASE+'/uapi/domestic-stock/v1/quotations/investor-trade-by-stock-daily',headers=H,timeout=15,
                    params={'FID_COND_MRKT_DIV_CODE':'J','FID_INPUT_ISCD':code,'FID_INPUT_DATE_1':d,'FID_ORG_ADJ_PRC':'','FID_ETC_CLS_CODE':''}).json()
                if j.get('rt_cd')=='0': out=j.get('output2') or []; break
                print('ERR',code,j.get('msg1'))
            except Exception as e: print('EXC',code,e)
        new=[r for r in out if r.get('stck_bsop_date') and r['stck_bsop_date'] not in seen and r.get('stck_clpr')]
        if not new: break
        for r in new:
            seen.add(r['stck_bsop_date']); n+=1
            v=[round(float(r.get(c) or 0)/100,1) for c in C]
            line=','.join(map(str,[r['stck_bsop_date'],code,r['stck_clpr'],*v])); OUT.write(line+'\n')
            if os.environ.get('QUIET')!='1': print(line)
        last=min(r['stck_bsop_date'] for r in new)
        if last<'20150101': break
        d=(dt.datetime.strptime(last,'%Y%m%d')-dt.timedelta(days=1)).strftime('%Y%m%d')
    print('DONE',code,n)
OUT.close(); print('FLOWS_END')
