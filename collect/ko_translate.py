"""영어 기사 제목·요약 → 한국어(11/20 의장: "모든 문장은 한글로 번역해").
제미나이(GEMINI_API_KEY) 한 번에 여러 줄. 한글이 이미 있으면 그대로 둔다. 실패하면 빈 칸(원문은 화면·원고에 작게 남는다)."""
import json
import os
import re
import time

import requests

API = 'https://generativelanguage.googleapis.com/v1beta'
MODELS = ['gemini-3.5-flash', 'gemini-flash-latest', 'gemini-3.5-flash-lite', 'gemini-flash-lite-latest']   # 11/21: 2.5는 404(서비스 종료)
HANGUL = re.compile('[가-힣]')
PROMPT = '''아래 영어 경제 기사 문장을 한국어로 번역하라. 신문 제목·요약 문체로 짧고 정확하게.
회사·지수·인명은 한국 언론이 쓰는 표기(엔비디아, 앤트로픽, S&P500 등). 숫자·단위는 원문 그대로. 원문에 없는 말을 보태지 않는다.
JSON 배열 하나로만 답하라. 입력 순서와 같은 길이의 문자열 배열.

{items}'''


def need(s):
    s = '' if s is None else str(s)
    return bool(s.strip()) and s.lower() != 'nan' and not HANGUL.search(s)


def translate(texts, batch=40, log=print):
    """texts(list) → 같은 길이의 한국어 list. 한글이 있거나 빈 칸은 ''(번역 불필요)."""
    out = [''] * len(texts)
    key = os.environ.get('GEMINI_API_KEY')
    idx = [i for i, t in enumerate(texts) if need(t)]
    if not key or not idx:
        if idx:
            log('  번역: 제미나이 키 없음 → 원문 그대로')
        return out
    for k in range(0, len(idx), batch):
        part = idx[k:k + batch]
        items = json.dumps([str(texts[i])[:400] for i in part], ensure_ascii=False)
        for m in MODELS:
            ans = None
            for n in range(2):
                try:
                    r = requests.post(f'{API}/models/{m}:generateContent', headers={'x-goog-api-key': key}, timeout=120,
                                      json={'contents': [{'role': 'user', 'parts': [{'text': PROMPT.format(items=items)}]}],
                                            'generationConfig': {'temperature': 0.1, 'responseMimeType': 'application/json'}})
                    if r.status_code in (429, 500, 502, 503, 504) and n == 0:
                        time.sleep(20)
                        continue
                    r.raise_for_status()
                    txt = ''.join(p.get('text', '') for p in r.json()['candidates'][0]['content']['parts'])
                    ans = json.loads(re.sub(r'^```(json)?|```$', '', txt.strip()).strip())
                except Exception as e:
                    log(f'  번역 {m} 실패: {type(e).__name__} {str(e)[:100]}')
                break
            if isinstance(ans, list) and len(ans) == len(part):
                for i, t in zip(part, ans):
                    out[i] = str(t).strip()
                break
    log(f'  번역: {sum(1 for i in idx if out[i])}/{len(idx)}줄')
    return out
