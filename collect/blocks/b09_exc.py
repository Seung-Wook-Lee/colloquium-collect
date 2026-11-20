# ======================================================================
# [블록 9-예외] 미스 차트 예외 검정 — 지금 하락·상승이 그 종목에게 예외적인가 (2026-11-09 의장)
#   하는 일  : 스튜디오 톰앤수 100 종목마다 주봉 10년치로 두 가지 가설검정을 한다.
#              ① 자기 역사(10·5·3·1년): 귀무가설 "지금 52주 고점 대비 하락폭(13주 수익률)은 이 종목에게 평소 수준".
#                 p = 그 기간(10년·5년·3년·1년) 중 지금보다 더 극단이었던 주의 비율(경험적 백분위).
#              ② 베타 잔차: 귀무가설 "최근 움직임은 시장 × 베타로 설명된다".
#                 베타 = 직전 2년 주간(최근 13주 제외), 최근 4주·13주 잔차 합 z검정(정규 가정).
#              하락은 아래쪽 p, 상승은 위쪽 p. 판정 조건이 아니라 '정도'를 말하는 근거(문턱 아님).
#   소스     : yfinance 주봉 10년(종목 + 기준지수 ^GSPC·^KS11·^N225·379800.KS)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_예외검정.csv
#   쓰는 위원: 미스 차트(미스차트.txt 5-1). "아주 예외적인 하락입니다, 베타를 감안해도" 같은 말의 근거.
#   주의     : 1년 p는 강한 상승장 뒤에는 거의 모두 작게 나온다 → 10년 p를 주 판단으로 쓴다.
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
import math
import numpy as np

EXC_BENCH = {'S&P500': '^GSPC', '코스피': '^KS11', '니케이225': '^N225', 'KODEX 미국S&P500(원화)': '379800.KS'}
EXC_MKT = {'미국': '^GSPC', '한국': '^KS11', '일본': '^N225'}


def _exc_norm_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _exc_weekly(tickers):
    out = {}
    for i in range(0, len(tickers), 20):
        part = tickers[i:i + 20]
        for n in range(3):
            try:
                d = yf.download(part, period='10y', interval='1wk', auto_adjust=True,
                                group_by='ticker', threads=False, progress=False)
                for t in part:
                    if d is not None and not d.empty and t in d.columns.get_level_values(0):
                        c = d[t]['Close'].dropna()
                        c.index = pd.to_datetime(c.index).tz_localize(None)
                        if len(c) > 60:
                            out[t] = c
                break
            except Exception as e:
                if n == 2:
                    print(f'  예외검정 주봉 실패 {part[:3]}: {e}')
                time.sleep(5 * 3 ** n)
        time.sleep(2)
    return out


def exc_row(c, m):
    """c: 종목 주봉 종가, m: 기준지수 주봉 종가. 반환: 한 줄 dict"""
    dd = (c / c.rolling(52, min_periods=26).max() - 1).dropna()
    r13 = (c / c.shift(13) - 1).dropna()
    row = {'기준주': c.index[-1].date(), '52주고점대비(%)': round(dd.iloc[-1] * 100, 1),
           '13주수익(%)': round(r13.iloc[-1] * 100, 1)}
    end = c.index[-1]
    for yrs, lab in ((10, '10년'), (5, '5년'), (3, '3년'), (1, '1년')):
        a = dd[dd.index >= end - pd.DateOffset(years=yrs)]
        b = r13[r13.index >= end - pd.DateOffset(years=yrs)]
        row[f'{lab}_하락p'] = round(float((a <= a.iloc[-1]).mean()), 3)
        row[f'{lab}_13주하락p'] = round(float((b <= b.iloc[-1]).mean()), 3)
        row[f'{lab}_13주상승p'] = round(float((b >= b.iloc[-1]).mean()), 3)
        row[f'{lab}_표본주'] = len(a)
        row[f'{lab}_최대낙폭(%)'] = round(float(a.min()) * 100, 1)
    w = pd.concat([c.pct_change(), m.pct_change()], axis=1, sort=True).dropna()
    w.columns = ['s', 'm']
    est = w.iloc[-117:-13]
    if len(est) >= 52 and est['m'].var() > 0:
        beta = float(np.cov(est['s'], est['m'])[0, 1] / est['m'].var())
        sd = float((est['s'] - beta * est['m']).std())
        row['베타(주간2년)'] = round(beta, 2)
        for k in (4, 13):
            res = float((w['s'].iloc[-k:] - beta * w['m'].iloc[-k:]).sum())
            z = res / (sd * math.sqrt(k)) if sd > 0 else 0.0
            row[f'잔차{k}주(%)'] = round(res * 100, 1)
            row[f'잔차{k}주_하락p'] = round(_exc_norm_cdf(z), 3)
            row[f'잔차{k}주_상승p'] = round(1 - _exc_norm_cdf(z), 3)
    # 한 줄 정리(문턱 0.05는 '정도'를 말하는 표기일 뿐, 사고팔기 문턱 아님)
    down_hist = row['10년_하락p'] <= 0.05
    down_beta = min(row.get('잔차4주_하락p', 1), row.get('잔차13주_하락p', 1)) <= 0.05
    up_hist = row['10년_13주상승p'] <= 0.05
    up_beta = min(row.get('잔차4주_상승p', 1), row.get('잔차13주_상승p', 1)) <= 0.05
    if down_hist and down_beta:
        s = '아주 예외적인 하락(10년 기준, 베타를 감안해도)'
    elif down_hist:
        s = '10년 기준 드문 하락(베타만큼 빠짐)'
    elif down_beta:
        s = '깊이는 평소, 최근 하락은 베타로 설명 안 됨'
    elif up_hist and up_beta:
        s = '너무 많이 오름(10년 기준, 베타를 감안해도)'
    elif up_hist:
        s = '10년 기준 드문 상승(베타만큼 오름)'
    elif up_beta:
        s = '최근 상승은 베타로 설명 안 됨'
    else:
        s = '평소 범위'
    row['예외 정리'] = s
    return row


try:
    eu = u[['번호', '정식 종목명', '시장', '구분', '층', 'yfinance 티커', '베타 기준지수']].copy() \
        if '층' in u.columns and '베타 기준지수' in u.columns else \
        u[['번호', '정식 종목명', '시장', '구분', 'yfinance 티커']].copy()
    eu['기준지수'] = [EXC_BENCH.get(str(b), EXC_MKT.get(m, '^GSPC'))
                    for b, m in zip(eu.get('베타 기준지수', pd.Series([None] * len(eu), index=eu.index)), eu['시장'])]
    tick = sorted(set(eu['yfinance 티커'].astype(str)) | set(eu['기준지수']))
    W = _exc_weekly(tick)
    rows, bad = [], []
    for _, r in eu.iterrows():
        t, b = str(r['yfinance 티커']), r['기준지수']
        if t not in W or b not in W:
            bad.append(t)
            continue
        try:
            rows.append({'yfinance 티커': t, '기준지수': b, **exc_row(W[t], W[b])})
        except Exception as e:
            bad.append(f'{t}({type(e).__name__})')
    ex = eu.drop(columns=['기준지수']).merge(pd.DataFrame(rows), on='yfinance 티커', how='left')
    ex['계산시각(KST)'] = NOW.strftime('%Y-%m-%d %H:%M')
    ex.to_csv(f'{DAY}/{TODAY}_예외검정.csv', index=False, encoding='utf-8-sig')
    n_down = int(ex['예외 정리'].fillna('').str.startswith('아주 예외적인 하락').sum())
    n_up = int(ex['예외 정리'].fillna('').str.startswith('너무 많이 오름').sum())
    log(f'[9 예외] {len(rows)}/{len(eu)}종목 | 아주 예외적 하락 {n_down} · 너무 많이 오름 {n_up} | '
        f'못 받음: {", ".join(bad[:10]) or "없음"}')
except Exception as e:
    traceback.print_exc()
    log(f'[9 예외] 실패: {type(e).__name__} {e}')
