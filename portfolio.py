# ======================================================================
# 포트폴리오 분석 (스트림릿 '포트폴리오' 탭이 쓴다) — 금액 없이 종목·비중(%)만 다룬다
#   읽는 것  : 의장 포트폴리오 csv(종목, 전체비중% …) + 제안비중 csv(선택)
#              app/portfolio_map.csv(스튜디오 톰앤수 100 번호·티커·담당 데스크), 00_가격이력, 그날 _닉스.csv
#   하는 일  : 1 목표 대비 차이(시장마다 현금성30·지수30·주식40)  2 쏠림(데스크·시장·섹터·상위 종목)
#              3 위험도(베타·상관·최대 낙폭, 기준일 뒤 수익률)  4 닉스 신호 대조(사실만, 판정 안 함)
#              5 매매 후보표(제안 비중·마감 비중과 지금 비중의 차이)
#   주의     : 수익률·낙폭은 현지 통화 가격 기준(환율 미반영), 지금 비중을 과거에 그대로 들고 있었다고 보고 계산
# ======================================================================
import re

import numpy as np
import pandas as pd

TARGET = {'현금성': 30.0, '지수': 30.0, '주식·ETF': 40.0}      # 2026-10-18 자산 배분, 시장마다 같은 틀
BENCH = {'한국': '102110.KS', '미국': 'SPYM', '일본': 'SPYM'}   # 베타 기준(TIGER 200, SPYM). 일본은 지수 ETF가 없어 SPYM
ALIAS = {'알파벳': 'G02', '알파벳a': 'G02', '구글': 'G02', 'googl': 'G02', 'tiger머니마켓펀드': 'K43',
         '머니마켓': 'K43', 'jp모건': 'G19', '마벨': 'G11', 'dram': 'G45', 'boxx': 'G46'}
SEMI_EXTRA = {'G45', 'G43', 'G44', 'K24', 'K25', 'K26', 'K27', 'K37', 'K41'}   # 반도체 ETF


def _key(s):
    return re.sub(r'[\s·&().,\-]', '', str(s)).lower()


def _num(s):
    return pd.to_numeric(s, errors='coerce')


# ---------------------------------------------------------------- 입력 정리
def load(h, umap):
    """포트폴리오 csv → 한 줄 한 종목, 번호·티커·데스크·섹터·자산군 붙이기"""
    h = h.copy()
    h.columns = [c.strip() for c in h.columns]
    wcol = next((c for c in ('전체비중%', '비중%', '비중(%)', '현재%') if c in h), None)
    if '종목' not in h or wcol is None:
        raise ValueError('csv에 "종목"과 "전체비중%" 칸이 있어야 합니다.')
    h['비중'] = _num(h[wcol]).fillna(0.0)

    um = umap.copy()
    look, names = {}, {}
    for _, r in um.iterrows():
        for v in (r['번호'], r['원본 표기'], r['정식 종목명'], r['yfinance 티커']):
            if pd.notna(v):
                look.setdefault(_key(v), r['번호'])
        for v in (r['원본 표기'], r['정식 종목명']):          # 앞부분 맞추기는 이름으로만(티커는 짧아서 오인)
            if pd.notna(v) and len(_key(v)) >= 2:
                names.setdefault(_key(v), r['번호'])
    look.update(ALIAS)

    def find(row):
        if '번호' in row and pd.notna(row.get('번호')) and str(row['번호']) in set(um['번호']):
            return str(row['번호'])
        k = _key(row['종목'])
        if k in look:
            return look[k]
        hit = [no for kk, no in names.items() if len(k) >= 2 and kk.startswith(k)]   # '마벨 테크' → '마벨 테크놀로지'
        return hit[0] if len(set(hit)) == 1 else None

    h['번호'] = h.apply(find, axis=1)
    h = h.merge(um.rename(columns={'시장': '유니버스 시장', '구분': '유니버스 구분'}), on='번호', how='left')
    if '시장' not in h:
        h['시장'] = h['유니버스 시장']
    h['시장'] = h['시장'].fillna(h['유니버스 시장']).fillna('기타')

    def bucket(r):
        g = str(r.get('구분', '') or '')
        if g in TARGET:
            return g
        s = str(r.get('섹터/테마', '') or '')
        if '현금성' in s:
            return '현금성'
        if '지수' in s and '커버드콜' not in s:
            return '지수'
        return '주식·ETF'
    h['자산군'] = h.apply(bucket, axis=1)
    h['데스크'] = h['데스크'].fillna('담당 없음')
    h['반도체'] = h['섹터/테마'].fillna('').str.contains('반도체') | h['번호'].isin(SEMI_EXTRA)
    return h


# ---------------------------------------------------------------- 1. 목표 대비 차이
def target_gap(h):
    """시장별·전체 자산군 비중(시장 안 %)과 목표 30/30/40의 차이"""
    rows = []
    for mk, g in list(h.groupby('시장')) + [('전체', h)]:
        tot = g['비중'].sum()
        for b, t in TARGET.items():
            w = g.loc[g['자산군'] == b, '비중'].sum()
            share = w / tot * 100 if tot else np.nan
            rows.append({'시장': mk, '자산군': b, '전체 대비%': round(w, 1), '시장 안%': round(share, 1),
                         '목표%': t, '차이%p': round(share - t, 1)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 2. 쏠림
def concentration(h):
    w = h['비중'] / h['비중'].sum() * 100
    top = h.assign(w=w).sort_values('w', ascending=False)
    stats = {
        '종목 수': int((h['비중'] > 0).sum()),
        f"1위 종목 ({top.iloc[0]['w']:.1f}%)": top.iloc[0]['종목'],
        '상위 5종목 합%': round(top['w'].head(5).sum(), 1),
        '반도체 합%': round(w[h['반도체']].sum(), 1),
        '실효 종목 수': round(1 / ((w / 100) ** 2).sum(), 1),   # 비중이 고르다면 몇 종목과 같은지(HHI 역수)
    }
    by = lambda col: (h.assign(w=w).groupby(col)['w'].sum().round(1).sort_values(ascending=False)
                      .rename('비중%').reset_index())
    h = h.assign(업종=np.where(h['반도체'], '반도체(전체)', h['섹터/테마'].fillna('기타').str.replace(r'\(.*', '', regex=True)))
    return stats, by('데스크'), by('시장'), by('업종')


# ---------------------------------------------------------------- 3. 위험도
def weekly(px, tickers, years=2):
    p = px[px['티커'].isin(tickers)].pivot_table(index='날짜', columns='티커', values='가격').sort_index()
    if not len(p):
        return pd.DataFrame()
    p = p[p.index >= p.index[-1] - pd.DateOffset(years=years)]
    return p.resample('W-FRI').last().pct_change(fill_method=None).iloc[1:]


def betas(h, px):
    """종목마다 2년 주간 베타(한국=TIGER 200, 미국·일본=SPYM 기준)"""
    tick = h['yfinance 티커'].dropna().tolist() + list(set(BENCH.values()))
    r = weekly(px, tick, 2)
    out = {}
    for _, row in h.dropna(subset=['yfinance 티커']).iterrows():
        t, b = row['yfinance 티커'], BENCH.get(row['시장'], 'SPYM')
        if t not in r or b not in r:
            continue
        x = r[[t, b]].dropna()
        if len(x) < 26:
            continue
        out[t] = round(x[t].cov(x[b]) / x[b].var(), 2) if t != b else 1.0
    return pd.Series(out, name='베타')


def port_series(h, px, years=3):
    """지금 비중을 그대로 들고 있었다면의 포트폴리오 가치(1.0 시작), 현지 통화 기준"""
    hh = h.dropna(subset=['yfinance 티커'])
    hh = hh[hh['비중'] > 0]
    p = px[px['티커'].isin(hh['yfinance 티커'])].pivot_table(index='날짜', columns='티커', values='가격').sort_index()
    if not len(p):
        return pd.Series(dtype=float)
    p = p[p.index >= p.index[-1] - pd.DateOffset(years=years)].ffill()
    r = p.pct_change(fill_method=None)
    w = hh.groupby('yfinance 티커')['비중'].sum().reindex(r.columns).fillna(0)
    avail = r.notna().mul(w, axis=1)                       # 상장 전 종목은 그날 비중에서 빼고 나눈다
    pr = (r.fillna(0).mul(w, axis=1).sum(axis=1) / avail.sum(axis=1).replace(0, np.nan)).fillna(0)
    return (1 + pr).cumprod()


def drawdown(s):
    if not len(s):
        return np.nan, None, None
    dd = s / s.cummax() - 1
    end = dd.idxmin()
    start = s[:end].idxmax()
    return round(dd.min() * 100, 1), start, end


def corr(h, px, min_w=1.0):
    hh = h[(h['비중'] >= min_w)].dropna(subset=['yfinance 티커'])
    r = weekly(px, hh['yfinance 티커'].tolist(), 1)
    if not len(r):
        return pd.DataFrame(), pd.DataFrame()
    name = hh.drop_duplicates('yfinance 티커').set_index('yfinance 티커')['종목']
    c = r.corr(min_periods=26).rename(index=name, columns=name)
    pairs = []
    cols = list(c.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            v = c.iloc[i, j]
            if pd.notna(v) and v >= 0.7:
                pairs.append({'종목 1': cols[i], '종목 2': cols[j], '상관': round(v, 2)})
    return c, pd.DataFrame(pairs).sort_values('상관', ascending=False) if pairs else pd.DataFrame()


def since(h, px, base):
    """기준일 종가 → 최신 종가 수익률, 종목별과 비중 가중 합"""
    hh = h.dropna(subset=['yfinance 티커'])
    p = px[px['티커'].isin(hh['yfinance 티커'])].pivot_table(index='날짜', columns='티커', values='가격').sort_index().ffill()
    p0 = p[p.index <= pd.Timestamp(base)]
    if not len(p0) or not len(p):
        return pd.DataFrame(), np.nan, None
    ret = (p.iloc[-1] / p0.iloc[-1] - 1) * 100
    t = hh[['종목', 'yfinance 티커', '비중']].copy()
    t['기준일 뒤%'] = t['yfinance 티커'].map(ret)
    t['기여%p'] = t['비중'] / h['비중'].sum() * t['기준일 뒤%']
    known = t['기준일 뒤%'].notna()
    total = t.loc[known, '기여%p'].sum() / (t.loc[known, '비중'].sum() / h['비중'].sum())
    return t.sort_values('기여%p'), round(total, 2), p.index[-1]


# ---------------------------------------------------------------- 4. 닉스 신호 대조 (사실만)
def signals(h, nx):
    if not len(nx):
        return pd.DataFrame()
    n = nx.set_index('번호')
    rows = []
    for _, r in h[h['비중'] > 0].sort_values('비중', ascending=False).iterrows():
        if r['번호'] not in n.index:
            continue
        x = n.loc[r['번호']]
        g = lambda c: x[c] if c in x and pd.notna(x[c]) else None
        f = lambda c: float(g(c)) if g(c) is not None else np.nan
        notes = []
        for c, lab in (('주_지지상태', '주봉 지지'), ('주_저항상태', '주봉 저항'), ('주_패턴', '주봉 패턴'), ('일_패턴', '일봉 패턴')):
            if g(c):
                notes.append(f'{lab} {g(c)}')
        m0, m1 = f('주_MACD오실레이터'), f('주_MACD오실레이터_1봉전')
        macd = ''
        if pd.notna(m0) and pd.notna(m1):
            macd = ('음수권 ' if m0 < 0 else '양수권 ') + ('상승' if m0 > m1 else '하락' if m0 < m1 else '보합')
        rsi = f('일_RSI')
        if pd.notna(rsi) and (rsi <= 30 or rsi >= 70):
            notes.append(f'일봉 RSI {rsi:.0f}')
        pb = f('일_볼린저_%B')
        if pd.notna(pb) and pb <= 0:
            notes.append('일봉 볼린저 하단 아래')
        elif pd.notna(pb) and pb >= 1:
            notes.append('일봉 볼린저 상단 위')
        rows.append({'종목': r['종목'], '비중%': r['비중'], '데스크': r['데스크'],
                     '52주 고점 대비%': f('52주고점대비(%)'), '일 RSI': rsi, '주 RSI': f('주_RSI'),
                     '20주 이격도': f('주_20주_이격도'), '주 MACD 오실레이터': macd,
                     '일목(주봉 구름)': g('주_일목_구름위치') or '', '눈여겨볼 점': ' · '.join(notes)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 5. 매매 후보표
def trade_list(h, prop=None):
    """지금 비중과 (가) 제안 비중 csv, (나) 마감 비율(시장 안 %)을 전체 %로 바꾼 값의 차이"""
    t = h[['종목', '시장', '자산군', '데스크', '비중']].rename(columns={'비중': '지금%'}).copy()
    if '마감비율%(시장내)' in h:
        mk = h.groupby('시장')['비중'].transform('sum')
        t['마감 목표%'] = (_num(h['마감비율%(시장내)']).fillna(0) * mk / 100).round(1)
        t['마감까지%p'] = (t['마감 목표%'] - t['지금%']).round(1)
    if prop is not None and len(prop) and '제안%' in prop:
        pk = {_key(k): v for k, v in zip(prop['종목'], _num(prop['제안%']))}
        pr = {_key(k): v for k, v in zip(prop['종목'], prop.get('근거', pd.Series([''] * len(prop))))}

        def pick(d, name):
            k = _key(name)
            if k in d:
                return d[k]
            return next((v for kk, v in d.items() if kk.startswith(k) or k.startswith(kk)), np.nan)
        t['제안%'] = t['종목'].map(lambda s: pick(pk, s))
        t['제안까지%p'] = (t['제안%'] - t['지금%']).round(1)
        t['제안 근거'] = t['종목'].map(lambda s: pick(pr, s))
    if '절세매도후보' in h:
        t['절세 후보'] = h['절세매도후보'].fillna('')
    if '수익률%' in h:
        t['수익률%'] = _num(h['수익률%'])
    key = '제안까지%p' if '제안까지%p' in t else ('마감까지%p' if '마감까지%p' in t else None)
    if key:
        t = t.reindex(t[key].abs().sort_values(ascending=False).index)
    return t
