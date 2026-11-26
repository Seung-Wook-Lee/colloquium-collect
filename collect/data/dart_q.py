# 11/22 의장 선택 "DART 분기 실적으로 보충": 한투 분기 손익이 안 될 때 한국 종목 분기 매출·영업이익·순이익을 DART 정기보고서에서.
#   분기·반기·3분기 보고서의 당기 금액 = 그 3개월, 4분기 = 사업보고서 연간 − 3분기 누적. 연결 우선, 없으면 별도. 조회만.
import io, os, time, zipfile, datetime as dt, xml.etree.ElementTree as ET, requests

DART = 'https://opendart.fss.or.kr/api'
_CC = {}
ERR = []
ACC = {'매출': (['ifrs-full_Revenue'], ['매출액', '영업수익', '수익(매출액)', '매출']),
       '영업이익': (['dart_OperatingIncomeLoss'], ['영업이익', '영업이익(손실)']),
       '순이익': (['ifrs-full_ProfitLoss', 'ifrs-full_ProfitLossAttributableToOwnersOfParent'], ['당기순이익', '당기순이익(손실)', '분기순이익', '반기순이익'])}
QEND = {'11013': '03-31', '11012': '06-30', '11014': '09-30'}


def ready():
    return bool(os.environ.get('DART_KEY'))


def _get(api, p):
    for n in range(3):
        try:
            time.sleep(0.25)
            j = requests.get(f'{DART}/{api}', params={'crtfc_key': os.environ['DART_KEY'].strip(), **p}, timeout=20).json()
            if j.get('status') == '000':
                return j.get('list') or []
            if j.get('status') == '013':
                return None
            raise ValueError(f"{j.get('status')} {j.get('message')}")
        except Exception as e:
            if n == 2:
                ERR.append(str(e)[:120]); return None
            time.sleep(2 + 2 * n)


def corp(code):
    if not _CC:
        r = requests.get(f'{DART}/corpCode.xml', params={'crtfc_key': os.environ['DART_KEY'].strip()}, timeout=60)
        root = ET.fromstring(zipfile.ZipFile(io.BytesIO(r.content)).read('CORPCODE.xml'))
        for e in root.iter('list'):
            s = (e.findtext('stock_code') or '').strip()
            if s:
                _CC[s] = e.findtext('corp_code')
    return _CC.get(str(code).zfill(6))


def _amt(v):
    try:
        return float(str(v).replace(',', '').strip())
    except Exception:
        return None


def _pick(rows, k):
    ids, names = ACC[k]
    rows = [x for x in rows if x.get('sj_div') in ('IS', 'CIS')]
    for i in ids:
        for x in rows:
            if x.get('account_id') == i:
                return x
    for nm in names:
        for x in rows:
            if x.get('account_nm', '').replace(' ', '') == nm.replace(' ', ''):
                return x
    return None


def _rep(cc, y, rc):
    for fs in ('CFS', 'OFS'):
        r = _get('fnlttSinglAcntAll.json', {'corp_code': cc, 'bsns_year': str(y), 'reprt_code': rc, 'fs_div': fs})
        if r:
            return r
    return None


def quarterly(code, years=3):
    """[(분기말, 매출, 영업이익, 순이익)] 원 단위, 오래된 순"""
    cc = corp(code)
    if not cc:
        return []
    out, T = [], dt.date.today()
    Y = T.year
    due = {'11013': (5, 15), '11012': (8, 14), '11014': (11, 14), '11011': (3, 31)}   # 공시 마감(대략): 아직 안 나온 보고서는 묻지 않음
    for y in range(Y - years + 1, Y + 1):
        cum3 = {}
        for rc in ('11013', '11012', '11014', '11011'):
            m, d_ = due[rc]
            if dt.date(y + (1 if rc == '11011' else 0), m, d_) > T + dt.timedelta(days=10):
                continue
            rows = _rep(cc, y, rc)
            if not rows:
                continue
            v = {}
            for k in ACC:
                x = _pick(rows, k)
                if rc == '11011':
                    a = _amt(x.get('thstrm_amount')) if x else None
                    v[k] = a - cum3[k] if a is not None and cum3.get(k) is not None else None
                else:
                    v[k] = _amt(x.get('thstrm_amount')) if x else None
                    if rc == '11014':
                        cum3[k] = _amt(x.get('thstrm_add_amount')) if x else None
            if any(v[k] is not None for k in ('매출', '영업이익')):
                out.append((f'{y}-{QEND.get(rc, "12-31")}', v['매출'], v['영업이익'], v['순이익']))
    return out


# ---------------------------------------------------------------- 지역별 매출(11/26 의장 "나라별로 어느 나라이고, 어느 회사가 어디에 많이 팔았는지가 중요… 에이피알")
# 지역별 매출은 DART 숫자 API(fnlttSinglAcntAll)에 없고 정기보고서 원문의 표(매출 현황·부문 정보 주석)에 있다.
# → 정기보고서 원문(document.xml)의 표 중 첫 칸에 지역 이름이 2줄 넘게 있는 표를 그대로 옮겨 10년치 데이터베이스 칸 '지역매출'에 둔다.
#   처음 한 번만 과거 보고서를 받고, 그 뒤엔 칸에 없는 접수번호(새 보고서)만 받는다.
import re   # noqa: E402

REGION_KAN = '지역매출'
REGION_COLS = ['종목코드', '분기말', '보고서', '접수번호', '표번호', '표앞글', '단위', '머리', '지역', '값1', '값2', '값3']
REGION_WORDS = ['국내', '내수', '한국', '대한민국', '해외', '수출', '미국', '북미', '미주', '캐나다', '일본', '중국', '중화권', '홍콩', '대만',
                '아시아', '동남아', '동남아시아', '베트남', '태국', '싱가포르', '말레이시아', '인도네시아', '필리핀', '유럽', '영국', '중동', '호주',
                '오세아니아', '러시아', '남미', '기타', '기타지역', '기타국가', '합계', '총계', '계']
FOREIGN = {'미국', '북미', '미주', '일본', '중국', '중화권', '홍콩', '대만', '아시아', '동남아', '동남아시아', '유럽', '해외', '수출'}
_TAG = re.compile(r'<[^>]+>')


def _txt(s):
    return re.sub(r'\s+', ' ', _TAG.sub(' ', s).replace('&nbsp;', ' ').replace('&amp;', '&')).strip()


def _num(s):
    s = s.replace(',', '').replace(' ', '')
    neg = s.startswith('(') and s.endswith(')')
    s = s.strip('()△▲')
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg or s.startswith('-') and v > 0 else v


def region_tables(xml):
    """보고서 원문 → [(표번호, 표앞글, 단위, 머리, [(지역, 값1, 값2, 값3)])]. 첫 칸이 지역 이름인 줄이 2줄 이상 + 해외 지역 1줄 이상인 표만."""
    out = []
    for i, m in enumerate(re.finditer(r'<TABLE\b.*?</TABLE>', xml, re.S | re.I)):
        rows = []
        for tr in re.findall(r'<TR\b.*?</TR>', m.group(0), re.S | re.I):
            cells = [_txt(c) for c in re.findall(r'<(?:TD|TH|TE|TU)\b[^>]*>(.*?)</(?:TD|TH|TE|TU)>', tr, re.S | re.I)]
            if cells:
                rows.append(cells)
        if len(rows) < 3:
            continue
        key = lambda c: c.replace(' ', '').strip('()[]·-')
        reg = [r for r in rows if key(r[0]) in REGION_WORDS]
        if len(reg) < 2 or not any(key(r[0]) in FOREIGN for r in reg):
            continue
        before = _txt(xml[max(0, m.start() - 600):m.start()])
        unit = re.findall(r'단위\s*[:：]?\s*([^\)\]]{1,12})', before + ' ' + _txt(m.group(0))[:200])
        body = []
        for r in reg:
            vs = [v for v in (_num(c) for c in r[1:]) if v is not None][:3]
            body.append((key(r[0]), *(vs + [None] * (3 - len(vs)))))
        out.append((i, before[-80:], unit[0].strip() if unit else '', ' | '.join(rows[0])[:200], body))
    return out


def _qend(report_nm):
    m = re.search(r'\((\d{4})\.(\d{2})\)', report_nm)
    if not m:
        return ''
    y, mo = int(m.group(1)), int(m.group(2))
    return (dt.date(y + (mo == 12), mo % 12 + 1, 1) - dt.timedelta(days=1)).isoformat()


def regions(code, since='20230101', skip=()):
    """정기보고서(사업·반기·분기)마다 지역 표 → 줄 목록(REGION_COLS). skip = 이미 칸에 있는 접수번호."""
    cc = corp(code)
    if not cc:
        return []
    L, page = [], 1
    while True:
        r = _get('list.json', {'corp_code': cc, 'bgn_de': since, 'pblntf_ty': 'A', 'page_no': page, 'page_count': 100}) or []
        L += r
        if len(r) < 100:
            break
        page += 1
    out = []
    for x in L:
        nm, no = x.get('report_nm', ''), x.get('rcept_no', '')
        if not re.search(r'(사업|반기|분기)보고서', nm) or no in skip:
            continue
        time.sleep(0.3)
        try:
            b = requests.get(f'{DART}/document.xml', params={'crtfc_key': os.environ['DART_KEY'].strip(), 'rcept_no': no}, timeout=60).content
            Z = zipfile.ZipFile(io.BytesIO(b))
            xml = '\n'.join(Z.read(f).decode('utf-8', 'ignore') for f in Z.namelist())
        except Exception as e:   # noqa: BLE001
            ERR.append(f'{no} 원문 실패 {str(e)[:80]}'); continue
        for ti, pre, unit, head, body in region_tables(xml):
            for reg, v1, v2, v3 in body:
                out.append(dict(종목코드=str(code).zfill(6), 분기말=_qend(nm), 보고서=nm, 접수번호=no, 표번호=ti, 표앞글=pre, 단위=unit, 머리=head,
                                지역=reg, 값1=v1, 값2=v2, 값3=v3))
    return out


def run(ctx, c=None):
    """블록 1-11: 지역별 매출 → 1_data/가격10년_지역매출.csv.gz(10년치 데이터베이스 칸). 대상 종목 = data.yaml '1-11'.종목, 없으면 에이피알."""
    import pandas as pd
    try:
        from . import px_store as PS
    except ImportError:
        import px_store as PS
    if not ready():
        return 'DART 키 없음 — 건너뜀'
    codes = (c or {}).get('종목') or ['278470']
    d = ctx['out']
    if ctx.get('drive'):
        import drive
        PS.fetch(drive, REGION_KAN, d)
    old = PS.table(d, REGION_KAN, dtype={'종목코드': str, '접수번호': str})
    seen = set(old['접수번호']) if len(old) else set()
    new = []
    for code in codes:
        new += regions(code, skip=seen)
    N = pd.DataFrame(new, columns=REGION_COLS)
    if len(N):
        D = pd.concat([old, N], ignore_index=True) if len(old) else N
        D = D.sort_values(['종목코드', '분기말', '접수번호', '표번호']).reset_index(drop=True)
        PS.put_table(d, REGION_KAN, D)
        if ctx.get('drive'):
            import drive
            drive.put(f'{PS.BASE}/1_data/{PS.name(REGION_KAN)}', open(f'{d}/{PS.name(REGION_KAN)}', 'rb').read())
    else:
        D = old
    # 첫 실행 확인용: 새로 받은 표를 그대로 찍는다(어느 표가 지역별 매출인지 의장께 보여 드리고 고름)
    for (no, ti), g in N.groupby(['접수번호', '표번호'], sort=False):
        r0 = g.iloc[0]
        print(f"[지역매출] {r0['보고서']} 표{ti} 단위 {r0['단위']} | 앞글 …{r0['표앞글'][-50:]} | 머리 {r0['머리'][:80]}")
        for _, r in g.iterrows():
            print(f"    {r['지역']}: {r['값1']} | {r['값2']} | {r['값3']}")
    return f"새 줄 {len(N)}(보고서 {N['접수번호'].nunique() if len(N) else 0}개) | 칸 {len(D)}줄 | DART 오류 {ERR[:3]}"
