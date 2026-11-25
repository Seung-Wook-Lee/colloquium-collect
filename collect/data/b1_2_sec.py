"""1-2 미국 재무(SEC XBRL, 공시일 기준 분기): 유니버스 미국 개별주 + S&P500."""
import os

from . import px_store as PS
from .common import universe, write


def run(ctx, c):
    from data import sec_fund
    if ctx.get('drive'):   # 11/26 의장: 과거 자료는 10년치 저장본 칸 — 칸이 아직 없으면 옛 파일을 칸으로 옮기고 휴지통
        import drive
        PS.fetch(drive, 'SEC재무', ctx['out'])
    U = universe(ctx)
    p = os.path.join(ctx['tmp'], '_u.csv'); U.to_csv(p, index=False, encoding='utf-8-sig')
    D = sec_fund.run(ctx['tmp'], p, sp500=c.get('S&P500', True))
    write(ctx, PS.name('SEC재무'), D)   # 10년치 저장본 칸(옛 1_data/SEC재무_분기)
    ctx['SEC'] = D
    return {'종목': int(D['ticker'].nunique()), '행': len(D), '시작': str(D['분기말'].min())[:10], '끝': str(D['분기말'].max())[:10]}
