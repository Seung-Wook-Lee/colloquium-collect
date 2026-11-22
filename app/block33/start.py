"""블록33 start 블록 — 모든 질문은 반드시 여기서 시작한다 (11/22 22:45~22:46 의장 확정).
11/22 23:30 의장 "왜 2원화 되어 있지?" → 하나의 흐름: 질문 → ① 블록 계산 → ② 거르기 → ③ 쓸 블록 → ④ 합산(C0~C5) → ⑤ 정확도 비교 → ⑥ 결과 → ⑦ 그림(종목일 때만).
  ①② = 엔진(engine.run)을 질문마다 이 코드 안에서 직접 부른다(미리 만든 판정표를 읽지 않음). START_IN = 엔진 입력 폴더.
  GitHub Actions start.yml 이 입력(드라이브 최신 07시 파일·보조 자료·유니버스)을 모아 이 파일을 돌린다.
  START_DIR = 블록점수이력·가격10년·지수_장기·Core50 있는 폴더, START_OUT = 결과 폴더.
질문을 받으면 질문장부에 번호를 매겨 적고, 아래 순서를 코드로 돌린다. 답에는 반드시 start 번호를 적는다.
① 쓸 블록 정하기: 33개 전부가 기본. 시장(한국·미국)·구분(주식·ETF)에서 공식 값이 절반 미만인 블록만 빠지고, 빠진 이유를 적는다.
   시장 블록 B01~B10은 모든 종목에 같은 값이라 순위가 아니라 국면·gate로 엔진 안에서 쓰인다(엔진 '국면' 칸).
② 최대 조합(C0)으로 선정.
③ 대안 조합 5개(C1~C5)를 만들어 과거 정확도를 겨룬다.
   정확도 = 블록점수이력(2017-12~ 매주, 그날까지 자료로 다시 매긴 블록 점수)에서
     - IC: 매주 종목 점수와 26주 뒤 수익의 순위 상관(스피어만) 평균
     - 상위 1/5 초과수익: 매주 점수 상위 1/5의 26주 수익 − 그 주 전체 평균
     - t: 26주 수익이 매주 겹치므로 독립 표본 = 주 수 ÷ 26 으로 보정
   판정 기준: 지금과 같은 국면(방어 국면) 주의 IC. C5(걸어가며 고른 조합)는 해마다 그 전 해까지의 결과로만 고른다.
   과거 이력에 없는 블록(실적·수급 등)은 그 조합의 과거 검증에서 빠지며, '검증에 쓴 블록 수'로 표시한다.
④ 가장 정확한 조합으로 오늘 결과. 엔진 판정(추천 상태·원칙·gate)을 옆에 그대로 붙인다.
⑤ 해석은 사람이(의장과 좁혀감). 이 코드는 순위를 손으로 바꾸지 않는다.
쓰는 법: python3 start.py "<질문>" [대상: core50|전체] [구분: 주식|ETF|모두]
결과: ../start/<번호>_{블록,조합정확도,결과}.csv, 질문장부: ../start/질문장부.csv"""
import os, sys, itertools, pandas as pd, numpy as np
H = os.environ.get('START_DIR') or os.path.dirname(os.path.abspath(__file__)); UP = f'{H}/..'
import datetime as dt
Q = sys.argv[1] if len(sys.argv) > 1 else ''
if not Q.strip(): sys.exit('질문이 없습니다: python3 start.py "<질문>"')
OD = os.environ.get('START_OUT') or f'{UP}/start'; os.makedirs(OD, exist_ok=True)
LOG = f'{OD}/질문장부.csv'
L0 = pd.read_csv(LOG) if os.path.exists(LOG) else pd.DataFrame(columns=['번호', '시각', '질문', '대상', '구분', '판정표날짜', '이긴조합'])
NO = int(L0['번호'].max()) + 1 if len(L0) else 1
TAG = f'S{NO:04d}'
TGT = sys.argv[2] if len(sys.argv) > 2 else 'core50'
KIND = sys.argv[3] if len(sys.argv) > 3 else '모두'
HZ = (sys.argv[4] if len(sys.argv) > 4 else '26') + '주'          # 정확도를 잴 보유 기간: 4·12·26·52
NUS = int(sys.argv[5]) if len(sys.argv) > 5 else 0                # 뽑을 수: 미국
NKR = int(sys.argv[6]) if len(sys.argv) > 6 else 0                # 뽑을 수: 한국
# 11/22 23:24 의장 "매번 그림을 그릴 필요 없음. 종목을 얘기할 때만" → 그림(png)은 종목을 뽑을 때(N미국+N한국 > 0)만. 나머지는 표·숫자(csv·화면)만.
FIG = (NUS + NKR) > 0 or os.environ.get('FIG') == '1'
# ①② 블록 계산·거르기: 엔진을 질문마다 직접 돌린다
_IN = os.environ.get('START_IN')
if _IN:
    _QC = os.path.dirname(os.path.abspath(__file__)); _REPO = os.path.dirname(_QC)
    sys.path[:0] = [_QC, _REPO, os.path.join(os.path.dirname(_REPO), 'collect'), os.path.join(_REPO, 'market')]
    import engine as ENG
    P, _D, _M, _m = ENG.run(_IN)
    PDATE = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')
    P.to_csv(f'{OD}/{TAG}_판정표.csv', index=False, encoding='utf-8-sig'); _M.to_csv(f'{OD}/{TAG}_시장블록.csv', index=False, encoding='utf-8-sig')
    print(f'① 블록 계산·② 거르기: 엔진 직접 실행 {PDATE} (입력 {os.environ.get("START_INDATE", "")}) | 판정 {P["판정"].value_counts().to_dict()}')
    U = pd.read_csv(f'{_IN}/유니버스.csv', encoding='utf-8-sig')
else:   # 손 시험용(드라이브 없는 곳): 미리 만든 판정표. 답에는 쓰지 않는다.
    P = pd.read_csv(f'{H}/pan.csv'); PDATE = '미리 만든 판정표 ' + dt.datetime.fromtimestamp(os.path.getmtime(f'{H}/pan.csv')).strftime('%Y-%m-%d %H:%M')
    print('주의: START_IN 없음 → 미리 만든 판정표로 손 시험(엔진 직접 아님)')
    U = pd.read_csv(f'{H}/uni_e.csv')
BH = pd.read_csv(f'{H}/bhist.csv', low_memory=False)
K = pd.read_csv(f'{H}/Core50.csv') if os.path.exists(f'{H}/Core50.csv') else pd.read_csv(sorted([f'{UP}/{x}' for x in os.listdir(UP) if x.startswith('Core50_AI_비AI_Ver')])[-1])
SB = [f'B{i}' for i in range(11, 35)]
REV = {'B28'}                                  # 높을수록 나쁜 블록(과열) → 1−값
MEM = {'G09', 'K01', 'K11', 'G13', 'G56'}      # blocks.yaml 메모리반대: B15는 엔진이 이미 뒤집음, B23은 여기서
W = {'L1': (.7, .1, .2), 'L2': (.6, .2, .2), 'L3': (.5, .3, .2), 'L4': (.4, .4, .2), 'L5': (.3, .5, .2)}
DROP = {'G179'}

def num(x):
    if isinstance(x, str):
        return {'통과': 1.0, '탈락': 0.0}.get(x, pd.to_numeric(x, errors='coerce'))
    return x

def prep(D):
    D = D.copy()
    for b in SB:
        D[b] = D[b].map(num).astype(float) if b in D else np.nan
    for b in REV:
        D[b] = 1 - D[b]
    m = D['번호'].isin(MEM); D.loc[m, 'B23'] = 1 - D.loc[m, 'B23']
    return D

# 대상
X = prep(P[~P['번호'].isin(DROP)])
if TGT == 'core50': X = X[X['번호'].isin(K['번호'])]
X = X[X['층'] != 'S0'] if '층' in X else X
if KIND in ('주식', 'ETF'): X = X[X['구분'] == ('개별주' if KIND == '주식' else 'ETF')]
lay = dict(zip(P['번호'], P['층L']))

# ① 쓸 블록: 시장×구분마다 값이 절반 이상인 블록
rows = []
for (mk, kd), g in X.groupby(['시장', '구분']):
    for b in SB:
        c = g[b].notna().mean()
        rows.append(dict(시장=mk, 구분=kd, 블록=b, 값있는비율=round(c, 2), 씀='예' if c >= .5 else '아니오(이 시장·구분에 공식 값 없음)'))
BL = pd.DataFrame(rows)
use = {(mk, kd): set(g.loc[g['씀'] == '예', '블록']) for (mk, kd), g in BL.groupby(['시장', '구분'])}
for (mk, kd), s in use.items():
    m = (X['시장'] == mk) & (X['구분'] == kd)
    X.loc[m, [b for b in SB if b not in s]] = np.nan
BL.to_csv(f'{OD}/{TAG}_블록.csv', index=False, encoding='utf-8-sig')

# ② ③ 조합
G3 = {'가치퀄리티': ['B15', 'B23', 'B25', 'B26', 'B27', 'B28'],
      '추세바닥': ['B11', 'B12', 'B13', 'B14', 'B17', 'B29', 'B30', 'B31', 'B32', 'B33'],
      '전망과매도': ['B24', 'B16', 'B18', 'B19', 'B20', 'B21', 'B22', 'B34']}
G0 = {'가치퀄리티': ['B15', 'B25', 'B26'], '추세바닥': ['B30', 'B31', 'B11', 'B12'], '전망과매도': ['B24', 'B16']}   # blocks.yaml 원칙.층별 묶음 그대로

def eq(D, bs):
    return D[[b for b in bs if b in D]].mean(axis=1)

def layered(D, G):
    w = np.array([W.get(lay.get(n), W['L3']) for n in D['번호']])
    v = np.column_stack([eq(D, bs) for bs in G.values()]); ok = ~np.isnan(v)
    den = np.where(ok, w, 0).sum(1)
    return pd.Series(np.where(den > 0, np.nansum(np.where(ok, v, 0) * w, 1) / np.where(den > 0, den, 1), np.nan), index=D.index)

COMBO = {
    'C0 최대(쓸 수 있는 블록 전부, 같은 무게)': ('eq', SB),
    'C1 층별 가중 + 블록 전부 세 묶음': ('lay', G3),
    'C2 층별 가중 원래 묶음(blocks.yaml 원칙)': ('lay', G0),
    'C3 가격 바닥(B11~B14·B16·B17·B29)': ('eq', ['B11', 'B12', 'B13', 'B14', 'B16', 'B17', 'B29']),
    'C4 추세(B30~B33)': ('eq', ['B30', 'B31', 'B32', 'B33']),
}

def score(D, c):
    t, a = c
    return eq(D, a) if t == 'eq' else layered(D, a)

HB = prep(BH); HB['날짜'] = pd.to_datetime(HB['날짜']); HB['y'] = HB['날짜'].dt.year
# 11/22 22:53 의장 "현 시점 인식 반영: 20% 빠졌지만 더 빠질 수도" →
#   지금 NDX 52주 고점 대비 낙폭 ±5%p 안이던 주만으로 조합 정확도를 재고 그 결과로 이긴 조합을 고른다.
#   더 빠질 가능성: 그 주들에 상위 1/5를 샀을 때 4주·12주 뒤 평균(먼저 더 빠졌나)과 보유기간 수익 하위 10%(나쁜 경우)를 함께 적는다.
_I = pd.read_csv(f'{H}/지수_장기.csv.gz'); _N = _I[_I['지수'] == '^NDX'].set_index('날짜')['종가'].dropna(); _N.index = pd.to_datetime(_N.index)
print(f'블록 계산 시각: {PDATE}')
_DD = (_N / _N.rolling(252, min_periods=200).max() - 1)
DD_NOW = float(_DD.iloc[-1]); BAND = (DD_NOW - .05, DD_NOW + .05)
HB['NDX낙폭'] = _DD.reindex(HB['날짜'], method='ffill').values
HB['비슷'] = HB['NDX낙폭'].between(*BAND).astype(int)
if TGT == 'core50': HB = HB[HB['번호'].isin(K['번호'])]
if KIND in ('주식', 'ETF'): HB = HB[HB['구분'] == ('개별주' if KIND == '주식' else 'ETF')]
HAVE = [b for b in SB if HB[b].notna().mean() > .3]

def acc(s, D):
    D = D.assign(s=s).dropna(subset=['s', HZ])
    r = []
    for dt, g in D.groupby('날짜'):
        if len(g) < 8 or g['s'].nunique() < 3: continue
        ic = g['s'].rank().corr(g[HZ].rank())
        t = g[g['s'] >= g['s'].quantile(.8)]
        q = t[HZ].mean() - g[HZ].mean()
        r.append((dt, ic, q, int(g['방어국면'].iloc[0]), int(g['비슷'].iloc[0]), t['4주'].mean(), t['12주'].mean(), t[HZ].mean(), t[HZ].quantile(.1)))
    return pd.DataFrame(r, columns=['날짜', 'IC', '초과', '방어', '비슷', '상위4주', '상위12주', '상위수익', '상위하위10'])

def summ(R, name, used):
    out = []
    for lab, m in ((f'지금 낙폭 비슷({BAND[0]:.0%}~{BAND[1]:.0%})', R['비슷'] == 1), ('방어 국면', R['방어'] == 1), ('모든 주', R['방어'] >= 0)):
        r = R[m]; n = len(r); ne = max(n / 26, 1)
        out.append({'조합': name, '국면': lab, '주수': n, 'IC 평균': r['IC'].mean(), 'IC t': r['IC'].mean() / (r['IC'].std() / np.sqrt(ne)) if n > 1 else np.nan,
                    f'상위1/5 초과(%p, {HZ})': r['초과'].mean(), '초과 t': r['초과'].mean() / (r['초과'].std() / np.sqrt(ne)) if n > 1 else np.nan,
                    '상위1/5 4주 뒤(%)': r['상위4주'].mean(), '상위1/5 12주 뒤(%)': r['상위12주'].mean(), f'상위1/5 {HZ} 평균(%)': r['상위수익'].mean(),
                    f'상위1/5 {HZ} 나쁜 경우 하위10%(%)': r['상위하위10'].mean(), '검증에 쓴 블록': ','.join(used)})
    return out

S = []; Rs = {}
for nm, c in COMBO.items():
    bs = c[1] if c[0] == 'eq' else sum(c[1].values(), [])
    used = [b for b in bs if b in HAVE]
    R = acc(score(HB, c), HB); Rs[nm] = R; S += summ(R, nm, used)

# C5 걸어가며 고른 조합: 해마다 그 전 해까지 방어 국면 주의 IC가 가장 높은 블록 묶음(이력에 있는 블록 중 2~4개)을 골라 그해에 씀
cand = [c for k in (2, 3, 4) for c in itertools.combinations(HAVE, k)]
ys = sorted(HB['y'].unique()); recs = []; pick = {}
pre = {}
for c in cand:
    R = acc(eq(HB, c), HB); R['y'] = R['날짜'].dt.year; pre[c] = R
for y in ys[2:]:
    best = max(cand, key=lambda c: pre[c][(pre[c]['y'] < y) & (pre[c]['비슷'] == 1)]['IC'].mean() if len(pre[c][(pre[c]['y'] < y) & (pre[c]['비슷'] == 1)]) else -9)
    pick[y] = best; recs.append(pre[best][pre[best]['y'] == y])
R5 = pd.concat(recs) if recs else pd.DataFrame(columns=['날짜', 'IC', '초과', '방어'])
last5 = pick[max(pick)] if pick else ()
n5 = f'C5 걸어가며 고른 조합(올해: {"+".join(last5)})'
COMBO[n5] = ('eq', list(last5)); S += summ(R5, n5, list(last5))
A = pd.DataFrame(S)
A.round(3).to_csv(f'{OD}/{TAG}_조합정확도.csv', index=False, encoding='utf-8-sig')
d = A[A['국면'].str.startswith('지금 낙폭')].sort_values('IC 평균', ascending=False)
win = d['조합'].iloc[0]

# ④ 결과: 이긴 조합 점수 + 최대 조합 점수 + 엔진 판정 그대로
tk = dict(zip(U['번호'], U['yfinance 티커']))
X['이름'] = [tk.get(n) if m == '미국' else s for n, m, s in zip(X['번호'], X['시장'], X['종목'])]
X['이긴 조합 점수'] = score(X, COMBO[win]); X['C0 최대 점수'] = score(X, COMBO['C0 최대(쓸 수 있는 블록 전부, 같은 무게)'])
X['쓴 블록 수'] = X[SB].notna().sum(axis=1)
X['그룹'] = X['번호'].map(dict(zip(K['번호'], K['그룹'])))
cols = ['구분', '그룹', '이름', '층L', '이긴 조합 점수', 'C0 최대 점수', '쓴 블록 수', '판정', '추천', '원칙', '관문']
O = X.sort_values('이긴 조합 점수', ascending=False)[cols]
O.to_csv(f'{OD}/{TAG}_결과.csv', index=False, encoding='utf-8-sig')
# 뽑기: 엔진 gate(판정 '걸러짐')를 통과하고, 우리 가격10년 자료에 1년(252일) 이상 값이 있는 것 중 이긴 조합 점수 순. 사람 손 조정 없음.
# (11/22 의장: 과거값이 없어 계산 안 되는 종목은 답에서 거론하지 않음 → 코드에서 뺌)
_C = pd.read_csv(f'{H}/가격10년_종가.csv.gz', index_col=0)
X['가격일수'] = [int(_C[t].notna().sum()) if t in _C else 0 for t in X['번호'].map(tk)]
SEL = pd.concat([X[(X['시장'] == mk) & (X['판정'] != '걸러짐') & (X['가격일수'] >= 252)].sort_values('이긴 조합 점수', ascending=False).head(n)
                 for mk, n in (('미국', NUS), ('한국', NKR)) if n])  if (NUS or NKR) else pd.DataFrame(columns=X.columns)
if len(SEL):
    SEL[['시장'] + cols].to_csv(f'{OD}/{TAG}_뽑기.csv', index=False, encoding='utf-8-sig')
    print('뽑기'); print(SEL[['시장'] + cols].round(2).to_string(index=False))
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 30)
print('이긴 조합:', win)
print(d.drop(columns=['국면']).round(3).to_string(index=False))
print('지금 NDX 52주 고점 대비', f'{DD_NOW:.1%}', '| 비슷한 주 수', int(HB.drop_duplicates('날짜')['비슷'].sum()))
print(A[A['국면'] == '방어 국면'].drop(columns=['국면', '검증에 쓴 블록']).round(2).to_string(index=False))
print(A[A['국면'] == '모든 주'].drop(columns=['국면', '검증에 쓴 블록']).round(3).to_string(index=False))
for kd, g in O.groupby('구분'):
    print(kd); print(g.head(12).round(2).to_string(index=False))
L0 = pd.concat([L0, pd.DataFrame([dict(번호=NO, 시각=dt.datetime.now().strftime('%Y-%m-%d %H:%M'), 질문=Q, 대상=TGT, 구분=KIND, 판정표날짜=PDATE, 이긴조합=win)])])
L0.to_csv(LOG, index=False, encoding='utf-8-sig')
print(f'start 번호 {TAG} | 질문: {Q} | 판정표 받은 시각 {PDATE}')
print('빠진 블록:'); print(BL[BL['씀'] != '예'].groupby('블록').apply(lambda g: ', '.join(g['시장'] + g['구분'])).to_string())
print('이력에 있는 블록:', HAVE, '| 국면:', P['국면'].dropna().iloc[0] if '국면' in P else '')

# ⑥ 그림(11/22 22:59 의장 "어디서 어떤 점수를 받았는지 코딩 결과를 그려서 보여줘, 숫자로 해석")
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
for fp in ('/root/.fonts/NanumGothic.ttf', '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'):
    if os.path.exists(fp): fm.fontManager.addfont(fp); plt.rcParams['font.family'] = fm.FontProperties(fname=fp).get_name()
plt.rcParams.update({'font.size': 7, 'axes.unicode_minus': False})
# 종목별: 지금 낙폭과 비슷했던 주에 그 종목을 샀다면(4·12·보유기간 뒤, 하위 10%)
SIM = HB[HB['비슷'] == 1].groupby('번호').agg(주수=(HZ, 'count'), 뒤4주=('4주', 'mean'), 뒤12주=('12주', 'mean'), 보유평균=(HZ, 'mean'),
                                           하위10=(HZ, lambda v: v.quantile(.1)), 중앙=(HZ, 'median'), 승률=(HZ, lambda v: (v.dropna() > 0).mean()))
X = X.join(SIM, on='번호')
X.drop(columns=[c for c in X if c.startswith('_')], errors='ignore').to_csv(f'{OD}/{TAG}_종목별전부.csv', index=False, encoding='utf-8-sig')
fig = plt.figure(figsize=(11, 8.5), dpi=150)
gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.15], width_ratios=[1, 1.3])
# (가) 조합 6개 정확도
ax = fig.add_subplot(gs[0, 0]); dd_ = d.sort_values('IC 평균')
ax.barh([c.split(' ')[0] + ' ' + c.split(' ')[1] for c in dd_['조합']], dd_['IC 평균'], color=['#c0392b' if v < 0 else '#2e86c1' for v in dd_['IC 평균']])
for i, (v, m) in enumerate(zip(dd_['IC 평균'], dd_[f'상위1/5 {HZ} 평균(%)'])): ax.text(v, i, f' IC {v:.2f} · 상위1/5 {m:+.0f}%', va='center', fontsize=6)
ax.axvline(0, color='k', lw=.5); ax.set_title(f'(가) 조합 6개 정확도 — NDX 낙폭 {BAND[0]:.0%}~{BAND[1]:.0%}였던 주, {HZ} 보유', fontsize=8)
# (나) 산점도: 이긴 조합 점수 vs 같은 국면 과거 보유 수익
ax = fig.add_subplot(gs[0, 1]); Z = X.dropna(subset=['이긴 조합 점수'])
sel = set(SEL['번호']) if len(SEL) else set()
c_ = ['#e67e22' if n in sel else ('#bbbbbb' if j == '걸러짐' else '#5d6d7e') for n, j in zip(Z['번호'], Z['판정'])]
Z = Z.assign(_y=Z['중앙'].clip(upper=200)); ax.scatter(Z['이긴 조합 점수'], Z['_y'], c=c_, s=18)
for _, r in Z.iterrows():
    if pd.notna(r['_y']): ax.annotate(r['이름'] + ('↑' if r['중앙'] > 200 else ''), (r['이긴 조합 점수'], r['_y']), fontsize=5.5, xytext=(2, 2), textcoords='offset points')
ax.axhline(Z['중앙'].median(), color='k', lw=.5, ls='--')
ax.set_xlabel(f'이긴 조합 점수 ({win.split(" ")[0]})'); ax.set_ylabel(f'비슷한 낙폭 주에 샀을 때 {HZ} 수익 중앙값(%, 200 넘으면 ↑)')
ax.set_title('(나) 점수와 과거 수익 — 주황 = 뽑힌 10개, 회색 = 엔진 걸러짐', fontsize=8)
# (다) 히트맵: 뽑힌 종목 × 블록
ax = fig.add_subplot(gs[1, :])
if len(SEL):
    S2 = X.set_index('번호').loc[list(SEL['번호'])]
    M = S2[SB].astype(float)
    im = ax.imshow(M.values, cmap='RdYlGn', vmin=0, vmax=1, aspect='auto')
    ax.set_xticks(range(len(SB))); ax.set_xticklabels([b + ('*' if b in COMBO[win][1] else '') for b in SB], fontsize=6)
    ax.set_yticks(range(len(S2))); ax.set_yticklabels([f"{n} · {e} · {'' if pd.isna(h) else f'{h:+.0f}%'}" for n, e, h in zip(S2['이름'], S2['추천'], S2['중앙'])], fontsize=6)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M.values[i, j]
            ax.text(j, i, '' if np.isnan(v) else f'{v:.1f}', ha='center', va='center', fontsize=5)
    ax.set_title(f'(다) 뽑힌 10개의 블록 점수(빈칸 = 해당 없음, * = 이긴 조합에 쓴 블록) · 왼쪽 % = 비슷한 낙폭 주 {HZ} 수익 중앙값', fontsize=8)
fig.suptitle(f'start {TAG} · {Q}'.replace('−', '-'), fontsize=9); fig.tight_layout()
if FIG: fig.savefig(f'{OD}/{TAG}_그림.png'); print('그림', f'{OD}/{TAG}_그림.png')
plt.close(fig)
if len(SEL):
    print(X[X['번호'].isin(sel)][['시장', '이름', '이긴 조합 점수', 'C0 최대 점수', 'B13', 'B16', 'B29', 'B15', 'B23', 'B24', 'B30', '추천', '주수', '뒤4주', '뒤12주', '보유평균', '중앙', '하위10', '승률']].round(2).to_string(index=False))

# ⑦ 종목마다: 돌린 블록 수, 높은 점수 블록 2개·낮은 점수 블록 2개, 종합 점수 (11/22 23:00 의장)
import yaml
_QP = os.environ.get('QC_PRIVATE', '/home/user/team_q/colloquium_private') + '/blocks.yaml'
try:
    _BY = yaml.safe_load(open(_QP, encoding='utf-8'))
    QN = {k: v.get('질문', '') for sec in ('시장', '종목') for k, v in (_BY.get(sec) or {}).items() if isinstance(v, dict)}
except Exception:
    QN = {}
QN['B28'] = '과열 아님(B28 거꾸로)'
NMK = len([k for k in QN if k <= 'B10'])
if len(SEL):
    rows = []
    for _, r in X[X['번호'].isin(sel)].iterrows():
        v = r[SB].astype(float).dropna().sort_values()
        f = lambda b: f"{b} {QN.get(b, '')[:14]} {v[b]:.2f}"
        rows.append({'시장': r['시장'], '종목': r['이름'], '돌린 블록': f'종목 {len(v)}/24 + 시장 {NMK}',
                     '높은 1': f(v.index[-1]), '높은 2': f(v.index[-2]), '낮은 1': f(v.index[0]), '낮은 2': f(v.index[1]),
                     '종합(C0 전부)': round(r['C0 최대 점수'], 2), f'종합({win.split(" ")[0]})': round(r['이긴 조합 점수'], 2), '엔진': r['추천']})
    T = pd.DataFrame(rows).sort_values(f'종합({win.split(" ")[0]})', ascending=False)
    T.to_csv(f'{OD}/{TAG}_블록요약.csv', index=False, encoding='utf-8-sig')
    print(T.to_string(index=False))
if len(SEL) and FIG:
    fig, ax = plt.subplots(figsize=(13, 0.42 * len(T) + 0.9), dpi=150); ax.axis('off')
    tb = ax.table(cellText=T.values, colLabels=T.columns, loc='center', cellLoc='left'); tb.auto_set_font_size(False); tb.set_fontsize(6); tb.scale(1, 1.35)
    for (i, j), c in tb.get_celld().items():
        if i == 0: c.set_facecolor('#e5e8e8'); c.set_text_props(weight='bold')
        elif T.columns[j].startswith('높은'): c.set_facecolor('#d5f5e3')
        elif T.columns[j].startswith('낮은'): c.set_facecolor('#fadbd8')
    tb.auto_set_column_width(list(range(len(T.columns))))
    ax.set_title(f'start {TAG} · 종목별 블록 요약 (점수 = 블록 공식 통과 비율 0~1)', fontsize=8)
    fig.tight_layout(); fig.savefig(f'{OD}/{TAG}_블록요약.png')
