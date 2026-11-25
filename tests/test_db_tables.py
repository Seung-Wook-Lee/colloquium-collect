"""11/26 의장 "10년치 저장본 밖에 따로 있는 과거 자료들을 저장본에 합치시오"(저장본의 칸으로), "옛 파일을 지우고":
과거 자료는 1_data/가격10년_{칸}.csv.gz 하나로 읽고 쓴다. 옛 자리 이름은 px_store.TABLES(옮기기 표) 밖에서 쓰지 않는다."""
import pathlib
import sys

import pandas as pd

R = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(R / 'collect' / 'data')]
OLD = ['시타델_주봉', 'SEC재무_분기', 'DART재무_분기', '국내수급_일별', '장기펀드13F_이력', '노르웨이_보유_이력', '공매도_미국_이력', 'ETF좌수_이력', '지수_장기.csv', '블록점수이력.csv',
       '시장위험_장기', '공포탐욕_이력', '지정학위험_이력', '신용스프레드_이력', 'CPCE.csv', '시장블록이력', '추가자료_종가']
CODE = [p for d in ('app', 'collect') for p in (R / d).rglob('*.py')]


class FakeDrive:
    def __init__(self, files): self.f = dict(files); self.trashed = []
    def get(self, p): return self.f.get(p)
    def put(self, p, b): self.f[p] = b
    def trash(self, p): self.trashed.append(p); self.f.pop(p, None); return 1


def test_old_names_only_in_move_table():
    bad = []
    for p in CODE:
        if p.name in ('px_store.py',) or 'market/good_stock_pit.py' in str(p):   # good_stock_pit은 /mnt 사본을 읽는 지난 분석
            continue
        src = p.read_text(encoding='utf-8')
        for o in OLD:
            for ln in src.splitlines():
                code = ln.split('#')[0]
                if o in code and '옛' not in ln and '"""' not in ln and "'history/" not in code:   # history/ = 받는 코드의 작업 파일(PS.market이 칸으로 합침)
                    bad.append(f'{p.relative_to(R)}: {ln.strip()[:90]}')
    assert not bad, '\n'.join(bad)


def test_fetch_moves_old_file_then_trashes(tmp_path):
    import gzip
    import px_store as PS
    raw = '날짜,코드,외국인\n2026-11-25,005930,1\n'.encode()
    old = f"{PS.BASE}/1_data/장기/장기펀드13F_이력.csv"
    D = FakeDrive({old: raw})
    assert PS.fetch(D, '13F', str(tmp_path), log=lambda *a: None)
    new = f"{PS.BASE}/1_data/가격10년_13F.csv.gz"
    assert gzip.decompress(D.f[new]) == raw and D.trashed == [old]
    assert len(PS.table(str(tmp_path), '13F')) == 1
    D2 = FakeDrive({new: D.f[new]})   # 칸이 있으면 옛 자리는 건드리지 않음
    assert PS.fetch(D2, '13F', str(tmp_path)) and D2.trashed == []


def test_market_merges_five_into_one(tmp_path):
    import px_store as PS
    B = PS.BASE
    def csv(df): return df.to_csv(encoding='utf-8-sig').encode('utf-8-sig')
    ix = pd.to_datetime(['2024-01-02', '2024-01-03']); ix.name = '날짜'
    D = FakeDrive({f'{B}/1_data/장기/시장위험_장기.csv': csv(pd.DataFrame({'SPX': [1., 2.], 'CPCE': [0.5, None]}, index=ix)),
                   f'{B}/1_data/장기/CPCE.csv': csv(pd.DataFrame({'CPCE': [0.9, 0.8]}, index=ix)),
                   f'{B}/1_data/장기/공포탐욕_이력.csv': csv(pd.DataFrame({'Fear Greed': [30., 40.]}, index=ix)),
                   f'{B}/1_data/장기/지정학위험_이력.csv': csv(pd.DataFrame({'GPRD': [100., 120.]}, index=ix))})
    M = PS.market(D, '', str(tmp_path), log=lambda *a: None)
    assert list(M['공포탐욕']) == [30., 40.] and list(M['지정학위험']) == [100., 120.]
    assert list(M['CPCE']) == [0.5, 0.8]   # 시장위험_장기 값 우선, 빈 날은 CPCE.csv
    assert f'{B}/1_data/{PS.name("시장지표")}' in D.f and not any('장기/' in k for k in D.f)
    assert PS.frame(str(tmp_path), '시장지표').shape == (2, 4)
