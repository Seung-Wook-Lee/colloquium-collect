"""블록 완성도 점검표(11/19 의장). 성적을 매기기 전에 블록이 '완성'됐는지 프로그램이 판정한다.

점검 5가지(블록마다, 공식마다):
 ① 채움률: 그 공식이 '해당되는' 종목 중 값이 있는 비율. 해당 범위는 blocks.yaml '칸범위'
    (예: 외국인·기관·연기금 수급은 한국 종목만, 재무 이익 칸은 개별주만, 부채·FCF·Z는 금융 층 S5 제외).
    범위 밖은 결측이 아니라 '해당 없음'.
 ② 과거 계산: 공식이 쓰는 칸의 과거 자료 종류(blocks.yaml '칸과거'). 가장 약한 칸이 그 공식의 등급.
 ③ 칸 존재: 공식이 쓰는 칸 이름이 엔진이 만든 칸에 실제로 있는지(오타·미연결 = 공식이 영원히 '자료 없음').
 ④ 역할 일치: 적힌 역할이 엔진 코드에서 실제 그 역할로 쓰이는지.
 ⑤ 시험: tests/test_quant_center.py 가 엔진·합산·메타·점검표를 시험한다(실행 결과는 따로).

판정: 공식 채움률 < 삭제선 = '삭제 대상', < 완성선 = '보완 필요', 그 외 '완성'.
블록: 공식이 모두 완성(삭제 대상 없음) + 칸 존재 + 역할 일치 = '완성'.
실행: python audit.py <입력 폴더>  →  <입력>/../out_블록완성도.csv, out_공식완성도.csv
"""
import os
import sys

import numpy as np
import pandas as pd
import yaml

import engine as E

ORDER = ['가격', 'BLOCK20', '공시', '누적', '없음']   # 과거 계산 등급(앞이 강함)


def scope_mask(var, f, SCOPE):
    m = pd.Series(True, index=f.index)
    for sc, names in SCOPE.items():
        if var not in names:
            continue
        if sc == '한국': m &= f['시장'] == '한국'
        elif sc == '미국': m &= f['시장'] == '미국'
        elif sc == '개별주': m &= f['구분'] == '개별주'
        elif sc == 'ETF': m &= f['구분'] == 'ETF'
        elif sc == '개별주수급': m &= f['구분'] == '개별주'
        elif sc == '비금융': m &= (f['layer'] != 'S5') & (f['구분'] == '개별주')
        elif sc == 'BLOCK20': m &= f['ticker'].isin(BLOCK20_TICKERS)
    return m


BLOCK20_TICKERS = set()


def hist_class(var, HIST):
    for k, names in HIST.items():
        if var in names:
            return k
    return '없음'


def audit(d, cfg='blocks.yaml', S=None, f=None, m=None):
    B = yaml.safe_load(open(cfg, encoding='utf-8'))
    A = B.get('완성도', {})
    SCOPE, HIST = A.get('칸범위', {}), A.get('칸과거', {})
    del_line, ok_line = A.get('삭제선', 0.5), A.get('완성선', 0.8)
    if S is None:
        S, _, _, m = E.run(d, cfg)
        f = E.run.last_f
    global BLOCK20_TICKERS
    try:
        L = pd.read_csv(f'{d}/forward_log.csv', encoding='utf-8-sig')
        BLOCK20_TICKERS = set(L.loc[L['asof'] == L['asof'].max(), 'ticker'])
    except (FileNotFoundError, KeyError):
        BLOCK20_TICKERS = set()
    f = f[f['layer'] != 'S0'].reset_index(drop=True)
    rows = [r.to_dict() for _, r in f.iterrows()]
    cols = set(f.columns)
    mcols = set(k for k in m if not k.startswith('_'))
    # 엔진이 역할을 실제로 쓰는 블록(엔진 코드가 질문으로 찾는 거르기·매도 블록)
    SB = B['종목']
    Q = {b['질문']: k for k, b in SB.items()}
    used_filter = {Q.get('이익이 늘고 있나?'), Q.get('사건 역풍이 있나?')} | {k for q, k in Q.items() if q.startswith('추천할 만큼')}
    used_sell = {Q.get('너무 많이 올랐나?'), Q.get('고점 부근이 아닌가?')}
    FR, BR = [], []
    for sec in ('시장', '종목'):
        for bid, b in B[sec].items():
            fl, roles_ok, note = [], True, []
            role = b.get('역할', '시장')
            if sec == '시장':
                if bid in A.get('시장연결', {}):
                    note.append(A['시장연결'][bid])
                else:
                    note.append('계산·보고만(추천·비중 공식에 연결 안 됨)'); roles_ok = False
            elif role == '거르기':
                if bid not in used_filter: roles_ok = False; note.append('거르기인데 엔진 거르기 단계가 안 씀')
            elif role == '매도':
                if bid not in used_sell: roles_ok = False; note.append('매도인데 매도신호 계산이 안 씀')
            elif role == '정보':
                note.append('점수에 안 들어감(갈래·매도신호 표시만)')
            elif role not in ('점수', '핵심', '타이밍'):
                roles_ok = False; note.append(f'모르는 역할 {role}')
            if b.get('국면') not in (None, '강세', '방어'):
                roles_ok = False; note.append(f"모르는 국면 {b.get('국면')}")
            for k, x in enumerate(b['공식']):
                name, expr = x[0], x[1]
                vars_ = list(compile(expr, '<f>', 'eval').co_names)
                exist = all((v in mcols) if sec == '시장' else (v in cols) for v in vars_)
                hc = max((hist_class(v, HIST) for v in vars_), key=ORDER.index) if vars_ else '없음'
                if sec == '시장':
                    fill, n_app = (1.0 if E._ev(expr, m) is not None else 0.0), 1
                else:
                    app = pd.Series(True, index=f.index)
                    if b.get('대상') == '개별주':
                        app &= f['구분'] == '개별주'
                    for v in vars_:
                        app &= scope_mask(v, f, SCOPE)
                    idx = list(np.where(app)[0]); n_app = len(idx)
                    fill = (sum(E._ev(expr, rows[i]) is not None for i in idx) / n_app) if n_app else np.nan
                grow = any(v in A.get('쌓는중', []) for v in vars_)
                st = ('칸 없음' if not exist else '해당 종목 없음' if pd.isna(fill)
                      else ('쌓는 중' if grow else '삭제 대상') if fill < del_line else '보완 필요' if fill < ok_line else '완성')
                fl.append(st)
                FR.append(dict(블록=bid, 질문=b['질문'], 공식=name, 칸=', '.join(vars_), 해당종목=n_app,
                               채움률=None if pd.isna(fill) else round(fill, 2), 과거계산=hc, 칸존재=exist, 상태=st))
            n = len(fl)
            done = roles_ok and all(s in ('완성', '보완 필요', '쌓는 중') for s in fl) and fl.count('완성') * 2 >= n - fl.count('쌓는 중')
            hist_ok = sum(1 for r in FR if r['블록'] == bid and r['과거계산'] in ('가격', 'BLOCK20', '공시'))
            BR.append(dict(블록=bid, 질문=b['질문'], 역할=role, 국면=b.get('국면', ''), 공식수=n,
                           완성=fl.count('완성'), 보완필요=fl.count('보완 필요'), 삭제대상=fl.count('삭제 대상'),
                           쌓는중=fl.count('쌓는 중'), 칸없음=fl.count('칸 없음'), 과거계산가능=f'{hist_ok}/{n}', 역할일치=roles_ok,
                           메모=' / '.join(note), 판정='완성' if done else '미완성'))
    return pd.DataFrame(BR), pd.DataFrame(FR)


if __name__ == '__main__':
    d = sys.argv[1]
    os.environ.setdefault('QC_NO_LEDGER', '1')
    BR, FR = audit(d)
    BR.to_csv(f'{d}/../out_블록완성도.csv', index=False, encoding='utf-8-sig')
    FR.to_csv(f'{d}/../out_공식완성도.csv', index=False, encoding='utf-8-sig')
    print(BR.to_string(index=False))
    print(FR[FR['상태'] != '완성'].to_string(index=False))
