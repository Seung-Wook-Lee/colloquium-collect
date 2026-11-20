"""위원 발언 원고를 코드로 만든다(2026-11-17 의장: 위원 발언·오늘의 한 종목은 AI가 즉흥으로 쓰지 않는다).
입력  : 07시 수집 파일(입력 폴더, 날짜 앞머리 없는 이름) + 퀀트센터 엔진 결과(판정표 S, 시장블록 M, 시장 값 m) + rules.yaml
규칙  : 숫자는 파일 값 그대로, 판정은 엔진 칸 또는 rules.yaml 문턱, 문장은 이 파일의 틀(위원마다 함수 하나).
출력  : 회의원고.txt(사람이 읽는 대본), 발표.json(스트림릿 '회의 발표' 화면), 오늘의한종목.csv
페르소나를 고칠 때: 숫자·낱말·순서는 rules.yaml, 문장 틀은 이 파일의 해당 위원 함수만 고친다."""
import datetime as dt
import json
import math
import os

import numpy as np
import pandas as pd

import re as _re
BAN = _re.compile(r'^(?:카카오|LIG|LG|LS)(?![A-Za-z])')   # 콜로키움_룰.txt 4장: 언급하지 않는다(rules.yaml 금지이름으로 바꿀 수 있음)


def banned(name):
    return bool(BAN.search(str(name).strip()))


DESKS = ['미스 세마이', '미스터 빅스', '미스터 로보', '미스 파이낸스', '마담헤비', '일라이 존슨']


# ---------------------------------------------------------------- 숫자 글씨
def ok(v):
    return v is not None and not (isinstance(v, float) and math.isnan(v)) and not (isinstance(v, str) and v.strip() in ('', 'nan'))


def num(v):
    try:
        x = float(str(v).replace(',', ''))
        return None if math.isnan(x) else x
    except Exception:
        return None


def n(v, d=1, u=''):
    v = num(v)
    return '자료 없음' if v is None else f'{v:,.{d}f}{u}'


def p(v, d=1, u='%'):
    v = num(v)
    return '자료 없음' if v is None else f'{v:+,.{d}f}{u}'


GAL = {'눌림': '52주 고점에서 10% 넘게 떨어짐(눌림)', '주도': '52주 고점 10% 안(주도)'}


SIGC = {'빨강': 'red', '주황': 'orange', '초록': 'green', '노랑': 'orange'}
_CHG = _re.compile(r'^(.*?)\s*\(((?:[^()]|\([^()]*\))*?(?:1달|1주|YTD|전일|직전|전년|1개월|1주 전|20일)(?:[^()]|\([^()]*\))*)\)\s*(.*)$')


class L:
    """발언 한 줄: 제목, 사실, 이유(근거). 이유는 화면에서 작은 회색 글씨.
    11/20 의장 "엑셀처럼 표로": 화면은 [항목 | 값 | 변화 | 기준·신호 | 근거] 표. val·chg·crit·sig를 주지 않으면 fact·why에서 나눈다."""
    def __init__(self, title, fact, why='', val=None, chg=None, crit=None, sig=None):
        self.title, self.fact, self.why = title, fact, why
        self.val, self.chg, self.crit, self.sig = val, chg, crit, sig

    def row(self):
        fact, why = str(self.fact), str(self.why or '')
        val, chg, crit, sig = self.val, self.chg, self.crit, self.sig
        if val is None:
            m = _CHG.match(fact)
            if chg is None and m and len(m.group(1)) <= 40:
                val, chg = (m.group(1) + (' ' + m.group(3) if m.group(3) else '')).strip(), m.group(2)
            else:
                val = fact
        m = _re.match(r'^\[(빨강|주황|초록|노랑)\]\s*(.*)$', why)
        if m and sig is None:
            sig, why = SIGC[m.group(1)], m.group(2)
        if crit is None:
            m2 = _re.match(r'^(.*?)\s*\(([^()]*(?:\.csv|FRED|ICI|블룸버그|야후)[^()]*)\)$', why)
            if sig and m2:
                crit, why = m2.group(1), m2.group(2)
            elif sig:
                crit, why = why, ''
            elif why.startswith('규칙:'):
                crit, why = why[3:].strip(), ''
            elif why.startswith(('의장 기준 신호 없음', '신호 없음')):
                crit, why = '신호 없음', why.replace('의장 기준 신호 없음', '').replace('신호 없음', '').strip(' ()')
        return {'항목': str(self.title), '값': str(val), '변화': str(chg or ''), '기준·신호': str(crit or ''), '근거': why, '신호': sig or ''}


def _read(d, name):
    try:
        return pd.read_csv(f'{d}/{name}.csv', encoding='utf-8-sig')
    except FileNotFoundError:
        return pd.DataFrame()


# ---------------------------------------------------------------- 엔진 표 + 종목 칸
def table(S, f):
    keep = [c for c in f.columns if c not in S.columns or c == '번호']
    T = S.merge(f[keep], on='번호', how='left')
    return T[~T['종목'].map(banned)].reset_index(drop=True)


def _env(r):
    return {k: (None if (isinstance(v, float) and math.isnan(v)) else v) for k, v in r.items()}


def _cond(expr, r):
    try:
        return bool(eval(expr, {'__builtins__': {}}, _env(r)))
    except Exception:
        return False


def _sort(T, keys):
    by, asc = [], []
    for k in keys:
        a = k.endswith('_asc')
        k = k[:-4] if a else k
        if k in T:
            by.append(k); asc.append(a)
    return T.sort_values(by, ascending=asc, na_position='last') if by else T


def pick(T, rule, extra=None):
    """rules.yaml 한종목 규칙 하나로 한 종목. 돌려주는 값: (행 또는 None, 후보 수)"""
    X = T if extra is None else T[extra]
    if rule.get('구분'):
        X = X[X['구분'] == rule['구분']]
    if rule.get('시장'):
        X = X[X['시장'] == rule['시장']]
    grades = rule.get('등급', ['추천'])
    if grades != ['전체']:
        X = X[X['판정'] == '후보']
    for g in (grades if grades != ['전체'] else [None]):
        G = X if g is None else X[X['추천'] == g]
        G = G[[_cond(rule.get('조건', 'True'), r) for _, r in G.iterrows()]] if len(G) else G
        if len(G):
            return _sort(G, rule.get('정렬', [])).iloc[0], len(G)
    return None, 0


def top7(T, RC):
    """오늘의 추천 종목 7: 옛 gen7.py와 같은 규칙(blocks.yaml 추천 설정, 손 목록 없음)."""
    nk, nu, vmax = RC.get('국내수', 5), RC.get('미국ETF수', 2), RC.get('변동성상한', 60)
    A = T.copy()
    A['미국ETF'] = (A['시장'] == '한국') & (A['구분'] != '개별주') & A['종목'].astype(str).str.contains('미국')
    cand = A[A['추천'] == '추천'].sort_values(['블록예비율', '싼가', '점수'], ascending=False)
    picks, drops = [], []
    for _, r in cand.iterrows():
        why = []
        if r['시장'] != '한국':
            why.append('미국 개별·해외 상장 → 국내 상장 ETF로만 편입(룰 2장)')
        if ok(r.get('vol60')) and r['vol60'] > vmax:
            why.append(f"60일 변동성 {r['vol60']:.0f}% > {vmax}%")
        if (num(r.get('f5')) or 0) < 0 and (num(r.get('f20')) or 0) < 0:
            why.append(f"외국인 5일 {n(r['f5'], 0, '억')}·20일 {n(r['f20'], 0, '억')} 동시 순매도")
        if why:
            drops.append((r['종목'], ' / '.join(why))); continue
        grp = 'us' if r['미국ETF'] else 'kr'
        if sum(1 for _, g in picks if g == grp) >= (nu if grp == 'us' else nk):
            drops.append((r['종목'], f"추천 등급이나 순위 밖(예 비율 {r['블록예비율']}, 싼가 {r['싼가']})")); continue
        picks.append((r, grp))
    return [r for r, _ in picks], drops


def ta(r):
    """닉스 팀 지표 읽기: 지지·저항, 볼린저, RSI, CCI, 스토캐스틱 슬로우, 이격도, 일목 — 일봉·주봉(닉스.csv 칸 그대로)."""
    out = []
    for k, nm, ma in (('일', '일봉', '20일'), ('주', '주봉', '20주')):
        g = lambda c: r.get(f'{k}_{c}')
        raw = lambda c: str(g(c)) if ok(g(c)) else '자료 없음'
        out.append(f"{nm} 지지 {raw('지지1')}({p(g('지지1_거리(%)'))}) · 저항 {raw('저항1')}({p(g('저항1_거리(%)'))}), "
                   f"볼린저 %B {n(g('볼린저_%B'), 2)}, RSI {n(g('RSI'), 0)}, CCI {n(g('CCI'), 0)}, "
                   f"스토캐스틱 K {n(g('STO_K'), 0)}/D {n(g('STO_D'), 0)}, {ma} 이격 {n(g(f'{ma}_이격도'), 1)}, 일목 구름 {g('일목_구름위치') if ok(g('일목_구름위치')) else '자료 없음'}")
    return ' | '.join(out)


# ---------------------------------------------------------------- 위원
class Ctx:
    def __init__(self, d, S, M, m, f, R, RC, today):
        self.d, self.S, self.M, self.m, self.f, self.R, self.RC, self.today = d, S, M, m, f, R, RC, today
        self.T = table(S, f)
        self.N = _read(d, '닉스').rename(columns={'번호': '번호'})
        self.T = self.T.merge(self.N[[c for c in self.N.columns if c.startswith(('일_', '주_')) or c == '번호']], on='번호', how='left') if len(self.N) else self.T
        self.mac = _read(d, '매크로')
        global BAN
        if R.get('금지이름'):
            BAN = _re.compile(r'^(?:' + '|'.join(map(_re.escape, R['금지이름'])) + r')(?![A-Za-z])')
        self.px = _read(d, '시세')
        if len(self.px):
            self.px = self.px[~self.px['정식 종목명'].map(banned)]
        self.news = _read(d, '뉴스')
        self.picks = {}
        self.gate = {}
        if R.get('결론') and R['결론'].get('시장관문', True):   # 11/20 의장 블록 정비 1번: 결론이 '사지 않는다'인 시장은 종목 추천 → 바닥 대기
            try:
                _, ST, _ = _buy_state(self)
                for mk, v in ST.items():
                    if not v['buy'] and v['act'] != '엔진 포트폴리오대로':
                        mask = (self.T['시장'] == mk) & (self.T['추천'] == '추천')
                        self.gate[mk] = (int(mask.sum()), v['act'])
                        self.T.loc[mask, '추천'] = '바닥 대기'
                        S.loc[(S['시장'] == mk) & (S['추천'] == '추천'), '추천'] = '바닥 대기'   # 판정표에도
            except Exception as e:   # noqa: BLE001
                self.gate['오류'] = (0, str(e)[:80])
        self.top, self.drops = top7(self.T, RC)
        bd = R.get('엘피스_200일선') or {}   # 11/20 의장: 현재가 ÷ 200일선이 하단~상단 = '안', 하단 아래 = '추세 무너짐', 상단 위 = '위'
        x = pd.to_numeric(self.T['px_ma200'], errors='coerce') if 'px_ma200' in self.T else pd.Series(np.nan, index=self.T.index)
        lo, hi = num(bd.get('하단')), num(bd.get('상단'))
        self.T['구간200'] = (np.where(x < lo, '추세 무너짐', np.where(x > hi, '위', '안')) if lo is not None and hi is not None else None)
        self.T.loc[x.isna(), '구간200'] = None
        self.band200 = dict(하단=lo, 상단=hi)
        self.U = _read(d, '유니버스')

    def mac_row(self, item):
        if not len(self.mac):
            return None
        x = self.mac[self.mac['항목'].astype(str).str.replace('\\', '') == item]
        return x.iloc[0] if len(x) else None

    def burden_opp(self):
        M = self.M
        if not len(M):
            return [], []
        b = M[(M['방향'] == '부담') & (M['결과'] == '통과')]['공식'].tolist()
        o = M[(M['방향'] == '기회') & (M['결과'] == '통과')]['공식'].tolist()
        return b, o

    def block_lines(self, side):
        """11/20 의장: 통과한 시장 블록 공식을 영어 공식 이름(굵은 제목) + 한글 설명(아랫줄)으로."""
        M = self.M
        if not len(M):
            return []
        X = M[(M['방향'] == side) & (M['결과'] == '통과')]
        return [L(str(r['영문']) if ok(r.get('영문')) else r['공식'], _re.sub(r'\((기회|부담)\)', '', str(r['공식'])).strip(), f"{r['블록']} {r['질문']}",
                  crit=side, sig='green' if side == '기회' else 'orange')
                for _, r in X.iterrows()]

    def regime(self, mk):
        m = self.m
        if f'DEF_{mk}' not in m:
            return None
        st = '방어' if m[f'DEF_{mk}'] else '평상'
        return st, m.get(f'ROT_G_{mk}'), m.get(f'ROT_M_{mk}'), m.get(f'IDX_{mk}')

    def set_pick(self, who, r, rule, mark='추천', why=''):
        self.picks[who] = dict(위원=who, 표시=mark if r is not None else '해당 없음', 종목='' if r is None else r['종목'],
                               번호='' if r is None else r['번호'], 시장='' if r is None else r['시장'],
                               규칙=rule.get('설명', ''), 근거=why)

    def pick_line(self, who, rule, r, cnt, why_fn, mark='추천'):
        if r is None:
            self.set_pick(who, None, rule)
            return L('오늘의 한 종목', '해당 없음', f"규칙: {rule.get('설명', '')} — 오늘 맞는 종목 0개")
        why = why_fn(r)
        self.set_pick(who, r, rule, mark, why)
        return L('오늘의 한 종목', f"[{mark}] {r['종목']} — {why}", f"규칙: {rule.get('설명', '')} (맞는 종목 {cnt}개 중 1위)")


def mr_market(c):
    """11/20 의장: 미스터 마켓은 시장만(개별 종목 금지). 오전 국장전 = 간밤 미국 시장만, 밤 미장전 = 한국 시장만.
    지수는 표(extra)로, 줄은 국면·이격만."""
    R = c.R['미스터 마켓']
    cfg = R['회의별'][c.session]
    out = []
    for mk in cfg['국면']:
        g = c.regime(mk)
        if g:
            st, G, M_, idx = g
            out.append(L(f'{mk} 국면', f"{st} 국면 · 지수 4국면 {idx or '자료 없음'}",
                         f"AI(S1~S3)÷금융·방어(S5~S6) 비율 50일 이격 {p(G, 2)}, 20일 변화 {p(M_, 2)} — 진입 −2%·−3%(5일 중 3일+당일), 둘 다 0 이상이면 해제"))
    rows = []
    for it in cfg['지수']:
        r = c.mac_row(it)
        if r is None:
            continue
        v, pv = num(r['값']), num(r.get('전일 값'))
        d1 = (v / pv - 1) * 100 if v and pv else None
        rows.append([it, n(v, 2), p(d1, 2), p(num(r.get('최고 대비(%)')))])
    tbl = ''
    if rows:
        out.append(L(cfg['지수제목'], ', '.join(f"{a} {b}({c_})" for a, b, c_, _ in rows), '07시 매크로.csv, 전일 값 대비 · 사상 최고 대비는 표'))
        tbl = '| 지수 | 종가 | 전일 대비 | 사상 최고 대비 |\n|---|---|---|---|\n' + '\n'.join('| ' + ' | '.join(x) + ' |' for x in rows)
    if cfg.get('코스피이격'):
        kg = c.m.get('KS_GAP50')
        if kg is not None:
            st = '과열' if kg >= R['코스피이격_과열'] else ('과열 주의' if kg >= R['코스피이격_주의'] else '과열 기준 아래')
            out.append(L('코스피 50일 이격', f"{kg:.1f} — {st}", f"의장 기준 {R['코스피이격_주의']} 과열 주의, {R['코스피이격_과열']} 과열"))
    return out, [], tbl


def mover_news(c, name):
    """크게 움직인 종목 ① 무슨 일: 07시 수집 뉴스 첫 기사(데스크가 씀)."""
    if not len(c.news):
        return ''
    hd = c.news[c.news.get('종목', pd.Series(dtype=str)).astype(str) == name]
    return f" · 기사: {hd.iloc[0]['출처']} \"{hd.iloc[0]['제목']}\"" if len(hd) else ''


def _gmd(g):
    """grid → 회의 원고(md) 표."""
    return (f"**{g['title']}**\n\n" if g.get('title') else '') + '| ' + ' | '.join(g['columns']) + ' |\n|' + '---|' * len(g['columns']) + '\n' + \
        '\n'.join('| ' + ' | '.join(str(x) for x in r) + ' |' for r in g['rows']) + (f"\n\n_출처: {g['source']}_" if g.get('source') else '')


def _etf_short(r):
    """미국 ETF = 티커(짧은 한글), 11/20 의장. 한국 ETF = 이름 그대로."""
    if r.get('시장') != '미국':
        return str(r['이름'])
    t = _re.sub(r'^미국\s+', '', str(r.get('섹터/테마') or '')).replace(' 지수', '').replace(' 섹터', '').strip()
    return f"{r['코드']}({t})" if t else str(r['코드'])


def miss_citadel(c):
    """11/20 의장 "안 보이니까 표로": 긴 나열은 표(grid), 줄은 요약만."""
    R = c.R['미스 시타델']; k = R['상위']
    out, G = [], []
    pre = getattr(c, 'session', '국장전') == '미장전'   # 11/21 의장: 미장전은 미국 수급, 한국 외국인 수급은 다음날 아침(국장전)에
    F = _read(c.d, '국내수급')
    F = F[~F['종목'].map(banned)] if len(F) else F
    if len(F) and not pre:
        for col in ('외국인 5일(억원)', '외국인 20일(억원)', '기관 5일(억원)', '개인 5일(억원)'):
            F[col] = pd.to_numeric(F[col], errors='coerce')
        s5 = F['외국인 5일(억원)'].sum()
        top = F.nlargest(k, '외국인 5일(억원)'); bot = F.nsmallest(k, '외국인 5일(억원)')
        out.append(L('외국인 순매수', f"한국 개별주 {len(F)}종목 외국인 5일 합계 {p(s5, 0, '억')} (상위·하위 종목은 아래 표)", f"기준일 {F['기준일'].iloc[0]}, 07시 국내수급.csv"))
        G.append({'type': 'grid', 'title': f'외국인 5일 순매수 상위·순매도 상위 {k}종목',
                  'columns': ['구분', '종목', '외국인 5일(억원)', '외국인 20일(억원)'],
                  'rows': [['순매수', r['종목'], p(r['외국인 5일(억원)'], 0, ''), p(r['외국인 20일(억원)'], 0, '')] for _, r in top.iterrows()] +
                          [['순매도', r['종목'], p(r['외국인 5일(억원)'], 0, ''), p(r['외국인 20일(억원)'], 0, '')] for _, r in bot.iterrows()],
                  'source': f"국내수급.csv, 기준일 {F['기준일'].iloc[0]}"})
        G.append({'type': 'grid', 'title': f'주체별 5일 순매수 합계(한국 개별주 {len(F)}종목)', 'columns': ['주체', '5일 합계(억원)'],
                  'rows': [[w, p(F[f'{w} 5일(억원)'].sum(), 0, '')] for w in ('외국인', '기관', '개인')], 'source': '국내수급.csv'})
        turn = F[F['표시'].astype(str).str.contains('매수 전환')]
        if len(turn):
            out.append(L('외국인 매수 전환', ', '.join(turn['종목'].head(5)), "국내수급.csv '표시' 칸"))
    A = _read(c.d, 'ETF자금')
    A = A[~A['이름'].map(banned)] if len(A) else A
    if len(A):
        A['유입_5일'] = pd.to_numeric(A['유입_5일'], errors='coerce')
        for mk, unit, div in ((('미국', '억 달러', 100),) if pre else (('한국', '억원', 1), ('미국', '억 달러', 100))):   # 미국 원자료 백만달러 → 억 달러
            X = A[A['시장'] == mk].dropna(subset=['유입_5일'])
            if len(X):
                fmt = (lambda v: p(v, 0, '')) if div == 1 else (lambda v: p(v / div, 1, ''))
                G.append({'type': 'grid', 'title': f'{mk} ETF 자금 5일 유입·유출 상위 {k}', 'columns': ['구분', 'ETF', f'5일 유입({unit})'],
                          'rows': [['유입', _etf_short(r), fmt(r['유입_5일'])] for _, r in X.nlargest(k, '유입_5일').iterrows()] +
                                  [['유출', _etf_short(r), fmt(r['유입_5일'])] for _, r in X.nsmallest(k, '유입_5일').iterrows()],
                          'source': 'ETF자금.csv(좌수 변화 × NAV)'})
    Q = _read(c.d, '수급포지셔닝')
    if len(Q):
        g = dict(zip(Q['항목'], Q['값'])); w = dict(zip(Q['항목'], Q['1주 전']))
        rows = []
        cta = num(g.get('CTA σ(근사)'))
        if cta is not None:
            zone = '수급 바닥 구간' if cta <= R['CTA_바닥'] else ('수급 고점 구간' if cta >= R['CTA_고점'] else '중간 구간')
            rows.append(['CTA positioning', f"{cta:+.2f}σ", f"{n(w.get('CTA σ(근사)'), 2)}σ", zone,
                         f"추세추종 펀드 포지션. {R['CTA_바닥']}σ 아래 바닥, +4σ 뒤 1.5σ 꺾이면 고점"])
        ve = num(g.get('변동성타기팅 노출(배)'))
        vz = R.get('볼타깃_많이팜', 0.6)
        if ve is not None:
            rows.append(['Vol-target exposure', f"{n(ve, 2)}배", f"{n(w.get('변동성타기팅 노출(배)'), 2)}배",
                         '이미 많이 팜(기회)' if ve < vz else '보통',
                         f"변동성 목표 펀드 보유 배수 = 목표 변동성 10% ÷ 실현 변동성(상한 1.5). {vz}배 아래 = 기계적 매도가 이미 많이 나옴"])
        buyn, upp, turn, plus = (num(g.get(k)) for k in ('추세 신호 매수 수(21·63·100일)', 'CTA 매수 전환까지(%)', '시스템 매수 전환', 'CTA 플러스 전환'))
        if buyn is not None:   # 11/20 의장: 시스템 자금 매수 전환이 중요(그래야 지른다)
            rows.append(['CTA 추세 신호(21·63·100일)', f"매수 {int(buyn)}/3", '', '전부 매수' if buyn >= 3 else f"매수 전환까지 S&P {p(upp, 1)}",
                         'S&P500이 21·63·100일 전보다 높으면 매수 신호(JPM 방식). 매수 전환까지 = 가장 가까운 매도 신호가 바뀌는 상승 폭'])
            vd = num(g.get('변동성타기팅 5일 변화(배)'))
            if turn == 1 or plus == 1:
                out.insert(0, L('시스템 거래 전환', '시스템 거래가 플러스(매수) 쪽으로 돌았습니다' if plus == 1 else '시스템 거래가 매수 쪽으로 돌기 시작했습니다',
                                f"CTA 매수 신호 {int(buyn)}/3, CTA 포지션 5일 {p(num(g.get('CTA σ 5일 변화')), 2, '')}σ, 변동성 목표 노출 5일 {p(vd, 2, '')}배",
                                crit='5일 사이 CTA 매수 신호가 늘고 CTA 포지션이 오름(CTA 0 위로 = 플러스)', sig='green'))
            else:
                out.append(L('시스템 거래 전환', '아직 아님' if (num(g.get('CTA σ 5일 변화')) or 0) <= 0 else '포지션은 오르지만 새 매수 신호 없음',
                             f"CTA 매수 신호 {int(buyn)}/3, 매수 전환까지 S&P {p(upp, 1)}, 변동성 목표 노출 5일 {p(vd, 2, '')}배"))
        if rows:
            out.append(L('포지셔닝', ', '.join(f"{r[0]} {r[1]}({r[3]})" for r in rows),
                         f"VIX 1년 백분위 {n(g.get('VIX 1년 백분위(%)'), 0)}%, VXN 1년 백분위 {n(g.get('VXN 1년 백분위(%)'), 0)}%"))
            G.append({'type': 'grid', 'title': '포지셔닝', 'columns': ['지표', '오늘', '1주 전', '구간', '읽는 법'], 'rows': rows, 'source': '수급포지셔닝.csv'})
    MM = _read(c.d, 'MMF')
    if len(MM):
        r = MM.iloc[0]
        out.append(L('미국 MMF 잔고', f"{n(r.get('잔고(조달러)'), 2)}조달러, 1주 {p(r.get('1주 변화(십억달러)'), 1, '십억달러')}", f"ICI, 기준 {r.get('기준일(수)', '')}"))
    rule = c.R['한종목']['미스 시타델']
    r, cnt = pick(c.T, rule)
    out.append(c.pick_line('미스 시타델', rule, r, cnt, lambda r: f"외국인 5일 {n(r['f5'], 0, '억')}, 20일 {n(r['f20'], 0, '억')}, 엔진 {r['추천']}(블록 예 {n(r['블록예비율'], 2)})"))
    return out, G, '\n\n'.join(_gmd(g) for g in G)


def macro_table(c):
    """11/20 의장: 매크로 체크리스트는 칸 맨 아래로, 이유·근거를 표로 자세히, 몇 번째 항목(빨강·주황 박스)인지도."""
    out = []
    C = _read(c.d, '매크로체크리스트')
    if len(C):
        sm = C[C['항목'] == '요약']
        X = C[C['항목'] != '요약'].reset_index(drop=True)
        head = str(sm.iloc[0]['값']).split('|')[0].strip() if len(sm) else ''
        good, bad = (X['좋아질 기미'] == '예').sum(), (X['나빠질 기미'] == '예').sum()
        rows = ['| 번호 | 항목 | 값 | 1주 전 | 1달 전 | 20일 고점 | 20일 저점 | 판정 | 판정 기준 | 출처 |', '|---|---|---|---|---|---|---|---|---|---|']
        for i, r in X.iterrows():
            j = '좋아질 기미' if r.get('좋아질 기미') == '예' else ('나빠질 기미' if r.get('나빠질 기미') == '예' else '변화 없음')
            rows.append(f"| {i + 1} | {r['항목']} | {r['값']} | {r.get('1주 전', '')} | {r.get('1달 전', '')} | {r.get('최근 고점', '')} | {r.get('최근 저점', '')} | "
                        f"{j} | {r.get('나쁜 쪽', '')} 나쁨, {r.get('문턱(가정치)', '')} | {r.get('출처', '')} |")
        out += [f"**매크로 체크리스트 · {head} · 좋아질 기미 {good}/{len(X)}, 나빠질 기미 {bad}/{len(X)}**", '', '\n'.join(rows).replace('nan', ''), '']
    M = c.M
    if len(M):
        X = M.copy()
        X['_on'] = X['결과'] == '통과'
        # 11/20 의장 '하나만 나와야지': 같은 블록·같은 지표의 문턱만 다른 공식(10년물 4.8%·5.0% 등)은 한 줄 — 켜진 것 중 가장 센 문턱
        X['_k'] = X['블록'].astype(str) + X['방향'].astype(str) + X['공식'].astype(str).str.replace(r'[−+-]?[\d.]+', '#', regex=True)
        X['_n'] = pd.to_numeric(X['공식'].astype(str).str.extract(r'([\d.]+)(?:[^\d.]*)$')[0], errors='coerce')   # 문턱 = 맨 끝 숫자(10Y의 10이 아님)
        X['_s'] = X.apply(lambda r: (r['_n'] if '이상' in str(r['공식']) else -r['_n']) if pd.notna(r['_n']) else 0, axis=1)
        X = X.sort_values(['_on', '_s'], ascending=[False, False]).drop_duplicates('_k')
        X = X.sort_values(['방향', '_on', '블록'], ascending=[True, False, True]).reset_index(drop=True)
        nb, no = (X['방향'] == '부담'), (X['방향'] == '기회')
        rows = ['| 번호 | 블록 | 질문 | 공식 | 쪽 | 오늘 |', '|---|---|---|---|---|---|']
        for i, r in X.iterrows():
            nm = _re.sub(r'\((기회|부담)\)', '', str(r['공식'])).strip()
            en_ = str(r['영문']) if ok(r.get('영문')) else ''
            for k, v in (('HY spread', 'High Yield Spread'), ('UST 10Y yield', 'US Treasury 10-Year Yield'), ('HY 스프레드', 'High Yield Spread'), ('HY ', 'High Yield Spread '), ('10Y−2Y', 'US Treasury 10-Year minus 2-Year'),
                         ('HMM bear-regime probability', 'Hidden Markov Model bear-regime probability'), ('HMM', 'Hidden Markov Model')):
                en_, nm = en_.replace(k, v), nm.replace(k, v)   # 11/20 의장: 약자 금지
            rows.append(f"| {i + 1} | {r['블록']} | {r['질문']} | {(en_ + ' — ') if en_ else ''}{nm} | "
                        f"{'나쁜 신호(부담)' if r['방향'] == '부담' else '좋은 신호(기회)'} | {'켜짐' if r['_on'] else '꺼짐'} |")
        out += [f"**시장 블록 · 나쁜 신호(부담) {nb.sum()}개 중 {(nb & X['_on']).sum()}개 켜짐, 좋은 신호(기회) {no.sum()}개 중 {(no & X['_on']).sum()}개 켜짐**",
                '', '\n'.join(rows), '']
    K = _read(c.d, '리스크')
    if len(K) and '신호' in K:
        Z = K[K['신호'].astype(str).str.contains('빨강|주황')].reset_index(drop=True)
        if len(Z):
            rows = ['| 번호 | 구분 | 항목 | 값 | 신호 | 이유 | 의장 기준 |', '|---|---|---|---|---|---|---|']
            for i, r in Z.iterrows():
                rows.append(f"| {i + 1} | {r.get('구분', '')} | {r['항목']} | {r['값']}{'' if str(r.get('단위', 'nan')) == 'nan' else r.get('단위')} | "
                            f"{r['신호']} | {r.get('표시', '')} | {r.get('의장 기준(참고)', '')} |")
            out += [f"**리스크 표 빨강·주황 박스 {len(Z)}개**", '', '\n'.join(rows).replace('nan', ''), '']
    return '\n'.join(out)


def rio(c):
    out = []
    for it in ('CPI 전년비', '근원 CPI 전년비', '근원 PCE 전년비'):   # 11/20 의장: CPI·Core CPI 둘 다, 연준 용어, 전월 대비
        r = c.mac_row(it)
        if r is not None:
            out.append(L(it.replace(' 전년비', '').replace('근원 CPI', 'Core CPI').replace('근원 PCE', 'Core PCE'),
                         f"전년비 {n(r['값'], 2, '%')}(전월 대비 {p(r['1달'], 2, '%p')})", f"기준 {r['기준일']}, {r['출처']}"))
    for it in ('미국 2년', '미국 10년'):   # 11/20 의장: 10년 실질 삭제
        r = c.mac_row(it)
        if r is not None:
            out.append(L(it, f"{n(r['값'], 3, '%')}(1달 {p(r['1달'], 2, '%p')}, YTD {p(r['YTD'], 2, '%p')})",
                         (f"[{r['신호']}] {r['표시']}" if ok(r.get('신호')) else '의장 기준 신호 없음') + ' (07시 매크로.csv)'))
    K = _read(c.d, '리스크')
    if len(K):
        h = K[K['항목'] == '하이일드 스프레드']
        if len(h):
            h = h.iloc[0]
            out.append(L('하이일드 스프레드', f"{n(h['값'], 2, '%')}(1주 전 {n(h['1주 전'], 2, '%')})", (f"[{h['신호']}] {h['표시']}" if ok(h.get('신호')) else '신호 없음') + ' (리스크.csv)'))
    V = _read(c.d, '지수밸류')
    if len(V):
        v = V.iloc[-1]
        out.append(L('지수 밸류', f"S&P500 선행 PER {n(v['선행PER'], 1, '배')}, 선행 EPS {n(v['선행EPS'], 1)}", f"{v['날짜']} {v['출처']}"))
    if c.m.get('KS_GAP50') is not None:
        g, MR = c.m['KS_GAP50'], c.R.get('미스터 마켓', {})
        hot, warn = MR.get('코스피이격_과열', 130), MR.get('코스피이격_주의', 125)
        out.append(L('시장 이격', f"코스피 50일 이격 {g:.1f}", '지수2년.csv 계산', val=f"코스피 50일 이격 {g:.1f}",
                     crit=f"{warn} 과열 주의 · {hot} 과열" + (' → 과열' if g >= hot else (' → 과열 주의' if g >= warn else '')),
                     sig='red' if g >= hot else ('orange' if g >= warn else '')))
    b, o = c.burden_opp()   # 11/20 의장: 시장 블록은 칸 맨 아래 표로 자세히(macro_table)
    dfn = any(c.m.get(f'DEF_{mk}') for mk in ('한국', '미국'))
    go = eval(c.R['미스 리스크']['여건_규칙'], {'__builtins__': {}}, {'기회': len(o), '부담': len(b), '방어': dfn})
    out.append(L('현금 집행 여건', '됨' if go else '아님', f"기회 {len(o)}, 부담 {len(b)}, 방어 국면 {'예' if dfn else '아니오'}",
                 crit=f"규칙: {c.R['미스 리스크']['여건_규칙']}", sig='green' if go else 'orange'))
    return out, []


def phobos(c):
    G = _read(c.d, '공포탐욕')
    if not len(G):
        return [L('공포탐욕', '자료 없음', '07시 공포탐욕.csv 없음')], [], ''
    Z = c.R['미스 리스크']['구간']
    zone = lambda s: next((z for a, b, z in Z if num(s) is not None and a <= round(num(s)) <= b), '자료 없음')
    t = G[G['구분'] == '종합'].iloc[0]
    ind = G[G['구분'] == '지표'].reset_index(drop=True)
    sc = num(t['점수'])
    out = [L('종합', f"Fear & Greed Index {n(sc, 1)} {zone(sc)} — 전일 {p(sc - num(t['전일']) if num(t['전일']) is not None else None, 1, '')}, "
                  f"1주 전 대비 {p(sc - num(t['1주 전']) if num(t['1주 전']) is not None else None, 1, '')}, 1개월 전 대비 {p(sc - num(t['1개월 전']) if num(t['1개월 전']) is not None else None, 1, '')}",
             '구간: 0~24 Extreme Fear, 25~44 Fear, 45~55 Neutral, 56~75 Greed, 76~100 Extreme Greed')]
    rows = [[str(r['지표']), n(r['점수'], 1), zone(r['점수']), f"{n(r['원천값'], 2)} ({r['원천값 설명']})", str(r['해석'])] for _, r in ind.iterrows()]
    tbl = '| 지표 | 점수 | 구간 | 오늘 값 | 시장 의미 |\n|---|---|---|---|---|\n' + '\n'.join('| ' + ' | '.join(x) + ' |' for x in rows)
    s = pd.to_numeric(ind['점수'], errors='coerce')
    fear = [x.split('. ', 1)[-1] for x, v in zip(ind['지표'], s) if v <= 44]
    greed = [x.split('. ', 1)[-1] for x, v in zip(ind['지표'], s) if v >= 56]
    out.append(L('공포 쪽 지표', f"{len(fear)}개 ({', '.join(fear) or '없음'})", '점수 44 이하'))
    out.append(L('탐욕 쪽 지표', f"{len(greed)}개 ({', '.join(greed) or '없음'})", '점수 56 이상'))
    price3, bond2 = s.iloc[:3].mean(), s.iloc[5:7]
    if len(s) >= 7:
        if (bond2 <= 44).all():
            read = '채권 둘(Safe Haven·Junk Bond)까지 공포: 돈이 위험 자산에서 빠지는 쪽'
        elif price3 <= 44 and (bond2 >= 45).any():
            read = '가격 셋은 공포인데 채권 쪽은 공포가 아님: 주가는 흔들렸고 돈은 아직 위험 회피로 가지 않음'
        else:
            read = '가격 셋과 채권 둘이 같은 공포 신호를 내지 않음'
        out.append(L('시장 분위기', read, f"가격 셋(1~3) 평균 {price3:.1f}, Safe Haven {n(s.iloc[5], 1)}, Junk Bond {n(s.iloc[6], 1)} — 읽는 요령: 가격 셋 공포 + 채권 둘 정상 = 주가만 흔들림, 채권 둘까지 공포 = 위험 회피"))
    return out, [{'type': 'grid', 'columns': ['지표', '점수', '구간', '오늘 값', '시장 의미'], 'rows': rows}], tbl


def ttuji(c):
    S = c.S
    cnt = S['추천'].value_counts().to_dict()
    out = [L('엔진 판정', ', '.join(f'{k} {v}' for k, v in cnt.items()), '퀀트센터 blocks.yaml 전 종목 계산(out_판정표)')]
    rc = c.RC
    out.append(L('선정 기준', f"블록 예 비율 {rc.get('추천선', 0.6667):.2f} 이상 추천·{rc.get('관찰선', 0.5):.2f} 이상 관찰, 국내 {rc.get('국내수', 5)} + 국내 상장 미국 ETF {rc.get('미국ETF수', 2)}, 60일 변동성 {rc.get('변동성상한', 60)}% 이하, 외국인 5·20일 동시 순매도 제외",
                 '콜로키움_룰.txt 2장 + blocks.yaml 추천 설정'))
    for i, r in enumerate(c.top, 1):
        warn = f", 주문 {int(r['주문승수']*100)}%({r['경보']})" if ok(r.get('주문승수')) and r['주문승수'] < 1 else ''
        out.append(L(f'추천 {i}', f"{r['종목']} — 블록 예 {int(r['블록예']) if ok(r.get('블록예')) else '-'}/{int(r['블록수']) if ok(r.get('블록수')) else '-'}({n(r['블록예비율'], 2)}), 싼가 {n(r['싼가'], 2)}, {GAL.get(r['갈래'], r['갈래'])}{warn}",
                     f"드문 통과 공식: {r['왜'] or '없음'} · 3년 PER 하위 {n((num(r.get('per_pct3')) or float('nan'))*100, 0, '%')}"))
    if not c.top:
        out.append(L('오늘의 추천 종목', '없음', '추천 등급이 거르기·안정성 조건을 통과하지 못함'))
    for nm, why in c.drops[:3]:
        out.append(L(f'제외 {nm}', why, '룰 2장 안정성·국내 상장 조건'))
    rule = c.R['한종목']['뚜지']
    why = lambda r: f"블록 예 비율 {n(r['블록예비율'], 2)}, 싼가 {n(r['싼가'], 2)}, 점수 {n(r['점수'], 2)}"
    if c.top:
        out.append(c.pick_line('뚜지', rule, c.top[0], len(c.top), why))
    else:   # rules.yaml 한종목.뚜지.없을때: 추천 7이 비면 엔진 추천 등급 1위를 [주목]으로(국내 상장 조건 밖이라 편입 대상 아님)
        A = c.T[c.T['추천'] == '추천'].sort_values(['블록예비율', '싼가', '점수'], ascending=False)
        r = A.iloc[0] if len(A) else None
        out.append(c.pick_line('뚜지', {**rule, '설명': rule.get('없을때', rule.get('설명', ''))}, r, len(A),
                               lambda r: why(r) + (f" — 편입 제외 사유: {dict(c.drops).get(r['종목'], '')}" if dict(c.drops).get(r['종목']) else ''), mark='주목'))
    c.picks['센터'] = {**c.picks['뚜지'], '위원': '오늘의 한 종목(뚜지)'}   # 키만 내부용, 원고에 '센터'라는 말은 쓰지 않음
    G = [{'type': 'line', 'tickers': [r['ticker'] for r in c.top if ok(r.get('ticker'))], 'days': 365}] if c.top else []
    try:   # 11/20 의장: 블록 1~5 하위 블록(1-1 번호)은 언제든 넣고 뺀다 → 뚜지 발표에 켜짐·꺼짐 표
        import qc_config as QCC
        import subblocks as SBK
        B = QCC.load_blocks()
        rows = SBK.table(B)
        if rows:
            X = [r for r in rows if r[3] != '켜짐']
            out.append(L('하위 블록', f"켜짐 {len(rows) - len(X)} · 꺼짐 {len(X)}" + (f" ({', '.join(r[1] + ' ' + r[2] for r in X[:8])})" if X else ''),
                         '비공개 subblocks.yaml 켜기 목록(블록 2 phase · 3 Analysis · 4 portfolio · 5 colloquium)'))
            G.append({'type': 'grid', 'title': '하위 블록 켜짐·꺼짐', 'columns': ['블록', '번호', '이름', '상태'], 'rows': rows, 'source': 'subblocks.yaml'})
    except Exception:   # noqa: BLE001
        pass
    return out, G


def miss_chart(c):
    out = []
    for r in c.top:
        out.append(L(r['종목'], f"일봉 RSI {n(r.get('일_RSI'), 0)}, 주봉 RSI {n(r.get('주_RSI'), 0)}, 일봉 %B {n(r.get('일_볼린저_%B'), 2)}, 일목 구름 {r.get('일_일목_구름위치') if ok(r.get('일_일목_구름위치')) else '자료 없음'}, "
                     f"주봉 MACD 오실레이터 {'상승' if (num(r.get('osc_w')) or 0) > (num(r.get('osc_w1')) or 0) else '하락'}",
                     f"50일 이격 {n(r.get('gap50'), 1)}, 52주 고점 대비 {p(r.get('dd52'))} (닉스.csv)"))
    rule = c.R['한종목']['미스 차트']
    r, cnt = pick(c.T, rule)
    out.append(c.pick_line('미스 차트', rule, r, cnt, ta))
    return out, []


def nyx(c, who):
    rule = c.R['한종목'][who]
    base = (c.T['층'] != 'S0') if '층' in c.T else None   # 11/20: 기준층(지수·현금·MMF·금·커버드콜)은 닉스 팀 한 종목 후보에서 뺀다(MMF가 '너무 많이 오름'으로 뽑힌 일)
    r, cnt = pick(c.T, rule, base)
    out = []
    if who == '아트로포스':
        X = c.T[(c.T['매도신호'].fillna('') != '') & (c.T['판정'] == '후보') & (base if base is not None else True)]
        X = X.sort_values('rsi_d', ascending=False).head(3)
        if len(X):
            out.append(L('주의 깊게 지켜볼 종목', ', '.join(f"{x['종목']}({x['매도신호']})" for _, x in X.iterrows()), '엔진 매도 신호(이익 꺾임·사건 역풍·고점 부근·너무 많이 오름·외국인 5·20일 순매도)'))
        else:
            out.append(L('주의 깊게 지켜볼 종목', '없음', '후보 종목 중 엔진 매도 신호 0개'))
        out.append(c.pick_line(who, rule, r, cnt, lambda r: f"{r['매도신호']} — {ta(r)}", mark='제외'))
    else:
        out.append(L('조건', rule.get('설명', ''), f"오늘 맞는 종목 {cnt}개"))
        out.append(c.pick_line(who, rule, r, cnt, ta))
    return out, [{'type': 'rsi', 'tickers': [r['ticker']]}] if r is not None and ok(r.get('ticker')) else []


def miss_value(c, desk_has):
    T = c.T[(c.T['구분'] == '개별주') & (c.T['판정'] == '후보')]
    out = []
    X = T.dropna(subset=['per_pct3'])
    fmt = lambda r: f"{r['종목']} PER {n(r.get('per_now'), 1, '배')}(3년 중앙값 {n(r.get('per_med3'), 1, '배')}, 3년 중 하위 {n(num(r['per_pct3'])*100, 0, '%')}), 선행 PER {n(r.get('fper'), 1, '배')}, PBR {n(r.get('pbr'), 2, '배')}"
    if len(X):
        out.append(L('3년 PER 가장 싼 쪽', ' / '.join(fmt(r) for _, r in X.nsmallest(3, 'per_pct3').iterrows()), '자기 3년 PER 백분위(PER3년.csv), 엔진 후보 개별주'))
        out.append(L('3년 PER 가장 비싼 쪽', ' / '.join(fmt(r) for _, r in X.nlargest(3, 'per_pct3').iterrows()), '같은 표'))
    semi = T[T.get('sector', pd.Series('', index=T.index)).astype(str).str.contains('반도체') & T['pbr'].notna()]
    if len(semi):
        out.append(L('반도체 PBR', ' / '.join(f"{r['종목']} PBR {n(r['pbr'], 2, '배')}(층 안 하위 {n(num(r.get('pbr_rank'), )*100 if ok(r.get('pbr_rank')) else None, 0, '%')})" for _, r in semi.nsmallest(3, 'pbr').iterrows()), '반도체는 PBR 우선, PER 참고(룰 4장)'))
    out.append(L('데스크 보고', '있음' if desk_has else '없음', '담당 종목 전일 ±3% 또는 3일 안 실적 공시가 있으면 있음'))
    rule = c.R['한종목']['미스 밸류']
    r, cnt = pick(c.T, rule)
    out.append(c.pick_line('미스 밸류', rule, r, cnt, fmt))
    return out, []


def desk_of(name, sector, layer, D):
    if layer == 'S0':
        return None
    for k, v in D['종목지정'].items():
        if k == name:
            return v
    import re
    for desk, pat in D['낱말']:
        if re.search(pat, str(sector)):
            return desk
    return None


def desks(c):
    D = c.R['데스크']
    T = c.T.copy()
    T['데스크'] = [desk_of(r['종목'], r.get('sector', ''), r.get('층'), D) for _, r in T.iterrows()]
    T = T[T['구분'] == '개별주']
    px = dict(zip(c.px.get('번호', []), pd.to_numeric(c.px.get('등락률(%)', pd.Series(dtype=float)), errors='coerce')))
    DA, SE = _read(c.d, 'DART'), _read(c.d, 'SEC')
    lim = pd.Timestamp(c.today) - pd.Timedelta(days=D['실적일수'])
    recent = {}
    if len(DA) and '잠정 공시일' in DA:
        for _, x in DA.iterrows():
            dd = pd.to_datetime(str(x['잠정 공시일']), errors='coerce')
            if ok(x.get('잠정 공시일')) and not pd.isna(dd) and dd >= lim:
                recent[x['번호']] = f"{x['잠정 분기']} 잠정 매출 {n(x['잠정 매출(억원)'], 0, '억')}, 영업이익 {n(x['잠정 영업이익(억원)'], 0, '억')}, 순이익 {n(x['잠정 순이익(억원)'], 0, '억')}(DART {str(x['잠정 공시일'])[:10]})"
    if len(SE) and '실적 받은날' in SE:
        for _, x in SE.iterrows():
            dd = pd.to_datetime(str(x['실적 받은날']), errors='coerce')
            if not pd.isna(dd) and dd >= lim and ok(x.get('기준일(최근 분기 끝)')):
                recent.setdefault(x['번호'], f"분기 끝 {x['기준일(최근 분기 끝)']} 매출 TTM {n(x['매출 TTM(백만$)'], 0, '백만$')}, 영업이익 TTM {n(x['영업이익 TTM(백만$)'], 0, '백만$')}, PER TTM {n(x['PER TTM(주가÷EPS)'], 1, '배')}(SEC)")
    res, has = {}, False
    for desk in DESKS:
        G = T[T['데스크'] == desk]
        out = []
        for _, r in G.iterrows():
            mv = px.get(r['번호'])
            if mv is not None and not math.isnan(mv) and abs(mv) >= D['보고문턱_등락(%)']:
                out.append(L(f"{r['종목']} {p(mv, 2)}", f"엔진 {r['추천']}, 블록 예 {n(r['블록예비율'], 2)}, 20일 {p(r.get('20일(%)'))}" + (f", 빠지는 이유: {r['빠지는 이유']}" if mv < 0 and ok(r.get('빠지는 이유')) else '') + mover_news(c, r['종목']),
                             f"전일 ±{D['보고문턱_등락(%)']}% 이상(시세.csv)"))
            if r['번호'] in recent:
                out.append(L(f"{r['종목']} 실적", recent[r['번호']], f"{D['실적일수']}일 안 DART 잠정 공시 또는 SEC 실적 수신"))
        has = has or bool(out)
        if not out:
            out.append(L('담당 종목', f"{len(G)}종목, 전일 ±{D['보고문턱_등락(%)']}%·{D['실적일수']}일 안 실적 공시 없음", '시세.csv·DART·SEC'))
        rule = c.R['한종목']['섹터 데스크']
        r, cnt = pick(c.T, rule, extra=c.T['번호'].isin(G['번호']))
        out.append(c.pick_line(desk, rule, r, cnt, lambda r: f"엔진 {r['추천']}, 블록 예 {n(r['블록예비율'], 2)}, 싼가 {n(r['싼가'], 2)}"))
        res[desk] = out
    return res, has


def elpis(c):
    out = []
    b, o = c.burden_opp()
    out.append(L('기회 블록', f"통과 {len(o)}개" if o else '통과 없음', '엔진 시장 블록 중 방향 = 기회, 결과 = 통과'))
    out += c.block_lines('기회')
    G = _read(c.d, '공포탐욕')
    if len(G):
        sc = num(G[G['구분'] == '종합'].iloc[0]['점수'])
        pull = c.T[(c.T['갈래'] == '눌림') & (c.T['추천'].isin(['추천', '관찰']))]   # 11/19 가짜 바닥 검사 폐지
        bd = c.band200; rng = f"200일선의 {n(bd['하단'], 2)}~{n(bd['상단'], 2)}배"
        inn, broke = pull[pull['구간200'] == '안'], pull[pull['구간200'] == '추세 무너짐']
        out.append(L('공포 속 기회', f"Fear & Greed {n(sc, 1)}, 52주 고점에서 10% 넘게 떨어진 추천·관찰 종목 중 {rng} 사이 {len(inn)}종목"
                     + (f" (추세 무너짐으로 뺌 {len(broke)}종목: {', '.join(broke['종목'].head(5))})" if len(broke) else ''),
                     f"52주 고점에서 10% 넘게 떨어진 종목(눌림) 중 현재가가 {rng} 사이. {n(bd['하단'], 2)}배 아래 = 추세 무너짐"))
    for it in ('WTI', '금', '원/달러'):
        r = c.mac_row(it)
        if r is not None:
            out.append(L(it, f"{n(r['값'], 2)}(1달 {p(r['1달'])}, YTD {p(r['YTD'])})", f"{r['기준일']} {r['출처']}"))
    rule = dict(c.R['한종목']['엘피스'])
    rule['설명'] = rule.get('설명', '').replace('{하단}', n(c.band200['하단'], 2)).replace('{상단}', n(c.band200['상단'], 2))
    r, cnt = pick(c.T, rule)
    out.append(c.pick_line('엘피스', rule, r, cnt, lambda r: f"52주 고점 대비 {p(r.get('dd52'))}, 블록 예 {n(r['블록예비율'], 2)}, 현재가 ÷ 200일선 {n(r.get('px_ma200'), 2)}(200일선 {n(r.get('ma200'), 2)})"))
    return out, []


def gukjang(c, EV, CAL):
    R = c.R['국장']
    out = []
    S = _read(c.d, '일정')
    if len(S):
        end = pd.Timestamp(c.today) + pd.Timedelta(days=R['일정일수'] - 1)
        X = S[(pd.to_datetime(S['날짜'], errors='coerce') >= pd.Timestamp(c.today)) & (pd.to_datetime(S['날짜'], errors='coerce') <= end)]
        for _, s in X.iterrows():
            out.append(L(f"{str(s['날짜'])[5:]} {s['시각(한국)']}", f"{s['구분']} {s['대상']} — {s['내용']}", f"확인: {s['확인']}, 출처 {s['출처']}"))
    N = c.news
    T = _read(c.d, '주가뉴스')   # 11/20 의장: 주가 관련 뉴스 10건 + FinBERT 긍정·부정(07시 b09_newstop.py)
    if len(T):
        T = T[~T['제목'].astype(str).str.contains('(?<![A-Za-z])' + BAN.pattern.replace('^', ''))]
        for _, x in T.iterrows():
            stock = f" · {x['종목']} 전일 {p(x['등락률(%)'], 2)}" if ok(x.get('종목')) and str(x['종목']) else ''
            ko = str(x.get('제목(한글)', '') or '').strip()
            ko = '' if ko.lower() == 'nan' else ko
            out.append(L(f"[{x['판정']}] {x.get('구분', '')} {x['시각(한국)']} {x['출처']}", (ko or str(x['제목'])) + stock,
                         (f"원제목: {x['제목']} · " if ko else '') + f"FinBERT 긍정 {n(x['긍정'], 2)} · 부정 {n(x['부정'], 2)}(07시 주가뉴스.csv)"))
    elif len(N):
        ok_src = R['승인매체']
        X = N[N['출처'].astype(str).map(lambda x: any(m in x for m in ok_src)) & ~N['제목'].astype(str).str.contains('(?<![A-Za-z])' + BAN.pattern.replace('^', ''))].head(R['기사수'])
        for _, x in X.iterrows():
            out.append(L(f"{x['시각(한국)']} {x['출처']}", str(x['제목']), '승인 매체 원제목 그대로(07시 뉴스.csv)'))
    for _, e in EV.iterrows():
        out.append(L(f"사건 {e['업종']}", f"{e['사건']} {e['상태']}", e['출처']))
    for _, e in CAL[CAL['확정'] == '예'].iterrows() if len(CAL) else []:
        out.append(L(f"변수 {e['날짜']}", e['사건'], f"영향 층 {e['영향 층'] or '기록만'} · {e['출처']}"))
    if not out:
        out.append(L('오늘 자료', '일정·승인 매체 기사 없음', '07시 일정.csv·뉴스.csv'))
    return out, []


# ---------------------------------------------------------------- 0 결론 (11/20 의장)
def _read2(d, name):
    """작업 폴더(in/)에 없으면 한 단계 위(bottom.py 출력 자리)에서 읽는다."""
    X = _read(d, name)
    return X if len(X) else _read(os.path.dirname(os.path.abspath(d)), name)


def _betas(c, rows):
    """1년 일별 베타: 미국 종목·이름에 '미국'이 든 ETF는 나스닥100 대비, 나머지 한국은 코스피 대비."""
    if not len(rows) or not len(c.U) or 'yfinance 티커' not in c.U:
        return {}
    tk = c.U.drop_duplicates('번호').set_index('번호')['yfinance 티커'].dropna().to_dict()
    want = {}
    for _, r in rows.iterrows():
        t = tk.get(r['번호'])
        if ok(t):
            want[r['번호']] = (t, c.R['결론']['기준지수']['미국' if (r['시장'] == '미국' or '미국' in str(r['종목'])) else '한국'])
    if not want:
        return {}
    try:
        import yfinance as yf
        P = yf.download(sorted({t for t, _ in want.values()} | {i for _, i in want.values()}), period='1y', auto_adjust=True, progress=False)['Close']
    except Exception:   # noqa: BLE001 — 내려받기 실패면 유니버스 '베타(2년 주간)'
        if '베타(2년 주간)' in c.U:
            bb = c.U.drop_duplicates('번호').set_index('번호')['베타(2년 주간)']
            return {b: float(bb[b]) for b in want if b in bb and ok(bb[b])}
        return {}
    Rt = P.pct_change(fill_method=None)
    out = {}
    for b, (t, i) in want.items():
        if t in Rt and i in Rt:
            x = pd.concat([Rt[t], Rt[i]], axis=1).dropna()
            if len(x) > 60:
                out[b] = float(x.iloc[:, 0].cov(x.iloc[:, 1]) / x.iloc[:, 1].var())
    return out


def _buy_state(c):
    """11/20 의장 '지금 살 때인가'(결론 칸과 시장 관문이 함께 씀). 돌려주는 값: (신용 줄 목록, 시장별 {act, why, buy, dfn, g}, 공용 값)"""
    R = c.R['결론']; out = []
    K = _read(c.d, '리스크')

    def rk(item):
        if not len(K):
            return None
        x = K[K['항목'].astype(str).str.replace('\\', '') == item]
        return x.iloc[0] if len(x) else None
    hy, hy20, ccc = rk('하이일드 스프레드'), rk('하이일드 스프레드 20일 변화'), rk('CCC 이하 스프레드')
    hyv = num(hy['값']) if hy is not None else None
    h20 = num(hy20['값']) if hy20 is not None else None
    cv = num(ccc['값']) if ccc is not None else None
    m_ = _re.search(r'최고\s*([\d.]+)', str(ccc.get('비고', '')).replace('\\', '')) if ccc is not None else None
    chi = float(m_.group(1)) if m_ else None
    crisis = (hyv is not None and hyv >= R['신용위기_하이일드']) or (h20 is not None and h20 >= R['신용위기_하이일드20일'])
    cnear = cv is not None and chi is not None and cv >= chi * R['신용주의_CCC_수집최고비']
    st = '위기' if crisis else ('약한 회사채(CCC) 최고치 부근 — 주의' if cnear else '위기 기준 아래')
    out.append(L('회사채(신용)', f"{st}: 하이일드 {n(hyv, 2, '%')}(20일 {p(h20, 2, '%p')}), CCC 이하 {n(cv, 2, '%')}(수집 최고 {n(chi, 2, '%')})",
                 f"규칙: 하이일드 {R['신용위기_하이일드']}% 이상 또는 20일 +{R['신용위기_하이일드20일']}%p 이상 = 위기(사지 않음), "
                 f"CCC가 수집 최고의 {R['신용주의_CCC_수집최고비']:.0%} 이상 = 주의 (리스크.csv)"))
    B = _read2(c.d, '바닥확률')   # 11/21 의장: 하위 블록 2-12 = Lunde & Timmermann 위험률 모형(이번 하락의 바닥일 확률)
    bp = {r['기준지수']: num(r.get('확률')) for _, r in B.iterrows()} if len(B) and '확률' in B else {}
    nd = bp['^NDX'] / 100 if bp.get('^NDX') is not None else None
    WB = pd.DataFrame()
    kr = c.mac_row('코스피')
    kdd = num(kr.get('최고 대비(%)')) if kr is not None else None
    KC = _read2(c.d, '조정단계_오늘_코스피')   # 11/20 의장: 한국 '산다' 문턱 = 미국 correction(−10%) × 코스피 변동성 비율(매일)
    kmul = num(KC.iloc[0].get('단계배수')) if len(KC) and '단계배수' in KC else None
    kthr = -R['한국_산다_미국단계'] * kmul if (kmul is not None and R.get('한국_산다_미국단계')) else None
    kdesc = (f"미국 −{R['한국_산다_미국단계']:g}% correction × 코스피 배수 {kmul:.2f}(최근 {n(KC.iloc[0].get('배수_년'), 0)}년 주간 변동성 ÷ S&P500) = {kthr:.1f}%"
             if kthr is not None else '한국 문턱 자료 없음(조정단계_오늘_코스피.csv 단계배수)')
    ST = {}
    for mk in ('미국', '한국'):
        g = c.regime(mk); dfn = bool(g and g[0] == '방어')
        if crisis:
            act, why = '사지 않는다', '신용 위기 규칙'
        elif mk == '미국' and nd is not None and nd >= R['바닥_경보']:
            act, why = '산다(바닥 경보)', f"나스닥100이 이번 하락의 바닥일 확률 {nd:.0%} ≥ 경보 {R['바닥_경보']:.0%}"
        elif mk == '미국' and nd is not None and nd >= R['바닥_준비']:
            act, why = f"산다 — {R['나눔']}번 나눠 1번째(바닥 준비)", f"나스닥100이 이번 하락의 바닥일 확률 {nd:.0%} ≥ 준비 {R['바닥_준비']:.0%}(경보 {R['바닥_경보']:.0%})"
        elif mk == '한국' and kdd is not None and kthr is not None and kdd <= kthr:
            act, why = f"산다 — {R['나눔']}번 나눠 1번째(많이 빠짐)", f"코스피 사상 최고 대비 {kdd:+.1f}% ≤ {kdesc}"
        elif dfn:
            why = (f"방어 국면, 나스닥100이 이번 하락의 바닥일 확률 {p(nd * 100 if nd is not None else None, 0)} < 준비 {R['바닥_준비']:.0%}" if mk == '미국'
                   else f"방어 국면, 코스피 사상 최고 대비 {p(kdd)} > {kdesc}")
            act = '아직 사지 않는다(약세장, 바닥 신호 없음)'
        else:
            act, why = '엔진 포트폴리오대로', '평상 국면'
        ST[mk] = dict(act=act, why=why, buy=act.startswith('산다'), dfn=dfn, g=g)
    return out, ST, dict(cnear=cnear, nd=nd, bp=bp, WB=WB, crisis=crisis)


def conclusion(c):
    """11/20 의장: 결론 칸·'센터'는 없다. 미스터 마켓 = 약세/강세와 근거 숫자만(사라 마라 표현 금지, 사는 건 의장이 판단).
    뚜지 = 시장별 '눈에 띄는 저평가 종목'(엔진 원칙 '떨어진 우량주' + 싼가·베타 기준, 순위점수 순)과 뽑힌 이유(판정표 칸 숫자), 검정 통계.
    의장 장기 후보는 기준가에 닿은 날만. 돌려주는 값 = (미스터 마켓 줄, 뚜지 줄). 매수 판정(ST)은 포트폴리오용으로 c.state에만 둔다."""
    R = c.R['결론']
    out, ST, V = _buy_state(c)
    c.state = {mk: (v['buy'], v['act']) for mk, v in ST.items()}
    nd = V['nd']
    credit = out[0] if out else None
    mood = []
    for mk in ('미국', '한국'):
        g = ST[mk]['g']
        if not g:
            continue
        st = '약세' if g[0] == '방어' else '강세'
        num_ = [f"국면 {g[0]}", f"지수 4국면 {g[3] or '자료 없음'}"]
        if mk == '미국':
            for ix, nm_ in (('^NDX', '나스닥100'), ('^GSPC', 'S&P500')):
                if V['bp'].get(ix) is not None:
                    num_.append(f"{nm_}이 이번 하락의 바닥일 확률 {V['bp'][ix]:.0f}%")
        kr = c.mac_row('S&P500' if mk == '미국' else '코스피')
        if kr is not None:
            num_.append(f"{'S&P500' if mk == '미국' else '코스피'} 사상 최고 대비 {p(num(kr.get('최고 대비(%)')))}")
        mood.append(L(f'{mk} 시장', st, ' · '.join(num_)))
    if credit is not None:
        mood.append(L('회사채(신용)', credit.fact, f"위기 기준: 하이일드 {R['신용위기_하이일드']}% 이상 또는 20일 +{R['신용위기_하이일드20일']}%p 이상 · 주의 기준: CCC가 수집 최고의 {R['신용주의_CCC_수집최고비']:.0%} 이상"))
    T = c.T
    cand_all = T[(T.get('원칙', pd.Series(index=T.index, dtype=str)) == '떨어진 우량주') & T['추천'].isin(['추천', '관찰', '바닥 대기'])]
    beta = _betas(c, pd.concat([cand_all, T[T['종목'].isin([r['종목'] for r in c.top])]]).drop_duplicates('번호'))
    out = []
    for mk in ('미국', '한국'):
        X = cand_all[cand_all['시장'] == mk].copy()
        X['베타'] = X['번호'].map(beta)
        X = X[(X['싼가'].fillna(0) >= R['싼가_최소']) & (X['베타'].fillna(0) >= R['베타_최소'])]
        X = X.sort_values('순위점수', ascending=False).head(R['종목수'])
        if len(X):
            fact = ', '.join(f"{r['종목']}(52주 고점 대비 {p(r.get('dd52'))}, 베타 {r['베타']:.2f}, 싼가 {n(r['싼가'], 2)}) "
                             f"PER {n(r.get('per_now'), 1, '배')}·3년 중앙 {n(r.get('per_med3'), 1, '배')}·순위점수 {n(r.get('순위점수'), 2)}" for _, r in X.iterrows())
        else:
            fact = '해당 없음'
        ev = R['검정근거']
        WB = V['WB']
        if mk == '미국' and len(WB):
            band = '경보(≥0.9)' if (nd or 0) >= R['바닥_경보'] else '준비(≥0.5)'
            w = WB[WB['구간'] == band]
            ev += ' / 바닥 근접도 ' + band + ' 26주: ' + ', '.join(f"{r['대상']} {p(r['26주 평균'])}(승률 {n(r['26주 승률'], 0)}%)" for _, r in w.iterrows())
        out.append(L(f"{mk}: 눈에 띄는 저평가 종목", fact,
                     f"엔진 원칙 '떨어진 우량주'(추천·관찰) 중 싼가 {R['싼가_최소']} 이상·베타 {R['베타_최소']} 이상, 순위점수 순 {R['종목수']}개 · {ev}"))
    LC = R.get('장기후보') or []
    LC = LC if isinstance(LC, dict) else {k: {} for k in LC}
    for b, cfg in LC.items():   # 11/20 의장 "아주 좋은 주식, 많이 떨어지면 왕창 사서 오래" — 의장 기준가·지정학 충격 때 표시
        cfg = cfg or {}
        x = T[T['번호'] == b]
        if not len(x):
            continue
        r = x.iloc[0]
        GB = _read(c.d, '가격대'); gb = GB[GB['번호'] == b].iloc[0] if len(GB) and (GB['번호'] == b).any() else None
        band = (f", 관찰 가격 {n(gb.get('관찰가격'), 2)}({p(gb.get('관찰_현재대비%'), 0)}), 추천 가격 {n(gb.get('추천가격'), 2)}({p(gb.get('추천_현재대비%'), 0)})"
                + (f" — {gb['막는 것']}" if ok(gb.get('막는 것')) else '')) if gb is not None else ''
        px = num(gb.get('현재가')) if gb is not None else None
        if px is None:   # 가격대는 후보 종목만 → 아니면 판정표 종가
            px = next((num(r.get(k)) for k in ('close', '종가', 'px') if num(r.get(k)) is not None), None)
        ref, lo = num(cfg.get('기준가')), num(cfg.get('기준가_하단'))
        refs = (f", 의장 기준가 {(n(lo, 0) + '~') if lo else ''}{n(ref, 0)}(현재가 {n(px, 2)}, 기준가까지 {p((ref / px - 1) * 100 if px else None)})" if ref else '')
        if not (ref and px is not None and px <= ref):   # 11/20 의장 "장기 후보를 여기서 왜 얘기하냐": 기준가에 닿은 날만
            continue
        EVs = _read(c.d, '사건상태')
        pat = cfg.get('지정학_낱말')
        geo_ev = EVs[EVs['사건'].astype(str).str.contains(pat) & EVs['상태'].astype(str).str.contains('진행')] if (pat and len(EVs) and '사건' in EVs) else pd.DataFrame()
        gpr = num(c.m.get('GPR_PCT')) if isinstance(c.m, dict) else None
        geo = len(geo_ev) > 0 or (gpr is not None and cfg.get('GPR_PCT_최소') is not None and gpr >= cfg['GPR_PCT_최소'])
        if not pat and cfg.get('GPR_PCT_최소') is None:   # 지정학 조건 없는 종목(예: 카니발) = 가격만
            out.append(L(f"{r['종목']}: 의장 기준가 도달", '기준가 도달', f"현재가 {n(px, 2)} ≤ 기준가 {n(ref, 0)}"))
            continue
        out.append(L(f"{r['종목']}: 의장 기준가 도달", '지정학 충격 진행 중 — 의장 기회 조건 충족' if geo else '기준가 도달(지정학 충격 조건은 아직)',
                     f"현재가 {n(px, 2)} ≤ 기준가 {n(ref, 0)} · 지정학: 사건상태 진행 {len(geo_ev)}건, GPR 백분위 {n(gpr, 0)}"))
    return mood, out


# ---------------------------------------------------------------- 반대 의견 (11/20 의장)
def objections(c):
    """11/20 의장: 오늘의 한 종목에 문제(이익 추정치 하향 등)가 있으면 다른 위원이 반대한다. 규칙은 rules.yaml '반대'."""
    R = c.R.get('반대') or {}
    keys, out, seen = R.get('빠지는이유', []), [], {}
    for who, pk in c.picks.items():
        if pk.get('표시') not in ('추천', '관찰') or not ok(pk.get('번호')) or who == '센터':
            continue
        x = c.T[c.T['번호'] == pk['번호']]
        if not len(x):
            continue
        r = x.iloc[0]
        why = [k for k in keys if k in str(r.get('빠지는 이유') or '')]
        if R.get('매도신호') and ok(r.get('매도신호')):
            why.append(f"매도 신호: {r['매도신호']}")
        if why:
            seen.setdefault(pk['종목'], [[], why])[0].append(who)
    for name, (whos, why) in seen.items():
        out.append(L(f"{name} 반대 ({', '.join(whos)} 선정)", ' / '.join(why),
                     f"규칙: 오늘의 한 종목에 '{', '.join(keys)}' 또는 매도 신호가 있으면 반대(판정표 칸)"))
    if not out:
        out.append(L('반대 의견', '없음', '오늘의 한 종목 중 반대 규칙에 걸린 종목 없음'))
    return out, []


# ---------------------------------------------------------------- 묶기
def build(d, S, M, m, f, R, RC, today, EV=None, CAL=None, session='국장전'):
    c = Ctx(d, S, M, m, f, R, RC, today)
    c.session = session
    EV = EV if EV is not None else _read(d, '사건상태')
    CAL = CAL if CAL is not None else _read(d, '변수달력')
    sections = []   # (번호 제목, 위원, 역할, 줄, 그래프, 덧붙일 글)
    mood, picks_ = [], []   # 11/20 의장: 결론 칸·'센터' 없음 → 시장 약세/강세는 미스터 마켓, 저평가 종목은 뚜지
    if c.R.get('결론'):
        try:
            mood, picks_ = conclusion(c)
        except Exception as e:   # noqa: BLE001
            mood = [L('시장', '계산 실패', str(e)[:120])]
    a, g, tbl = mr_market(c); sections.append(('1 시장', '마켓 센터', '간밤 미국 시장' if session == '국장전' else '한국 시장', mood + a, g, tbl))
    a, g, tbl = miss_citadel(c); sections.append(('2 수급·포지셔닝', '미스 시타델', '수급·포지셔닝', a, g, tbl))
    # 11/20 의장: 리오(매크로 여건)·포보스(공포탐욕)는 겹치니 '미스 리스크' 한 위원으로 합친다
    a1, g1 = rio(c)
    a2, g2, tbl = phobos(c)
    sections.append(('3 리스크', '미스 리스크', '리스크·공포와 탐욕', a1 + a2, g1 + g2, (tbl + '\n\n' + macro_table(c)).strip()))   # 체크리스트는 맨 아래
    a, g = ttuji(c); sections.append(('4 엔진 블록 센터', '뚜지(센터장)', '엔진 블록 결과', a, g, ''))   # 11/20 의장: 뚜지는 엔진 블록 센터장
    a, g = miss_chart(c); sections.append(('4 퀀트센터', '미스 차트(팀장)', '추천 종목 기술 지표', a, g, ''))   # 11/20 의장: 퀀트센터 팀장은 미스 차트
    for who, role in (('클로토', '바닥 진입'), ('라케시스', '추세·비중 확대'), ('아트로포스', '과열 분할 매도')):
        a, g = nyx(c, who); sections.append(('4 퀀트센터 — 닉스 팀', who, role, a, g, ''))
    dk, has = desks(c)
    a, g = miss_value(c, has); sections.append(('4-1 밸류에이션', '미스 밸류', '밸류에이션', a, g, ''))
    for desk in DESKS:
        sections.append(('4-2 섹터 데스크', desk, '섹터 데스크', dk[desk], [], ''))
    a, g = elpis(c); sections.append(('5 긍정 요인', '엘피스', '긍정 요인', a, g, ''))
    a, g = gukjang(c, EV, CAL); sections.append(('6 기타', '국장', '일정·승인 매체 기사·사건', a, g, ''))
    if c.R.get('반대'):   # 11/20 의장: 회의니까 다른 위원이 반대한다
        a, g = objections(c); sections.append(('7 반대 의견', c.R['반대'].get('위원', '미스 리스크'), '오늘의 한 종목 반대', a, g, ''))
    # 11/20 의장 "종목 추천은 마지막에 해. 중간에 쓸데없는 추천하지 말고": 위원별 '오늘의 한 종목' 줄은 원고에서 뺀다(csv는 그대로),
    # 뚜지의 추천 목록·제외 줄은 맨 끝 칸으로 옮기고, 종목 추천은 그 칸 하나에서만 한다.
    REC = _re.compile(r'^(추천 \d+|제외 |오늘의 추천 종목)')
    moved, out = [], []
    for sec, who, role, lines, g, extra in sections:
        keep = []
        for l in lines:
            if l.title == '오늘의 한 종목':
                continue
            (moved if who.startswith('뚜지') and REC.match(str(l.title)) else keep).append(l)
        out.append((sec, who, role, keep, g, extra))
    last = picks_ + moved
    if last:
        out.append(('8 종목 추천', '뚜지(센터장)', '눈에 띄는 저평가 종목·엔진 추천', last, [], ''))
    return c, out


def render_txt(sections, today, picks, note=''):
    day = f'{today:%Y-%m-%d}'
    out = [f'스튜디오 톰앤수 회의 원고 {day}',
           '만든 방식: 코드 자동 생성(colloquium-collect meeting/personas.py + meeting/rules.yaml, 엔진 block33/blocks.yaml). AI가 쓰거나 고르지 않음.',
           '숫자는 07시 수집 파일·엔진 결과 그대로. "└ 근거"는 그 줄의 출처·규칙.']
    if note:
        out.append(note)
    cur = None
    for sec, who, role, lines, _, extra in sections:
        if sec != cur:
            out += ['', '=' * 50, sec, '=' * 50]
            cur = sec
        out += ['', f'{who}:']
        for i, l in enumerate(lines, 1):
            out.append(f'{i}. {l.title}')
            out.append(f'   {l.fact}')
            if l.why:
                out.append(f'   └ 근거: {l.why}')
        if extra:
            out += ['', extra]
    return '\n'.join(out) + '\n'


def _it(t):
    """회의실 채팅은 <sub>를 글자로 보여 준다(11/20 의장) → 근거는 기울임체. 안의 * 는 지워 모양이 깨지지 않게."""
    t = str(t).replace('*', '').strip()
    return f'*{t}*' if t else ''


def render_md(sections, today, picks, note=''):
    """회의실(채팅)에 그대로 붙이는 원고(11/20 의장 'txt 파일 같다, 가독성 없다').
    위원마다 '## 위원' 칸. 줄 = 굵은 '번호. 제목' / 내용 / 기울임체 근거. 표는 앞뒤 빈 줄."""
    day = f'{today:%Y-%m-%d}'
    out = [f'# 스튜디오 톰앤수 회의 원고 {day}']
    if note:
        out.append(_it(note))
    for sec, who, role, lines, _, extra in sections:
        out += ['', f'## {sec} | {who}', '', f'{who}:', '']
        for i, l in enumerate(lines, 1):
            out.append(f'**{i}. {l.title}**  ')
            out.append(l.fact + ('  ' if l.why else ''))
            if l.why:
                out.append(_it('근거: ' + str(l.why)))
            out.append('')
        if extra:
            out += [extra, '']
    return '\n'.join(out).rstrip() + '\n'


def render_json(sections, today, note='', state=None):
    mem, sub = [], None
    for sec, who, role, lines, charts, extra in sections:
        ls = [f'{i}. **{l.title}**: {l.fact}' + (f'  \n:small[:gray[{l.why}]]' if l.why else '') for i, l in enumerate(lines, 1)]
        item = {'name': who, 'role': role, 'lines': ls, 'charts': charts, 'rows': [l.row() for l in lines]}
        if sec.startswith('4-2'):
            if sub is None:
                sub = {'name': '섹터 데스크', 'role': '담당 종목', 'lines': [], 'sub': []}
                mem.append(sub)
            sub['sub'].append(item)
        else:
            mem.append(item)
    return json.dumps({'date': f'{today:%Y%m%d}', 'note': note or '코드 자동 생성(meeting/personas.py). AI가 쓰지 않음.', 'members': mem,
                       'state': {k: {'buy': v[0], 'act': v[1]} for k, v in (state or {}).items()}},   # 포트폴리오용(원고에는 안 나옴) ensure_ascii=False, indent=1,
                      default=lambda o: None if isinstance(o, float) and math.isnan(o) else (o.item() if hasattr(o, 'item') else str(o)))


def premarket(c, Q, today):
    """미장전 시황(미스터 마켓, 22:00 회의 맨 앞). Q = daily.py가 받은 야후 시세표(이름·티커·값·전일대비(%)·시각)."""
    P = c.R.get('미장전', {})
    out = []
    if Q is not None and len(Q):
        for _, q in Q.iterrows():
            if pd.isna(q['값']):
                continue
            chg = q['전일대비(%)']
            big = (q['티커'].endswith('=F') and q['티커'] in ('ES=F', 'NQ=F', 'YM=F') and pd.notna(chg) and abs(chg) >= P.get('크게움직임_선물(%)', 1))
            out.append(L(q['이름'], f"{n(q['값'], 2)}" + (f" ({'+' if chg >= 0 else ''}{chg:.2f}%)" if pd.notna(chg) else '') + (' — 선물 큰 움직임' if big else ''),
                         f"야후 {q['티커']}, {q['시각']} 기준, 전일 종가 대비"))
    else:
        out.append(L('시세', '야후 시세를 받지 못함', '미장전 시세 받기 실패'))
    S = _read(c.d, '일정')
    if len(S):
        t0, t1 = P.get('밤일정_시작', '18:00'), P.get('밤일정_끝', '08:00')
        d0, d1 = str(today), str(today + dt.timedelta(days=1))
        tm = S['시각(한국)'].astype(str).str.extract(r'(\d\d:\d\d)')[0].fillna('')
        night = S[S['구분'].astype(str).str.startswith('미국') & (((S['날짜'].astype(str) == d0) & (tm >= t0)) | ((S['날짜'].astype(str) == d1) & (tm != '') & (tm < t1)))]
        night = night[~night['대상'].astype(str).map(banned)]
        if len(night):
            out.append(L('오늘 밤 미국 일정', ' / '.join(f"{r['시각(한국)']} {r['대상']} {r['내용']}" for _, r in night.iterrows()), f'07시 일정.csv, 한국 시각 {d0} {t0} ~ {d1} {t1}'))
        else:
            out.append(L('오늘 밤 미국 일정', '없음', f'07시 일정.csv, 한국 시각 {d0} {t0} ~ {d1} {t1}'))
    return out


def ask_index(c):
    """돌발 질문용 종목 색인(meeting/ask.py가 읽음): 판정표 종목 → 별칭(원본 표기·티커·코드)·섹터·층·담당 데스크."""
    D = c.R['데스크']
    U = c.U.set_index('번호') if len(c.U) and '번호' in c.U.columns else pd.DataFrame()
    rows = []
    for _, r in c.T.iterrows():
        u = U.loc[r['번호']] if len(U) and r['번호'] in U.index else {}
        get = (lambda k: u.get(k, '')) if len(U) and r['번호'] in U.index else (lambda k: '')
        alias = [str(get(k)).strip() for k in ('원본 표기', '정식 종목명', 'yfinance 티커', '코드')]
        alias = [a.split('.')[0] if k == 2 else a for k, a in enumerate(alias)]
        alias = sorted({a for a in alias if a and a != 'nan' and a != str(r['종목'])})
        sec = r.get('sector', '') if str(r.get('sector', '')) not in ('', 'nan') else get('섹터/테마')
        rows.append(dict(번호=r['번호'], 종목=r['종목'], 별칭='|'.join(alias), 섹터=sec, 층=r.get('층'),
                         데스크=desk_of(r['종목'], sec, r.get('층'), D) or ('미스 리스크' if r.get('층') == 'S0' else '')))
    return pd.DataFrame(rows, columns=['번호', '종목', '별칭', '섹터', '층', '데스크'])


def picks_csv(picks):
    order = ['센터', '뚜지', '미스 차트', '클로토', '라케시스', '아트로포스', '미스 밸류', '미스 시타델', '엘피스'] + DESKS
    return pd.DataFrame([picks[k] for k in order if k in picks])
