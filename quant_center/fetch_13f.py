"""장기 펀드 13F(미국 주식 보유) → 종목별 '지난 분기 늘렸나·줄였나' (11/19 의장, 보너스 블록).

펀드(blocks.yaml '장기펀드'): 국민연금·캘퍼스·캘스터스·노르웨이 중앙은행(NBIM)·테마섹·캐나다 CPP·온타리오 교원연금.
싱가포르 GIC는 SEC 13F를 내지 않아 제외(테마섹으로 대신).

- 받기: SEC EDGAR(무료). 13F-HR 원본(정정 13F-HR/A 제외), 2013년 이후. 받은 파일은 캐시 폴더에 보관(재실행 시 새 분기만).
- 종목 연결: CUSIP 앞 6자리(발행사) ↔ 유니버스 미국 개별주. SEC 회사명(company_tickers.json)과 13F 발행사명을 정규화해 맞춤.
  같은 발행사의 여러 주식(GOOGL·GOOG)은 합산.
- 수량: 주식 수(SH)만, 옵션(put/call)·채권(PRN) 제외. 액면분할은 yfinance 분할 기록으로 앞 분기 수량을 보정.
- 늘렸나: 펀드마다 분기 주식 수 변화. 신규 = 앞 분기 0 → 보유, 전량 매도 = 보유 → 0.
- 시점: '공시일'(그 분기 13F가 모두 나온 마지막 공시일) 이후에만 그 분기 값을 씀(미래 정보 없음).

출력(입력 폴더): 장기펀드13F.csv(종목별 최신), 장기펀드13F_이력.csv(종목×분기, 성적 측정용)
칸: lt_funds(보유 펀드 수), lt_up(늘린 펀드 수, 신규 포함), lt_dn(줄인 펀드 수, 전량 매도 포함),
    lt_net(합산 주식 수 변화 %), lt_net_prev(그 전 분기 합산 변화 %)
실행: python fetch_13f.py <입력 폴더> [캐시 폴더]
"""
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qc_config as QCC  # noqa: E402

UA = f"colloquium-research {os.environ.get('SEC_EMAIL') or 'admin@example.org'}"   # SEC 요구: 수집기 이름 + 연락처(GitHub Secrets SEC_EMAIL)
HERE = os.path.dirname(os.path.abspath(__file__))
STOP = {'INC', 'CORP', 'CORPORATION', 'CO', 'COMPANY', 'LTD', 'LIMITED', 'PLC', 'HOLDINGS', 'HLDGS', 'HOLDING', 'GROUP',
        'THE', 'NV', 'N', 'V', 'SA', 'AG', 'SE', 'CL', 'CLASS', 'A', 'B', 'C', 'NEW', 'DEL', 'COM', 'ORD', 'SHS', 'ADR',
        'SPONSORED', 'SPON', 'ADS', 'INCORPORATED', 'INTL', 'INTERNATIONAL', 'TECHNOLOGIES', 'TECHNOLOGY', 'MFG', 'LLC', 'LP'}


def _get(url, path=None, tries=4):
    if path and os.path.exists(path):
        return open(path, 'rb').read()
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Encoding': 'identity'})
            b = urllib.request.urlopen(req, timeout=60).read()
            time.sleep(0.15)   # SEC 초당 10회 한도 아래
            if path:
                os.makedirs(os.path.dirname(path), exist_ok=True); open(path, 'wb').write(b)
            return b
        except Exception:
            time.sleep(2 ** k)
    raise RuntimeError(f'SEC 받기 실패: {url}')


def norm(s):
    s = re.sub(r'[^A-Z0-9 ]', ' ', str(s).upper().replace('&', ' AND '))
    return ' '.join(w for w in s.split() if w not in STOP)


def filings(cik, cache, since):
    j = json.loads(_get(f'https://data.sec.gov/submissions/CIK{int(cik):010d}.json'))
    r = j['filings']['recent']
    out = [(fd, rd, a) for fm, fd, rd, a in zip(r['form'], r['filingDate'], r['reportDate'], r['accessionNumber'])
           if fm in ('13F-HR', '13F-HR/A') and rd >= since]
    for extra in j['filings'].get('files', []):
        e = json.loads(_get(f"https://data.sec.gov/submissions/{extra['name']}"))
        out += [(fd, rd, a) for fm, fd, rd, a in zip(e['form'], e['filingDate'], e['reportDate'], e['accessionNumber'])
                if fm in ('13F-HR', '13F-HR/A') and rd >= since]
    return j['name'], sorted(set(out))


def table(cik, acc, cache):
    base = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace("-", "")}'
    idx = json.loads(_get(f'{base}/index.json', f'{cache}/{cik}/{acc}/index.json'))
    xs = [i['name'] for i in idx['directory']['item'] if i['name'].lower().endswith('.xml') and i['name'] != 'primary_doc.xml']
    rows = []
    for x in xs:
        root = ET.fromstring(_get(f'{base}/{x}', f'{cache}/{cik}/{acc}/{x}'))
        for it in root.iter():
            if not it.tag.endswith('infoTable'):
                continue
            g = {c.tag.split('}')[-1]: c for c in it.iter()}
            if 'putCall' in g and (g['putCall'].text or '').strip():
                continue
            if (g.get('sshPrnamtType').text if 'sshPrnamtType' in g else 'SH').strip() != 'SH':
                continue
            rows.append(dict(name=g['nameOfIssuer'].text, cusip=(g['cusip'].text or '').strip().upper(),
                             shares=float(g['sshPrnamt'].text), value=float(g['value'].text)))
    return pd.DataFrame(rows)


def build(d, cache, since=None):
    B = QCC.load_blocks()
    C = B['장기펀드']
    U = pd.read_csv(f'{d}/유니버스.csv', encoding='utf-8-sig')
    U = U[(U['시장'] == '미국') & (U['구분'] == '개별주')]
    tick = [str(t).upper() for t in U['yfinance 티커']]
    T = json.loads(_get('https://www.sec.gov/files/company_tickers.json', f'{cache}/company_tickers.json'))
    title = {v['ticker'].upper().replace('.', '-'): v['title'] for v in T.values()}
    H = []
    for nm, cik in C['펀드'].items():
        name, fl = filings(cik, cache, since or C.get('시작', '2013-01-01'))
        for fd, rd, acc in fl:
            t = table(cik, acc, cache)
            if not len(t):
                continue
            t['cusip6'] = t['cusip'].str[:6]
            g = t.groupby('cusip6').agg(shares=('shares', 'sum'), name=('name', 'first')).reset_index()
            g['fund'] = nm; g['period'] = rd; g['filed'] = fd; g['nrow'] = len(t); g['acc'] = acc
            H.append(g)
        print(f'{nm} ({name}): 13F {len(fl)}개', flush=True)
    H = pd.concat(H, ignore_index=True)
    # 같은 펀드·분기에 원본·정정이 여럿이면 종목이 가장 많은 보고서 하나만(일부만 담은 정정·빈 보고서 배제).
    # 그 펀드 평소 종목 수의 20% 미만인 보고서는 그 분기 '보고 없음'으로 보고 비교에서 뺌(전량 매도로 오해 방지)
    best = H.groupby(['fund', 'period', 'acc'])['nrow'].first().reset_index().sort_values('nrow').drop_duplicates(['fund', 'period'], keep='last')
    med = best.groupby('fund')['nrow'].transform('median')
    best = best[best['nrow'] >= 0.2 * med]
    H = H.merge(best[['fund', 'period', 'acc']], on=['fund', 'period', 'acc'])
    FILED = set(zip(best['fund'], best['period']))
    # 종목 연결: 발행사명 정규화 일치 → 가장 많이 나온 CUSIP6
    H['nn'] = H['name'].map(norm)
    cnt = H.groupby(['cusip6', 'nn']).size().reset_index(name='n')
    H['period'] = H['period'].astype(str)
    link, miss = {}, []
    for t in tick:
        nt = norm(title.get(t, ''))
        if not nt:
            miss.append(t); continue
        c = cnt[cnt['nn'].str.replace(' ', '') == nt.replace(' ', '')]   # 띄어쓰기 차이(EXXON MOBIL = EXXONMOBIL)는 같은 회사
        if not len(c):   # 13F 이름이 줄임말(예: TAIWAN SEMICONDUCTOR MFG)일 때만 앞부분 일치 허용(반대 방향은 다른 회사 위험)
            c = cnt[cnt['nn'].map(lambda x: len(x) >= 6 and nt.startswith(x + ' '))]
        if not len(c):
            miss.append(t); continue
        n = c.groupby('cusip6')['n'].sum()
        recent = set(H.loc[H['period'] >= H['period'].max()[:4] + '-01-01', 'cusip6']) & set(n.index)
        link[t] = sorted(set(n[n >= 0.2 * n.max()].index) | recent)   # 회사 재편으로 CUSIP이 바뀐 경우(블랙록 2024 등)도 함께
    c2t = {}
    for t, cs in link.items():
        for c6 in cs:
            c2t.setdefault(c6, t)
    H = H[H['cusip6'].isin(c2t)].copy()
    H['tk'] = H['cusip6'].map(c2t)
    # 액면분할(yfinance): 앞 분기 말 ~ 이번 분기 말 사이 분할 비율만큼 앞 분기 수량 보정
    try:
        import yfinance as yf
        SP = {t: yf.Ticker(t).splits for t in link}
    except Exception:
        SP = {}
    periods = sorted(H['period'].unique())
    rows = []
    for t, g in H.groupby('tk'):
        sp = SP.get(t)
        if sp is not None and len(sp):
            sp.index = sp.index.tz_localize(None)
        W = g.pivot_table(index='period', columns='fund', values='shares', aggfunc='sum').reindex(periods)
        filed = H.groupby('period')['filed'].max().reindex(periods)
        held = W.notna()
        def kf(p0, p1):   # p0~p1 사이 액면분할 배수
            if sp is None or not len(sp):
                return 1.0
            s_ = sp[(sp.index > pd.Timestamp(p0)) & (sp.index <= pd.Timestamp(p1))]
            return float(np.prod(s_.values)) if len(s_) else 1.0
        for i in range(1, len(periods)):
            p1 = periods[i]
            A0, A1, up, dn, nf = 0.0, 0.0, 0, 0, 0
            for fu in W.columns:
                if (fu, p1) not in FILED:
                    continue
                # 펀드마다 직전 보고 분기와 비교(반기만 내는 분기가 있는 펀드도 비교, 200일 이내)
                prev = [p for p in periods[:i] if (fu, p) in FILED and (pd.Timestamp(p1) - pd.Timestamp(p)).days <= 200]
                if not prev:
                    continue
                p0 = prev[-1]
                a0 = (0 if pd.isna(W.at[p0, fu]) else W.at[p0, fu]) * kf(p0, p1)
                a1 = 0 if pd.isna(W.at[p1, fu]) else W.at[p1, fu]
                if a0 == 0 and a1 == 0:
                    continue
                nf += 1; A0 += a0; A1 += a1
                up += int(a1 > a0 * 1.0001); dn += int(a1 < a0 * 0.9999)
            net = (A1 / A0 - 1) * 100 if A0 > 0 else np.nan   # 앞 기록 없음(신규 상장·이름 바뀜) = 비교 없음
            if nf < C.get('최소펀드', 2):   # 펀드 한 곳만 들고 있으면 '장기 펀드들'의 판단으로 보지 않음
                net = np.nan
            rows.append(dict(ticker=t, 분기=p1, 공시일=filed.loc[p1], lt_funds=int(held.loc[p1].sum()), 비교펀드=nf,
                             lt_up=up, lt_dn=dn, lt_net=None if pd.isna(net) else round(net, 2)))
    R = pd.DataFrame(rows).sort_values(['ticker', '분기'])
    R['lt_net_prev'] = R.groupby('ticker')['lt_net'].shift(1)
    build.link = link
    return R, miss


if __name__ == '__main__':
    # 매일(인자 없음, 회의 원고 07시): 입력 폴더 in/, 최근 3년만(빠름). 전체 이력(성적용): python fetch_13f.py <입력> <캐시> --full
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    d = a[0] if a else 'in'
    cache = a[1] if len(a) > 1 else os.path.join(d, '..', '13F캐시')
    full = '--full' in sys.argv
    since = None if full else (pd.Timestamp.now() - pd.DateOffset(years=3)).strftime('%Y-%m-%d')
    R, miss = build(d, cache, since)
    if full:
        R.to_csv(f'{d}/장기펀드13F_이력.csv', index=False, encoding='utf-8-sig')
    recent = sorted(R['분기'].unique())[-2:]   # 최근 두 분기(반기만 내는 펀드 대비)보다 오래된 값은 쓰지 않음
    L = R[R['분기'].isin(recent)].dropna(subset=['lt_net']).sort_values('분기').groupby('ticker').tail(1)
    L.to_csv(f'{d}/장기펀드13F.csv', index=False, encoding='utf-8-sig')
    print(f'연결 {L["ticker"].nunique()}종목, 연결 못 함 {len(miss)}: {", ".join(miss)}')
    print(L.sort_values('lt_net', ascending=False).to_string(index=False))
