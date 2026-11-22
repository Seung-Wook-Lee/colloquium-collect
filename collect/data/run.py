"""블록 1 data 실행: 켜진 하위 블록을 번호 순서대로(비공개 data.yaml '켜기').
  python -m data.run                    # GitHub Actions: 드라이브 읽고 '콜로키움 수집데이터/1_data/'에 올림
  python -m data.run --local <폴더>     # 손 시험: <폴더>/유니버스.csv(·kr_standardized_pit.parquet 등), 결과 <폴더>/1_data/
  python -m data.run --only 1-6,1-8     # 일부만(앞 블록 결과는 1_data에서 읽음)"""
import argparse
import importlib
import json
import os
import tempfile
import time
import traceback

from .common import D_OUT, cfg

SUB = {'1-1': 'b1_1_prices', '1-2': 'b1_2_sec', '1-3': 'b1_3_dart', '1-6': 'b1_6_clean', '1-4': 'b1_4_per',
       '1-5': 'b1_5_flows', '1-7': 'b1_7_universe', '1-8': 'b1_8_layers', '1-9': 'b1_9_quality'}
ORDER = ['1-1', '1-2', '1-3', '1-6', '1-4', '1-5', '1-7', '1-8', '1-9']   # 1-4는 1-6 정제 가격을 쓴다


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--local'); ap.add_argument('--only')
    a = ap.parse_args()
    C = cfg()
    on = C.get('켜기', ORDER)
    if a.only:
        on = [x for x in a.only.split(',')]
        if '1-8' in on and '1-7' not in on:
            on.append('1-7')   # 층은 유니버스 규칙이 먼저
    use_drive = False
    if a.local:
        IN = os.path.abspath(a.local)
    else:
        import drive
        use_drive = drive.ready()
        IN = tempfile.mkdtemp()
    OUT = os.path.join(IN, '1_data'); os.makedirs(OUT, exist_ok=True)
    ctx = {'in': IN, 'out': OUT, 'tmp': tempfile.mkdtemp(), 'drive': use_drive}
    rep = {}
    for k in ORDER:
        if k not in on:
            rep[k] = '적용 안 함'
            continue
        t0 = time.time()
        try:
            mod = importlib.import_module(f'data.{SUB[k]}')
            rep[k] = mod.run(ctx, C.get(k, {}) or {})
        except Exception as e:   # noqa: BLE001
            traceback.print_exc()
            rep[k] = f'실패: {type(e).__name__}: {e}'[:300]
        print(f'[{k}] {time.time() - t0:.0f}초 {rep[k]}', flush=True)
    js = json.dumps(rep, ensure_ascii=False, indent=1, default=str)
    open(os.path.join(OUT, '블록1_실행기록.json'), 'w', encoding='utf-8').write(js)
    if use_drive:
        import drive
        for name in ctx.get('written', []) + ['블록1_실행기록.json']:
            drive.put(f'{D_OUT}/{name}', open(os.path.join(OUT, name), 'rb').read())
        print(f'[드라이브] {D_OUT}/ {len(ctx.get("written", []))}개')


if __name__ == '__main__':
    main()
