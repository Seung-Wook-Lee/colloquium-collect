# 미스 ETF 카드 — ETF 바구니 속(상위 10·비중·쏠림·보수·괴리율·과세)과 반도체 ETF 겹침 표
#   국내 상장: 한투 ETF 구성종목(FHKST121600C0) + ETF 현재가(FHPST02400000, NAV·괴리율·추적오차)
#             해외 종목을 담은 국내 ETF는 한투 줄을 그대로 쓰고, 비면 같은 지수의 미국 ETF(meta.csv 미국대리) 보유로 대신한다.
#   미국 상장: 야후 funds_data(상위 10·섹터·보수·순자산)
#   과세 문구는 페르소나 미스ETF.txt 1-① 기준. 카드에 없는 값은 '자료 없음'.
import re
import time

import pandas as pd
import requests

BASE = 'https://openapi.koreainvestment.com:9443'
CASH = ('현금', '원화', '예금', 'CASH', '설정', '선물', 'KRW')

TAX = {
    '국내': '국내 주식형: 매매차익 비과세, 분배금 배당소득세 15.4%',
    '혼합': '국내 상장 해외(혼합) ETF: 매매차익·분배금 모두 배당소득세 15.4%(금융소득 2천만 원 초과 시 종합과세)',
    '해외': '국내 상장 해외 ETF: 매매차익·분배금 모두 배당소득세 15.4%(금융소득 2천만 원 초과 시 종합과세)',
    '금': '금현물 ETF: 자료 없음(세법 확인 필요)',
    '현금성': '국내 상장 채권·현금성: 매매차익·분배금 배당소득세 15.4%',
    '미국': '미국 상장: 양도소득세 22%(연 250만 원 공제, 분리과세), 배당은 미국 원천 15%',
}


def _get(token, key, secret, path, tr, params):
    h = {'content-type': 'application/json; charset=utf-8', 'authorization': f'Bearer {token}', 'appkey': key,
         'appsecret': secret, 'tr_id': tr, 'custtype': 'P'}
    err = ''
    for n in range(3):
        try:
            time.sleep(0.25)
            j = requests.get(f'{BASE}{path}', headers=h, params=params, timeout=15).json()
            if j.get('rt_cd') == '0':
                return j
            err = f"{j.get('msg_cd')} {j.get('msg1')}"
        except Exception as e:
            err = str(e)[:80]
        time.sleep(1 + 2 * n)
    raise RuntimeError(err)


def _f(x):
    try:
        v = float(str(x).replace(',', ''))
        return v
    except Exception:
        return None


def kr_holdings(token, key, secret, code, top=10):
    """한투 ETF 구성종목 전부(해외 종목 포함). [(코드, 이름, 비중%)] 비중 큰 순. 현금·선물 줄은 뺀다."""
    j = _get(token, key, secret, '/uapi/etfetn/v1/quotations/inquire-component-stock-price', 'FHKST121600C0',
             {'FID_COND_MRKT_DIV_CODE': 'J', 'FID_INPUT_ISCD': code, 'FID_COND_SCR_DIV_CODE': '11216'})
    rows = j.get('output2') or []
    pick = lambda r, *ks: next((r[k] for k in ks if r.get(k) not in (None, '')), None)
    out = []
    for r in rows:
        nm = (pick(r, 'hts_kor_isnm', 'prdt_name') or '').strip()
        w = _f(pick(r, 'etf_cnfg_issu_rlim', 'etf_vltn_amt_rlim', 'rlim'))
        cd = str(pick(r, 'stck_shrn_iscd', 'mksc_shrn_iscd') or '').strip()
        if not nm or w is None or w <= 0 or any(c in nm.upper() for c in CASH):
            continue
        out.append((cd, nm, w))
    out.sort(key=lambda x: -x[2])
    return out[:top], len(rows)


def kr_quote(token, key, secret, code):
    """ETF 현재가: NAV·괴리율·추적오차율·순자산. 칸 이름이 바뀌면 빈칸."""
    o = _get(token, key, secret, '/uapi/etfetn/v1/quotations/inquire-price', 'FHPST02400000',
             {'FID_COND_MRKT_DIV_CODE': 'J', 'FID_INPUT_ISCD': code}).get('output') or {}
    g = lambda *ks: next((_f(o[k]) for k in ks if o.get(k) not in (None, '')), None)
    return {'종가': g('stck_prpr'), 'NAV': g('nav'), '괴리율(%)': g('dprt'), '추적오차율(%)': g('trc_errt'),
            '순자산(억원)': g('etf_ntas_ttam')}


def us_holdings(ticker, top=10):
    """야후 funds_data: 상위 보유·섹터·보수·순자산·설명."""
    import yfinance as yf
    f = yf.Ticker(ticker).funds_data
    d = f.top_holdings.head(top)
    w = d['Holding Percent'] if 'Holding Percent' in d else d.iloc[:, -1]
    nm = d['Name'] if 'Name' in d else [''] * len(d)
    hold = [(str(t), str(n), round(float(x) * 100, 2)) for t, n, x in zip(d.index, nm, w)]
    info = {}
    try:
        op = f.fund_operations
        col = op.columns[0]
        info['보수(%)'] = round(float(op.loc['Annual Report Expense Ratio', col]) * 100, 2)
        info['순자산(야후 원값)'] = round(float(op.loc['Total Net Assets', col]), 1)
    except Exception:
        pass
    try:
        sw = {k: round(v * 100, 1) for k, v in (f.sector_weightings or {}).items() if v and v > 0.005}
        info['섹터'] = ', '.join(f'{k} {v}%' for k, v in sorted(sw.items(), key=lambda x: -x[1]))
    except Exception:
        pass
    try:
        info['설명'] = re.split(r'(?<=\.)\s', f.description or '')[0][:300]
    except Exception:
        pass
    return hold, info


def okey(code, name):
    """겹침 비교 열쇠: 국내 6자리 코드는 그대로, 미국 티커는 대문자, 아니면 이름 앞 두 낱말."""
    c = str(code or '').strip().upper()
    if re.fullmatch(r'\d{6}', c) or re.fullmatch(r'[A-Z]{1,5}(\.[A-Z])?', c):
        return c
    w = re.sub(r'[^0-9A-Za-z가-힣 ]', ' ', str(name)).upper().split()
    w = [x for x in w if x not in ('INC', 'CORP', 'CO', 'LTD', 'THE', 'CLASS', 'A', 'ORD', 'PLC', 'NV', 'HOLDINGS')]
    return ' '.join(w[:2])


def overlap(H, nos):
    """반도체 겹침 표: 두 ETF 상위 10에 같이 든 종목의 작은 쪽 비중 합(%) — 상위 10만 비교."""
    k = {n: {} for n in nos}
    for r in H[H['번호'].isin(nos)].itertuples():
        k[r.번호][r.열쇠] = k[r.번호].get(r.열쇠, 0) + r.비중
    M = pd.DataFrame(index=nos, columns=nos, dtype=float)
    for a in nos:
        for b in nos:
            M.loc[a, b] = round(sum(min(k[a][x], k[b][x]) for x in set(k[a]) & set(k[b])), 1)
    return M


def card(r, hold, q, src, today):
    """ETF 카드 한 장(txt). r: meta 줄(+이름), hold: [(코드, 이름, 비중)], q: 정보 dict."""
    top3 = round(sum(w for _, _, w in hold[:3]), 1) if hold else None
    top10 = round(sum(w for _, _, w in hold[:10]), 1) if hold else None
    nm = r['이름']
    us = r['상장'] == '미국'
    hedge = ('달러 자산 그대로(미국 상장)' if us else '환헤지(H)' if '(H)' in nm else
             '해당 없음(원화 자산)' if r['기초자산'] in ('국내', '금', '현금성') else '환노출(이름에 H 없음, 확인 필요)')
    tax = TAX['미국'] if us else TAX.get(r['기초자산'], '자료 없음')
    L = [f'ETF 카드 | {r["번호"]} {nm} | 기준 {today[:4]}-{today[4:6]}-{today[6:]} | 위원 미스 ETF',
         f'상장: {r["상장"]} | 코드: {r["코드"]} | 기초자산: {r["기초자산"]}',
         f'추종 지수·설명: {q.get("설명") or "자료 없음"}',
         f'환헤지: {hedge}',
         f'보수: {q["보수(%)"]}%' if q.get('보수(%)') is not None else '보수: 자료 없음',
         f'괴리율: {q["괴리율(%)"]}% | 추적오차율: {q.get("추적오차율(%)")}% | NAV {q.get("NAV")}' if q.get('괴리율(%)') is not None else '괴리율: 자료 없음',
         f'순자산: {q.get("순자산(억원)")}억원' if q.get('순자산(억원)') is not None else
         (f'순자산: {q["순자산(야후 원값)"]:,} (야후 Total Net Assets 원값, 단위 표기 없음)' if q.get('순자산(야후 원값)') is not None else '순자산: 자료 없음'),
         f'과세: {tax}',
         f'섹터: {q["섹터"]}' if q.get('섹터') else '섹터: 자료 없음',
         f'상위 3 쏠림(concentration, 쏠림): {top3}% | 상위 10 합: {top10}%' if hold else '상위 3 쏠림: 자료 없음',
         '', '상위 10 (순위, 이름, 코드, 비중%)']
    L += [f'{i}. {n} ({c}) {w:.2f}%' for i, (c, n, w) in enumerate(hold, 1)] or ['자료 없음']
    if r.get('메모'):
        L += ['', f'메모: {r["메모"]}']
    L += ['', f'출처: {src}']
    return '\n'.join(L) + '\n'
