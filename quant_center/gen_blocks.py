import yaml, html, sys
sys.path.insert(0, 'qblocks'); import qc_config as QCC
B=QCC.load_blocks()
e=html.escape
RC={'거르기':'#b4232f','점수':'#1f7a4a','핵심':'#0b3d6e','타이밍':'#a05a00','매도':'#6b2fb0','비중':'#4a5568','정보':'#4a5568'}
def tbl(sec):
    r=[]
    for k,b in B[sec].items():
        role=b.get('역할','시장'); c=RC.get(role,'#2f6fb0')
        fs=''.join(f'<li>{e(str(x[0]))}</li>' for x in b['공식'])
        r.append(f'<tr><td class="id">{k}</td><td class="q">{e(b["질문"])}<br><span class="role" style="background:{c}">{role}</span></td><td><ul>{fs}</ul></td></tr>')
    return '<table><tr><th>번호</th><th>질문</th><th>답을 내는 공식</th></tr>'+''.join(r)+'</table>'
nf=sum(len(b['공식']) for s in ('시장','종목') for b in B[s].values())
flow=''.join(f'<div class="st"><b>{a}</b><span>{b}</span></div><div class="ar">▶</div>' for a,b in [
 ('시장 B01~B08','부담·기회 개수 → 투입 여건'),('거르기 B09~B12','이익 증가 · 사건 역풍 없음 · 고점 −10% 밖 · 연매출 10조'),
 ('판정 B13~B24','14블록마다 공식 과반 = 예, 예 2/3 이상 추천 · 1/2 관찰'),('안정성','60일 변동성 ≤60% · 외국인 5·20일 동시 순매도 아님'),('B26~B28','분할 차수 · 비중 상한 · 팔 때')])[:-len('<div class="ar">▶</div>')]
css='''@page{size:A4;margin:11mm 10mm}body{font-family:"Noto Sans CJK KR",sans-serif;font-size:8.4pt;color:#1d2433;line-height:1.4}
h1{font-size:17pt;color:#0b3d6e;margin:0}.sub{color:#6b7585;margin:2px 0 8px}h2{font-size:11.5pt;color:#fff;background:#0b3d6e;padding:3px 8px;border-radius:4px;margin:10px 0 5px}
.flow{display:flex;align-items:stretch;gap:3px;margin:6px 0}.st{flex:1;background:#eef3f9;border-radius:6px;padding:6px}.st b{display:block;color:#0b3d6e;font-size:9pt}.st span{font-size:7.6pt}.ar{align-self:center;color:#2f6fb0}
.cmp{display:flex;gap:10px}.cmp div{flex:1;border:1px solid #d6dfea;border-radius:6px;padding:6px 9px}.cmp b{color:#0b3d6e}
table{width:100%;border-collapse:collapse}th{background:#eef3f9;text-align:left;padding:3px 5px;white-space:nowrap}td{border-bottom:1px solid #e3e8ef;padding:3px 5px;vertical-align:top}
.id{font-weight:700;color:#0b3d6e;white-space:nowrap}.q{width:30%;font-weight:600}.role{display:inline-block;color:#fff;border-radius:8px;padding:0 6px;font-size:7pt;margin-top:2px}
ul{margin:0;padding-left:13px}tr{break-inside:avoid}'''
doc=f'''<!doctype html><html><head><meta charset="utf-8"><title>퀀트센터 블록 구성</title><style>{css}</style></head><body>
<h1>퀀트센터 블록 재구성</h1><div class="sub">2026-11-16 · BLOCK20 → 질문 블록 · 블록 {len(B["시장"])+len(B["종목"])}개 + 엔진 계산 3개, 공식 {nf}개 · 파일 blocks.yaml 한 줄로 더하고 뺌</div>
<h2>무엇이 바뀌었나</h2><div class="cmp">
<div><b>전 (BLOCK20)</b><br>· 블록 B01~B20이 기법별(HMM, GARCH, 모멘텀 등)<br>· 기준이 위원별 텍스트로 흩어져 적용 안 됨<br>· 평균 점수 하나로 줄 세움</div>
<div><b>지금 (질문 블록)</b><br>· 블록 하나 = 질문 하나, 그 답을 내는 공식은 전부 그 블록 안에<br>· 의장 질문은 반대 이유 공식으로 등록 → 전 종목 재실행<br>· 블록마다 예/아니오, 예 비율로 추천<br>· 싼가가 대전제, 고점 부근·사건 역풍은 거르기<br>· 빠진 것: 추세추종·패턴·자료 없는 블록·포트 겹침</div></div>
<h2>흐름</h2><div class="flow">{flow}</div>
<h2>시장 블록 — 오늘 돈을 넣을 때인가</h2>{tbl("시장")}
<h2>종목 블록 — 이 종목을 지금 살 때인가</h2>{tbl("종목")}
<div class="sub" style="margin-top:6px">엔진 계산: B26 분할 차수(1차 거르기 통과, 2차 주봉 오실레이터 상승, 3차 일봉 RSI≤30·50일 이격≤90·5일선 아래·주봉 오실레이터 상승) · B27 비중 상한(반켈리) · B28 팔 때(이익 꺾임·사건 역풍·고점 부근·과열·외국인 5·20일 순매도). 백테스트 검증은 팀Q(전).</div>
</body></html>'''
open('/mnt/project-files/퀀트센터/블록구성_20261116.html','w',encoding='utf-8').write(doc)
