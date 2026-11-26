"""위원 공부 고리 — 모으기 → 후보 → 의장 승인 → 서재 → 회의 인용 (2026-11-20 의장).
"니 스스로 자료를 모으고, 나에게 허락을 받고, 자료를 쌓아서 똑똑해지는 걸 하도록 해."
규칙(위원·낱말·후보 수)은 rules.yaml '공부'. Claude는 후보를 고르지 않는다: 낱말에 걸린 승인 매체 기사·논문만 후보가 된다.

  python meeting/study.py gather  [--date YYYYMMDD]            후보 만들기 → 위원공부/후보/YYYYMMDD_공부후보.csv
  python meeting/study.py approve --date YYYYMMDD 1,3,5 [--reject 2,4] [--why "의장 이유"]
                                                              의장 승인 기록 → 승인누적.csv + 서재 카드
  python meeting/study.py shelf                               승인누적.csv → 서재/<위원>/ 카드 다시 쓰기
서재 카드는 rag/build.py가 '위원공부' 폴더로 읽어 그 위원 서랍에 넣는다(rag/config.py SOURCES·PERSONAS).
드라이브 창구(DRIVE_URL·DRIVE_TOKEN)가 있으면 같은 파일을 '콜로키움 수집데이터/위원공부/'에도 올린다(스트림릿 승인 화면)."""
import argparse
import datetime as dt
import io
import os
import re
import sys
import xml.etree.ElementTree as ET

import pandas as pd
import requests
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'collect'))   # drive.py·ko_translate.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'collect', 'data'))   # px_store.py
KST = dt.timezone(dt.timedelta(hours=9))
LOCAL = os.environ.get('STUDY_ROOT', '/mnt/project-files/위원공부')
DRIVE = '콜로키움 수집데이터/위원공부'
COLS = ['번호', '위원', '분야', '종류', '제목(한글)', '원제목', '출처', '날짜', '링크', '요약(한글)', '요약',
        '쓰일칸', '의장판정', '의장이유']
ATOM = '{http://www.w3.org/2005/Atom}'


def rules():
    return yaml.safe_load(open(os.path.join(HERE, 'rules.yaml'), encoding='utf-8'))


# ------------------------------------------------------------------ 저장(로컬 공유 폴더 + 드라이브)
def _drive():
    try:
        import drive
        return drive if drive.ready() else None
    except Exception:
        return None


def _kan(rel):
    """11/26 의장 "데이터베이스칸으로 합쳐": 후보·승인 기록은 10년치 데이터베이스 칸(1_data/가격10년_공부후보·공부승인)."""
    m = re.match(r'후보/(\d{8})_공부후보\.csv$', rel)
    if m:
        return '공부후보', m.group(1)
    if rel == '승인누적.csv':
        return '공부승인', None
    return None, None


def read_csv(rel):
    k, day = _kan(rel)
    d = _drive()
    if k and d:
        import px_store as PS
        T = PS.rows(d, k)
        if day is not None:
            T = T[T['후보날짜'].astype(str) == day] if '후보날짜' in T else T.iloc[0:0]
        return T.reset_index(drop=True) if len(T) else pd.DataFrame(columns=COLS)
    p = os.path.join(LOCAL, rel)
    if os.path.exists(p):
        return pd.read_csv(p, encoding='utf-8-sig', dtype=str).fillna('')
    b = d.get(f'{DRIVE}/{rel}') if d else None
    return pd.read_csv(io.BytesIO(b), encoding='utf-8-sig', dtype=str).fillna('') if b else pd.DataFrame(columns=COLS)


def write_csv(rel, df):
    k, day = _kan(rel)
    d = _drive()
    if k and d:
        import px_store as PS
        if day is not None:
            PS.put_day(d, k, '후보날짜', day, df.drop(columns=['후보날짜'], errors='ignore'))
        else:
            PS.put_rows(d, k, df)
        return
    b = df.to_csv(index=False).encode('utf-8-sig')
    try:
        os.makedirs(os.path.dirname(os.path.join(LOCAL, rel)), exist_ok=True)
        open(os.path.join(LOCAL, rel), 'wb').write(b)
    except OSError:
        pass
    if d:
        d.put(f'{DRIVE}/{rel}', b)
    else:   # 11/20: 드라이브 창구 없이 만든 후보는 스트림릿 승인 화면에 안 보인다
        print(f'[주의] 드라이브 창구 없음 → {rel} 은 로컬에만 저장(승인 화면은 드라이브를 읽음)')


def arxiv(q, n=20):
    """arXiv 논문(제목·요약·날짜·링크). 실패하면 빈 목록."""
    try:
        r = requests.get(rules()['공부']['논문'].format(q=q.replace(' ', '+')), timeout=30)
        root = ET.fromstring(r.content)
    except Exception:
        return []
    out = []
    for e in root.findall(f'{ATOM}entry')[:n]:
        g = lambda k: re.sub(r'\s+', ' ', e.findtext(f'{ATOM}{k}') or '').strip()
        out.append(dict(날짜=g('published')[:10], 매체='arXiv', 제목=g('title'), 링크=g('id'), 요약=g('summary')[:600]))
    return out


def seen_links():
    """이미 후보에 오른 링크(승인·거절 모두) — 같은 자료를 두 번 묻지 않는다."""
    acc = read_csv('승인누적.csv')
    s = set(acc.get('링크', []))
    d = _drive()
    if d:   # 11/26: 후보는 이제 데이터베이스 칸 하나(공부후보, 후보날짜 칸) — 옛 '후보/' 폴더 대신 칸 전체에서 링크를 봄
        import px_store as PS
        s |= set(PS.rows(d, '공부후보').get('링크', []))
    if os.path.isdir(os.path.join(LOCAL, '후보')):
        for f in os.listdir(os.path.join(LOCAL, '후보')):
            if f.endswith('_공부후보.csv'):
                s |= set(pd.read_csv(os.path.join(LOCAL, '후보', f), encoding='utf-8-sig', dtype=str)['링크'].fillna(''))
    return s


def gather(day):
    R = rules()
    S = R['공부']
    # 11/26 의장 "위원 공부 후보 모으기는 고치세요": 뉴스 제목은 아침 수집(supplement.py RSS)이 쌓은 00_사건로그.csv만 읽음.
    # (회의가 뉴스를 받지 않게 바꾼 #365 뒤 지워진 events.fetch_rss를 부르다 멈추던 것). 이 단계는 아침 수집 끝(collect.yml)에서 돈다.
    import events
    d = _drive()
    b = d.get('콜로키움 수집데이터/00_퀀트입력/00_사건로그.csv') if d else None
    news = pd.read_csv(io.BytesIO(b), encoding='utf-8-sig', dtype=str).fillna('') if b else pd.DataFrame(columns=events.LOG_COLS)
    fail = [] if b else ['사건로그 없음']
    cut = (dt.datetime.strptime(day, '%Y%m%d') - dt.timedelta(days=S['지난일'])).strftime('%Y-%m-%d')
    news = news[news['날짜'].astype(str) >= cut] if len(news) else news
    seen = seen_links()
    rows = []
    for who, w in S['위원'].items():
        pat = re.compile(w['낱말'], re.I)
        hit = [dict(r) for _, r in news.iterrows() if pat.search(str(r['제목']))] if len(news) else []
        hit = sorted(hit, key=lambda r: str(r['날짜']), reverse=True)
        papers = arxiv(w['논문']) if w.get('논문') else []
        take, n = [], S['후보수']
        for r, kind in [(x, '기사') for x in hit] + [(x, '논문') for x in papers]:
            if r['링크'] in seen or len(take) >= n:
                continue
            seen.add(r['링크'])
            take.append(dict(위원=who, 분야=w['분야'], 종류=kind, 원제목=r['제목'], 출처=r['매체'], 날짜=str(r['날짜']),
                             링크=r['링크'], 요약=r.get('요약', ''), 쓰일칸=w['쓰일칸']))
        rows += take
    df = pd.DataFrame(rows, columns=COLS)
    if len(df):
        import ko_translate
        df['제목(한글)'] = ko_translate.translate(df['원제목'].tolist())
        df['요약(한글)'] = ko_translate.translate(df['요약'].fillna('').tolist())
    df['번호'] = range(1, len(df) + 1)
    df = df.fillna('')
    write_csv(f'후보/{day}_공부후보.csv', df)
    print(f'공부 후보 {len(df)}건 → 후보/{day}_공부후보.csv' + (f' (RSS 실패: {", ".join(fail)})' if fail else ''))
    return df


# ------------------------------------------------------------------ ③ 승인 → ④ 서재
def _nums(s):
    return [int(x) for x in re.split(r'[,\s]+', s or '') if x.strip().isdigit()]


def approve(day, ok, no=(), why=''):
    rel = f'후보/{day}_공부후보.csv'
    C = read_csv(rel)
    C['번호'] = C['번호'].astype(int)
    C.loc[C['번호'].isin(ok), '의장판정'] = '승인'
    C.loc[C['번호'].isin(no), '의장판정'] = '거절'
    if why:
        C.loc[C['번호'].isin(list(ok) + list(no)), '의장이유'] = why
    write_csv(rel, C)
    acc = read_csv('승인누적.csv')
    done = C[C['의장판정'].isin(['승인', '거절'])].assign(후보날짜=day)
    acc = pd.concat([acc[~acc['링크'].isin(done['링크'])], done], ignore_index=True)
    write_csv('승인누적.csv', acc)
    shelf(acc)
    print(f'{day}: 승인 {len(ok)}건, 거절 {len(no)}건 기록')


def card(r):
    t = r.get('제목(한글)') or r['원제목']
    return '\n'.join([
        f"# {t}", '',
        f"- 위원: {r['위원']} ({r['분야']})",
        f"- 출처: {r['출처']} · {r['날짜']} · {r['종류']}",
        f"- 원제목: {r['원제목']}",
        f"- 링크: {r['링크']}",
        f"- 쓰일 칸: {r['쓰일칸']}",
        f"- 의장 승인: {r.get('후보날짜', '')}" + (f" — {r['의장이유']}" if r.get('의장이유') else ''), '',
        '## 요약', r.get('요약(한글)') or r.get('요약') or '(요약 없음: 원문 링크 참고)', ''])


def shelf(acc=None):
    """승인된 줄만 서재/<위원>/YYYYMMDD_번호.md 카드로. 서재/색인.csv에 목록."""
    acc = read_csv('승인누적.csv') if acc is None else acc
    ok = acc[acc['의장판정'] == '승인']
    for _, r in ok.iterrows():
        rel = f"서재/{r['위원']}/{r.get('후보날짜', '')}_{r['번호']}.md"
        try:
            os.makedirs(os.path.join(LOCAL, os.path.dirname(rel)), exist_ok=True)
            open(os.path.join(LOCAL, rel), 'w', encoding='utf-8').write(card(r))
        except OSError:
            pass
        d = _drive()
        if d:   # 서재 카드도 드라이브에(스트림릿 승인 → 다음 회의 준비 때 카드가 쌓임)
            d.put(f'{DRIVE}/{rel}', card(r).encode('utf-8'))
    write_csv('서재/색인.csv', ok.reindex(columns=['후보날짜', '번호', '위원', '분야', '종류', '제목(한글)', '원제목', '출처', '날짜', '링크', '쓰일칸', '의장이유']))
    print(f'서재 카드 {len(ok)}장')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['gather', 'approve', 'shelf'])
    ap.add_argument('nums', nargs='?', default='')
    ap.add_argument('--date', default=dt.datetime.now(KST).strftime('%Y%m%d'))
    ap.add_argument('--reject', default='')
    ap.add_argument('--why', default='')
    a = ap.parse_args()
    if a.cmd == 'gather':
        gather(a.date)
    elif a.cmd == 'approve':
        approve(a.date, _nums(a.nums), _nums(a.reject), a.why)
    else:
        shelf()


if __name__ == '__main__':
    main()
