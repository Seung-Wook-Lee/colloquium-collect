"""블록 1 공통: 비공개 설정, 출력 폴더, 드라이브 저장, 유니버스."""
import os
import sys

import pandas as pd
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [REPO, os.path.join(os.path.dirname(REPO), 'app', 'block33')]   # qc_config(비공개 설정 읽기)는 app/block33
import qc_config as QCC  # noqa: E402

D_DATA = '콜로키움 수집데이터'
D_OUT = f'{D_DATA}/1_data'


def cfg():
    p = os.path.join(QCC.private_dir(), 'data.yaml')
    return yaml.safe_load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


def write(ctx, name, df, index=False):
    """1_data 폴더에 저장(.csv.gz). ctx['out'] 아래에 두고, 드라이브를 쓰면 올린다."""
    p = os.path.join(ctx['out'], name)
    df.to_csv(p, index=index, encoding='utf-8-sig', compression='gzip' if name.endswith('.gz') else None)
    ctx.setdefault('written', []).append(name)
    return p


def read(ctx, name, **kw):
    p = os.path.join(ctx['out'], name)
    if not os.path.exists(p) and ctx.get('drive'):
        import drive
        b = drive.get(f'{D_OUT}/{name}')
        if b:
            open(p, 'wb').write(b)
    if not os.path.exists(p):
        return None
    return pd.read_csv(p, encoding='utf-8-sig', **kw)


def universe(ctx):
    """유니버스 원본: 로컬 폴더 유니버스.csv, 없으면 드라이브 콜로키움/포트폴리오 최신."""
    p = os.path.join(ctx['in'], '유니버스.csv')
    if not os.path.exists(p) and ctx.get('drive'):
        import drive
        names = sorted(f['name'] for f in drive.ls('콜로키움/포트폴리오') if f['name'].startswith('콜로키움100_유니버스_') and f['name'].endswith('.csv'))
        if names:
            open(p, 'wb').write(drive.get(f'콜로키움/포트폴리오/{names[-1]}'))
    return pd.read_csv(p, encoding='utf-8-sig', dtype=str)


def need(ctx, key, name, **kw):
    """앞 하위 블록 결과: 이번 실행에 있으면 그것, 없으면 1_data에 저장된 것."""
    if ctx.get(key) is None:
        ctx[key] = read(ctx, name, **kw)
    return ctx[key]
