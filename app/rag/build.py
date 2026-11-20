# ======================================================================
# 위원 자료 검색 — 색인 만들기(1~3단계를 한 번에)
#   python rag/build.py            바뀐 문단만 새로 임베딩(매일 회의 전·자료를 넣은 뒤)
#   python rag/build.py --full     전부 다시
#   결과(색인 폴더, 기본 /mnt/project-files/위원검색/색인/):
#     문단.csv      문단 하나 = 한 줄(id, 출처, 줄, 날짜, 종류, 위원, 종목, 머리말, 글)
#     벡터.npy      문단.csv와 같은 순서의 좌표(float16)
#     색인정보.txt   언제·어떤 모델·몇 문단·위원별 문단 수·새로 넣은 문단 수
# ======================================================================
import argparse, collections, datetime as dt, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C          # noqa: E402
import chunker as K         # noqa: E402
import embedder as E        # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
COLS = ['id', 'vec_key', '출처', '줄', '날짜', '종류', '위원', '종목', '머리말', '글']


def load_old():
    p, v, info = f'{C.INDEX_DIR}/문단.csv', f'{C.INDEX_DIR}/벡터.npy', f'{C.INDEX_DIR}/색인정보.txt'
    if not (os.path.exists(p) and os.path.exists(v) and os.path.exists(info)):
        return {}
    if f'모델: {E.name()}' not in open(info, encoding='utf-8').read():
        print('모델이 바뀌어 전부 다시 임베딩합니다.')
        return {}
    old = pd.read_csv(p, dtype=str, keep_default_na=False)
    vec = np.load(v)
    keep = old['좌표'] != '대기' if '좌표' in old else np.ones(len(old), bool)
    return dict(zip(old['vec_key'][keep], vec[keep.values if hasattr(keep, 'values') else keep]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--full', action='store_true')
    a = ap.parse_args()
    os.makedirs(C.INDEX_DIR, exist_ok=True)
    tagger = K.StockTagger()
    files = K.list_files()
    rows = []
    for f in files:
        rows += K.chunks_of(f, tagger)
    df = pd.DataFrame(rows, columns=COLS).drop_duplicates('id')
    print(f'파일 {len(files)}개 → 문단 {len(df)}개')

    cache = {} if a.full else load_old()
    need = df[~df['vec_key'].isin(cache.keys())].drop_duplicates('vec_key')
    print(f'다시 쓰는 좌표 {df["vec_key"].isin(cache.keys()).sum()}개, 새로 임베딩 {len(need)}개 ({E.name()})')
    part = f'{C.INDEX_DIR}/.진행중_{E.name().replace(":", "_")}.npz'   # 중간에 끊겨도(한도 초과 등) 다음에 이어서
    if os.path.exists(part) and not a.full:
        z = np.load(part)
        cache.update(zip(z['keys'], z['vecs']))
        need = need[~need['vec_key'].isin(cache.keys())]
        print(f'지난번 이어서: {len(z["keys"])}개 받아 둔 것 사용, 남은 {len(need)}개')
    done_k, done_v = [], []
    for i in range(0, len(need), 200):
        b = need.iloc[i:i + 200]
        try:
            vecs = E.embed_docs([f'[{h}]\n{g}' for h, g in zip(b['머리말'], b['글'])], titles=list(b['머리말']))
        except E.DailyLimit as e:
            print(f'{e} (남은 {len(need) - i}개 — 이번 색인에서는 글자 검색으로만 잡히고 근거로는 안 씀)')
            break
        cache.update(zip(b['vec_key'], vecs))
        done_k += list(b['vec_key'])
        done_v += list(vecs)
        old = np.load(part) if os.path.exists(part) else None
        ks = np.concatenate([old['keys'], done_k]) if old is not None else np.array(done_k)
        vs = np.concatenate([old['vecs'], np.array(done_v, dtype=np.float16)]) if old is not None else np.array(done_v, dtype=np.float16)
        np.savez(part.replace('.npz', '.tmp.npz'), keys=ks, vecs=vs)
        os.replace(part.replace('.npz', '.tmp.npz'), part)
        done_k, done_v = [], []
        print(f'  {min(i + 200, len(need))}/{len(need)} 저장', flush=True)
    dim = len(next(iter(cache.values()))) if cache else 768
    zero = np.zeros(dim, dtype=np.float16)
    df['좌표'] = ['있음' if k in cache else '대기' for k in df['vec_key']]
    mat = np.stack([cache.get(k, zero) for k in df['vec_key']]).astype(np.float16)
    pending = int((df['좌표'] == '대기').sum())

    tmp = f'{C.INDEX_DIR}/.tmp'
    os.makedirs(tmp, exist_ok=True)
    df.to_csv(f'{tmp}/문단.csv', index=False, encoding='utf-8-sig')
    np.save(f'{tmp}/벡터.npy', mat)
    by_who = collections.Counter(w for ws in df['위원'] for w in ws.split('|'))
    by_kind = collections.Counter(df['종류'])
    info = [f'위원 자료 검색 색인 — {dt.datetime.now(KST):%Y-%m-%d %H:%M} KST',
            f'모델: {E.name()}',
            f'자료 뿌리: {C.ROOT}  (폴더 {", ".join(C.SOURCES)})',
            f'파일 {len(files)}개, 문단 {len(df)}개, 좌표 대기(하루 한도로 못 한 것) {pending}개',
            '위원별 문단(꼬리표, 공통=모든 위원이 봄): ' + ', '.join(f'{k} {v}' for k, v in by_who.most_common()),
            '종류별 문단: ' + ', '.join(f'{k} {v}' for k, v in by_kind.most_common()),
            f'종목 꼬리표 붙은 문단: {(df["종목"] != "").sum()}개']
    open(f'{tmp}/색인정보.txt', 'w', encoding='utf-8').write('\n'.join(info) + '\n')
    for n in ('문단.csv', '벡터.npy', '색인정보.txt'):     # 셋을 한꺼번에 바꿔 어긋나지 않게
        os.replace(f'{tmp}/{n}', f'{C.INDEX_DIR}/{n}')
    os.rmdir(tmp)
    if os.path.exists(part) and not pending:
        os.remove(part)
    print('\n'.join(info))


if __name__ == '__main__':
    main()
