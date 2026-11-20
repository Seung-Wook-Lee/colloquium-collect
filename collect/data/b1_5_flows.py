"""1-5 수급 자료: 매일 수집(00_퀀트입력)의 13F·공매도·ETF 보유·팀Q 퀀트자료를 1_data로 모은다."""
import os

from .common import write
import pandas as pd

FILES = ['장기펀드13F.csv', '공매도.csv', 'ETF보유.csv', 'ETF멤버.csv', '퀀트자료.csv']


def run(ctx, c):
    got = {}
    for name in c.get('파일', FILES):
        p = os.path.join(ctx['in'], name)
        if not os.path.exists(p) and ctx.get('drive'):
            import drive
            b = drive.get(f"콜로키움 수집데이터/00_퀀트입력/{name}")
            if b:
                open(p, 'wb').write(b)
        if os.path.exists(p):
            df = pd.read_csv(p, encoding='utf-8-sig')
            write(ctx, f"수급_{name.replace('.csv', '')}.csv.gz", df)
            got[name] = len(df)
        else:
            got[name] = '없음'
    return got
