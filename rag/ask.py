# ======================================================================
# 위원 자료 검색 — 4단계: 질문에 맞는 문단 찾기 (5단계 답변은 위원이 이 결과만 보고 한다)
#
#   python rag/ask.py "HBM 공급 부족은 언제까지?" --위원 미스세마이
#   python rag/ask.py "마벨 데이터센터 매출" --위원 세마이 --저장
#   python rag/ask.py --질문파일 오늘질문.txt --저장        (한 줄에 '위원<TAB>질문' 또는 '질문')
#   그 밖: --전체(서랍 무시, 의장·진행용) --종목 MRVL --종류 기업카드,회의록 --이후 2026-11-01 --k 8
#
#   찾는 방법(4단계 강화):
#     ① 서랍: 그 위원 꼬리표 문단 + 공통 문단만(남의 폴더 자료 금지 원칙)
#     ② 뜻 검색(좌표 거리) + 글자 검색(BM25, 종목 코드·숫자·영문 약어를 정확히) → 순위를 섞음(RRF)
#     ③ 질문 넓히기: '마벨'이면 MRVL·마벨 테크놀로지도, 'HBM'이면 '고대역폭 메모리'도(동의어.csv·유니버스)
#     ④ 최근 자료 가산점, 질문에 나온 종목 꼬리표 가산점, 한 파일에서 최대 2문단
#     ⑤ 충분히 가까운 문단이 없으면 '자료 없음' — 지어내지 않게
# ======================================================================
import argparse, collections, csv, datetime as dt, math, os, re, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C          # noqa: E402
import chunker as K         # noqa: E402
import embedder as E        # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
TOK_EN = re.compile(r'[A-Za-z0-9][A-Za-z0-9.&+\-]*[A-Za-z0-9]|[A-Za-z0-9]')
TOK_KO = re.compile(r'[가-힣]+')
STOP = {'은', '는', '이', '가', '을', '를', '의', '에', '와', '과', '도', '로', '으로', '에서', '하다', '있다', '대한', '어떻게', '무엇', '언제', '얼마', '어디'}


def tokens(text):
    out = [t.lower() for t in TOK_EN.findall(text)]
    for w in TOK_KO.findall(text):
        if w in STOP:
            continue
        if len(w) >= 2:
            out.append(w)
        out += [w[i:i + 2] for i in range(len(w) - 1)]
    return out


class BM25:
    def __init__(self, docs, k1=1.4, b=0.75):
        self.k1, self.b = k1, b
        self.tf = [collections.Counter(d) for d in docs]
        self.len = np.array([len(d) for d in docs], dtype=float)
        self.avg = self.len.mean() if len(docs) else 1
        df = collections.Counter(t for c in self.tf for t in c)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def score(self, q, idx):
        s = np.zeros(len(idx))
        for t in set(q):
            idf = self.idf.get(t)
            if not idf:
                continue
            for j, i in enumerate(idx):
                f = self.tf[i].get(t)
                if f:
                    s[j] += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
        return s


def load_synonyms():
    groups = []
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '동의어.csv')
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding='utf-8-sig')):
            g = [s.strip() for s in (r.get('같은말') or '').split('|') if s.strip()]
            if g:
                groups.append(g)
    return groups


def persona_of(name):
    n = re.sub(r'\s+', '', name or '')
    for who, al in C.PERSONAS.items():
        if n == who or n in [re.sub(r'\s+', '', a) for a in al]:
            return who
    raise SystemExit(f'모르는 위원 이름: {name} (가능: {", ".join(C.PERSONAS)})')


class Index:
    def __init__(self):
        p = f'{C.INDEX_DIR}/문단.csv'
        if not os.path.exists(p):
            raise SystemExit(f'색인이 없습니다. 먼저 python rag/build.py ({C.INDEX_DIR})')
        info = open(f'{C.INDEX_DIR}/색인정보.txt', encoding='utf-8').read()
        if f'모델: {E.name()}' not in info:
            raise SystemExit(f'색인 모델과 지금 모델({E.name()})이 다릅니다. build.py --full 로 다시 만드세요.')
        self.info = info.split('\n')[0]
        self.df = pd.read_csv(p, dtype=str, keep_default_na=False)
        self.vec = np.load(f'{C.INDEX_DIR}/벡터.npy').astype(np.float32)
        self.bm = BM25([tokens(f'{h} {g} {s}') for h, g, s in zip(self.df['머리말'], self.df['글'], self.df['종목'])])
        self.tagger = K.StockTagger()
        self.syn = load_synonyms()
        today = dt.datetime.now(KST).date()
        age = [(today - dt.date.fromisoformat(d)).days if d else 365 for d in self.df['날짜']]
        self.recent = 1 + C.RECENT_WEIGHT * np.power(0.5, np.maximum(age, 0) / C.RECENT_HALF_LIFE)

    def cover(self, qt, body_t):
        """질문 낱말이 문단에 얼마나 들어 있나(드문 낱말일수록 무겁게). 자료에 아예 없는 낱말은 가장 무겁게."""
        mx = max(self.bm.idf.values()) if self.bm.idf else 1
        w = {t: self.bm.idf.get(t, mx) for t in set(qt)}
        return sum(v for t, v in w.items() if t in body_t) / max(1e-9, sum(w.values()))

    def expand(self, q):
        """질문 넓히기: 종목 별칭·동의어를 글자 검색 쪽에만 더한다."""
        extra, stocks = [], self.tagger.find(q)
        for no in stocks:
            extra += [s for s, n in self.tagger.names.items() if n == no]
        for g in self.syn:
            if any(s.lower() in q.lower() for s in g):
                extra += g
        return ' '.join([q] + extra), stocks

    def search(self, q, who=None, k=C.TOP_K, stock=None, kinds=None, since=None):
        df = self.df
        m = np.ones(len(df), bool)
        if who:
            m &= df['위원'].str.split('|').apply(lambda ws: who in ws or ws == ['공통']).values
        if stock:
            no = self.tagger.find(stock) or [stock]
            m &= df['종목'].apply(lambda s: bool(set(s.split('|')) & set(no))).values
        if kinds:
            m &= df['종류'].isin(kinds).values
        if since:
            m &= (df['날짜'] >= since).values
        idx = np.where(m)[0]
        if not len(idx):
            return [], {'서랍 문단': 0}
        qx, qstocks = self.expand(q)
        try:
            qv = E.embed_query(q)
            dense = self.vec[idx] @ qv
            mode = '뜻+글자'
        except Exception as e:          # 하루 한도 등으로 질문 좌표를 못 만들면 글자 검색만(더 엄격하게)
            print(f'  뜻 검색 못 함({str(e)[:60]}) → 글자 검색만', file=sys.stderr)
            dense = np.zeros(len(idx), dtype=np.float32)
            mode = '글자만'
        qt = tokens(qx)
        bm = self.bm.score(qt, idx)
        bm_top = bm.max() if len(bm) else 0
        d_rank = np.empty(len(idx)); d_rank[np.argsort(-dense)] = np.arange(1, len(idx) + 1)
        b_rank = np.empty(len(idx)); b_rank[np.argsort(-bm)] = np.arange(1, len(idx) + 1)
        rrf = 1 / (C.RRF_K + d_rank) + np.where(bm > 0, 1 / (C.RRF_K + b_rank), 0)
        boost = self.recent[idx].copy()
        if qstocks:
            hit = df['종목'].values[idx]
            boost *= np.array([1 + C.STOCK_BOOST if set(h.split('|')) & set(qstocks) else 1 for h in hit])
        score = rrf * boost
        # 정확히 맞아야 하는 낱말(영문 약어·숫자·종목)이 문단에 있는가
        keyterms = {t for t in tokens(qx) if re.fullmatch(r'[a-z0-9.&+\-]{2,}', t)}
        order = np.argsort(-score)
        out, per = [], collections.Counter()
        for j in order:
            i = idx[j]
            src = df['출처'].iat[i]
            if per[src] >= C.PER_FILE:
                continue
            body_t = set(tokens(df['글'].iat[i] + ' ' + df['머리말'].iat[i]))
            exact = bool(keyterms & body_t) or bool(qstocks and set(df['종목'].iat[i].split('|')) & set(qstocks))
            if mode == '뜻+글자':
                ok = dense[j] >= C.SIM_STRONG or (dense[j] >= C.SIM_WEAK and bm[j] > 0 and (exact or not keyterms))
            else:   # 글자만: 질문 낱말이 고르게 많이 맞고(최고 점수의 절반 이상·질문 낱말 40% 이상), 약어·종목이 있으면 그것도 맞아야
                cover = self.cover(qt, body_t)
                ok = bm[j] > 0 and bm[j] >= 0.5 * bm_top and cover >= C.BM25_COVER and (exact or not keyterms)
            if not ok:
                continue
            per[src] += 1
            out.append({'i': int(i), '뜻': float(dense[j]), '뜻순위': int(d_rank[j]), '글자순위': int(b_rank[j]) if bm[j] > 0 else None,
                        '점수': float(score[j]), **df.iloc[i].to_dict()})
            if len(out) >= k:
                break
        stat = {'서랍 문단': len(idx), '가장 가까운 뜻': float(dense.max()), '질문 종목': ','.join(qstocks), '방식': mode}
        return out, stat


def render(q, who, hits, stat, tagger):
    now = dt.datetime.now(KST)
    L = [f'[위원 자료 검색] {now:%Y-%m-%d %H:%M} KST',
         f'질문: {q}',
         f'서랍: {who or "전체"} (찾아본 문단 {stat.get("서랍 문단", 0)}개) · 방식: {stat.get("방식", "")}', '']
    if not hits:
        L += ['결과: 자료 없음',
              (f'  (가장 가까운 문단의 뜻 유사도 {stat.get("가장 가까운 뜻", 0):.2f} — 근거 문턱 {C.SIM_WEAK:.2f} 미만)'
               if stat.get('방식') == '뜻+글자' else '  (글자 검색만 — 질문 낱말이 충분히 맞는 문단 없음)'),
              '  위원은 이 질문에 "제 자료에는 없습니다"라고 답하고, 일반 지식으로 채우지 않는다.']
        return '\n'.join(L) + '\n'
    L.append(f'결과: 근거 문단 {len(hits)}개 (뜻 유사도 높은 순이 아니라 뜻·글자·최신을 섞은 순)')
    for n, h in enumerate(hits, 1):
        stocks = ', '.join(tagger.label.get(s, s) for s in h['종목'].split('|') if s)
        L += ['', f'[{n}] {h["출처"]} ({h["줄"]}줄) · {h["날짜"]} · {h["종류"]} · 위원 {h["위원"]}' + (f' · 종목 {stocks}' if stocks else ''),
              f'    머리말: {h["머리말"]}',
              f'    맞음 정도: 뜻 {h["뜻"]:.2f}(순위 {h["뜻순위"]}) / 글자 ' + (f'순위 {h["글자순위"]}' if h['글자순위'] else '없음'),
              *['    ' + ln for ln in h['글'].split('\n')]]
    L += ['', '─' * 40,
          '[답할 때 규칙] 위 문단에 있는 내용·숫자만 쓴다. 문장 끝에 [1]처럼 문단 번호를 단다.',
          '문단에 없는 숫자·사실은 "자료 없음"으로 말한다. 문단 날짜가 오래됐으면 날짜를 함께 말한다.']
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('질문', nargs='?')
    ap.add_argument('--위원')
    ap.add_argument('--전체', action='store_true')
    ap.add_argument('--종목')
    ap.add_argument('--종류', help='기획기사,기업카드,교재,회의록,의장자료,공부자료,룰북,분석,증권사리포트,뉴스')
    ap.add_argument('--이후', help='YYYY-MM-DD')
    ap.add_argument('--k', type=int, default=C.TOP_K)
    ap.add_argument('--질문파일')
    ap.add_argument('--저장', action='store_true', help=f'{C.RESULT_DIR}/YYYYMMDD/ 에 txt로')
    a = ap.parse_args()
    jobs = []
    if a.질문파일:
        for ln in open(a.질문파일, encoding='utf-8-sig'):
            ln = ln.strip()
            if ln and not ln.startswith('#'):
                w, _, q = ln.partition('\t') if '\t' in ln else (a.위원 or '', '', ln)
                jobs.append((w.strip(), q.strip()))
    elif a.질문:
        jobs.append((a.위원 or '', a.질문))
    else:
        ap.error('질문을 넣으세요')
    ix = Index()
    kinds = [s.strip() for s in a.종류.split(',')] if a.종류 else None
    texts = []
    for w, q in jobs:
        who = None if (a.전체 or not w) else persona_of(w)
        hits, stat = ix.search(q, who, a.k, a.종목, kinds, a.이후)
        texts.append(render(q, who, hits, stat, ix.tagger))
    body = ('\n' + '=' * 60 + '\n\n').join(texts)
    print(body)
    if a.저장:
        now = dt.datetime.now(KST)
        d = f'{C.RESULT_DIR}/{now:%Y%m%d}'
        os.makedirs(d, exist_ok=True)
        tag = re.sub(r'[^\w가-힣]+', '', (jobs[0][0] or '전체'))[:10]
        p = f'{d}/검색_{now:%H%M%S}_{tag}.txt'
        open(p, 'w', encoding='utf-8').write(body)
        print(f'저장: {p}')


if __name__ == '__main__':
    main()
