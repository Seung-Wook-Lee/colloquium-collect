# 11/2 의장 질문 확인용: ① CNN 공포탐욕 7개 지표 원천값 이력이 맞는가 ② FactSet Earnings Insight(무료 주간 PDF)를 받을 수 있는가
import requests, pandas as pd, io, re
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'}
r = requests.get('https://production.dataviz.cnn.io/index/fearandgreed/graphdata', headers=UA, timeout=30)
print('CNN', r.status_code)
j = r.json()
for k in ['market_momentum_sp500', 'stock_price_strength', 'stock_price_breadth', 'put_call_options',
          'market_volatility_vix', 'safe_haven_demand', 'junk_bond_demand']:
    x = j.get(k, {}); pts = x.get('data') or []
    s = pd.Series({pd.to_datetime(p['x'], unit='ms').date(): round(p['y'], 3) for p in pts})
    print(f'### {k} score={x.get("score")} n={len(s)} {s.index.min()}~{s.index.max()}')
    print(' 처음 3:', s.head(3).to_dict()); print(' 끝 8:', s.tail(8).to_dict())
    print(' 1주 간격:', s.iloc[::5].tail(6).to_dict())
for u in ['https://insight.factset.com/topic/earnings', 'https://advantage.factset.com/hubfs/Website/Resources%20Section/Research%20Desk/Earnings%20Insight/EarningsInsight_103026.pdf',
          'https://www.factset.com/earningsinsight']:
    try:
        r = requests.get(u, headers=UA, timeout=30)
        pdfs = sorted(set(re.findall(r'https?://[^"\'\s]+EarningsInsight[^"\'\s]*\.pdf', r.text)))[:5] if 'html' in r.headers.get('content-type', '') else []
        print('###', r.status_code, r.headers.get('content-type'), len(r.content), u, pdfs)
    except Exception as e:
        print('### ERR', u, e)
