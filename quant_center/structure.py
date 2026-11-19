"""blocks.yaml → 사람이 보는 구조표(블록 = 목적 + 공식). 설정이 바뀌면 다시 돌리면 됨."""
import yaml
import qc_config as QCC
B = QCC.load_blocks()
L = ['퀀트센터 블록 구조 (blocks.yaml에서 자동 생성)', '']
L.append('[시장 블록] 오늘 돈을 얼마나 넣을 때인가')
for k, b in B['시장'].items():
    L.append(f'{k} = {b["질문"]} : ' + ' / '.join(n for n, _, _ in b['공식']))
L += ['', '[종목 블록] 이 종목을 지금 살 때인가']
for k, b in B['종목'].items():
    L.append(f'{k} = {b["질문"]} ({b["역할"]}) : ' + ' / '.join(n + ('' if s == '확정' else '*') for n, _, s, _ in b['공식']))
last = int(list(B['종목'])[-1][1:])
L += [f'B{last+1:02d} = 분할 몇 차인가? (타이밍) : 1차 거르기 통과 / 2차 주봉 MACD 오실레이터 상승 / 3차 일봉 RSI ≤30 + 50일 이격 ≤90 + 월봉 5개월선 아래 + 주봉 오실레이터 상승',
      f'B{last+2:02d} = 얼마나 사나? (비중) : BLOCK20 반켈리 상한',
      f'B{last+3:02d} = 팔 때인가? (매도) : 이익 꺾임 / 사건 역풍 / 너무 많이 오름 / 외국인 5·20일 순매도',
      '', '공식은 모두 11/16 의장 승인. 검증은 나중.',
      '거르기 블록을 모두 통과해야 후보(연매출 10조 미만은 참고만). 점수 = 점수 블록별 통과 비율의 평균(블록마다 같은 무게, 자료 없는 공식이 절반 넘는 블록은 제외).']
open('구조.txt', 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('\n'.join(L))
