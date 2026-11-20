"""사건상태.csv·변수달력.csv를 규칙으로 만든다(2026-11-17 의장: 사람·AI가 웹 검색으로 손으로 채우지 않는다).
- 사건상태: 승인 매체 RSS 제목(+07시 뉴스.csv의 승인 매체 줄)을 날마다 쌓은 로그에서, rules.yaml '사건'의 낱말이
  '유지일' 안에 나왔으면 '진행 중(최근 보도 날짜)'. 엔진 features.py가 업종 글자로 종목에 붙여 B10 사건 역풍에 쓴다.
- 변수달력: 07시 일정.csv(DART 공시·FRED 발표 달력·야후 예정일)에서 rules.yaml '변수' 규칙에 맞는 줄만.
  확정 = 예 이고 영향 층이 있으면 엔진 orders.py B28(주문 50%)이 읽는다."""
import re
import datetime as dt
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import pandas as pd
import requests

KST = dt.timezone(dt.timedelta(hours=9))
LOG_COLS = ['날짜', '매체', '제목', '링크']


def _read(d, name):
    try:
        return pd.read_csv(f'{d}/{name}.csv', encoding='utf-8-sig')
    except FileNotFoundError:
        return pd.DataFrame()
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 빈 파일·깨진 파일이면 그 칸만 비움
        print(f'[빠진 자료] {name} → 그 칸만 비우고 계속: {type(e).__name__}')
        return pd.DataFrame()


def _date(s):
    s = (s or '').strip()
    if not s:
        return None
    try:
        return parsedate_to_datetime(s).astimezone(KST).date()
    except Exception:
        pass
    try:
        return pd.Timestamp(s).tz_localize(None).date() if pd.Timestamp(s).tzinfo is None else pd.Timestamp(s).tz_convert(KST).date()
    except Exception:
        return None


def fetch_rss(R, timeout=20):
    """승인 매체 RSS 제목. 실패한 주소는 건너뛰고 이유를 돌려준다."""
    rows, fail = [], []
    for media, url in R.get('RSS', []):
        try:
            r = requests.get(url, timeout=timeout, headers={'User-Agent': 'Mozilla/5.0 (colloquium rss)'})
            r.raise_for_status()
            root = ET.fromstring(r.content)
            items = root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')
            for it in items:
                g = lambda k: (it.findtext(k) or it.findtext('{http://www.w3.org/2005/Atom}' + k) or '').strip()
                link = g('link') or (it.find('{http://www.w3.org/2005/Atom}link').get('href') if it.find('{http://www.w3.org/2005/Atom}link') is not None else '')
                day = _date(g('pubDate') or g('published') or g('updated') or g('{http://purl.org/dc/elements/1.1/}date'))
                if g('title') and day:
                    rows.append(dict(날짜=str(day), 매체=media, 제목=g('title'), 링크=link))
        except Exception as e:
            fail.append(f'{media}({type(e).__name__})')
    return pd.DataFrame(rows, columns=LOG_COLS), fail


def news_csv_rows(d, R, today):
    """07시 뉴스.csv 중 승인 매체 줄(연합뉴스·CNBC 등). 시각 칸이 'MM-DD HH:MM'이라 올해로 붙인다."""
    N = _read(d, '뉴스')
    if not len(N):
        return pd.DataFrame(columns=LOG_COLS)
    ok = R['국장']['승인매체']
    rows = []
    for _, x in N.iterrows():
        src = str(x.get('출처', ''))
        media = next((m for m in ok if m in src), None)
        m = re.match(r'(\d\d)-(\d\d)', str(x.get('시각(한국)', '')))
        if not media or not m:
            continue
        rows.append(dict(날짜=f'{today.year}-{m.group(1)}-{m.group(2)}', 매체=media, 제목=str(x['제목']), 링크=str(x.get('링크', ''))))
    return pd.DataFrame(rows, columns=LOG_COLS)


def update_log(old, new, today, keep_days=60):
    L = pd.concat([old, new], ignore_index=True) if len(old) else new.copy()
    if not len(L):
        return pd.DataFrame(columns=LOG_COLS)
    L = L.drop_duplicates(['매체', '제목'], keep='first')
    L = L[pd.to_datetime(L['날짜'], errors='coerce') >= pd.Timestamp(today) - pd.Timedelta(days=keep_days)]
    return L.sort_values('날짜', ascending=False).reset_index(drop=True)


def event_state(R, log, today):
    """규칙: 최근 유지일 안에 승인 매체 제목이 '낱말'(과 '함께' 낱말)을 담으면 진행 중."""
    rows = []
    L = log.copy()
    L['_d'] = pd.to_datetime(L['날짜'], errors='coerce')
    for ev in R.get('사건', []):
        w = re.compile(ev['낱말'], re.I)
        w2 = re.compile(ev['함께'], re.I) if ev.get('함께') else None
        win = L[L['_d'] >= pd.Timestamp(today) - pd.Timedelta(days=int(ev.get('유지일', 14)))]
        hit = win[win['제목'].map(lambda t: bool(w.search(t)) and (w2 is None or bool(w2.search(t))))]
        if not len(hit):
            continue
        last = hit.sort_values('_d').iloc[-1]
        for sec in ev['업종']:
            rows.append(dict(업종=sec, 사건=ev['사건'], 상태=f"진행 중(최근 보도 {last['날짜']}, {len(hit)}건)",
                             날짜=last['날짜'], 출처=f"{last['매체']} \"{last['제목']}\""))
    return pd.DataFrame(rows, columns=['업종', '사건', '상태', '날짜', '출처'])


def calendar(R, d, today):
    """07시 일정.csv → 변수달력.csv (엔진 칸 그대로: 시기,사건,영향 업종 낱말,방향,출처,날짜,영향 층,확정)."""
    V = R['변수']
    S = _read(d, '일정')
    U = _read(d, '유니버스')
    cols = ['시기', '사건', '영향 업종 낱말', '방향', '출처', '날짜', '영향 층', '확정']
    if not len(S):
        return pd.DataFrame(columns=cols)
    # 종목 이름 → (번호, 층, 섹터)
    key = {}
    for _, u in U.iterrows():
        for nm in (u.get('정식 종목명'), u.get('원본 표기')):
            if isinstance(nm, str) and nm.strip():
                key[nm.strip().lower()] = (u['번호'], u.get('층'), str(u.get('섹터/테마', '')))
    cap_kr = dict(zip(_read(d, '밸류에이션').get('번호', []), pd.to_numeric(_read(d, '밸류에이션').get('시가총액(억원)', pd.Series(dtype=float)), errors='coerce')))
    SEC = _read(d, 'SEC')
    cap_us = dict(zip(SEC.get('번호', []), pd.to_numeric(SEC.get('시가총액(백만$)', pd.Series(dtype=float)), errors='coerce')))
    SEC_NM = {str(n).lower(): no for n, no in zip(SEC.get('정식 종목명', []), SEC.get('번호', []))}
    U_by_no = {u['번호']: (u['번호'], u.get('층'), str(u.get('섹터/테마', ''))) for _, u in U.iterrows()}

    def find(name):
        n = str(name).strip().lower()
        if n in key:
            return key[n]
        n2 = re.sub(r',?\s*(inc\.?|corporation|corp\.?|company|co\.?|ltd\.?|plc|holdings?)$', '', n).replace('the ', '').strip()
        for k, v in key.items():
            if k == n2 or (len(n2) >= 4 and (k.startswith(n2) or n2.startswith(k))):
                return v
        if n in SEC_NM and SEC_NM[n] in U_by_no:
            return U_by_no[SEC_NM[n]]
        return None

    rows = []
    end = pd.Timestamp(today) + pd.Timedelta(days=int(V.get('일수', 14)))
    ind = re.compile(V['지표_낱말'], re.I)
    for _, s in S.iterrows():
        day = pd.to_datetime(s['날짜'], errors='coerce')
        if pd.isna(day) or day < pd.Timestamp(today) or day > end:
            continue
        kind, who, what, chk = str(s['구분']), str(s['대상']), str(s['내용']), str(s.get('확인', ''))
        src = f"{s.get('출처', '')} · {chk}".strip(' ·')
        timed = str(s.get('시각(한국)', '')).strip() not in ('', '미정', 'nan')
        if kind == '미국 지표' and (ind.search(who) or ind.search(what)):
            rows.append(dict(시기=str(day.date()), 사건=f'{who} 발표', **{'영향 업종 낱말': ''}, 방향='양쪽(지표 결과)', 출처=src,
                             날짜=str(day.date()), **{'영향 층': ''}, 확정='예' if chk.startswith('확정') else '아니오'))
            continue
        if '실적' not in kind:
            continue
        hit = find(who)
        if not hit:
            continue
        no, lay, sec = hit
        if kind.startswith('미국'):
            big = (cap_us.get(no) or 0) >= V['대형_미국_시총(백만달러)']
            sure = chk.startswith('확정') or (V.get('미국실적_시각있으면_확정') and timed)
        else:
            big = (cap_kr.get(no) or 0) >= V['대형_한국_시총(억원)'] and '실적' in what and 'IR' not in what and '설명회' not in what
            sure = chk.startswith('확정')
        if not big:
            continue
        lays = '|'.join(V['AI층']) if lay in V['AI층'] else str(lay)
        rows.append(dict(시기=str(day.date()), 사건=f'{who} 실적({what})', **{'영향 업종 낱말': sec.replace('·', '|')}, 방향='양쪽(실적 결과)',
                         출처=src, 날짜=str(day.date()), **{'영향 층': lays}, 확정='예' if sure else '아니오', _k=no))
    C = pd.DataFrame(rows, columns=cols + ['_k'])
    if len(C):   # 같은 종목·같은 날이 두 줄(시각 있음/미정)이면 확정 줄 하나만
        C['_k'] = C['_k'].fillna(C['사건'])
        C = C.sort_values('확정', ascending=False).drop_duplicates(['_k', '날짜']).sort_values('날짜').reset_index(drop=True)
    return C[cols]
