"""1-2 미국 재무(SEC XBRL, 공시일 기준 분기): 유니버스 미국 개별주 + S&P500."""
import os

from .common import universe, write


def run(ctx, c):
    from data import sec_fund
    U = universe(ctx)
    p = os.path.join(ctx['tmp'], '_u.csv'); U.to_csv(p, index=False, encoding='utf-8-sig')
    D = sec_fund.run(ctx['tmp'], p, sp500=c.get('S&P500', True))
    write(ctx, 'SEC재무_분기.csv.gz', D)
    ctx['SEC'] = D
    return {'종목': int(D['ticker'].nunique()), '행': len(D), '시작': str(D['분기말'].min())[:10], '끝': str(D['분기말'].max())[:10]}
