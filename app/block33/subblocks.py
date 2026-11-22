"""블록 2~5 하위 블록 켜기·끄기 (11/20 의장: "하위 블록은 1-1 이런 식으로 만들어서 언제든지 넣고 뺄 수 있도록").
번호표와 켜기 목록은 비공개 Team_Q colloquium_private/subblocks.yaml. 블록 1은 data.yaml '켜기'.
load_blocks()가 apply()를 불러, 꺼진 하위 블록을 엔진·회의·포트폴리오가 쓰는 설정에서 뺀다.
  - 시장 블록(B01~B10 = 2-1~2-10): blocks.yaml '시장'에서 뺌
  - 종목 블록(B11~B34): 판정표에 '꺼짐'으로 남고 점수·원칙 목록에서 빠짐
  - 단계(거르기·합산·메타): '순서'에서 뺌(앞 단계가 꼭 필요하면 남기고 이유를 적음)
  - 설정 칸(결론·원칙.층별·의장 장기 후보 등): 그 칸을 뺌
"""
import copy
import os

import yaml

KIND = {'블록2': '2 phase', '블록3': '3 Analysis', '블록4': '4 portfolio', '블록5': '5 colloquium'}


def path(pdir):
    return os.path.join(pdir, 'subblocks.yaml')


def load(pdir):
    p = path(pdir)
    return yaml.safe_load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


def off(T):
    """꺼진 번호 집합"""
    out = set()
    for blk in T.values():
        on = set(map(str, blk.get('켜기', [])))
        out |= {k for k in blk.get('번호', {}) if str(k) not in on}
    return out


def is_on(B, num):
    return num not in set(B.get('_꺼짐', []))


def apply(B, T):
    """blocks.yaml(B)에 켜기 목록(T)을 반영한 사본. B['_꺼짐'] = 꺼진 번호 목록, B['_하위블록'] = 번호표."""
    if not T:
        return B
    B = copy.deepcopy(B)
    X = off(T)
    B['_꺼짐'] = sorted(X, key=lambda s: tuple(int(x) for x in s.split('-')))
    B['_하위블록'] = T
    note = B.setdefault('_꺼짐_메모', {})
    allnum = {k: v for blk in T.values() for k, v in blk.get('번호', {}).items()}
    offb = {allnum[k]['블록'] for k in X if allnum[k].get('블록')}
    for b in [b for b in offb if b in B.get('시장', {})]:
        B['시장'].pop(b)
    B['_꺼짐_종목'] = sorted(b for b in offb if b in B.get('종목', {}))
    if 'B00' in offb and isinstance(B.get('국면'), dict):
        B['국면'] = {**B['국면'], '_끔': True}
    P = B.get('원칙')
    if P:
        for k in ('떨어짐', '우량_통과', '우량_예', '순위', '업종관문', '업종참고'):
            if isinstance(P.get(k), list):
                P[k] = [b for b in P[k] if b not in offb]
        LY = P.get('층별') or {}
        if LY.get('묶음'):
            LY['묶음'] = {g: [b for b in ks if b not in offb] for g, ks in LY['묶음'].items()}
        if LY.get('추세확인'):
            LY['추세확인'] = [b for b in LY['추세확인'] if b not in offb]
            if not LY['추세확인']:
                LY.pop('추세확인_층', None)
    for k in X:
        v = allnum[k]
        st, cf = v.get('단계'), v.get('설정')
        if st and st in B.get('순서', []):
            need = st == '합산' and (B.get('추천') or {}).get('기준') == '종합점수'
            if st == '거르기':   # 판정 단계가 '후보' 칸을 쓰므로 단계는 두고 모두 통과
                B['_거르기_끔'] = True
            elif need:
                note[k] = '추천 기준이 종합점수라 합산 단계는 남김'
            else:
                B['순서'] = [x for x in B['순서'] if x != st]
        if cf == '원칙':
            B.pop('원칙', None)
        elif cf == '원칙.층별' and B.get('원칙'):
            B['원칙'].pop('층별', None)
        elif cf == '결론':
            B.pop('결론', None)
        elif cf == '결론.시장관문' and B.get('결론'):
            B['결론'] = {**B['결론'], '시장관문': False}
        elif cf == '의장 장기 후보':
            B.pop('의장 장기 후보', None)
    return B


def table(B):
    """뚜지 발표 '하위 블록' 표: [블록, 번호, 이름, 상태]"""
    T = B.get('_하위블록') or {}
    X = set(B.get('_꺼짐', []))
    note = B.get('_꺼짐_메모', {})
    rows = []
    for key, blk in T.items():
        for num, v in blk.get('번호', {}).items():
            tag = f" ({v['블록']})" if v.get('블록') else ''
            rows.append([KIND.get(key, key), num, f"{v['이름']}{tag}", ('적용 안 함' + (f" — {note[num]}" if num in note else '')) if num in X else '적용'])
    return rows
