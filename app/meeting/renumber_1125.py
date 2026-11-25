"""11/25 의장 "코드에서 기존 번호를 쓰던 것을 모두 새 번호로 바꿔. 기록도 바꿔. 다 바꿔."
옛 번호(G41·K01 …) → 층 번호(U0-1·K1-9 …)로 기록 파일을 한 번 바꾸는 일회용 코드. 다 바꾼 뒤 지운다.
- 옛→새는 드라이브 콜로키움/포트폴리오의 두 유니버스(옛 20261125b, 새 20261125d)를 맞대어 그 자리에서 만든다(표 파일 남기지 않음).
- 바꾸는 칸: 이름에 '번호'가 든 칸, 또는 값 절반 이상이 옛 번호 꼴(G12·K3)인 칸, 그리고 칸 이름이 옛 번호인 것.
- 지운 종목(새 유니버스에 없음)의 옛 번호는 그대로 둔다(지우기는 의장 허락 뒤).
- 바꾸기 전 원본은 같은 드라이브 아래 _옛번호_원본_1125/에 그대로 둔다.
쓰기: python renumber_1125.py drive          (Actions, DRIVE_URL·DRIVE_TOKEN)
      python renumber_1125.py local 폴더 옛.csv 새.csv"""
import gzip
import io
import os
import re
import sys

import pandas as pd

OLD = re.compile(r'^[GK]\d{1,3}$')
SKIP = re.compile(r'^(가격10년|거래량10년|지수_장기|시장위험_장기|노르웨이|_)')


def make_map(old_u, new_u):
    """새 유니버스(층 번호·번호 두 칸)와 옛 유니버스(중복 번호 포함)로 옛→새."""
    M = dict(zip(new_u['번호'].astype(str), new_u['층 번호'].astype(str)))
    t2n = dict(zip(new_u['yfinance 티커'].astype(str), new_u['층 번호'].astype(str)))
    for n, t in zip(old_u['번호'].astype(str), old_u['yfinance 티커'].astype(str)):
        if n not in M and t in t2n:
            M[n] = t2n[t]
    return M


def conv_df(df, M):
    """바뀐 칸 수(0이면 그대로)."""
    n = 0
    ren = {c: M[c] for c in df.columns if c in M}
    if ren:
        df.rename(columns=ren, inplace=True)
        n += len(ren)
    for c in df.columns:
        s = df[c]
        if not pd.api.types.is_string_dtype(s) and s.dtype != object:
            continue
        v = s.dropna().astype(str).str.strip()
        if not len(v):
            continue
        if '번호' in str(c) or v.str.match(OLD).mean() > 0.5:
            new = s.map(lambda x: M.get(str(x).strip(), x) if isinstance(x, str) else x)
            if not new.equals(s):
                df[c] = new
                n += 1
    return n


def conv_bytes(name, b, M):
    """파일 bytes → (바뀐 bytes 또는 None, 바뀐 칸 수)."""
    gz = name.endswith('.gz')
    raw = gzip.decompress(b) if gz else b
    try:
        df = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False, na_values=[''], encoding='utf-8-sig', low_memory=False)
    except Exception:
        return None, 0
    n = conv_df(df, M)
    if not n:
        return None, 0
    df.columns = ['' if str(c).startswith('Unnamed: ') else c for c in df.columns]
    out = ('\ufeff' + df.to_csv(index=False)).encode('utf-8')
    return (gzip.compress(out) if gz else out), n


def run_drive():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'collect'))
    import drive
    P, D = '콜로키움/포트폴리오', '콜로키움 수집데이터'
    rd = lambda p: pd.read_csv(io.BytesIO(drive.get(p)), dtype=str, encoding='utf-8-sig')
    M = make_map(rd(f'{P}/콜로키움100_유니버스_20261125b.csv'), rd(f'{P}/콜로키움_유니버스_20261125d.csv'))
    print('옛 번호', len(M))
    folders = [f'{D}/00_퀀트입력', f'{D}/1_data', f'{D}/1_data/장기', f'{D}/00_누적', f'{D}/start']
    done = []
    for fd in folders:
        try:
            fs = drive.ls(fd)
        except Exception as e:   # noqa: BLE001
            print('목록 실패', fd, e); continue
        for f in fs:
            nm = f['name']
            if not nm.endswith(('.csv', '.csv.gz')) or SKIP.match(nm) or int(f.get('size') or 0) > 60_000_000:
                continue
            try:
                b = drive.get(f'{fd}/{nm}')
                if b is None:
                    continue
                nb, n = conv_bytes(nm, b, M)
                if nb is None:
                    continue
                bak = f'{D}/_옛번호_원본_1125/{fd.replace(D + "/", "").replace("/", "_")}/{nm}'
                drive.put(bak, b)
                drive.put(f'{fd}/{nm}', nb)
                done.append(f'{fd}/{nm}({n}칸)')
                print('바꿈', fd, nm, n)
            except Exception as e:   # noqa: BLE001
                print('실패', fd, nm, e)
    # 새 유니버스: 층 번호 하나로(옛 번호 칸 없앰)
    U = rd(f'{P}/콜로키움_유니버스_20261125d.csv')
    U = U.drop(columns=['번호']).rename(columns={'층 번호': '번호'})
    drive.put(f'{P}/콜로키움100_유니버스_20261125e.csv', ('\ufeff' + U.to_csv(index=False)).encode('utf-8'))
    print('유니버스 20261125e', len(U))
    print('바꾼 파일', len(done))
    for x in done:
        print(' -', x)


def run_local(folder, old_csv, new_csv):
    M = make_map(pd.read_csv(old_csv, dtype=str, encoding='utf-8-sig'), pd.read_csv(new_csv, dtype=str, encoding='utf-8-sig'))
    n_files = 0
    for root, _, files in os.walk(folder):
        for nm in files:
            if not nm.endswith(('.csv', '.csv.gz')) or SKIP.match(nm) or '유니버스' in nm:   # 유니버스 파일 자체·지운 줄 목록은 그대로
                continue
            p = os.path.join(root, nm)
            if os.path.getsize(p) > 60_000_000:
                continue
            nb, n = conv_bytes(nm, open(p, 'rb').read(), M)
            if nb is not None:
                open(p, 'wb').write(nb)
                n_files += 1
                print('바꿈', p, n)
    print('바꾼 파일', n_files)


if __name__ == '__main__':
    if sys.argv[1] == 'drive':
        run_drive()
    else:
        run_local(*sys.argv[2:5])
