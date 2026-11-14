# ======================================================================
# 위원 자료 검색 — 1·2단계: 자료 모으기 + 문단 자르기 + 꼬리표(위원·종목·날짜·출처)
#   문단마다 '어느 문서의 어느 소제목 아래인지'를 앞머리로 붙인다(문맥 머리말).
#   예) [기업카드 마벨 > 3. 데이터센터 부문] … — 문단만 떼어 봐도 무슨 얘기인지 알게.
# ======================================================================
import csv, glob, hashlib, io, os, re, datetime as dt
import config as C

VER_RE = re.compile(r'_?Ver\.\d{8}(_\d{4})?', re.I)
DATE_RES = [re.compile(r'(20\d{2})(\d{2})(\d{2})'), re.compile(r'(20\d{2})-(\d{2})-(\d{2})')]
HEAD_RE = re.compile(r'^\s*(#{1,4}\s+.+|\d{1,2}(-\d{1,2})?[.)]\s+\S.{0,60}|\[[^\]]{2,30}\]\s*$|[■□●◆▶※]\s*\S.{0,60}|.{2,60}\n?[=─━-]{5,})\s*$')


def _norm(s):
    return re.sub(r'\s+', '', s)


# ---------------------------------------------------------------- 파일 고르기
def list_files():
    """읽을 파일 목록. 같은 문서의 옛 Ver는 빼고 가장 늦은 것만."""
    files = []
    for src in C.SOURCES:
        for p in glob.glob(f'{C.ROOT}/{src}/**/*', recursive=True):
            if not os.path.isfile(p) or os.path.splitext(p)[1].lower() not in C.EXT:
                continue
            if any(s in p for s in C.SKIP_PARTS):
                continue
            size = os.path.getsize(p)
            if size == 0 or (p.lower().endswith('.csv') and size > C.CSV_MAX) or size > C.TXT_MAX:
                continue
            files.append(p)
    newest = {}
    for p in files:
        key = os.path.join(os.path.dirname(p), VER_RE.sub('', os.path.basename(p)))
        if key not in newest or os.path.basename(p) > os.path.basename(newest[key]):
            newest[key] = p
    return sorted(newest.values())


# ---------------------------------------------------------------- 꼬리표
def file_date(path):
    name = os.path.basename(path)
    for rx in DATE_RES:
        m = rx.findall(name)
        if m:
            y, mo, d = m[-1] if rx is DATE_RES[1] else m[0]
            try:
                return dt.date(int(y), int(mo), int(d)).isoformat()
            except ValueError:
                pass
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat()


def _alias_table():
    t = []
    for who, names in C.PERSONAS.items():
        for n in names:
            t.append((_norm(n), who))
    return t


ALIASES = _alias_table()


def path_personas(rel):
    """경로 조각(폴더·파일 이름을 _ · 공백 등으로 나눈 낱말)에 위원 이름이 있으면 그 위원."""
    who = set()
    parts = rel.split('/')
    for i, part in enumerate(parts):
        if i == 0 and part in C.FOLDER_OWNER:
            who.add(C.FOLDER_OWNER[part])
        stem = os.path.splitext(part)[0]
        for tok in re.split(r'[_\s·.\-()]+', stem):
            for a, w in ALIASES:
                if tok == a:
                    who.add(w)
        joined = _norm(stem)
        for a, w in ALIASES:            # '미스세마이_교재' 처럼 붙어 있는 첫머리
            if len(a) >= 4 and joined.startswith(a):
                who.add(w)
    return sorted(who)


def kind_of(rel):
    for k, v in [('기획기사', '기획기사'), ('유튜브', '유튜브'), ('기업카드', '기업카드'), ('교재', '교재'), ('회의록', '회의록'), ('의장자료', '의장자료'),
                 ('리포트', '증권사리포트'), ('페르소나/공부자료', '공부자료'), ('페르소나', '룰북'),
                 ('위원공부', '공부자료'), ('종목분석', '분석'), ('뉴스브리핑', '뉴스'), ('미스터역도산', '분석'), ('미스차트', '분석')]:
        if k in rel:
            return v
    return '기타'


class StockTagger:
    """유니버스·담당표로 문단 속 종목을 찾고, 종목 → 담당 위원을 안다."""

    def __init__(self):
        self.names = {}       # 표기 → 번호
        self.label = {}       # 번호 → '마벨(MRVL)'
        self.owner = {}       # 번호 → 위원
        u = sorted(glob.glob(f'{C.ROOT}/유니버스/콜로키움100_유니버스_*.csv'))
        if u:
            with open(u[-1], encoding='utf-8-sig') as f:
                for r in csv.DictReader(f):
                    no = (r.get('번호') or '').strip()
                    if not no:
                        continue
                    nm = (r.get('정식 종목명') or r.get('원본 표기') or '').strip()
                    tk = (r.get('yfinance 티커') or '').split('.')[0].strip()
                    self.label[no] = f'{nm}({tk})' if tk and tk != nm else nm
                    for s in {r.get('원본 표기', ''), r.get('정식 종목명', ''), r.get('코드', ''), tk}:
                        s = (s or '').strip()
                        if s in C.AMBIGUOUS:
                            continue
                        if (len(s) >= 2 and not s.isdigit()) or (s.isdigit() and len(s) == 6):
                            self.names[s] = no
        d = sorted(glob.glob(f'{C.ROOT}/유니버스/데스크별_담당표_*.csv'))
        if d:
            with open(d[-1], encoding='utf-8-sig') as f:
                for r in csv.DictReader(f):
                    desk = _norm(r.get('데스크', ''))
                    for key, who in C.DESK_TO_PERSONA.items():
                        if key in desk:
                            self.owner[(r.get('번호') or '').strip()] = who
                    nm = (r.get('종목명') or '').strip()
                    if nm and (r.get('번호') or '').strip():
                        self.names.setdefault(nm, r['번호'].strip())
        extra = os.path.join(os.path.dirname(__file__), '동의어.csv')   # '마벨' 같은 줄임 이름
        if os.path.exists(extra):
            with open(extra, encoding='utf-8-sig') as f:
                for r in csv.DictReader(f):
                    if r.get('종목번호'):
                        for s in (r.get('같은말') or '').split('|'):
                            if s.strip():
                                self.names[s.strip()] = r['종목번호'].strip()
        # 영문 티커는 낱말 경계로, 한글은 그대로 찾는다. 긴 이름 먼저.
        pats = sorted(self.names, key=len, reverse=True)
        eng = [re.escape(p) for p in pats if re.fullmatch(r'[A-Za-z0-9.\-]+', p)]
        kor = [re.escape(p) for p in pats if not re.fullmatch(r'[A-Za-z0-9.\-]+', p)]
        self.rx_eng = re.compile(r'(?<![A-Za-z0-9])(' + '|'.join(eng) + r')(?![A-Za-z0-9])') if eng else None
        self.rx_kor = re.compile('(' + '|'.join(kor) + ')') if kor else None

    def find(self, text):
        hit = set()
        for rx in (self.rx_eng, self.rx_kor):
            if rx:
                for m in rx.finditer(text):
                    hit.add(self.names[m.group(1)])
        return sorted(hit)


# ---------------------------------------------------------------- 자르기
def _title(path):
    stem = VER_RE.sub('', os.path.splitext(os.path.basename(path))[0])
    return stem.replace('_', ' ').strip()


def split_text(text):
    """글 → [(소제목, 본문, 시작줄, 끝줄)]. 빈 줄·소제목에서 끊고, 작은 덩이는 붙이고, 큰 덩이는 줄 단위로 나눈다."""
    lines = text.replace('\r\n', '\n').split('\n')
    blocks, cur, start, head = [], [], 1, ''

    def flush(end):
        body = '\n'.join(cur).strip()
        if body:
            blocks.append([head, body, start, end])

    for i, ln in enumerate(lines, 1):
        is_head = bool(HEAD_RE.match(ln)) and len(ln.strip()) <= 70
        if is_head or not ln.strip():
            flush(i - 1)
            cur = []
            start = i + 1
            if is_head:
                head = re.sub(r'^[#\s]+', '', ln).strip(' =─━-')
                cur = [ln]
                start = i
            continue
        cur.append(ln)
    flush(len(lines))

    out = []           # 작은 덩이 붙이기
    for h, b, s, e in blocks:
        if out and len(out[-1][1]) < C.CHUNK_MIN and len(out[-1][1]) + len(b) < C.CHUNK_MAX:   # 작은 덩이는 다음 것과 붙임(소제목은 첫 것)
            out[-1][1] += '\n' + b
            out[-1][3] = e
        else:
            out.append([h, b, s, e])
    final = []          # 큰 덩이 나누기
    for h, b, s, e in out:
        if len(b) <= C.CHUNK_MAX:
            final.append((h, b, s, e))
            continue
        piece, ps, n = [], s, s
        for ln in b.split('\n'):
            for part in ([ln] if len(ln) <= C.CHUNK_MAX else re.split(r'(?<=[.다요。])\s+', ln)):
                if piece and sum(len(x) for x in piece) + len(part) > C.CHUNK_MAX:
                    final.append((h, '\n'.join(piece), ps, n))
                    piece, ps = [], n
                piece.append(part)
            n += 1
        if piece:
            final.append((h, '\n'.join(piece), ps, e))
    return final


def split_csv(text):
    """csv → 줄마다 '열: 값' 글로 바꿔 몇 줄씩 묶는다(머리줄을 매번 알 수 있게)."""
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        return []
    head = [h.strip() for h in rows[0]]
    out, piece, ps = [], [], 2
    for i, r in enumerate(rows[1:], 2):
        line = '; '.join(f'{h}: {v.strip()}' for h, v in zip(head, r) if v.strip())
        if not line:
            continue
        if piece and sum(len(x) for x in piece) + len(line) > C.CHUNK_MAX:
            out.append(('표', '\n'.join(piece), ps, i - 1))
            piece, ps = [], i
        piece.append(line)
    if piece:
        out.append(('표', '\n'.join(piece), ps, len(rows)))
    return out


def chunks_of(path, tagger):
    rel = os.path.relpath(path, C.ROOT)
    try:
        text = open(path, encoding='utf-8-sig').read()
    except UnicodeDecodeError:
        text = open(path, encoding='cp949', errors='replace').read()
    parts = split_csv(text) if path.lower().endswith('.csv') else split_text(text)
    title = _title(path)
    who_path = path_personas(rel)
    date = file_date(path)
    kind = kind_of(rel)
    file_stocks = tagger.find(title)
    out = []
    for head, body, s, e in parts:
        if len(body.strip()) < 20:
            continue
        ctx = f'{title} > {head}' if head and head != title else title
        stocks = sorted(set(file_stocks) | set(tagger.find(body)))
        owners = set(who_path)
        if not owners and kind in ('기업카드', '증권사리포트'):
            owners |= {tagger.owner[s] for s in file_stocks if s in tagger.owner}
        embed_text = f'[{ctx}]\n{body}'
        out.append({
            'id': hashlib.sha1(f'{rel}|{s}|{body}'.encode()).hexdigest()[:16],
            'vec_key': hashlib.sha1(embed_text.encode()).hexdigest(),
            '출처': rel, '줄': f'{s}-{e}', '날짜': date, '종류': kind,
            '위원': '|'.join(sorted(owners)) or '공통',
            '종목': '|'.join(stocks), '머리말': ctx, '글': body,
        })
    return out
