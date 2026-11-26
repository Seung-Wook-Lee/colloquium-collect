"""유니버스 관리(11/26 의장 "유니버스 관리하는 코드 만들어. 그걸 돌리면 자동으로 CSV에서 지워지도록 하고, 추가할 때는 추가되도록").
- 넣기·빼기 목록은 collect/layers.py 의 ADD·OUT 한 곳.
- 유니버스 = 10년치 데이터베이스 칸(1_data/가격10년_유니버스.csv.gz) 하나. 그 칸 안에서 줄을 지우고 더함(새 파일을 만들지 않음, 11/26 의장 "새 파일 만들지 말라니까", "하나로 통일해").
- 지운 종목은 10년치 데이터베이스(1_data/가격10년_시가·고가·저가·종가·거래량·EPS) 칸에서도 지움.
- 더한 종목의 과거 가격은 다음 가격 수집(아침 8시 미국 · 저녁 8시 한국)이 '새 종목만 과거치' 규칙(px_store.update)으로 한 번 받음.
  python collect/universe_manage.py           # 드라이브에 반영
  python collect/universe_manage.py --dry     # 바뀔 것만 보여 줌"""
import argparse
import io  # noqa: F401
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, 'data')]
import layers  # noqa: E402
import px_store as PS  # noqa: E402



def apply(u, out=None, add=None):
    """유니버스 표 → (새 표, 지운 티커, 더한 티커)."""
    out = set(layers.OUT if out is None else out)
    add = list(layers.ADD if add is None else add)
    t = u['yfinance 티커'].astype(str)
    gone = sorted(set(t[t.isin(out)]))
    u = u[~t.isin(out)]
    have = set(u['yfinance 티커'].astype(str))
    new = [r for r in add if str(r.get('yfinance 티커')) not in have and str(r.get('yfinance 티커')) not in out]
    if new:
        u = pd.concat([u, pd.DataFrame(new)], ignore_index=True)[list(u.columns) + [c for c in pd.DataFrame(new).columns if c not in u.columns]]
    return u, gone, [r['yfinance 티커'] for r in new]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    import drive
    u = PS.universe(drive)   # 유니버스 = 10년치 데이터베이스 칸 하나(11/26 의장 "하나로 통일해")
    if not len(u):
        print('[유니버스] 데이터베이스 유니버스 칸 없음'); return
    v, gone, new = apply(u)
    print(f'[유니버스] 데이터베이스 칸 {PS.name(PS.UNIV_KAN)}: {len(u)}줄 → {len(v)}줄 | 지움 {gone or "없음"} | 더함 {new or "없음"}')
    if a.dry:
        return
    if gone or new:
        PS.put_universe(drive, v)
        print('[유니버스] 데이터베이스 칸에 반영(새 파일 없음)')
    # 10년치 데이터베이스: 빼기 목록 티커 칸 지움(이미 없으면 그대로)
    out = set(layers.OUT)
    for k in list(PS.F) + ['EPS']:
        p = f'{PS.BASE}/1_data/{PS.name(k)}'
        b = drive.get(p)
        if not b:
            continue
        d = pd.read_csv(io.BytesIO(b), index_col=0, encoding='utf-8-sig', compression='gzip')
        drop = [c for c in d.columns if c in out]
        if drop:
            buf = io.BytesIO()
            d.drop(columns=drop).to_csv(buf, encoding='utf-8-sig', compression={'method': 'gzip'})
            drive.put(p, buf.getvalue())
            print(f'[데이터베이스] {PS.name(k)}: {drop} 칸 지움')
        else:
            print(f'[데이터베이스] {PS.name(k)}: 지울 칸 없음')


if __name__ == '__main__':
    main()
