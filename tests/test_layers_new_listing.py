"""11/26 의장 "상장한 지 한 달도 안 된 것의 5년 자료가 어디 있나": 층L은 야후에서 받지 않고 데이터베이스 가격만.
자료가 짧은 새 종목(ANT)은 비워 두고 넘어간다(다음 실행에 다시 계산)."""
import pathlib
import sys

import numpy as np
import pandas as pd

R = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(R / 'app' / 'block33'), str(R / 'collect'), str(R / 'collect' / 'data')]
import engine as E  # noqa: E402
import px_store as PS  # noqa: E402


def test_new_listing_blank_no_download(tmp_path, monkeypatch):
    import yfinance as yf
    monkeypatch.setattr(yf, 'download', lambda *a, **k: (_ for _ in ()).throw(AssertionError('야후에서 받으면 안 됨')))
    idx = pd.bdate_range(end='2026-11-26', periods=1300)
    rng = np.random.default_rng(0)
    C = pd.DataFrame({'AAA': 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx))))}, index=idx)
    C['ANT'] = np.nan
    C.loc[idx[-6:], 'ANT'] = [97.2, 88.9, 90, 91, 92, 93]
    C.to_csv(tmp_path / PS.name('Close'), encoding='utf-8-sig')
    pd.DataFrame({'번호': ['U1-1', 'U1-2'], '정식 종목명': ['A', 'Anthropic'], '시장': ['미국', '미국'],
                  '구분': ['개별주', '개별주'], 'yfinance 티커': ['AAA', 'ANT']}).to_csv(tmp_path / '유니버스.csv', index=False, encoding='utf-8-sig')
    B = {'유니버스': {'변동성_년': 5, '문턱': {'미국 기업': [20, 30, 40, 60]}}}
    f = pd.DataFrame({'번호': ['U1-1', 'U1-2']})
    out = E.layers_l(str(tmp_path), f, B, pd.DataFrame()).set_index('번호')
    assert out.loc['U1-1', '층L'] != '' and out.loc['U1-1', 'vol_yr'] > 0
    assert out.loc['U1-2', '층L'] == '' and np.isnan(out.loc['U1-2', 'vol_yr'])


def test_engine_has_no_yahoo_layer_download():
    s = (R / 'app' / 'block33' / 'engine.py').read_text(encoding='utf-8')
    assert 'UL.classify(U, cfg)' not in s
