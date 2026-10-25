"""Ask the UrbanCart channel-metrics agent from the command line or a small local web UI.

    python Part3_Prototype/app.py "What was Meta's CAC last month?"
    python Part3_Prototype/app.py --serve          # then open http://localhost:8765

No dependencies beyond the repo's own (duckdb, pandas). Gemini is used for parsing and
phrasing only when GEMINI_API_KEY is set (env or Part3_Prototype/.env); otherwise a
rule-based parser handles the question and the answer sentence is templated.
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from Part3_Prototype.engine import Engine  # noqa: E402

SUGGESTIONS = ["What was Meta's CAC last month?", "Which channel has the best LTV:CAC?", "Affiliate repeat purchase rate",
               "How much did we spend on Influencer in Q2?", "Meta CAC by month", "Total paid spend in Q2",
               "Revenue per customer for Organic", "What was Google's CAC in July?"]

HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>UrbanCart channel metrics</title>
<style>
:root{--bg:#f9f9f7;--card:#fff;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--line:#e1e0d9;--blue:#2a78d6;--ok:#006300;--bad:#b3261e}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,"Helvetica Neue",Arial,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:28px 16px 60px}h1{font-size:22px;margin:0 0 4px}.sub{color:var(--ink2);margin:0 0 18px}
form{display:flex;gap:8px}input{flex:1;font:inherit;padding:12px 14px;border:1px solid var(--line);border-radius:10px;background:var(--card)}
button{font:inherit;padding:12px 18px;border:0;border-radius:10px;background:var(--blue);color:#fff;cursor:pointer}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 20px}.chip{font-size:13px;padding:6px 10px;border:1px solid var(--line);border-radius:999px;background:var(--card);cursor:pointer;color:var(--ink2)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:14px}
.q{color:var(--muted);font-size:13px;margin-bottom:6px}.a{font-size:17px;margin:0 0 10px}.meta{font-size:12.5px;color:var(--ink2);display:flex;flex-wrap:wrap;gap:10px 18px;margin-bottom:10px}
.ok{color:var(--ok)}.bad{color:var(--bad)}table{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0}th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;white-space:nowrap}th{color:var(--ink2);font-weight:600}
details{margin-top:8px}summary{cursor:pointer;color:var(--ink2);font-size:13px}pre{background:#f1f0eb;padding:10px;border-radius:8px;overflow:auto;font-size:12px;line-height:1.4}
.foot{color:var(--muted);font-size:12.5px;margin-top:20px}
</style></head><body><div class="wrap">
<h1>UrbanCart channel metrics</h1><p class="sub">Ask about spend, new customers, CAC, revenue per customer, repeat rate, LTV or LTV:CAC by channel. Data as of <b>__ASOF__</b> (Jan–Jun 2026).</p>
<form id="f"><input id="q" placeholder="e.g. What was Meta's CAC last month?" autofocus><button>Ask</button></form>
<div class="chips" id="chips"></div><div id="out"></div>
<p class="foot">How it works: the question is mapped to one metric + parameters from a fixed registry (parser: <b>__PARSER__</b>), code validates them, an approved SQL template runs on the warehouse, and the answer may only contain numbers from that result. Every question, SQL and answer is logged.</p>
</div><script>
const S=__SUGG__;const chips=document.getElementById('chips');S.forEach(s=>{const b=document.createElement('button');b.type='button';b.className='chip';b.textContent=s;b.onclick=()=>{q.value=s;ask()};chips.appendChild(b)});
const f=document.getElementById('f'),q=document.getElementById('q'),out=document.getElementById('out');f.onsubmit=e=>{e.preventDefault();ask()};
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
async function ask(){const question=q.value.trim();if(!question)return;const r=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question})});const d=await r.json();render(question,d)}
function render(question,d){const c=document.createElement('div');c.className='card';let h=`<div class="q">${esc(question)}</div><p class="a">${esc(d.answer)}</p>`;
if(d.type==='answer'){h+=`<div class="meta"><span>metric: <b>${esc(d.metric_label)}</b></span><span>channel: <b>${esc(d.channel)}</b></span><span>period: <b>${esc(d.period_label)}</b></span><span>parser: <b>${esc(d.parser)}</b></span><span>sentence: <b>${esc(d.sentence_source)}</b></span><span class="${/REJECTED/.test(d.checker)?'bad':'ok'}">checker: ${esc(d.checker)}</span><span>data as of ${esc(d.data_as_of)}</span></div>`;
h+='<table><tr>'+d.columns.map(x=>`<th>${esc(x)}</th>`).join('')+'</tr>'+d.rows.map(r=>'<tr>'+d.columns.map(x=>`<td>${esc(r[x])}</td>`).join('')+'</tr>').join('')+'</table>';
h+=`<details><summary>SQL that produced this answer</summary><pre>${esc(d.sql)}</pre></details>`}
else{h+=`<div class="meta"><span>parser: <b>${esc(d.parser)}</b></span><span>no query was run</span></div>`}
c.innerHTML=h;out.prepend(c);q.select()}
const pre=new URLSearchParams(location.search).get('q');if(pre){q.value=pre;ask()}
</script></body></html>"""


def make_handler(engine: Engine):
    page = (HTML.replace("__ASOF__", engine.log and engine.log[0]["data_as_of"] or "2026-06-30")
                .replace("__SUGG__", json.dumps(SUGGESTIONS))
                .replace("__PARSER__", "Gemini + rules fallback" if engine.use_llm else "rules (no GEMINI_API_KEY set)"))

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def do_GET(self):
            body = page.encode()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            try:
                question = json.loads(self.rfile.read(n) or b"{}").get("question", "")
                resp = engine.ask(question)
            except Exception as e:  # never leak a traceback to the CMO
                resp = {"type": "clarify", "answer": f"Something went wrong running that question ({type(e).__name__}). It has been logged.", "parser": "n/a"}
            body = json.dumps(resp, ensure_ascii=False, default=str).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    return H


def main(argv: list[str]) -> None:
    engine = Engine()
    if argv and argv[0] == "--serve":
        port = int(argv[1]) if len(argv) > 1 else 8765
        print(f"UrbanCart metrics agent on http://localhost:{port}  (parser: {'gemini' if engine.use_llm else 'rules'}; Ctrl-C to stop)")
        ThreadingHTTPServer(("127.0.0.1", port), make_handler(engine)).serve_forever()
        return
    question = " ".join(argv) or "What was Meta's CAC last month?"
    r = engine.ask(question)
    print(f"Q: {question}\nA: {r['answer']}")
    print(f"   parser={r['parser']}  sentence={r.get('sentence_source', '-')}  checker={r.get('checker', '-')}  data as of {r['data_as_of']}")
    if r.get("sql"):
        print("   SQL:\n" + "\n".join("     " + l for l in r["sql"].splitlines()))


if __name__ == "__main__":
    main(sys.argv[1:])
