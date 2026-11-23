"""DBMF 보고서 PDF (11/23 의장: "DBMF가 무엇이고 어떻게 구성되어 있고, 우리 블록에 넣었을 때 어떤 효과, 바닥 찾기 용인지... PDF로").
숫자는 dbmf_test.py가 만든 /mnt/project-files/유니버스/start/dbmf/ 파일 그대로."""
import base64, io
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import pandas as pd
import yfinance as yf

IN = Path('/mnt/project-files/유니버스/start/dbmf/')
fm.fontManager.addfont('/root/.fonts/NanumGothic.ttf'); plt.rcParams['font.family'] = 'NanumGothic'; plt.rcParams['axes.unicode_minus'] = False
D = pd.read_csv(IN / 'dbmf_일별.csv', index_col=0, parse_dates=True, encoding='utf-8-sig')
N = pd.read_csv(IN / 'dbmf_nport.csv', parse_dates=['기준일'], encoding='utf-8-sig')
T = pd.read_csv(IN / 'dbmf_IC.csv', encoding='utf-8-sig')
E = pd.read_csv(IN / 'dbmf_사건.csv', index_col=0, parse_dates=True, encoding='utf-8-sig')
spx = yf.download('^GSPC', start='2019-05-01', auto_adjust=True, progress=False)['Close'].squeeze()


def img(fig):
    b = io.BytesIO(); fig.savefig(b, format='png', dpi=160, bbox_inches='tight'); plt.close(fig)
    return f'<img src="data:image/png;base64,{base64.b64encode(b.getvalue()).decode()}">'


thr = D['DBMF 주식노출'].expanding(120).quantile(0.10)
fig, ax = plt.subplots(3, 1, figsize=(10, 8.2), sharex=True, gridspec_kw={'height_ratios': [1.2, 1, 1]})
ax[0].plot(spx.index, spx, color='#333', lw=1); ax[0].set_title('S&P500', fontsize=10, loc='left')
for d in E.index:
    for a in ax: a.axvline(d, color='#c8372d', lw=0.8, alpha=0.5)
ax[1].plot(D.index, D['DBMF 주식노출'], color='#1f5fa8', lw=1, label='DBMF 주식 노출(가격으로 추정, 매일)')
ax[1].plot(thr.index, thr, color='#c8372d', lw=0.8, ls='--', label='하위 10% 문턱')
ax[1].scatter(N['기준일'], N['N-PORT 주식노출'], color='#e08a00', s=18, zorder=3, label='SEC 보고서 실제 보유(분기)')
ax[1].axhline(0, color='#999', lw=0.6); ax[1].legend(fontsize=8, loc='upper left'); ax[1].set_title('DBMF 주식 노출(순자산 대비 배)', fontsize=10, loc='left')
ax[2].plot(D.index, D['CTA σ'], color='#2e7d32', lw=1); ax[2].axhline(-4, color='#c8372d', lw=0.7, ls='--'); ax[2].axhline(0, color='#999', lw=0.6)
ax[2].set_title('우리 B06 CTA 포지션(표준편차 단위)', fontsize=10, loc='left')
fig.text(0.01, 0.0, '빨간 세로선 = DBMF 주식 노출이 하위 10%에 처음 들어간 날', fontsize=8, color='#c8372d')
G1 = img(fig)

def tbl(df):
    return '<table><tr>' + ''.join(f'<th>{c}</th>' for c in df.columns) + '</tr>' + ''.join('<tr>' + ''.join(f'<td>{v}</td>' for v in r) + '</tr>' for r in df.values) + '</table>'

pos = pd.DataFrame([['S&P500 선물', '매수', '19.2%'], ['MSCI 선진국(EAFE) 선물', '매수', '19.3%'], ['MSCI 신흥국 선물', '매수', '8.1%'], ['WTI 원유 선물', '매수', '6.5%'],
                    ['미국 2년 국채 선물', '매도', '−98.9%'], ['미국 10년 국채 선물', '매도', '−41.4%'], ['미국 초장기 국채 선물', '매도', '−9.1%'],
                    ['엔화 선물', '매도', '−61.4%'], ['유로 선물', '매도', '−12.9%'], ['금 선물', '매도', '−6.5%'], ['미국 단기 국채·환매조건부(현금 자리)', '보유', '약 81%']],
                   columns=['선물', '방향', '순자산 대비 명목'])
f = lambda v: '' if pd.isna(v) else f'{v:+.2f}'
pick = T[T['조건'].isin(['모든 날', '나스닥100 고점 −10% 아래', 'S&P 고점 −10% 아래'])]
ic = pd.DataFrame({'조건': pick['조건'], '기간': pick['기간'], 'DBMF 단독(낮을수록 기회)': pick['DBMF 단독(낮을수록 기회, z)'].map(f),
                   'B06 기존': pick['B06 기존(공식 3개 합)'].map(f), 'B06 + DBMF(기회로)': pick['B06 + DBMF 하위10%'].map(f),
                   'B06 − DBMF(위험으로)': pick['B06 − DBMF 하위10%(추세 따라가기)'].map(f)}).replace('', '사건 없음')
ev = pd.DataFrame({'날짜': E.index.strftime('%Y-%m-%d'), 'DBMF 주식 노출': E['DBMF 주식노출'].round(2), 'S&P 고점 대비(%)': (E['낙폭'] * 100).round(1), '63일 뒤 S&P(%)': (E['S&P 63일 뒤'] * 100).round(1)})
today_x, today_t = D['DBMF 주식노출'].iloc[-1], thr.iloc[-1]
html = f"""<html><head><meta charset="utf-8"><style>
@page{{size:A4;margin:14mm 13mm}} body{{font-family:'NanumGothic';font-size:10.5px;color:#222;line-height:1.55}}
h1{{font-size:19px;color:#1d6b3a;margin:0 0 4px}} h2{{font-size:13.5px;color:#1d6b3a;border-bottom:2px solid #1d6b3a;padding-bottom:2px;margin:16px 0 6px}}
table{{border-collapse:collapse;width:100%;margin:4px 0 8px}} th{{background:#1d6b3a;color:#fff;font-weight:normal;padding:3px 5px;font-size:9.5px}} td{{border-bottom:1px solid #ddd;padding:3px 5px;font-size:9.5px;text-align:center}}
img{{width:100%}} .box{{background:#f2f7f3;border-left:4px solid #1d6b3a;padding:6px 10px;margin:6px 0}} .sub{{color:#777;font-size:9px}} ol,ul{{margin:2px 0 4px 18px;padding:0}}
.pb{{page-break-before:always}}</style></head><body>
<h1>DBMF 보고서 — 무엇이고, 우리 블록에 넣으면 무엇이 달라지나</h1>
<div class="sub">스튜디오 톰앤수 · 2026-11-23 · 계산 코드 app/market/dbmf_test.py · 자료 SEC N-PORT(분기 보유), 야후 가격(2019-05~2026-11-20)</div>
<div class="box"><b>한 줄 요약</b><br>
1. DBMF는 바닥을 찾는 지표가 아니라, <b>CTA(추세 추종 펀드)가 주식을 얼마나 들고 있는지 보여 주는 추세 지표</b>입니다.<br>
2. 하락장에서 DBMF 주식 노출이 크게 줄면, 63일 뒤 주가가 <b>더 나빴습니다</b>. 그래서 '기회'가 아니라 <b>'아직 바닥 아님(위험)' 신호</b>로 쓸 때 B06 정확도가 올라갑니다.<br>
3. 다만 2023-03 이후로는 이 신호가 한 번도 나오지 않았습니다. 그래서 후반 기간으로는 검증할 수 없습니다.</div>

<h2>1. DBMF는 무엇인가</h2>
<ol><li>정식 이름은 iMGP DBi Managed Futures Strategy ETF입니다. 2019년 5월에 상장했고, 순자산은 약 38.9억 달러입니다(2026-06-30).</li>
<li>대형 CTA 20곳 안팎의 <b>최근 60일 성과</b>를 보고, 그 성과를 가장 잘 따라가는 선물 묶음(10~15개)을 계산해 똑같이 들고 갑니다. 운용역이 판단으로 바꾸지 않습니다.</li>
<li>CTA 업계 지수(SG CTA)와의 상관은 0.8~0.9입니다(운용사·ETF 매체 공개 값).</li>
<li>그래서 DBMF의 주식 선물 보유 = <b>CTA 업계가 지금 주식을 얼마나 사 두었는지의 추정치</b>입니다.</li></ol>

<h2>2. 무엇을 들고 있나 (SEC 보고서, 2026-06-30)</h2>
{tbl(pos)}
<div class="sub">주식 선물을 합치면 순자산의 약 47%를 매수했습니다. 채권·엔화는 매도했습니다. 돈의 대부분은 단기 국채에 두고 선물 증거금만 씁니다.</div>

<h2>3. 우리는 DBMF 주식 노출을 어떻게 매일 구하나</h2>
<ol><li>운용사의 매일 보유 파일은 이 작업 환경에서 받을 수 없습니다. 그래서 두 가지로 구합니다.</li>
<li><b>분기:</b> SEC 보고서(N-PORT)의 실제 보유를 씁니다. 20분기를 받았습니다.</li>
<li><b>매일:</b> DBMF 하루 수익률을 S&P·선진국·신흥국 주식, 10년 국채, 달러, 금, 원유 ETF 수익률에 60일 회귀해서, 주식 쪽 계수 합을 '주식 노출'로 봅니다.</li>
<li>매일 추정값과 SEC 실제 값의 상관은 <b>0.68</b>입니다(20분기).</li>
<li>우리 B06 CTA σ와의 상관은 수준이 0.56, 20일 변화가 0.10입니다. DBMF가 60일 성과를 보고 움직이므로 우리 CTA σ보다 <b>늦습니다</b>.</li></ol>
{G1}

<h2 class="pb">4. 바닥 찾기에 쓸 수 있나 — 63일 뒤 수익과의 순위상관(IC)</h2>
<div class="sub">전반 = 2019-05~2023-03, 후반 = 2023-03~2026-11. '사건 없음' = 그 기간에 DBMF 하위 10% 신호가 한 번도 나오지 않음. IC는 +일수록 그 신호가 높을 때 63일 뒤 수익이 좋았다는 뜻입니다.</div>
{tbl(ic)}
<ol><li><b>'기회'로 쓰면 틀립니다.</b> 나스닥100이 고점 대비 −10% 아래인 날 DBMF 단독 IC는 전반 −0.46입니다. 노출이 낮을수록 그 뒤가 더 나빴습니다.</li>
<li><b>'위험'으로 쓰면 B06이 나아집니다.</b> 노출이 하위 10%인 날 B06 점수에서 1을 빼면, 나스닥100 −10% 아래 전체 IC가 −0.26에서 +0.14로, 전반은 −0.31에서 0.00으로 오릅니다. S&P −10% 아래 전체도 −0.27에서 0.00으로 오릅니다.</li>
<li><b>후반은 검증할 수 없습니다.</b> 2023-03 뒤로는 신호가 0번이었습니다. 그래서 후반 IC는 B06 기존과 같습니다. 블록 규칙(전반·후반 모두 상승)은 채우지 못합니다.</li></ol>

<h2>5. 신호가 나온 날 (주식 노출 하위 10%에 처음 들어간 날)</h2>
{tbl(ev)}
<ol><li>2022년의 1월·4월·7월에는 신호가 나온 뒤 63일 동안 더 빠졌습니다(−5.8%, −11.3%, −7.6%). 하락이 이어지는 동안 CTA가 주식을 계속 줄였습니다.</li>
<li>2020-03-26, 2022-10-20처럼 신호가 바닥 근처에서 나온 때도 있습니다. 이 두 날은 고점 대비 −22~−24%였습니다.</li>
<li>S&P 고점 −10% 아래에서 나온 5번의 63일 뒤 평균은 +6.1%(오른 비율 80%)입니다. 같은 낙폭의 아무 날은 +5.4%(69%)였습니다. 표본이 5번이라 차이를 믿기 어렵습니다.</li></ol>

<h2>6. 오늘 값과 선택지</h2>
<ol><li>오늘(11/20 종가) DBMF 주식 노출은 <b>{today_x:.2f}</b>이고, 하위 10% 문턱은 {today_t:.2f}입니다. DBMF 공식은 계산 중이며, 오늘은 조건을 채우지 못해 신호가 나오지 않았습니다.</li>
<li>우리 B06 CTA σ는 {D['CTA σ'].dropna().iloc[-1]:.2f}입니다.</li></ol>
<table><tr><th>선택</th><th>하는 일</th><th>근거</th></tr>
<tr><td>A. B06 위험 공식으로 넣기</td><td>DBMF 주식 노출이 하위 10%면 B06 기회 점수에서 1을 뺌(매일 수집에 DBMF 계산 붙임)</td><td>하락 구간 IC가 확인 가능한 기간에서 모두 오름</td></tr>
<tr><td>B. 넣지 않고 지켜보기</td><td>매일 값만 계산해 화면에 보이고, 후반에 사건이 쌓이면 다시 검증</td><td>후반 사건 0번, 표본 2019~(7번)</td></tr></table>
<div class="sub">한계: DBMF는 2019년 5월부터만 있습니다. 매일 노출은 가격 회귀 추정이고, SEC 실제 값은 약 60일 늦게 공개됩니다. 출처: SEC EDGAR(CIK 0001020425, 시리즈 S000072813), DBMF 투자설명서(2026-04-30).</div>
</body></html>"""
out = Path('/tmp/claude-0/dbmfrep/dbmf.html'); out.write_text(html, encoding='utf-8')
import subprocess
js = f"const {{chromium}}=require('playwright');(async()=>{{const b=await chromium.launch();const p=await b.newPage();await p.goto('{out.as_uri()}');await p.pdf({{path:'{IN / 'DBMF_보고서_20261123.pdf'}',format:'A4',printBackground:true}});await b.close();}})();"
subprocess.run(['node', '-e', js], check=True)
print('ok')
