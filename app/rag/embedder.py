# ======================================================================
# 위원 자료 검색 — 3단계: 문단의 '뜻'을 숫자 좌표(벡터)로 바꾼다
#   gemini : 제미나이 임베딩(gemini-embedding-001, 768차원). 키는 GEMINI_API_KEY(Actions는 Secrets,
#            클로드 작업 창은 연결된 제미나이가 자동으로 넣어 줌). 100문단씩 묶어 보낸다.
#   bge-m3 : 무료 공개 모델을 내려받아 직접 돌림(sentence-transformers 필요, Actions 전용 — 작업 창은 내려받기가 막힘)
#   문서 쪽은 RETRIEVAL_DOCUMENT, 질문 쪽은 RETRIEVAL_QUERY로 따로 바꾼다(검색용으로 맞춘 좌표).
#   좌표는 길이 1로 맞춰 저장 → 코사인 유사도 = 곱셈 한 번.
# ======================================================================
import os, time
import numpy as np
import requests
import config as C

API = 'https://generativelanguage.googleapis.com/v1beta'


def _unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)


_SENT = []   # 최근 1분 동안 보낸 (시각, 문단 수, 토큰 어림) — 무료 한도(분당 100문단·약 3만 토큰)를 넘지 않게 천천히


class DailyLimit(RuntimeError):
    pass


def _pace(n, tok):
    def over():
        return _SENT and (sum(x[1] for x in _SENT) + n > C.GEMINI_PER_MIN or sum(x[2] for x in _SENT) + tok > C.GEMINI_TOK_PER_MIN)
    now = time.time()
    _SENT[:] = [x for x in _SENT if now - x[0] < 60]
    while over():
        time.sleep(max(1, 60 - (now - _SENT[0][0]) + 1))
        now = time.time()
        _SENT[:] = [x for x in _SENT if now - x[0] < 60]
    _SENT.append((now, n, tok))


def _batches(texts):
    """문단 수(GEMINI_BATCH)와 토큰 어림(GEMINI_TOK_PER_REQ) 둘 다 넘지 않게 묶는다."""
    i = 0
    while i < len(texts):
        j, tok = i, 0
        while j < len(texts) and j - i < C.GEMINI_BATCH and (j == i or tok + _tok(texts[j]) <= C.GEMINI_TOK_PER_REQ):
            tok += _tok(texts[j])
            j += 1
        yield i, j, tok
        i = j


def _tok(t):
    return int(min(len(t), 6000) * 0.85) + 10     # 한국어 1글자 ≈ 0.8토큰(실측 0.78)


def _gemini(texts, task, titles=None):
    key = os.environ.get('GEMINI_API_KEY', '').strip() or 'dummy'   # 작업 창에서는 프록시가 진짜 키로 바꿔 넣음
    url = f'{API}/models/{C.GEMINI_EMBED_MODEL}:batchEmbedContents'
    out = []
    for i, end, tok in _batches(texts):
        reqs = []
        for j, t in enumerate(texts[i:end]):
            r = {'model': f'models/{C.GEMINI_EMBED_MODEL}', 'content': {'parts': [{'text': t[:6000]}]},
                 'taskType': task, 'outputDimensionality': C.GEMINI_DIM}
            if titles and task == 'RETRIEVAL_DOCUMENT':
                r['title'] = titles[i + j][:200]
            reqs.append(r)
        _pace(len(reqs), tok)
        for n in range(8):
            try:
                resp = requests.post(url, headers={'x-goog-api-key': key}, json={'requests': reqs}, timeout=120)
                if resp.status_code == 429 and 'PerDay' in resp.text:
                    raise DailyLimit('제미나이 임베딩 하루 한도를 다 썼습니다. 받아 둔 것은 저장했고, 내일 다시 돌리면 이어서 합니다.')
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise RuntimeError(f'{resp.status_code} {resp.text[:400]}')
                resp.raise_for_status()
                out += [e['values'] for e in resp.json()['embeddings']]
                break
            except DailyLimit:
                raise
            except Exception as e:
                if n == 7:
                    raise
                wait = 65 if '429' in str(e) else min(90, 10 * (n + 1))
                print(f'  임베딩 재시도 {n + 1} ({str(e)[:80]}) {wait}초 뒤', flush=True)
                time.sleep(wait)
        if len(texts) > C.GEMINI_BATCH:
            print(f'  임베딩 {end}/{len(texts)}', flush=True)
    return _unit(out)


_ST = None


def _bge(texts, task):
    global _ST
    if _ST is None:
        from sentence_transformers import SentenceTransformer
        _ST = SentenceTransformer('BAAI/bge-m3', device='cpu')
    return _unit(_ST.encode(texts, batch_size=16, normalize_embeddings=True, show_progress_bar=len(texts) > 50))


def name():
    return f'gemini:{C.GEMINI_EMBED_MODEL}:{C.GEMINI_DIM}' if C.EMBEDDER == 'gemini' else 'bge-m3'


def embed_docs(texts, titles=None):
    return _gemini(texts, 'RETRIEVAL_DOCUMENT', titles) if C.EMBEDDER == 'gemini' else _bge(texts, 'doc')


def embed_query(text):
    return (_gemini([text], 'RETRIEVAL_QUERY') if C.EMBEDDER == 'gemini' else _bge([text], 'query'))[0]
