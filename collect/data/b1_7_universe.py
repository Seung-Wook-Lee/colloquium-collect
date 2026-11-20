"""1-7 유니버스 생성법: 삭제 목록·제외 시장(비공개 blocks.yaml '유니버스')."""
from .common import universe, write
import qc_config as QCC


def run(ctx, c):
    u = QCC.load_blocks()['유니버스']
    U = universe(ctx)
    n0 = len(U)
    U = U[~U['정식 종목명'].isin(u.get('삭제', [])) & ~U['yfinance 티커'].isin(u.get('삭제', [])) & ~U['시장'].isin(u.get('제외_시장', []))]
    ctx['U'] = U; ctx['ucfg'] = u
    return {'원본': n0, '남음': len(U)}
