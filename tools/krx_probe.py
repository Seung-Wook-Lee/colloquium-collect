"""KRX 계정 점검(수동): 비밀값이 들어 있는지(길이만), 로그인 뒤 ETF 상장좌수 일별을 받을 수 있는지."""
import os
i, p = os.environ.get('KRX_ID', ''), os.environ.get('KRX_PW', '')
print('[KRX 계정] KRX_ID', '있음' if i else '없음', '· KRX_PW', '있음' if p else '없음', flush=True)
if i and p:
    try:
        from pykrx import stock
        d = stock.get_etf_ohlcv_by_date('20180102', '20180110', '069500')
        print('[KRX ETF 일별]', d.columns.tolist(), len(d))
    except Exception as e:  # noqa: BLE001
        print('[KRX ETF 일별] 실패', type(e).__name__, str(e)[:300])
