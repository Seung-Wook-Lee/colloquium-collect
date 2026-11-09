# ======================================================================
# [블록 9-일본] 아야카 상 — 일본 날씨 한 줄, 일본 종목 주봉 위치, 주간 밸류 스냅숏, 실적 달력, TDnet 공시
#   하는 일  : (가) 일본 날씨: TOPIX(1306.T ETF로 대신)·닛케이225·J-REIT(1343.T ETF로 대신)의 20·60주선 위치,
#                  엔/달러(블록 3), 일본 10년(블록 3 재무성) → 브리핑 한 줄
#              (나) 콜로키움 100의 일본 종목: 주봉 종가, 20·60주선 이격, 주봉 RSI(와일더 14), 52주 고점 대비 (기술적 분석만)
#              (다) 매주 토요일(또는 지난 스냅숏이 7일 넘었으면) 야후 현재 PER·선행 PER·PBR·배당수익률·시총·다음 실적일을
#                  00_누적에 한 줄씩 쌓는다. 과거 재무 이력은 받지 않는다(EDINET 연결 안 함, 11/7 의장). 1~2년 뒤 우리 이력이 된다.
#              (라) 실적 달력: 스냅숏 때 야후 '다음 실적일'로 00_일본_실적달력.csv를 갱신(종목당 최신 한 줄)
#              (마) TDnet(도쿄거래소 적시공시) 그날 목록에서 우리 일본 종목만 골라 자사주·자본비용(PBR 개선)·배당·실적 공시를 쌓는다
#   소스     : 야후(키 없음), TDnet www.release.tdnet.info/inbs/I_list_NNN_YYYYMMDD.html (키 없음, 31일 보관)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_일본.csv (날씨 + 종목), YYYYMMDD_일본.txt (아야카 상 한 장)
#              수집데이터/00_누적/00_일본_밸류스냅숏.csv, 00_일본_실적달력.csv, 00_일본공시_누적.csv
#   쓰는 위원: 아야카 상(일본 전담, 2026-11-07 의장), 리오(일본 날씨 참고)
#   실패하면 : 부분마다 따로 건너뛰고 점검 파일에 남긴다
# ======================================================================
import re as _re, html as _html

JP_WEATHER = [('TOPIX', '1306.T', 'TOPIX ETF(1306)로 대신'), ('닛케이225', '^N225', ''),
              ('J-REIT', '1343.T', '동증 REIT 지수 ETF(1343)로 대신, 부동산 참고')]
JP_KIND = [('자사주', ('自己株式', '自社株')),
           ('자본비용·PBR', ('資本コスト', '株価を意識', '企業価値向上', '資本効率', '中期経営計画')),
           ('배당', ('配当', '株主還元')),
           ('실적', ('決算短信', '業績予想', '決算説明'))]
JP_ROWS, JP_LINES = [], []


def _wk_close(t):
    h = yf.Ticker(t).history(period='3y', interval='1wk', auto_adjust=True)
    return h['Close'].dropna() if len(h) else None


def _rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def _pos(s):
    """주봉 종가 → (종가, 20주선, 60주선, 20주 이격 %, 60주 이격 %, 위치 글)"""
    c, m20, m60 = float(s.iloc[-1]), float(s.rolling(20).mean().iloc[-1]), float(s.rolling(60).mean().iloc[-1])
    g20, g60 = (c / m20 - 1) * 100, (c / m60 - 1) * 100
    where = f'20주선 {"위" if g20 >= 0 else "아래"}·60주선 {"위" if g60 >= 0 else "아래"}'
    return c, m20, m60, g20, g60, where


jp = u[u['시장'] == '일본'].copy()

# (가) 일본 날씨
try:
    parts = []
    for name, t, note in JP_WEATHER:
        s = _wk_close(t)
        if s is None or len(s) < 61:
            parts.append(f'{name} 데이터 없음')
            continue
        c, m20, m60, g20, g60, where = _pos(s)
        JP_ROWS.append({'구분': '날씨', '항목': name, '티커': t, '기준주': s.index[-1].strftime('%Y-%m-%d'), '주봉 종가': round(c, 2),
                        '20주선': round(m20, 2), '60주선': round(m60, 2), '20주 이격(%)': round(g20, 1), '60주 이격(%)': round(g60, 1),
                        '위치': where, '비고': note})
        parts.append(f'{name} {where}(20주 {g20:+.1f}%, 60주 {g60:+.1f}%)')
    fx = YS.get('엔/달러') if 'YS' in globals() else None
    if fx is not None and len(fx) > 6:
        v, w = float(fx.iloc[-1]), at_or_before(fx, fx.index[-1] - pd.Timedelta(days=7))
        side = '' if w is None else (' 엔 약세 쪽' if v > w else ' 엔 강세 쪽')
        JP_ROWS.append({'구분': '날씨', '항목': '엔/달러', '티커': 'JPY=X', '기준주': fx.index[-1].strftime('%Y-%m-%d'),
                        '주봉 종가': round(v, 2), '비고': f'1주 전 {w:.2f}' if w else ''})
        parts.append(f'엔/달러 {v:.2f}' + (f'(1주 {v - w:+.2f},{side})' if w else ''))
    if 'JP10' in globals() and JP10 is not None and len(JP10) > 20:
        v, mo = float(JP10.iloc[-1]), at_or_before(JP10, JP10.index[-1] - pd.DateOffset(months=1))
        JP_ROWS.append({'구분': '날씨', '항목': '일본 10년', '티커': '재무성', '기준주': JP10.index[-1].strftime('%Y-%m-%d'),
                        '주봉 종가': round(v, 3), '비고': f'1달 전 {mo:.3f}' if mo else ''})
        parts.append(f'일본 10년 {v:.3f}%' + (f'(1달 {v - mo:+.2f}%p)' if mo else ''))
    JP_LINES.append('[일본 날씨] ' + ' | '.join(parts))
    log(f'[9 일본] 날씨: {" | ".join(parts)}')
except Exception as e:
    traceback.print_exc()
    log(f'[9 일본] 날씨 실패: {type(e).__name__} {e}')

# (나) 일본 종목 주봉 위치 (기술적 분석만)
try:
    ok = 0
    for _, r in jp.iterrows():
        try:
            s = _wk_close(r['yfinance 티커'])
        except Exception:
            s = None
        if s is None or len(s) < 61:
            continue
        c, m20, m60, g20, g60, where = _pos(s)
        hi52 = float(s.iloc[-52:].max())
        JP_ROWS.append({'구분': '종목', '항목': r['정식 종목명'], '번호': r['번호'], '티커': r['yfinance 티커'], '보유/관심': r['보유/관심'],
                        '기준주': s.index[-1].strftime('%Y-%m-%d'), '주봉 종가': round(c, 1), '20주선': round(m20, 1),
                        '60주선': round(m60, 1), '20주 이격(%)': round(g20, 1), '60주 이격(%)': round(g60, 1), '위치': where,
                        '주봉 RSI': round(float(_rsi(s).iloc[-1]), 1), '52주 고점 대비(%)': round((c / hi52 - 1) * 100, 1)})
        ok += 1
        time.sleep(0.3)
    log(f'[9 일본] 종목 주봉 {ok}/{len(jp)}')
except Exception as e:
    traceback.print_exc()
    log(f'[9 일본] 종목 주봉 실패: {type(e).__name__} {e}')

# (다)(라) 주간 밸류 스냅숏 + 실적 달력
SNAP, CAL = f'{KEEP}/00_일본_밸류스냅숏.csv', f'{KEEP}/00_일본_실적달력.csv'
try:
    old = pd.read_csv(SNAP, encoding='utf-8-sig', dtype={'번호': str}) if os.path.exists(SNAP) else None
    last_d = pd.to_datetime(old['날짜']).max() if old is not None and len(old) else None
    due = NOW.weekday() == 5 or last_d is None or (pd.Timestamp(NOW.date()) - last_d).days >= 7
    if old is not None and (old['날짜'] == NOW.strftime('%Y-%m-%d')).any():
        due = False
    if due:
        def _ts(x):
            try:
                return dt.datetime.fromtimestamp(int(x), KST).strftime('%Y-%m-%d') if x else ''
            except Exception:
                return ''

        rows, cal = [], []
        for _, r in jp.iterrows():
            t = r['yfinance 티커']
            try:
                i = yf.Ticker(t).info or {}
            except Exception as e:
                print('  야후 정보 실패', t, e)
                i = {}
            ds = sorted({_ts(i.get(k)) for k in ('earningsTimestamp', 'earningsTimestampStart', 'earningsTimestampEnd')} - {''})
            today_s = NOW.strftime('%Y-%m-%d')
            nxt = next((x for x in ds if x >= today_s), '')
            prev = max((x for x in ds if x < today_s), default='')
            ty = i.get('trailingAnnualDividendYield')
            rows.append({'날짜': NOW.strftime('%Y-%m-%d'), '번호': r['번호'], '종목': r['정식 종목명'], '티커': t,
                         '종가(엔)': i.get('regularMarketPrice') or i.get('currentPrice'),
                         'PER TTM': i.get('trailingPE'), '선행 PER': i.get('forwardPE'), 'PBR': i.get('priceToBook'),
                         '배당수익률 예상(%)': i.get('dividendYield'),
                         '배당수익률 직전12개월(%)': round(ty * 100, 2) if isinstance(ty, (int, float)) else None,
                         'ROE(%)': round(i['returnOnEquity'] * 100, 1) if isinstance(i.get('returnOnEquity'), (int, float)) else None,
                         '시총(억엔)': round(i['marketCap'] / 1e8) if i.get('marketCap') else None,
                         '다음 실적일(야후)': nxt, '지난 실적일(야후)': prev, '배당락일(야후)': _ts(i.get('exDividendDate')), '출처': '야후 info'})
            cal.append({'번호': r['번호'], '종목': r['정식 종목명'], '티커': t, '다음 실적일(야후)': nxt, '지난 실적일(야후)': prev,
                        '배당락일(야후)': _ts(i.get('exDividendDate')), '확인': '야후 예정일(회사 공지 아님)',
                        '갱신일': NOW.strftime('%Y-%m-%d')})
            time.sleep(0.4)
        new = pd.DataFrame(rows)
        (pd.concat([old, new]) if old is not None else new).to_csv(SNAP, index=False, encoding='utf-8-sig')
        pd.DataFrame(cal).sort_values('다음 실적일(야후)').to_csv(CAL, index=False, encoding='utf-8-sig')
        log(f'[9 일본] 밸류 스냅숏 저장 {new["PBR"].notna().sum()}/{len(new)}종목 (누적 {0 if old is None else old["날짜"].nunique()}+1주)')
    else:
        log(f'[9 일본] 밸류 스냅숏: 이번 주 이미 있음(마지막 {last_d:%Y-%m-%d}), 토요일에 새로')
    if os.path.exists(CAL):
        c = pd.read_csv(CAL, encoding='utf-8-sig', dtype=str).fillna('')
        soon = c[(c['다음 실적일(야후)'] >= NOW.strftime('%Y-%m-%d')) &
                 (c['다음 실적일(야후)'] <= (NOW + dt.timedelta(days=21)).strftime('%Y-%m-%d'))]
        JP_LINES.append('[일본 실적 3주 안(야후 예정일)] ' + (', '.join(f'{a} {b[5:]}' for a, b in soon[['종목', '다음 실적일(야후)']].values) or '없음'))
except Exception as e:
    traceback.print_exc()
    log(f'[9 일본] 밸류 스냅숏 실패: {type(e).__name__} {e}')

# (마) TDnet 적시공시: 우리 일본 종목만, 오늘·어제(주말 뒤면 사흘)
DISC = f'{KEEP}/00_일본공시_누적.csv'
try:
    codes = {str(c).strip()[:4]: n for c, n in zip(jp['코드'], jp['정식 종목명'])}
    hits, pages = [], 0
    for back in range(0, 4 if NOW.weekday() == 0 else 2):
        d = (NOW - dt.timedelta(days=back)).strftime('%Y%m%d')
        for p in range(1, 21):
            r = get(f'https://www.release.tdnet.info/inbs/I_list_{p:03d}_{d}.html', retry=1)
            if r is None:
                break
            r.encoding = 'utf-8'
            pages += 1
            for tr in _re.findall(r'<tr>(.*?)</tr>', r.text, _re.S):
                m = {k: _re.search(rf'kj{k}"[^>]*>(.*?)</td>', tr, _re.S) for k in ('Time', 'Code', 'Name', 'Title')}
                if not m['Code']:
                    continue
                code = _re.sub(r'<[^>]+>', '', m['Code'].group(1)).strip()[:4]
                if code not in codes:
                    continue
                title = _html.unescape(_re.sub(r'<[^>]+>', '', m['Title'].group(1))).strip()
                pdf = _re.search(r'href="([^"]+\.pdf)"', m['Title'].group(1))
                kind = next((k for k, keys in JP_KIND if any(x in title for x in keys)), '기타')
                hits.append({'날짜': f'{d[:4]}-{d[4:6]}-{d[6:]}', '시각': _re.sub(r'<[^>]+>', '', m['Time'].group(1)).strip(),
                             '코드': code, '종목': codes[code], '구분': kind, '제목(원문)': title,
                             'PDF': f'https://www.release.tdnet.info/inbs/{pdf.group(1)}' if pdf else ''})
            if 'I_list_%03d_%s' % (p + 1, d) not in r.text:
                break
    if pages == 0:
        raise RuntimeError('TDnet 목록을 하나도 못 받음(접속 차단 또는 주소 변경)')
    old = pd.read_csv(DISC, encoding='utf-8-sig', dtype=str) if os.path.exists(DISC) else None
    allr = pd.concat([old, pd.DataFrame(hits, dtype=str)]) if old is not None else pd.DataFrame(hits, dtype=str)
    if len(allr):
        allr = allr.drop_duplicates(['날짜', '시각', '코드', '제목(원문)']).sort_values(['날짜', '시각'])
        allr.to_csv(DISC, index=False, encoding='utf-8-sig')
    key = [h for h in hits if h['구분'] != '기타']
    JP_LINES.append('[일본 공시(TDnet) 자사주·자본비용·배당·실적] '
                    + ('; '.join(f'{h["종목"]} {h["날짜"][5:]} {h["구분"]}: {h["제목(원문)"]}' for h in key) or '없음'))
    log(f'[9 일본] TDnet {pages}쪽 | 우리 종목 공시 {len(hits)}건(주요 {len(key)}건)')
except Exception as e:
    traceback.print_exc()
    JP_LINES.append('[일본 공시(TDnet)] 수집 실패(점검 파일 참고)')
    log(f'[9 일본] TDnet 실패: {type(e).__name__} {e}')

# 저장
try:
    if JP_ROWS:
        pd.DataFrame(JP_ROWS).to_csv(f'{DAY}/{TODAY}_일본.csv', index=False, encoding='utf-8-sig')
    st = [r for r in JP_ROWS if r['구분'] == '종목']
    body = [f'아야카 상 일본 한 장 {TODAY}'] + JP_LINES + ['', '[일본 종목 주봉] 종목: 위치 | 20주·60주 이격 | 주봉 RSI | 52주 고점 대비']
    body += [f'- {r["항목"]}({r["보유/관심"]}): {r["위치"]} | {r["20주 이격(%)"]:+.1f}% · {r["60주 이격(%)"]:+.1f}% | '
             f'RSI {r["주봉 RSI"]:.0f} | {r["52주 고점 대비(%)"]:+.1f}%' for r in st] or ['- 없음']
    open(f'{DAY}/{TODAY}_일본.txt', 'w', encoding='utf-8').write('\n'.join(body) + '\n')
except Exception as e:
    traceback.print_exc()
    log(f'[9 일본] 저장 실패: {type(e).__name__} {e}')
