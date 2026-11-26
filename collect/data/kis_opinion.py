"""국내 증권사 투자의견(보고서 날짜·증권사·의견·목표가) — 한투 FHKST663300C0 → 10년치 데이터베이스 칸 '투자의견'
(드라이브 1_data/가격10년_투자의견.csv.gz). 11/26 의장 "최근 일주일 보고서만 참고해", "지금 바로 해".
처음엔 90일, 그다음은 칸의 마지막 날 3일 전부터만 받아 덧붙인다(11/25 의장: 통째로 다시 받기 금지). 새 파일 만들지 않음."""
import datetime as dt
import os
import sys
import tempfile

import pandas as pd

sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), os.path.dirname(os.path.abspath(__file__))]
import drive  # noqa: E402
import kis  # noqa: E402
import px_store as PS  # noqa: E402

KAN = '투자의견'
COLS = ['날짜', '코드', '종목', '증권사', '의견', '이전의견', '목표가', '전일종가']


def main():
    U = PS.universe(drive)
    K = U[(U['시장'] == '한국') & (U['구분'] == '개별주')].dropna(subset=['코드'])
    K = K.assign(코드=K['코드'].astype(str).str.zfill(6)).drop_duplicates('코드')
    tmp = tempfile.mkdtemp()
    PS.fetch(drive, KAN, tmp)
    old = PS.table(tmp, KAN, dtype={'코드': str}, parse_dates=['날짜'])
    days = 90 if old.empty else max(5, (dt.date.today() - old['날짜'].max().date()).days + 3)
    parts, rep = [], []
    for i, (c, nm) in enumerate(zip(K['코드'], K['정식 종목명'] if '정식 종목명' in K else K['코드'])):
        d = kis.opinion_kr(c, days=days, probe=(i == 0))
        rep.append(f'{c} {nm} {len(d)}건' + (f' 마지막 {d["날짜"].max():%Y-%m-%d}' if len(d) else ''))
        if len(d):
            parts.append(d.assign(코드=c, 종목=nm))
    new = pd.concat(parts) if parts else pd.DataFrame(columns=COLS)
    D = pd.concat([new, old]) if not old.empty else new
    D = D[COLS].drop_duplicates(['날짜', '코드', '증권사', '의견', '목표가'], keep='first').sort_values(['코드', '날짜'])
    print('\n'.join(rep)); print('투자의견 칸', D.shape, '받은 기간', days, '일')
    if drive.ready() and len(D):
        PS.put_table(tmp, KAN, D)
        drive.put(f'{PS.BASE}/1_data/{PS.name(KAN)}', open(f'{tmp}/{PS.name(KAN)}', 'rb').read())
        print('드라이브 저장', PS.name(KAN))


if __name__ == '__main__':
    main()
