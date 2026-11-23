"""우리 자료만 읽는 단일 입구 (11/23 의장: "우리 데이터에 금값이 있니 없니? 없으면 '데이터에 없어서 검색해야 할 것 같은데'라고 물어야. 이 순서를 반드시 지키게 코딩").

순서(바꾸지 말 것)
 1. 분석 스크립트는 가격을 이 모듈 get()으로만 읽는다. yfinance 직접 다운로드는 tests/test_ourdata_gate.py가 막는다.
 2. get()이 우리 자료에서 못 찾으면 NotInOurData를 낸다 → 계산을 멈추고 의장께 "우리 자료에 ○○이 없어 검색(외부 다운로드)해야 할 것 같습니다. 받아도 될까요?"를 먼저 묻는다.
 3. 의장이 허락하면 app/market/외부자료_허락.yaml에 날짜·지시와 함께 적고, 그 스크립트만 외부에서 받는다.

우리 자료(읽는 순서)
 - 시장위험_장기.csv : fetch_risk.yml이 매일 쌓는 장기 일봉(SPX·NDX·GOLD(금 선물 GC=F)·SILVER·BTC·TLT·IEF·SHY·LQD·QQQ·RSP·VIX…·FRED 금리)
 - 지수_장기.csv.gz  : ^GSPC·^NDX·^KS11(코스피) 종가
 - 가격10년_종가.csv.gz : 유니버스 종목·ETF 2016~ 종가(START_DIR에 있을 때)
 - 추가자료_종가.csv : 위에 없는 것을 한투에서 받아 둔 것(kis_extra.yml, 드라이브 1_data). 목록 collect/data/추가자료_목록.yaml
"""
import os
from pathlib import Path

import pandas as pd

DIRS = [Path(p) for p in (os.environ.get('START_DIR', ''), '/mnt/project-files/유니버스/코드', '/mnt/project-files/유니버스/start') if p]
ALIAS = {'금': 'GOLD', 'GC=F': 'GOLD', '은': 'SILVER', '장기채': 'TLT', 'S&P500': 'SPX', '^GSPC': 'SPX', '나스닥100': 'NDX', '^NDX': 'NDX',
         '코스피': '^KS11', 'KOSPI': '^KS11', '코스닥': 'KOSDAQ', '^KQ11': 'KOSDAQ', '금광주': 'GDX', '필라델피아반도체': 'SOX', '필반': 'SOX', '^SOX': 'SOX', '비트코인': 'BTC', 'BTC-USD': 'BTC'}


class NotInOurData(KeyError):
    pass


def _find(name):
    for d in DIRS:
        p = d / name
        if p.exists():
            return p
    return None


_cache = {}


def _risk():
    if 'risk' not in _cache:
        p = _find('시장위험_장기.csv')
        _cache['risk'] = pd.read_csv(p, index_col=0, parse_dates=True) if p else pd.DataFrame()
    return _cache['risk']


def _index():
    if 'idx' not in _cache:
        p = _find('지수_장기.csv.gz')
        if p:
            I = pd.read_csv(p); I['날짜'] = pd.to_datetime(I['날짜'])
            _cache['idx'] = I.pivot_table(index='날짜', columns='지수', values='종가')
        else:
            _cache['idx'] = pd.DataFrame()
    return _cache['idx']


def _px10():
    if 'px' not in _cache:
        p = _find('가격10년_종가.csv.gz')
        _cache['px'] = pd.read_csv(p, index_col=0, parse_dates=True) if p else pd.DataFrame()
    return _cache['px']


def _extra():
    if 'ex' not in _cache:
        p = _find('추가자료_종가.csv') or _find('추가자료_종가.csv.gz')
        _cache['ex'] = pd.read_csv(p, index_col=0, parse_dates=True, encoding='utf-8-sig') if p else pd.DataFrame()
    return _cache['ex']


def where(name):
    """그 이름이 우리 자료 어디에 있는지(파일, 칸). 없으면 None."""
    k = ALIAS.get(name, name)
    for fname, df in (('시장위험_장기.csv', _risk()), ('지수_장기.csv.gz', _index()), ('가격10년_종가.csv.gz', _px10()), ('추가자료_종가.csv', _extra())):
        if k in df.columns and df[k].notna().any():
            return fname, k
    return None


def get(*names, low=False):
    """우리 자료에서 일봉 종가(low=True면 저가 칸이 있을 때 저가)를 읽는다. 하나라도 없으면 NotInOurData."""
    out, miss = {}, []
    for n in names:
        w = where(n)
        if w is None:
            miss.append(n); continue
        fname, k = w
        df = {'시장위험_장기.csv': _risk(), '지수_장기.csv.gz': _index(), '가격10년_종가.csv.gz': _px10(), '추가자료_종가.csv': _extra()}[fname]
        col = f'{k}_LOW' if low and f'{k}_LOW' in df.columns else k
        out[n] = df[col].dropna()
    if miss:
        raise NotInOurData(f"우리 자료에 없음: {', '.join(miss)} → 계산 멈춤. collect/data/추가자료_목록.yaml에 더하고 kis_extra.yml(한투)로 받아 드라이브에 저장한 뒤 다시 계산(11/23 의장). 한투에 없으면 의장께 묻는다.")
    return pd.DataFrame(out)


def source_line(*names):
    """보고에 붙일 출처 한 줄."""
    return ' · '.join(f"{n}={'/'.join(where(n))}" if where(n) else f'{n}=우리 자료에 없음' for n in names)


def crash_low(s, bottom, before=15, after=15):
    """폭락 구간 저점일: 기준 바닥일(S&P 종가 바닥) 앞뒤 거래일 창 안의 종가 최저일. 창을 임의 날짜로 잡지 않는다(11/23 2025 금 2/28 오류)."""
    s = s.dropna(); i = s.index.searchsorted(pd.Timestamp(bottom))
    w = s.iloc[max(0, i - before): i + after + 1]
    return w.idxmin(), float(w.min())
