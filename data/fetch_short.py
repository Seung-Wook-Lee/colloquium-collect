"""B20 공매도 잔고(미국 개별주, 야후 무료, FINRA 월 2회 공시 기준) → in/공매도.csv
칸: ticker, 기준일, 공매도주식, 전월공매도주식, 유통대비(%), 커버일수(days to cover), 전월대비(%)"""
import time
import pandas as pd, yfinance as yf
N = pd.read_csv('in/닉스.csv', encoding='utf-8-sig')
us = N[(N['시장'] == '미국') & (N['구분'] == '개별주')]['yfinance 티커'].dropna().astype(str).unique()
rows = []
for t in us:
    try:
        i = yf.Ticker(t).info
    except Exception:
        continue
    s, p = i.get('sharesShort'), i.get('sharesShortPriorMonth')
    if not s:
        continue
    d = i.get('dateShortInterest')
    rows.append(dict(ticker=t, 기준일=pd.to_datetime(d, unit='s').strftime('%Y-%m-%d') if d else None, 공매도주식=s, 전월공매도주식=p,
                     **{'유통대비(%)': round(i['shortPercentOfFloat'] * 100, 2) if i.get('shortPercentOfFloat') is not None else None,
                        '커버일수': i.get('shortRatio'), '전월대비(%)': round((s / p - 1) * 100, 1) if p else None}))
    time.sleep(0.2)
pd.DataFrame(rows).to_csv('in/공매도.csv', index=False, encoding='utf-8-sig')
print(len(rows), '종목')
