import sys, html, pandas as pd, numpy as np, yaml
sys.path.insert(0,'qblocks'); import features as F
f=F.stocks('in').set_index('종목'); S=pd.read_csv('out_판정표.csv').set_index('종목')
P=pd.read_csv('in/가격2년.csv',index_col=0,parse_dates=True)
B=yaml.safe_load(open('qblocks/blocks.yaml',encoding='utf-8'))['종목']
PICK=[('삼성전자','반도체'),('삼성중공업','조선'),('현대모비스','자동차 부품'),('SK텔레콤','통신'),('TIGER 증권','증권 ETF'),
      ('KODEX 미국S&P500','미국 지수'),('TIGER 미국필라델피아반도체나스닥','미국 반도체')]
DROP=[('하나금융지주','관찰 등급(블록 4/8). ETF 보유 종목 반영 후 추천 등급이 된 TIGER 증권(블록 7/8, 60일 변동성 38%)으로 교체'),
      ('SOL 조선TOP3플러스·PLUS 글로벌HBM반도체','추천 등급이나 조선은 삼성중공업과 중복, HBM은 60일 변동성 63%로 안정성 기준 초과'),('SK하이닉스','시스템 추천(블록 9/11)이지만 60일 변동성 76%, 외국인 5일 −1조 576억·20일 −7조 3,920억 동시 순매도 → 안정성 기준 탈락'),
      ('삼성증권','시스템 추천(블록 7/10)이지만 외국인 5일 −215억·20일 −496억 동시 순매도 → 안정성 기준 탈락'),
      ('NVIDIA·GE Vernova·Caterpillar','시스템 추천 미국 개별주 → 의장 지시(미국은 국내 상장 ETF로)에 따라 필라델피아반도체 ETF로 대신')]
def n(v,d=1,s=''):
    return '–' if v is None or pd.isna(v) else f'{v:,.{d}f}{s}'
def spark(tk):
    if tk not in P: return ''
    s=P[tk].dropna().iloc[-260:]; m=s.rolling(50).mean()
    W,H=300,70; lo,hi=s.min(),s.max()
    pt=lambda i,v: f'{i*W/(len(s)-1):.1f},{H-(v-lo)/(hi-lo)*(H-6)-3:.1f}'
    a=' '.join(pt(i,v) for i,v in enumerate(s)); b=' '.join(pt(i,v) for i,v in enumerate(m) if not pd.isna(v))
    up=s.iloc[-1]>=s.iloc[0]
    return (f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}"><polyline points="{b}" fill="none" stroke="#c9a227" stroke-width="1.2" stroke-dasharray="3,2"/>'
            f'<polyline points="{a}" fill="none" stroke="#2f6fb0" stroke-width="1.6"/><circle cx="{W}" cy="{pt(len(s)-1,s.iloc[-1]).split(",")[1]}" r="3" fill="#d1495b"/></svg>'
            '<div class="lg"><i style="background:#2f6fb0"></i>1년 주가 <i style="background:#c9a227"></i>50일선</div>')
def dots(nm):
    yes=str(S.at[nm,'블록 예']); no=str(S.at[nm,'블록 아니오']); out=[]
    for k,b in B.items():
        if b['역할'] not in ('점수','타이밍','핵심'): continue
        q=b['질문'].split('?')[0].replace("'수급: ",'').strip()
        st='y' if f'{k} ' in yes else ('n' if f'{k} ' in no else 'x')
        out.append(f'<span class="d {st}">{html.escape(q)}</span>')
    return ''.join(out)
def bar(lbl,v,mx,good_low=True,unit='%'):
    if v is None or pd.isna(v): return ''
    w=min(abs(v)/mx,1)*100; c='#3a9d6a' if (abs(v)<mx*0.5)==good_low else '#e08a2c'
    return f'<div class="bar"><span class="bl">{lbl}</span><span class="bt"><span style="width:{w:.0f}%;background:{c}"></span></span><span class="bv">{n(v,1,unit)}</span></div>'
def reasons(nm):
    r=f.loc[nm]; out=[]
    if not pd.isna(r['op_yoy']):
        out.append(('이익', f"{str(r['last_q'])[:7]} 분기({r['q_src']}) 영업이익 전년 대비 {n(r['op_yoy'],0,'%')}"+(f", 영업이익률 {n(r['opm'],1,'%')}(전년보다 {n(r['opm_yoy'],1,'%p')} 개선)" if not pd.isna(r['opm']) else '')))
    if not pd.isna(r['est30']): out.append(('이익 추정치', f"애널리스트 EPS 추정치 30일 {n(r['est30'],1,'%')}, 90일 {n(r['est90'],1,'%')}"))
    if not pd.isna(r['per_ttm']): out.append(('밸류', f"PER {n(r['per_ttm'],1,'배')} → 선행 PER {n(r['fper'],1,'배')}, PBR {n(r['pbr'],2,'배')}, ROE {n(r['roe'],1,'%')}"))
    if 'per_pct3' in r and not pd.isna(r['per_pct3']): out.append(('3년 PER', f"현재 {n(r['per_now'],1,'배')}, 3년 중앙값 {n(r['per_med3'],1,'배')}, 3년 중 하위 {n(r['per_pct3']*100,0,'%')} 위치"))
    if not pd.isna(r['f5']): out.append(('외국인 수급', f"5일 {n(r['f5'],0,'억')}, 20일 {n(r['f20'],0,'억')}, 연속 {n(r['fstreak'],0,'일')}"))
    if not pd.isna(r['etf_flow5']): out.append(('ETF 자금', f"최근 5일 {n(r['etf_flow5'],0,'억')} 유입"))
    if nm in S.index and str(S.at[nm,'구성_이익통과'])!='nan': out.append(('구성 종목', f"{S.at[nm,'구성_이익통과']}"))
    out.append(('하락 위치', f"52주 고점 대비 {n(r['dd52'],1,'%')}, 50일 이격 {n(r['gap50'],1)}, 일봉 RSI {n(r['rsi_d'],0)}"))
    out.append(('Sigma Check', f"10년 자기역사 하락 p-value {n(r['p10'],3,'')} ({'p<0.05, 3-sigma급 드문 하락' if r['p10']<0.05 else '평소 범위'})"))
    out.append(('상대 강도', f"최근 20일 시장 대비 {n(r['rs20'],1,'%p')}, 동종 대비 {n(r['peer20'],1,'%p')}"))
    if not pd.isna(r['fscore']): out.append(('재무', f"F-Score {n(r['fscore'],0)}/9"+(f", Altman Z {n(r['z'],2)}" if not pd.isna(r['z']) else '')+(f", 순부채/EBITDA {n(r['debt_ebitda'],2,'배')}" if not pd.isna(r['debt_ebitda']) else '')+(f", FCF 수익률 {n(r['fcf_yield'],1,'%')}" if not pd.isna(r['fcf_yield']) else '')))
    v=f.loc[nm,'변수'] if '변수' in f.columns else None
    if isinstance(v,str) and v.strip(): out.append(('변수', v.split(' / ')[0]))
    return out
cards=[]
for i,(nm,sec) in enumerate(PICK,1):
    r=f.loc[nm]; s=S.loc[nm]
    tag=s['추천'] if s['추천'] in ('추천','관찰') else '미국 ETF(국내 상장)'
    blk=f"블록 {int(s['블록예'])}/{int(s['블록수'])} 충족"
    rs=''.join(f'<div class="row"><span class="k">{k}</span><span class="v">{html.escape(v)}</span></div>' for k,v in reasons(nm))
    cards.append(f'''<div class="card"><div class="hd"><span class="no">{i}</span><span class="nm">{html.escape(nm)}</span><span class="sec">{sec}</span>
<span class="tag t{'a' if tag=='추천' else 'b'}">{tag} · {blk}</span></div>
<div class="grid"><div class="lft">{spark(r['ticker'])}
{bar('60일 변동성',r['vol60'],80)}{bar('하루 꼬리손실',r['es5'],15)}{bar('고점 대비',r['dd52'],60,False)}
<div class="sm">종가 {n(r['close'],0)} · 베타 {n(r['beta'],2)} · 분할 {s['분할']} · 비중상한 {n(s['비중상한(%)'],1,'%')}</div></div>
<div class="rgt">{rs}</div></div><div class="dots">{dots(nm)}</div></div>''')
drop=''.join(f'<div class="row"><span class="k">{html.escape(a)}</span><span class="v">{html.escape(b)}</span></div>' for a,b in DROP)
css='''@page{size:A4;margin:11mm 10mm}body{font-family:"Noto Sans CJK KR","Noto Sans KR",sans-serif;color:#1d2433;font-size:8.6pt;line-height:1.4;margin:0}
h1{font-size:17pt;margin:0;color:#0b3d6e}.sub{color:#6b7585;margin:2px 0 8px}
.rule{background:#f1f5fa;border-radius:6px;padding:7px 10px;margin-bottom:8px}.rule b{color:#0b3d6e}
.card{border:1px solid #d6dfea;border-radius:8px;padding:8px 10px;margin:7px 0;break-inside:avoid}
.hd{display:flex;align-items:center;gap:8px;margin-bottom:5px}.no{background:#0b3d6e;color:#fff;border-radius:50%;width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center;font-weight:700}
.nm{font-size:12.5pt;font-weight:700;color:#0b3d6e}.sec{color:#6b7585}.tag{margin-left:auto;border-radius:10px;padding:2px 9px;font-weight:600;font-size:8pt}
.ta{background:#e3f4ea;color:#1f7a4a}.tb{background:#fff1dd;color:#a05a00}
.grid{display:flex;gap:12px}.lft{flex:0 0 300px}.rgt{flex:1}
.lg{font-size:7pt;color:#6b7585;margin:-2px 0 3px}.lg i{display:inline-block;width:10px;height:3px;margin:0 3px 2px 6px}
.bar{display:flex;align-items:center;gap:5px;margin:2px 0}.bl{flex:0 0 74px;white-space:nowrap;color:#4a5568}.bt{flex:1;height:7px;background:#edf1f6;border-radius:4px;overflow:hidden}.bt span{display:block;height:100%}.bv{flex:0 0 46px;text-align:right}
.sm{color:#4a5568;margin-top:3px;font-size:7.8pt}
.row{display:flex;gap:6px;margin:1.5px 0}.k{flex:0 0 72px;color:#2f6fb0;font-weight:600;white-space:nowrap}.v{flex:1}
.dots{margin-top:5px;display:flex;flex-wrap:wrap;gap:3px}.d{font-size:7pt;border-radius:8px;padding:1px 6px}.d.y{background:#e3f4ea;color:#1f7a4a}.d.n{background:#fde8ea;color:#b4232f}.d.x{background:#f0f0f0;color:#999}
h2{font-size:11pt;color:#0b3d6e;margin:10px 0 4px}'''
mk=pd.read_csv('out_시장블록.csv'); burden=mk[(mk['방향']=='부담')&(mk['결과']=='통과')]['공식'].tolist(); opp=mk[(mk['방향']=='기회')&(mk['결과']=='통과')]['공식'].tolist()
doc=f'''<!doctype html><html><head><meta charset="utf-8"><title>오늘의 추천 종목</title><style>{css}</style></head><body>
<h1>오늘의 추천 종목</h1><div class="sub">2026-11-16 14:30 · 퀀트센터 · 유니버스 200종목 전체 판정 · 국내 5종목, 국내 상장 미국 ETF 2종목</div>
<div class="rule"><b>선정 기준</b><br>
1) 거르기: 최근 분기 이익 증가(한 분기 꺾임은 앞 분기 증가+추정치 상향이면 통과), 사건 역풍 없음, 52주 고점에서 −10% 넘게 내려옴, 연매출 10조 원 이상<br>
2) 판정: 점수·타이밍·핵심 블록 14개마다 공식 과반 통과면 예. 예 2/3 이상 추천, 1/2 이상 관찰<br>
3) 안정성: 60일 변동성 60% 이하, 외국인 5일·20일 동시 순매도 아님<br>
4) ETF는 실제 보유 상위 10종목의 이익·전망·재무·밸류를 보유 비중으로 가중 평균하여 판정<br>5) 미국은 국내 상장 ETF로 편입: S&P500 지수와 추천 등급 필라델피아반도체(NVIDIA·브로드컴 포함)<br>
<b>시장 부담</b> {html.escape(', '.join(burden))} · <b>기회</b> {html.escape(', '.join(opp))}</div>
{''.join(cards)}
<h2>제외 종목 및 사유</h2>{drop}
<div class="sub" style="margin-top:8px">블록 표시: 초록 충족, 빨강 미충족, 회색 자료 없음. 분할 2차는 주봉 MACD 오실레이터 상승 구간. 백테스트 검증은 팀Q에서 진행 예정. 추천 후 10일 성과는 11/26 점검.</div>
</body></html>'''
open('/mnt/project-files/퀀트센터/추천7_20261116.html','w',encoding='utf-8').write(doc)
