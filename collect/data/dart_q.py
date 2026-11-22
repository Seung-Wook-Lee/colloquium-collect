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
            j = requests.get(f'{DART}/{api}', params={'crtfc_key': os.environ['DART_KEY'], **p}, timeout=20).json()
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
        r = requests.get(f'{DART}/corpCode.xml', params={'crtfc_key': os.environ['DART_KEY']}, timeout=60)
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
    out, Y = [], dt.date.today().year
    for y in range(Y - years + 1, Y + 1):
        cum3 = {}
        for rc in ('11013', '11012', '11014', '11011'):
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
