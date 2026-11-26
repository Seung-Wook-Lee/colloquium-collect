"""관세청 품목별 국가별 수출입실적 → 10년치 데이터베이스 칸(1_data/가격10년_화장품수출.csv.gz).
11/26 의장 카드 '화장품 수출 통계를 관세청에서 받아도 될까요?' → '받아도 됨'(에이피알 "특히 수출" 검정용).
- 품목: HS 3304(화장품, 기초·색조). 국가별 월 수출액(달러)·중량(kg). 전체는 국가 합.
- 받기: 저녁 8시 수집(kr_evening.yml)과 블록 1(data.run --only 1-10). 칸 마지막 달 2달 전부터만 다시 받아 덧붙임(관세청 잠정치 수정 반영).
  칸이 없으면 2016-01부터 1년씩 끊어 받음. 다른 저장 파일을 만들지 않음(11/26 의장 "10년치 하나에").
- 키: 깃허브 비밀값 DATA_GO_KR_KEY(공공데이터포털 일반 인증키, Decoding). 키가 없으면 건너뜀.
  python collect/data/customs.py            # 드라이브 칸에 덧붙임
  python collect/data/customs.py --local D  # D/가격10년_화장품수출.csv.gz 로 손 시험"""
import argparse
import datetime as dt
import os
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE)]
import px_store as PS  # noqa: E402

URL = 'https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList'
HS = ['3304']
KAN = '화장품수출'
START = '201601'
COLS = ['월', 'HS', '국가코드', '국가', '수출달러', '수출중량', '수입달러']


def _ym(d):
    return f'{d.year}{d.month:02d}'


def _add(ym, n):
    y, m = int(ym[:4]), int(ym[4:]) + n
    y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
    return f'{y}{m:02d}'


def _num(x):
    try:
        return float(str(x).replace(',', ''))
    except Exception:   # noqa: BLE001
        return None


def get(hs, a, b, key):
    """a~b(YYYYMM, 12달 이내) 국가별 월 줄. '총계' 줄은 뺌."""
    for n in range(3):
        try:
            r = requests.get(URL, params={'serviceKey': key, 'strtYymm': a, 'endYymm': b, 'hsSgn': hs}, timeout=60)
            root = ET.fromstring(r.content)
            code = root.findtext('.//resultCode')
            if code not in (None, '00'):
                raise ValueError(f"{code} {root.findtext('.//resultMsg')}")
            rows = []
            for it in root.iter('item'):
                g = lambda k: (it.findtext(k) or '').strip()
                y = g('year')
                if not y or '총계' in y:
                    continue
                rows.append({'월': y.replace('.', '-')[:7], 'HS': g('hsCd') or hs, '국가코드': g('statCd'), '국가': g('statCdCntnKor1'),
                             '수출달러': _num(g('expDlr')), '수출중량': _num(g('expWgt')), '수입달러': _num(g('impDlr'))})
            return pd.DataFrame(rows, columns=COLS)
        except Exception as e:   # noqa: BLE001
            if n == 2:
                print(f'[관세청] {hs} {a}~{b} 실패: {str(e)[:120]} | 응답 앞부분 {r.text[:200] if "r" in locals() else ""}')
                return pd.DataFrame(columns=COLS)
            time.sleep(3 + 3 * n)


def update(old, key, today=None):
    today = today or dt.date.today()
    end = _ym(today.replace(day=1) - dt.timedelta(days=1))   # 지난달까지(이번 달은 아직 없음)
    start = _add(old['월'].max().replace('-', ''), -2) if len(old) else START
    new = []
    for hs in HS:
        a = start
        while a <= end:
            b = min(_add(a, 11), end)
            new.append(get(hs, a, b, key)); a = _add(b, 1)
    N = pd.concat(new, ignore_index=True) if new else pd.DataFrame(columns=COLS)
    if not len(N):
        return old, 0, start, end
    keep = old[~old['월'].isin(set(N['월']))] if len(old) else old
    D = pd.concat([keep, N], ignore_index=True).sort_values(['HS', '월', '국가코드']).reset_index(drop=True)
    return D, N['월'].nunique(), start, end


def run(ctx, c=None):
    key = os.environ.get('DATA_GO_KR_KEY', '').strip()
    if not key:
        return '키 없음(DATA_GO_KR_KEY) — 건너뜀'
    d = ctx['out']
    if ctx.get('drive'):
        import drive
        PS.fetch(drive, KAN, d)
    old = PS.table(d, KAN, dtype={'국가코드': str, 'HS': str})
    old = old if len(old) else pd.DataFrame(columns=COLS)
    D, n, a, b = update(old, key)
    if n:
        PS.put_table(d, KAN, D)
        if ctx.get('drive'):
            import drive
            drive.put(f'{PS.BASE}/1_data/{PS.name(KAN)}', open(f'{d}/{PS.name(KAN)}', 'rb').read())
    tot = D.groupby('월')['수출달러'].sum() / 1e6 if len(D) else pd.Series(dtype=float)
    last = ' / '.join(f'{m} {v:,.0f}백만달러' for m, v in tot.tail(3).items())
    return f'{a}~{b} 받음, 새로 쓴 달 {n}개 | 칸 {len(D)}줄 {D["월"].min() if len(D) else "-"}~{D["월"].max() if len(D) else "-"} | 최근 3달 수출 {last}'


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--local')
    a = ap.parse_args()
    use = False
    if not a.local:
        import drive
        use = drive.ready()
    print('[관세청 화장품 수출]', run({'out': a.local or tempfile.mkdtemp(), 'drive': use}))
