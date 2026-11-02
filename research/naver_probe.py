# 네이버 증권 지수·시장지표 주소 시험(2026-11-02 의장 "네이버에 모든 지수가 있다, 방법을 찾아봐") — 결과는 실행 로그로 읽는다
import requests
H = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148',
     'Referer': 'https://m.stock.naver.com/'}
URLS = [
    'https://m.stock.naver.com/api/index/KOSPI/basic',
    'https://m.stock.naver.com/api/index/KOSDAQ/basic',
    'https://m.stock.naver.com/api/index/KOSPI/price?pageSize=5&page=1',
    'https://polling.finance.naver.com/api/realtime/domestic/index/KOSPI',
    'https://api.stock.naver.com/index/.IXIC/basic',
    'https://api.stock.naver.com/index/.INX/basic',
    'https://api.stock.naver.com/index/.SOX/basic',
    'https://api.stock.naver.com/index/.N225/basic',
    'https://api.stock.naver.com/index/.IXIC/price?page=1&pageSize=5',
    'https://api.stock.naver.com/chart/domestic/index/KOSPI?periodType=dayCandle',
    'https://api.stock.naver.com/chart/foreign/index/.IXIC?periodType=dayCandle',
    'https://api.finance.naver.com/siseJson.naver?symbol=KOSPI&requestType=1&startTime=20261020&endTime=20261102&timeframe=day',
    'https://fchart.stock.naver.com/sise.nhn?symbol=KOSPI&timeframe=day&count=5&requestType=0',
    'https://m.stock.naver.com/front-api/marketIndex/productDetail?category=exchange&reutersCode=FX_USDKRW',
    'https://m.stock.naver.com/front-api/marketIndex/prices?category=exchange&reutersCode=FX_USDKRW&page=1&pageSize=5',
    'https://m.stock.naver.com/front-api/marketIndex/productDetail?category=bond&reutersCode=US10YT%3DRR',
    'https://m.stock.naver.com/front-api/marketIndex/productDetail?category=energy&reutersCode=CLcv1',
    'https://m.stock.naver.com/front-api/marketIndex/productDetail?category=metals&reutersCode=GCcv1',
    'https://api.stock.naver.com/marketindex/majors/part1',
    'https://m.stock.naver.com/api/stock/005930/basic',
    'https://api.stock.naver.com/stock/NVDA.O/basic',
]
for u in URLS:
    try:
        r = requests.get(u, headers=H, timeout=15)
        print(f'### {r.status_code} {u}\n{r.text[:500]}\n')
    except Exception as e:
        print(f'### ERR {u} {type(e).__name__} {e}\n')
