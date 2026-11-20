# ======================================================================
# [블록 9-감성] 제2의 젠슨 황 있나 — 뉴스 감성(FinBERT) (2026-11-19 의장, 퀀트센터 B20)
#   하는 일  : 오늘 모은 뉴스(블록 9 b09_news, 국내외)의 제목+요약을 금융 감성 모델로 긍정·중립·부정 확률을 매긴다.
#              영어 = ProsusAI/finbert, 한국어 = snunlp/KR-FinBert-SC(서울대). 같은 문장에는 늘 같은 답(사람·AI 판단 없음).
#   소스     : 허깅페이스 공개 모델(무료, 처음 한 번 약 400MB씩 받음)
#   읽는 것  : 수집데이터/YYYYMMDD/YYYYMMDD_뉴스.csv
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_뉴스감성.csv (시각, 제목, 종목, 출처, 언어, 모델, 부정, 중립, 긍정)
#   쓰는 곳  : 퀀트센터 B20 '제2의 젠슨 황 있나?'(강한 부정 뉴스 + 주가 급락이 겹치면 거름)
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
SENT_MODELS = {'영어': 'ProsusAI/finbert', '한국어': 'snunlp/KR-FinBert-SC'}

try:
    import re as _re2
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
    NW = pd.read_csv(f'{DAY}/{TODAY}_뉴스.csv', encoding='utf-8-sig')
    NW['문장'] = (NW['제목'].fillna('').astype(str) + '. ' + NW['요약'].fillna('').astype(str)).str.slice(0, 600)
    NW['언어'] = ['한국어' if _re2.search('[가-힣]', t) else '영어' for t in NW['제목'].fillna('').astype(str)]
    rows = []
    for lang, name in SENT_MODELS.items():
        sub = NW[NW['언어'] == lang]
        if not len(sub):
            continue
        tok = AutoTokenizer.from_pretrained(name)
        mdl = AutoModelForSequenceClassification.from_pretrained(name).eval()
        lab = {i: str(v).lower() for i, v in mdl.config.id2label.items()}
        for i in range(0, len(sub), 16):
            part = sub.iloc[i:i + 16]
            enc = tok(list(part['문장']), padding=True, truncation=True, max_length=256, return_tensors='pt')
            with torch.no_grad():
                pr = torch.softmax(mdl(**enc).logits, dim=-1).numpy()
            for (_, r), p in zip(part.iterrows(), pr):
                d = {lab[j]: float(p[j]) for j in range(len(p))}
                rows.append({'시각': r.get('시각'), '제목': r['제목'], '종목': r.get('종목'), '출처': r.get('출처'), '언어': lang, '모델': name,
                             '부정': round(d.get('negative', 0), 3), '중립': round(d.get('neutral', 0), 3), '긍정': round(d.get('positive', 0), 3)})
    out = pd.DataFrame(rows)
    out.to_csv(f'{DAY}/{TODAY}_뉴스감성.csv', index=False, encoding='utf-8-sig')
    strong = int((out['부정'] >= 0.9).sum()) if len(out) else 0
    log(f'[9 감성] 뉴스 {len(out)}건 감성 매김, 강한 부정(≥0.9) {strong}건')
except Exception as e:
    traceback.print_exc()
    log(f'[9 감성] 실패: {type(e).__name__} {e}')
