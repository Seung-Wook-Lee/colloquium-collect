"""비공개 설정 찾기(11/19 의장: 저장소는 공개, 블록 문턱·가중·종목 목록·최종 판단은 비공개).
blocks.yaml·종목 목록(seed)는 비공개 저장소(team_q colloquium_private/)에 있고,
실행할 때 아래 순서로 찾는다. 공개 저장소에는 질문 이름만 적힌 blocks.sample.yaml만 있다.
  1) 환경 변수 QC_PRIVATE(폴더)  2) 이 저장소 옆의 ../team_q/colloquium_private  3) team_q_private/colloquium_private(워크플로)"""
import os

import yaml

HERE = os.path.dirname(os.path.realpath(__file__))
_CANDS = [os.environ.get('QC_PRIVATE', ''),
          os.path.join(HERE, '..', '..', '..', 'team_q', 'colloquium_private'),
          os.path.join(HERE, '..', '..', 'team_q', 'colloquium_private'),
          os.path.join(HERE, '..', '..', 'team_q_private', 'colloquium_private'),
          os.path.join(HERE, '..', 'team_q_private', 'colloquium_private'),
]


def private_dir():
    for d in _CANDS:
        if d and os.path.exists(os.path.join(d, 'blocks.yaml')):
            return os.path.abspath(d)
    raise FileNotFoundError('비공개 설정(blocks.yaml)이 없습니다. QC_PRIVATE에 colloquium_private 폴더를 지정하세요. '
                            '공개 저장소의 blocks.sample.yaml은 질문 이름만 있는 견본이라 엔진이 돌지 않습니다.')


def blocks_path():
    return os.path.join(private_dir(), 'blocks.yaml')


def load_blocks(path=None, switches=True):
    """blocks.yaml. switches=True면 하위 블록 켜기 목록(subblocks.yaml)을 반영해 꺼진 하위 블록을 뺀 사본(11/20 의장)."""
    B = yaml.safe_load(open(path or blocks_path(), encoding='utf-8'))
    if switches and path is None:
        import subblocks as SBK
        B = SBK.apply(B, SBK.load(private_dir()))
    return B
