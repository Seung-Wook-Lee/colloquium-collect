import html, re, sys
src='/mnt/project-files/퀀트센터/종목추천_Ver.20261116_1430.txt'; out='/mnt/project-files/퀀트센터/종목추천_20261116_1430.pdf'
T=open(src,encoding='utf-8').read().split('\n')
h=[]; card=False
def close():
    global card
    if card: h.append('</div>'); card=False
for ln in T:
    e=html.escape(ln)
    if not ln.strip(): continue
    if T.index(ln)==0: h.append(f'<h1>{e}</h1>'); continue
    if re.match(r'^\d\. ',ln): close(); h.append(f'<h2>{e}</h2>'); continue
    if ln.startswith('■'):
        close(); card=True; h.append(f'<div class="card"><h3>{e[1:].strip()}</h3>'); continue
    if ln.startswith('  [') :
        k,v=ln.strip().split('] ',1); items=''.join(f'<span class="chip">{html.escape(x)}</span>' for x in re.split(r', (?=[^,]*? 싼가 )',v))
        h.append(f'<div class="pool"><b>{html.escape(k[1:])}</b> {items}</div>'); continue
    m=re.match(r'^\s+([^:：]{1,22}):\s(.*)$',ln)
    if card and m: h.append(f'<div class="row"><span class="k">{html.escape(m.group(1).strip())}</span><span class="v">{html.escape(m.group(2))}</span></div>'); continue
    cls='note' if ln.startswith('자료') else 'line'
    h.append(f'<div class="{cls}">{e.strip()}</div>')
close()
css='''@page{size:A4;margin:14mm 12mm}body{font-family:"Noto Sans CJK KR","Noto Sans KR",sans-serif;color:#1d2433;font-size:9.6pt;line-height:1.45}
h1{font-size:16pt;margin:0 0 4px;color:#0b3d6e}h2{font-size:12pt;color:#fff;background:#0b3d6e;padding:4px 8px;border-radius:4px;margin:14px 0 6px}
h3{font-size:11pt;margin:0 0 4px;color:#0b3d6e;border-bottom:1px solid #d6dfea;padding-bottom:3px}
.note{color:#6b7585;font-size:8.5pt;margin-bottom:6px}.line{margin:2px 0 2px 4px}
.card{border:1px solid #d6dfea;border-left:4px solid #2f80c9;border-radius:6px;padding:7px 10px;margin:8px 0;break-inside:avoid;background:#fbfcfe}
.row{display:flex;gap:8px;margin:1px 0}.k{flex:0 0 92px;white-space:nowrap;color:#2f80c9;font-weight:600}.v{flex:1}
.pool{margin:4px 0}.chip{display:inline-block;background:#eef3f9;border-radius:10px;padding:1px 7px;margin:2px 3px;font-size:8.3pt}'''
doc=f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{"".join(h)}</body></html>'
open('/tmp/claude-0/-home-user/40351794-6060-59ec-aa9e-a0a3ccf2f31c/scratchpad/rep.html','w').write(doc)
print('ok')
