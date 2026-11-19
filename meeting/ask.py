"""돌발 질문(회의 원고에 없는 질문)에 프로그램이 답한다 — 2026-11-19 의장.
Claude는 문장을 쓰지 않고 이 프로그램 출력을 그대로 옮긴다. 규칙은 rules.yaml '돌발질문'.

쓰는 법:
  python meeting/ask.py --dir <그날 드라이브 폴더를 받은 곳> "삼성전자 지금 팔아야 하나?"
  폴더에는 YYYYMMDD_판정표.csv, YYYYMMDD_회의원고.txt(있으면 YYYYMMDD_종목색인.csv)가 있어야 한다.
답 순서: ① 종목 이름 → 담당 위원이 판정표 줄 ② 위원 이름 → 원고 그 위원 칸 ③ 낱말 → 원고 그 위원 칸 ④ 룰 미정 + 장부 기록."""
import argparse
import csv
import datetime as dt
import glob
import os
import re

import pandas as pd
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
KST = dt.timezone(dt.timedelta(hours=9))
DESKS = ['미스 세마이', '미스터 빅스', '미스터 로보', '미스 파이낸스', '마담헤비', '일라이 존슨']


def _latest(d, suffix, date=None):
    fs = sorted(glob.glob(os.path.join(d, f'{date or "*"}_{suffix}')))
    return fs[-1] if fs else None


def _norm(s):
    s = str(s).lower()
    s = re.sub(r',?\s*(inc\.?|corporation|corp\.?|company|co\.?|ltd\.?|plc|holdings?|limited|group)\b', '', s)
    return re.sub(r'[\s.,·()\-]', '', s)


def find_stocks(q, S, X):
    """질문 속 종목: 판정표 종목명·색인 별칭(원본 표기·티커·코드)이 질문에 들어 있으면. 긴 이름부터."""
    qn = _norm(q)
    qw = set(re.findall(r'[A-Za-z]{2,6}', q))   # 티커는 단어로만
    names = []
    al = dict(zip(X['종목'], X['별칭'].fillna(''))) if len(X) else {}
    for nm in S['종목'].astype(str):
        keys = [nm] + [a for a in str(al.get(nm, '')).split('|') if a]
        for k in keys:
            kn = _norm(k)
            if re.fullmatch(r'[A-Z]{1,5}', k):
                hit = k in qw
            else:
                hit = len(kn) >= 2 and kn in qn
            if hit:
                names.append((len(kn), nm))
                break
    names.sort(reverse=True)
    out = []
    for _, nm in names:   # '삼성전자우'가 맞으면 '삼성전자'는 빼지 않음 — 둘 다 질문에 있을 수 있으니 포함 관계만 정리
        if not any(_norm(nm) in _norm(o) and nm != o for o in out):
            out.append(nm)
    return out


def sections(txt):
    """회의원고.txt → {위원: [줄]}."""
    sec, cur = {}, None
    for line in txt.splitlines():
        m = re.match(r'^(\S[^:：]{0,15}):\s*$', line)
        if m and not line.startswith(('■', '|')):
            cur = m.group(1).strip()
            sec[cur] = []
        elif cur and line and not line.startswith('='):
            sec[cur].append(line)
        elif line.startswith('='):
            cur = None
    return {k: v for k, v in sec.items() if v}


def _v(x):
    if x is None or (isinstance(x, float) and pd.isna(x)) or str(x) in ('', 'nan'):
        return None
    return x


def stock_answer(names, S, X, cols):
    S = S.set_index('종목')
    desk = dict(zip(X['종목'], X['데스크'].fillna(''))) if len(X) else {}
    out = []
    for nm in names:
        r = S.loc[nm]
        who = desk.get(nm) or '뚜지'
        out.append(f'{who}: {nm} ({r.get("시장", "")} · {r.get("층", "")})')
        i = 0
        for c in cols:
            v = _v(r.get(c))
            if v is None:
                continue
            i += 1
            out.append(f'{i}. {c}: {v}')
        out.append('(근거: 오늘 판정표 — 퀀트센터 엔진 blocks.yaml 결과 그대로)')
    if len(names) > 1:
        T = S.loc[names, [c for c in ('추천', '블록예비율', '싼가', '점수', '갈래', '매도신호') if c in S.columns]]
        T = T.sort_values([c for c in ('블록예비율', '싼가', '점수') if c in T.columns], ascending=False)
        out.append('')
        out.append('뚜지: 비교(블록 예 비율 → 싼가 → 점수 순, 엔진 추천 정렬과 같음)')
        for k, (nm, r) in enumerate(T.iterrows(), 1):
            out.append(f'{k}. {nm}: ' + ', '.join(f'{c} {_v(v) if _v(v) is not None else "-"}' for c, v in r.items()))
    return '\n'.join(out)


def log_q(path, q, route, who):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    new = not os.path.exists(path)
    with open(path, 'a', encoding='utf-8-sig' if new else 'utf-8', newline='') as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(['일시(한국)', '질문', '답한 길', '위원', '규칙 정함'])
        w.writerow([dt.datetime.now(KST).strftime('%Y-%m-%d %H:%M'), q, route, who, ''])


def answer(q, d, R, date=None):
    A = R['돌발질문']
    fp, ft, fx = _latest(d, '판정표.csv', date), _latest(d, '회의원고.txt', date), _latest(d, '종목색인.csv', date)
    if not fp or not ft:
        return '원고 미생성: 그날 판정표·회의원고 파일이 없습니다.', '파일 없음', ''
    S = pd.read_csv(fp, encoding='utf-8-sig')
    X = pd.read_csv(fx, encoding='utf-8-sig') if fx else pd.DataFrame(columns=['종목', '별칭', '데스크'])
    txt = open(ft, encoding='utf-8').read()
    sec = sections(txt)
    # ① 종목
    names = find_stocks(q, S, X)
    if names:
        return stock_answer(names, S, X, A['종목칸']), '종목', ','.join(names)
    # ② 위원 이름
    for who in sorted(sec, key=len, reverse=True):
        if who in q:
            return f'{who}:\n' + '\n'.join(sec[who]) + '\n(오늘 회의원고 그 위원 칸 그대로)', '위원 이름', who
    # ③ 낱말
    for who, pat in A['위원낱말']:
        if re.search(pat, q, re.I) and who in sec:
            return f'{who}:\n' + '\n'.join(sec[who]) + f'\n(오늘 회의원고 그 위원 칸 그대로 — 질문 낱말 규칙 "{pat}")', '낱말', who
    # ④ 룰 미정
    return '룰 미정: 이 질문에 답할 규칙이 코드에 없습니다. 질문을 장부에 적었고, 의장께서 기준을 정하시면 규칙으로 넣겠습니다.', '룰 미정', ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('question')
    ap.add_argument('--dir', default='.')
    ap.add_argument('--date', help='YYYYMMDD(없으면 폴더의 가장 최근 날짜)')
    ap.add_argument('--log', help='장부 경로(기본: rules.yaml 돌발질문.장부)')
    ap.add_argument('--no-log', action='store_true')
    a = ap.parse_args()
    R = yaml.safe_load(open(os.path.join(HERE, 'rules.yaml'), encoding='utf-8'))
    text, route, who = answer(a.question, a.dir, R, a.date)
    print(text)
    if not a.no_log:
        base = '/mnt/project-files' if os.path.isdir('/mnt/project-files') else '.'
        log_q(a.log or os.path.join(base, R['돌발질문']['장부']), a.question, route, who)


if __name__ == '__main__':
    main()
