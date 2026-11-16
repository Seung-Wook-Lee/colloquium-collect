import sys, html, pandas as pd, numpy as np, yaml
sys.path.insert(0,'qblocks'); import features as F
f=F.stocks('in').set_index('종목'); S=pd.read_csv('out_판정표.csv').set_index('종목')
P=pd.read_csv('in/가격2년.csv',index_col=0,parse_dates=True)
B=yaml.safe_load(open('qblocks/blocks.yaml',encoding='utf-8'))['종목']
# 7종목은 엔진 결과로만 뽑는다(손으로 적는 목록 없음, 11/17 의장). 규칙은 blocks.yaml '추천'에서 읽는다.
RC=yaml.safe_load(open('qblocks/blocks.yaml',encoding='utf-8')).get('추천',{})
N_KR,N_US,VMAX=RC.get('국내수',5),RC.get('미국ETF수',2),RC.get('변동성상한',60)
AS=S.reset_index()
AS['미국ETF']=(AS['시장']=='한국')&(AS['구분']!='개별주')&AS['종목'].astype(str).str.contains('미국')
cand=AS[AS['추천']=='추천'].sort_values(['블록예비율','싼가','점수'],ascending=False)
PICK,DROP=[],[]
for _,r in cand.iterrows():
    nm=r['종목']; rf=f.loc[nm] if nm in f.index else None
    why=[]
    if r['시장']!='한국': why.append('미국 개별·해외 상장 → 국내 상장 ETF로만 편입(룰 2장)')
    if rf is not None and not pd.isna(rf.get('vol60')) and rf['vol60']>VMAX: why.append(f"60일 변동성 {rf['vol60']:.0f}% > {VMAX}%")
    if rf is not None and (rf.get('f5') or 0)<0 and (rf.get('f20') or 0)<0: why.append(f"외국인 5일 {rf['f5']:,.0f}억·20일 {rf['f20']:,.0f}억 동시 순매도")
    if why: DROP.append((nm,' / '.join(why))); continue
    grp='us' if r['미국ETF'] else 'kr'
    if sum(1 for _,g in PICK if g==grp) >= (N_US if grp=='us' else N_KR):
        DROP.append((nm,f"추천 등급이나 순위 밖(예 비율 {r['블록예비율']}, 싼가 {r['싼가']})")); continue
    PICK.append((nm,grp))
import orders as O
_m=pd.read_csv('out_시장블록.csv')
DEFK=str(AS.loc[AS['시장']=='한국','국면'].iloc[0]).startswith('방어') if (AS['시장']=='한국').any() else False
KEEP=[nm for nm,_ in PICK]
CB=cand[cand['시장'].eq('한국')&~cand['종목'].isin([a for a,_ in DROP if '순위 밖' not in _])].copy()
CB['vol60']=[f.loc[n,'vol60'] if n in f.index else np.nan for n in CB['종목']]
_P=F._px('in'); LR=O.layer_rs('in',_P)
BKT,LW=O.basket(CB,f,RC.get('바구니',{}) or yaml.safe_load(open('qblocks/blocks.yaml',encoding='utf-8'))['바구니'],DEFK,LR,O.basket_dd('in',_P))
BKT.to_csv(f'추천바구니_{pd.Timestamp.now(tz="Asia/Seoul").strftime("%Y%m%d")}.csv',index=False,encoding='utf-8-sig')
PICK=[(nm,str(f.loc[nm,'sector']) if nm in f.index and 'sector' in f.columns else '') for nm,_ in PICK]
TODAY=pd.Timestamp.now(tz='Asia/Seoul').strftime('%Y%m%d')
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
<div class="sm">종가 {n(r['close'],0)} · 베타 {n(r['beta'],2)} · 국면 {s.get('국면','')} · 주문 승수 {s.get('주문승수','')} · 분할 1/3(5·10거래일 재확인) · 비중상한 {n(s['비중상한(%)'],1,'%')}</div></div>
<div class="rgt">{rs}</div></div><div class="dots">{dots(nm)}</div></div>''')
bk=''.join(f"<tr><td>{html.escape(str(r['종목']))}</td><td>{r['층']}</td><td>{r['목표비중']}%</td><td>{'' if pd.isna(r['회차1']) else str(r['회차1'])+'%'}</td><td>{'' if pd.isna(r.get('주문승수')) else r['주문승수']}</td><td>{html.escape(str(r.get('경보','') or ''))}</td></tr>" for _,r in BKT.iterrows())
bk=f"<h2>추천 바구니 (층별 비중, 국면 {'방어' if DEFK else '평상'}, 층 비중 {LW})</h2><table border=1 cellspacing=0 cellpadding=3><tr><th>종목</th><th>층</th><th>목표 비중</th><th>1회차(1/3)</th><th>주문 승수</th><th>경보</th></tr>{bk}</table><div class=sub>1회차 뒤 5·10거래일에 같은 조건을 다시 충족하면 1/3씩 추가. 직전 추천 바구니가 −5% 이하면 이번 비중 절반.</div>"
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
<h1>오늘의 추천 종목</h1><div class="sub">{TODAY} · 퀀트센터 · 국면 {html.escape(str(AS['국면'].iloc[0]) if '국면' in AS else '')} · 엔진 추천 등급에서 국내 {N_KR}·국내 상장 미국 ETF {N_US} (추천 등급이 모자라면 모자란 대로)</div>
<div class="rule"><b>선정 기준</b><br>
1) 거르기: 최근 분기 이익 증가, 사건 역풍·7일 안 대형 이벤트 없음, 연매출 10조 원 이상(평상 국면은 52주 고점 −10% 밖 추가)<br>
2) 판정: 점수·타이밍·핵심 블록 14개마다 공식 과반 통과면 예. 예 2/3 이상 추천, 1/2 이상 관찰<br>
3) 안정성: 60일 변동성 60% 이하, 외국인 5일·20일 동시 순매도 아님<br>
4) ETF는 실제 보유 상위 10종목의 이익·전망·재무·밸류를 보유 비중으로 가중 평균하여 판정<br>5) 미국은 국내 상장 ETF로 편입. 순서: 블록 예 비율 → 싼가 → 점수<br>
<b>시장 부담</b> {html.escape(', '.join(burden))} · <b>기회</b> {html.escape(', '.join(opp))}</div>
{''.join(cards)}
{bk}
<h2>제외 종목 및 사유</h2>{drop}
<div class="sub" style="margin-top:8px">블록 표시: 초록 충족, 빨강 미충족, 회색 자료 없음. 분할 2차는 주봉 MACD 오실레이터 상승 구간. 백테스트 검증은 팀Q에서 진행 예정. 추천 후 10일 성과는 11/26 점검.</div>
</body></html>'''
open(f'추천7_{TODAY}.html','w',encoding='utf-8').write(doc)
