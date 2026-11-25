# ======================================================================
# 차트 실험실 — 실험 실행기 (2026-11-13 의장)
#   실험 하나 = chart_lab/experiments/<이름>.yaml 하나.
#   실행: python chart_lab/run.py <이름> [<이름> ...]      (GitHub Actions '차트 실험실 실행'이 이걸 부른다)
#   자료: 드라이브 10년치 데이터베이스 '콜로키움 수집데이터/1_data/가격10년_*'(읽기만, 주봉·월봉은 일봉에서 만듦)
#         또는 설정에서 '자료: 야후'면 야후 수정주가. 지수(^KS11·^GSPC·^N225)는 야후.
#   결과: 드라이브 '콜로키움 수집데이터/차트실험실/<이름>/' 에
#         <이름>_요약_Ver.YYYYMMDD_HHMM.csv   규칙별 1·3·6달(주봉이면 4·13·26주) 중앙값, 지수 대비, 아무 날 대비, 건수
#         <이름>_층별_Ver….csv               규칙 × 시장·층별 같은 표
#         <이름>_사건_Ver….csv               신호 하나하나(종목·날짜·지표값·뒤 수익률)
#         <이름>_지금신호_Ver….csv           마지막 5봉 안에 켜진 신호
#         <이름>_설명_Ver….txt               설정·자료 기간·정의·주의
#   원칙: 의장 기준을 먼저 그대로 시험, Claude가 고른 숫자는 '제안'으로 표시, 통계는 중앙값, 손절가 없음.
# ======================================================================
import io, os, sys, time, datetime as dt
import numpy as np
import pandas as pd
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'collect'))   # drive.py
import indicators as ind  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
STAMP = dt.datetime.now(KST).strftime('%Y%m%d_%H%M')
D_ROOT, D_DATA = '콜로키움', '콜로키움 수집데이터'
OUT_DRIVE = f'{D_DATA}/차트실험실'
TF_NAME = {'일봉': 'D', '주봉': 'W', '월봉': 'M'}
HORIZON = {'D': [('1달', 21), ('3달', 63), ('6달', 126)],
           'W': [('4주', 4), ('13주', 13), ('26주', 26)],
           'M': [('3달', 3), ('6달', 6), ('12달', 12)]}
COOLDOWN = {'D': 10, 'W': 2, 'M': 1}      # 같은 종목·같은 규칙이 이 봉 수 안에 또 켜지면 세지 않음
INDEX = {'한국': '^KS11', '미국': '^GSPC', '일본': '^N225'}
CASH_LIKE = {'BOXX', 'SGOV', '0043B0'}     # 현금성 ETF는 늘 뺀다
WARMUP = 60                                # 지표가 자리 잡기 전 앞 봉은 버림


def log(m):
    print(m, flush=True)


# ---------------------------------------------------------------- 자료
def _drive():
    import drive as gdrive
    return gdrive if gdrive.ready() else None


def load_universe(gd):
    local = os.environ.get('CHART_LAB_UNIV', '')
    if local:
        u = pd.read_csv(local, dtype={'코드': str}, encoding='utf-8-sig')
    else:
        names = sorted(f['name'] for f in gd.ls(f'{D_ROOT}/포트폴리오')
                       if f['name'].startswith('콜로키움100_유니버스_') and f['name'].endswith('.csv'))
        u = pd.read_csv(io.BytesIO(gd.get(f'{D_ROOT}/포트폴리오/{names[-1]}')), dtype={'코드': str}, encoding='utf-8-sig')
        log(f'[유니버스] {names[-1]}')
    u = u[u['yfinance 티커'].notna()].copy()
    u['코드'] = u['코드'].astype(str).str.strip()
    u['yfinance 티커'] = u['yfinance 티커'].astype(str).str.strip()
    return u[~u['코드'].isin(CASH_LIKE)].reset_index(drop=True)


def _norm(df):
    df = df.rename(columns={'날짜': 'date', '시가': 'open', '고가': 'high', '저가': 'low', '종가': 'close', '거래량': 'volume'})
    df['date'] = pd.to_datetime(df['date'])
    return df.sort_values('date').drop_duplicates('date').set_index('date')[['open', 'high', 'low', 'close', 'volume']]


def load_db(gd, u, tfs):
    """10년치 데이터베이스(드라이브 1_data/가격10년_*) → {tf: {번호: DataFrame}}. 주봉·월봉은 일봉에서 만든다(11/26 한투 창고 없앰)."""
    import tempfile
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'collect', 'data'))
    import px_store as PS
    d = os.environ.get('CHART_LAB_DATA', '') or tempfile.mkdtemp()
    for k in PS.F:
        if not os.path.exists(f'{d}/{PS.name(k)}'):
            open(f'{d}/{PS.name(k)}', 'wb').write(gd.get(f'{D_DATA}/1_data/{PS.name(k)}'))
    X = {c: PS.frame(d, k) for k, c in (('Open', 'open'), ('High', 'high'), ('Low', 'low'), ('Close', 'close'), ('Volume', 'volume'))}
    out = {tf: {} for tf in tfs}
    for _, s in u.iterrows():
        t = s['yfinance 티커']
        if t not in X['close']:
            continue
        df = pd.DataFrame({c: X[c][t] for c in X if t in X[c]}).dropna(subset=['close'])
        for tf in tfs:
            out[tf][s['번호']] = df if tf == 'D' else _resample(df, 'W-FRI' if tf == 'W' else 'ME')
    log(f'[데이터베이스] 가격10년 {len(out[tfs[0]])}종목')
    return out


def _resample(df, rule):
    g = df.resample(rule)
    r = pd.DataFrame({'open': g['open'].first(), 'high': g['high'].max(), 'low': g['low'].min(),
                      'close': g['close'].last(), 'volume': g['volume'].sum()})
    last = df['close'].groupby(pd.Grouper(freq=rule)).apply(lambda s: s.index.max())
    r.index = pd.DatetimeIndex(last.reindex(r.index).values)     # 봉 날짜 = 그 봉의 마지막 거래일
    return r.dropna(subset=['close'])


def load_yahoo(u, tfs):
    import yfinance as yf
    raw = yf.download(u['yfinance 티커'].tolist(), period='max', auto_adjust=True, group_by='ticker',
                      progress=False, threads=True)
    out = {tf: {} for tf in tfs}
    for _, s in u.iterrows():
        try:
            d = raw[s['yfinance 티커']].dropna(subset=['Close'])
        except KeyError:
            continue
        d = d.rename(columns=str.lower)[['open', 'high', 'low', 'close', 'volume']]
        d.index = pd.to_datetime(d.index).tz_localize(None)
        for tf in tfs:
            out[tf][s['번호']] = d if tf == 'D' else _resample(d, 'W-FRI' if tf == 'W' else 'ME')
    log(f'[야후] {len(out[tfs[0]])}종목')
    return out


def load_index():
    import yfinance as yf
    raw = yf.download(list(INDEX.values()), period='max', auto_adjust=True, progress=False)['Close']
    raw.index = pd.to_datetime(raw.index).tz_localize(None)
    return {m: raw[t].dropna() for m, t in INDEX.items()}


# ---------------------------------------------------------------- 조건
class TF:
    """조건 문장의 d. / w. / m. — 그 주기 지표를 기본 봉 날짜에 맞춰(그날까지 끝난 봉 값) 돌려준다."""

    def __init__(self, frame, base_index):
        self._f, self._b = frame, base_index
        self._cache = {}

    def __getattr__(self, k):
        if k.startswith('_'):
            raise AttributeError(k)
        if k not in self._cache:
            if self._f is None or k not in self._f.columns:
                raise KeyError(f'지표 이름 없음: {k}')
            s = self._f[k]
            self._cache[k] = s if s.index.equals(self._b) else s.reindex(self._b, method='ffill')
        return self._cache[k]


def eval_rule(conds, ns):
    m = None
    for c in conds:
        v = eval(str(c), {'__builtins__': {}}, ns)      # 설정 파일은 저장소 안 것만 읽는다
        v = v.fillna(False).astype(bool) if isinstance(v, pd.Series) else v
        m = v if m is None else (m & v)
    return m


def cooldown(mask, n):
    idx = np.flatnonzero(mask.values)
    keep, last = [], -10 ** 9
    for i in idx:
        if i - last > n:
            keep.append(i)
            last = i
    out = pd.Series(False, index=mask.index)
    out.iloc[keep] = True
    return out


def pick(u, f):
    """대상 거르기: 종목(코드·티커·이름), 시장, 층, 구분, 제외"""
    if not f:
        return u
    x = u
    if f.get('종목'):
        names = {str(v) for v in f['종목']}
        x = x[x['코드'].isin(names) | x['yfinance 티커'].isin(names) | x['정식 종목명'].isin(names)]
    for col in ('시장', '층', '구분'):
        if f.get(col):
            x = x[x[col].isin(f[col])]
    if f.get('제외'):
        ex = {str(v) for v in f['제외']}
        x = x[~(x['코드'].isin(ex) | x['yfinance 티커'].isin(ex) | x['정식 종목명'].isin(ex))]
    return x


# ---------------------------------------------------------------- 실행
def forward(close, idx_close, hs, mid):
    """봉마다 뒤 수익률(%)과 지수 대비(%p), 중간 기간 안 최저·최고(%)"""
    f = pd.DataFrame(index=close.index)
    ic = idx_close.reindex(close.index, method='ffill') if idx_close is not None else None
    for name, h in hs:
        f[f'r_{name}'] = (close.shift(-h) / close - 1) * 100
        if ic is not None:
            f[f'x_{name}'] = f[f'r_{name}'] - (ic.shift(-h) / ic - 1) * 100
    fut = pd.concat([close.shift(-k) for k in range(1, mid + 1)], axis=1)
    f['lo'] = (fut.min(axis=1) / close - 1) * 100
    f['hi'] = (fut.max(axis=1) / close - 1) * 100
    f.loc[close.shift(-mid).isna(), ['lo', 'hi']] = np.nan
    return f


def stats(ev, base, hs):
    r = {'건수': len(ev), '종목수': ev['번호'].nunique() if len(ev) else 0,
         '첫날': ev['날짜'].min().date() if len(ev) else '', '끝날': ev['날짜'].max().date() if len(ev) else ''}
    for name, _ in hs:
        e, b = ev[f'r_{name}'].dropna(), base[f'r_{name}'].dropna()
        r[f'{name}_건수'] = len(e)
        r[f'{name}_중앙값%'] = round(e.median(), 1) if len(e) else np.nan
        if f'x_{name}' in ev:
            r[f'{name}_지수대비%p'] = round(ev[f'x_{name}'].median(), 1) if len(e) else np.nan
        r[f'{name}_오른비율%'] = round((e > 0).mean() * 100, 1) if len(e) else np.nan
        r[f'{name}_아무날%'] = round(b.median(), 1) if len(b) else np.nan
        r[f'{name}_아무날대비%p'] = round(r[f'{name}_중앙값%'] - r[f'{name}_아무날%'], 1) if len(e) and len(b) else np.nan
    mid = hs[1][0]
    r[f'{mid}안_최저_중앙값%'] = round(ev['lo'].median(), 1) if len(ev) else np.nan
    r[f'{mid}안_최고_중앙값%'] = round(ev['hi'].median(), 1) if len(ev) else np.nan
    # 과최적화 점검: 기간 앞 절반·뒤 절반에서 아무 날 대비가 같은 쪽인지
    if len(ev):
        cut = base['날짜'].min() + (base['날짜'].max() - base['날짜'].min()) / 2
        for half, sel_e, sel_b in (('앞절반', ev['날짜'] < cut, base['날짜'] < cut), ('뒤절반', ev['날짜'] >= cut, base['날짜'] >= cut)):
            e, b = ev.loc[sel_e, f'r_{mid}'].dropna(), base.loc[sel_b, f'r_{mid}'].dropna()
            r[f'{half}_{mid}_건수'] = len(e)
            r[f'{half}_{mid}_아무날대비%p'] = round(e.median() - b.median(), 1) if len(e) and len(b) else np.nan
    r['판단주의'] = '건수 부족(30건 미만)' if r['건수'] < 30 else ''
    return r


def run(name):
    path = f'{HERE}/experiments/{name}.yaml'
    cfg = yaml.safe_load(open(path, encoding='utf-8'))
    base_tf = TF_NAME[cfg.get('기본봉', '일봉')]
    hs = HORIZON[base_tf]
    cd = int(cfg.get('중복제외봉', COOLDOWN[base_tf]))
    start = pd.Timestamp(str(cfg['시작'])) if cfg.get('시작') else None
    rules = cfg['규칙']
    text = yaml.safe_dump(cfg, allow_unicode=True)
    ctext = ' '.join(str(c) for r in rules for c in r['조건'])
    tfs = sorted({base_tf} | {t for t, p in (('D', 'd.'), ('W', 'w.'), ('M', 'm.')) if p in ctext}, key='DWM'.index)

    gd = _drive()
    u = load_universe(gd)
    u = pick(u, cfg.get('대상'))
    src = cfg.get('자료', '한투')
    extra = cfg.get('추가종목') or []          # 유니버스 밖 비교용(예: SPY·QQQ 긴 역사). 야후 자료일 때만.
    if extra:
        if src != '야후':
            log('[추가종목] 한투 자료에는 없어서 건너뜀(자료: 야후 에서만)')
        else:
            add = pd.DataFrame([{'번호': str(e['번호']), '코드': str(e['티커']), 'yfinance 티커': str(e['티커']),
                                 '정식 종목명': str(e.get('이름', e['티커'])), '시장': e.get('시장', '미국'),
                                 '층': e.get('층', ''), '구분': e.get('구분', 'ETF')} for e in extra])
            u = pd.concat([u, add], ignore_index=True)
            log(f'[추가종목] {", ".join(add["yfinance 티커"])}')
    data = load_yahoo(u, tfs) if src == '야후' else load_db(gd, u, tfs)
    idx = load_index()
    log(f'[실험] {name} | 기본봉 {cfg.get("기본봉", "일봉")} | 자료 {src} | 대상 {len(u)}종목 | 규칙 {len(rules)}개 | 중복 제외 {cd}봉')

    frames = {}
    for _, s in u.iterrows():
        k = s['번호']
        if k not in data[base_tf] or len(data[base_tf][k]) < WARMUP + 30:
            continue
        fr = {tf: ind.add_all(data[tf][k]) if k in data[tf] else None for tf in tfs}
        b = fr[base_tf]
        fw = forward(b['close'], idx.get(s['시장']), hs, hs[1][1])
        ok = pd.Series(np.arange(len(b)) >= WARMUP, index=b.index)
        if start is not None:
            ok &= b.index >= start
        frames[k] = (s, fr, fw, ok)
    log(f'[자료] 계산한 종목 {len(frames)}개')

    rows, grp, events, now = [], [], [], []
    for rule in rules:
        rn, kind = rule['이름'], rule.get('구분', '제안')
        tgt = set(pick(u, rule.get('대상'))['번호'])
        ev_l, base_l = [], []
        for k, (s, fr, fw, ok) in frames.items():
            if k not in tgt:
                continue
            b = fr[base_tf]
            ns = dict(ind.HELPERS)
            for tf, p in (('D', 'd'), ('W', 'w'), ('M', 'm')):
                if tf in fr:
                    ns[p] = TF(fr[tf], b.index)
            try:
                m = eval_rule(rule['조건'], ns) & ok
            except KeyError as e:
                raise SystemExit(f'규칙 {rn}: {e}')
            m = cooldown(m, cd)
            info = {'번호': k, '코드': s['코드'], '종목명': s['정식 종목명'], '시장': s['시장'], '층': s.get('층', '')}
            bb = fw[ok].assign(**info).rename_axis('날짜').reset_index()
            base_l.append(bb)
            if m.any():
                show = [c for c in rule.get('기록', []) if c in b.columns]
                e = pd.concat([b.loc[m, ['close'] + show], fw[m]], axis=1).assign(**info)
                e = e.rename_axis('날짜').reset_index()
                ev_l.append(e)
                tail = m.iloc[-5:]
                if tail.any():
                    now.append({'규칙': rn, '구분': kind, **info, '신호날짜': tail[tail].index[-1].date(),
                                '마지막봉': b.index[-1].date(), '종가': b['close'].iloc[-1]})
        ev = pd.concat(ev_l, ignore_index=True) if ev_l else pd.DataFrame(columns=['번호', '날짜', 'lo', 'hi'] + [f'r_{n}' for n, _ in hs])
        base = pd.concat(base_l, ignore_index=True)
        ev['날짜'] = pd.to_datetime(ev['날짜'])
        rows.append({'규칙': rn, '구분': kind, '설명': rule.get('설명', ''), **stats(ev, base, hs)})
        for col in ('시장', '층'):
            for g, b2 in base.groupby(col):
                rows_g = stats(ev[ev[col] == g] if len(ev) else ev, b2, hs)
                grp.append({'규칙': rn, '구분': kind, '나눈기준': col, '값': g, **rows_g})
        if len(ev):
            events.append(ev.assign(규칙=rn, 구분=kind))
        r = rows[-1]
        mid = hs[1][0]
        log(f'  {rn} [{kind}] {r["건수"]}건 | {mid} 중앙값 {r[f"{mid}_중앙값%"]}% (아무 날 {r[f"{mid}_아무날%"]}%, 대비 {r[f"{mid}_아무날대비%p"]}%p) {r["판단주의"]}')

    summ, by = pd.DataFrame(rows), pd.DataFrame(grp)
    evs = pd.concat(events, ignore_index=True) if events else pd.DataFrame()
    if len(evs):
        lead = ['규칙', '구분', '번호', '코드', '종목명', '시장', '층', '날짜']
        evs = evs[lead + [c for c in evs.columns if c not in lead]]
        num = evs.select_dtypes('number').columns
        evs[num] = evs[num].round(2)
        evs = evs.rename(columns={**{f'r_{n}': f'{n}뒤%' for n, _ in hs}, **{f'x_{n}': f'{n}_지수대비%p' for n, _ in hs},
                                  'lo': f'{hs[1][0]}안_최저%', 'hi': f'{hs[1][0]}안_최고%', 'close': '종가'})
    nowdf = pd.DataFrame(now)

    first = min((f[1][base_tf].index[WARMUP] for f in frames.values()), default=None)
    last = max((f[1][base_tf].index[-1] for f in frames.values()), default=None)
    hz = ', '.join(f'{n}={h}봉' for n, h in hs)
    note = f"""차트 실험실 결과 — {cfg.get('제목', name)}
실행: {STAMP} KST | 실험 파일 chart_lab/experiments/{name}.yaml
자료: {src} {'10년치 데이터베이스(드라이브 1_data)' if src == '한투' else '수정주가'} | 기본봉 {cfg.get('기본봉', '일봉')} | 기간 {first.date() if first is not None else ''} ~ {last.date() if last is not None else ''}
대상: {len(frames)}종목(현금성 ETF 제외) | 지수: 한국 ^KS11, 미국 ^GSPC, 일본 ^N225(야후)
뒤 수익률: 신호 봉 종가 → {hz} 뒤 종가. 지수 대비 = 같은 기간 지수 수익률을 뺀 값. '{hs[1][0]}안 최저·최고'는 다음 봉부터 {hs[1][1]}봉.
아무 날: 같은 대상 종목의 같은 기간 모든 봉(지표 준비 {WARMUP}봉 뒤)을 샀다고 볼 때의 중앙값.
중복: 같은 종목·같은 규칙이 {cd}봉 안에 다시 켜지면 세지 않음.
구분: '의장기준' = 의장님이 정한 기준 그대로(필요하면 환산), '제안' = Claude가 고른 숫자(의장 승인 아님).
과최적화 점검: 기간을 앞·뒤 절반으로 나눠 아무 날 대비가 같은 쪽인지 보세요. 30건 미만은 판단하지 않습니다.
통계는 모두 중앙값. 손절가·패턴 판정은 다루지 않습니다.

설명: {cfg.get('설명', '')}
출처: {cfg.get('출처', '')}

설정 원문:
{text}"""

    out = f'{HERE}/out/{name}'
    os.makedirs(out, exist_ok=True)
    files = {f'{name}_요약_Ver.{STAMP}.csv': summ, f'{name}_층별_Ver.{STAMP}.csv': by,
             f'{name}_사건_Ver.{STAMP}.csv': evs, f'{name}_지금신호_Ver.{STAMP}.csv': nowdf}
    for fn, df in files.items():
        df.to_csv(f'{out}/{fn}', index=False, encoding='utf-8-sig')
    with open(f'{out}/{name}_설명_Ver.{STAMP}.txt', 'w', encoding='utf-8') as f:
        f.write(note)
    if gd is not None and not os.environ.get('CHART_LAB_NO_UPLOAD'):
        for fn in os.listdir(out):
            if STAMP in fn:
                gd.put(f'{OUT_DRIVE}/{name}/{fn}', open(f'{out}/{fn}', 'rb').read())
        log(f'[저장] 드라이브 {OUT_DRIVE}/{name}/ (Ver.{STAMP})')
    log(f'[저장] {out}')
    return summ


if __name__ == '__main__':
    names = [n.strip() for a in sys.argv[1:] for n in a.replace(',', ' ').split() if n.strip()]
    if not names:
        raise SystemExit('실험 이름을 넣으세요. 목록: ' + ', '.join(sorted(f[:-5] for f in os.listdir(f'{HERE}/experiments') if f.endswith('.yaml'))))
    t0 = time.time()
    for n in names:
        run(n)
    log(f'끝 ({time.time() - t0:.0f}초)')
