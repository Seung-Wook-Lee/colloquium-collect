# 일회성: ICI MMF 주간 잔고를 어디서 받을 수 있나(본문·엑셀·RSS) 상태 코드와 첫 부분을 본다
import requests, re
H1 = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.9'}
for url in ['https://www.ici.org/research/stats/mmf', 'https://www.ici.org/mm_summary_data_2026.xls',
            'https://www.ici.org/research/stats', 'https://www.ici.org/rss.xml', 'https://www.ici.org/news-release',
            'https://r.jina.ai/https://www.ici.org/research/stats/mmf']:
    for h in (H1, {'User-Agent': 'colloquium-collect/1.0'}):
        try:
            r = requests.get(url, headers=h, timeout=30)
            t = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', r.text))
            i = t.find('Total money market')
            print(url, h['User-Agent'][:12], r.status_code, len(r.content), r.headers.get('server'), '|', t[i:i + 300] if i >= 0 else t[:200])
            xs = re.findall(r'href="([^"]*mm_summary[^"]*)"', r.text)
            if xs: print('  XLS', xs[:5])
        except Exception as e:
            print(url, 'EXC', e)
