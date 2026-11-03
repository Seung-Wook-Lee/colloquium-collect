"""오늘의 한 종목 채점부를 채운다 (2026-11-03 의장 "채점 장부를 강화하세요")

쓰는 법: python tools/score_picks.py <채점부.csv> [성적표.csv]
- 기준가가 빈 줄은 기준일 종가로 채운다.
- 1·2·4·12주 뒤 칸: 기준일에서 7·14·28·84일 지난 날(그날 또는 직전 거래일) 종가의 기준가 대비 수익률(%).
- 시장 대비(4주): 같은 4주 동안 그 종목 시장 지수(한국 ^KS11, 일본 ^N225, 그 밖 ^GSPC)보다 몇 %p 앞섰나.
- 적중(4주): 추천·선호·주목·비중 늘릴 추세 = 시장 대비 플러스면 O. 제외·이탈 경고 = 시장 대비 마이너스면 O. 관찰은 채점하지 않음.
- 성적표: 위원별 픽 수, 4주 채점 수, 적중률, 4주 수익률 중앙값, 시장 대비 중앙값.
가격은 야후 차트 API(수정 전 종가). 금액은 다루지 않는다.
"""
import datetime as dt
import json
import sys
import urllib.request

import pandas as pd

H = {'1주 뒤': 7, '2주 뒤': 14, '4주 뒤': 28, '12주 뒤': 84}
LONG = {'추천', '선호', '주목', '비중 늘릴 추세'}
SHORT = {'제외', '이탈 경고'}
_cache = {}


def closes(t):
    if t not in _cache:
        u = f'https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=2y&interval=1d'
        j = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30))
        j = j['chart']['result'][0]
        s = pd.Series(j['indicators']['quote'][0]['close'], index=pd.to_datetime(j['timestamp'], unit='s').normalize())
        if pd.isna(s.iloc[-1]) and j['meta'].get('regularMarketPrice'):
            s.iloc[-1] = j['meta']['regularMarketPrice']
        _cache[t] = s.dropna()
    return _cache[t]


def at(s, d):
    x = s[s.index <= pd.Timestamp(d)]
    return float(x.iloc[-1]) if len(x) else None


def market(t):
    return '^KS11' if t.endswith(('.KS', '.KQ')) else '^N225' if t.endswith('.T') else '^GSPC'


def main(path, board=None):
    df = pd.read_csv(path, encoding='utf-8-sig', dtype={'티커': str})
    for c in ['적중(4주)']:
        if c not in df:
            df[c] = ''
    today = pd.Timestamp(dt.date.today())
    for i, r in df.iterrows():
        try:
            s = closes(r['티커'])
        except Exception as e:
            print('가격 실패', r['티커'], e)
            continue
        base_d = pd.Timestamp(r['기준일'])
        if pd.isna(r['기준가']):
            df.at[i, '기준가'] = at(s, base_d)
        b = float(df.at[i, '기준가'])
        for col, days in H.items():
            d = base_d + pd.Timedelta(days=days)
            if d <= today and s.index[-1] >= d - pd.Timedelta(days=3):
                df.at[i, col] = round((at(s, d) / b - 1) * 100, 2)
        if pd.notna(df.at[i, '4주 뒤']) and str(df.at[i, '4주 뒤']) != '':
            m = closes(market(r['티커']))
            d4 = base_d + pd.Timedelta(days=28)
            mk = (at(m, d4) / at(m, base_d) - 1) * 100
            ex = round(float(df.at[i, '4주 뒤']) - mk, 2)
            df.at[i, '시장 대비(4주)'] = ex
            j = str(r['판정']).strip()
            df.at[i, '적중(4주)'] = ('O' if ex > 0 else 'X') if j in LONG else ('O' if ex < 0 else 'X') if j in SHORT else ''
    df.to_csv(path, index=False, encoding='utf-8-sig')
    if board:
        g = df.groupby('위원')
        out = pd.DataFrame({
            '픽 수': g.size(),
            '4주 채점 수': g['적중(4주)'].apply(lambda x: int(x.isin(['O', 'X']).sum())),
            '적중률(4주, %)': g['적중(4주)'].apply(lambda x: round((x == 'O').sum() / max(1, x.isin(['O', 'X']).sum()) * 100) if x.isin(['O', 'X']).any() else None),
            '4주 수익률 중앙값(%)': g['4주 뒤'].apply(lambda x: pd.to_numeric(x, errors='coerce').median()),
            '시장 대비 중앙값(4주, %p)': g['시장 대비(4주)'].apply(lambda x: pd.to_numeric(x, errors='coerce').median()),
            '1주 뒤 중앙값(%)': g['1주 뒤'].apply(lambda x: pd.to_numeric(x, errors='coerce').median()),
            '마지막 픽': g['날짜'].max(),
        }).reset_index()
        out.to_csv(board, index=False, encoding='utf-8-sig')
        print(out.to_string(index=False))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
