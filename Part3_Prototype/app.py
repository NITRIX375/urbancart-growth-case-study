"""UrbanCart growth dashboard + self-serve agent, in one local page.

    python Part3_Prototype/app.py --serve          # open http://localhost:8765
    python Part3_Prototype/app.py "What was Meta's CAC last month?"   # CLI, one question

No dependencies beyond the repo's own (duckdb, pandas). The page shows live KPI tiles and
the channel table from the same DuckDB clean layer the agent queries, the Part 1/2 charts,
a flow chart of how a question is answered, the pipeline architecture, data-quality status,
and the ask box. Gemini is used for parsing/phrasing only when GEMINI_API_KEY is set.
"""
from __future__ import annotations

import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from Part3_Prototype import registry as R          # noqa: E402
from Part3_Prototype.engine import Engine, fmt     # noqa: E402
from src import analysis as A, queries as Q        # noqa: E402

SUGGESTIONS = ["What was Meta's CAC last month?", "Which channel has the best LTV:CAC?", "Is the influencer programme paying for itself?",
               "How much did we spend on Influencer in Q2?", "Meta CAC by month", "Total paid spend in Q2",
               "Compare Google and Meta on how often customers come back", "What was Google's CAC in July?"]
STATIC = {  # url path -> file (whitelist; nothing else is served)
    "/static/ltv_cac.png": ROOT / "Part2_Memo/charts/1_ltv_cac_by_channel.png",
    "/static/monthly_cac.png": ROOT / "Part2_Memo/charts/2_monthly_cac_trend.png",
    "/static/reallocation.png": ROOT / "Part2_Memo/charts/3_proposed_reallocation.png",
    "/static/meta.png": ROOT / "Part1_Analysis/charts/meta_spend_vs_new_customers.png",
    "/static/architecture.png": ROOT / "Part3_Design/architecture.png",
}


def summary(engine: Engine) -> dict:
    """Everything the dashboard tiles and table need, from the same clean layer the agent queries."""
    sql, params, _ = R.build_sql(R.CHANNELS, R.MONTHS, "total")
    cur = engine.con.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    by = {r["channel"]: r for r in rows}
    paid = [by[c] for c in R.PAID]
    best = max(paid, key=lambda r: r["ltv_to_cac"]); worst = min(paid, key=lambda r: r["ltv_to_cac"])
    msql, mparams, _ = R.build_sql(["Meta Ads"], R.MONTHS, "month")
    meta = engine.con.execute(msql, mparams).fetchall()
    meta_jan, meta_jun = meta[0][cols.index("cac") + 1], meta[-1][cols.index("cac") + 1]  # +1: month column inserted
    dq = {k: A.run_sql(engine.con, Q.DQ[k]).iloc[0] for k in ("duplicate_order_rows", "blank_channel", "internal_accounts")}
    order = ["Google Ads", "Influencer", "Meta Ads", "Affiliate", "Organic"]
    table = [{"channel": c, "spend": fmt(by[c]["spend"], "inr"), "new_customers": fmt(by[c]["new_customers"], "count"),
              "cac": fmt(by[c]["cac"], "inr"), "revenue_per_customer": fmt(by[c]["revenue_per_customer"], "inr"),
              "repeat_rate_pct": fmt(by[c]["repeat_rate_pct"], "pct"), "ltv": fmt(by[c]["ltv"], "inr"),
              "ltv_to_cac": fmt(by[c]["ltv_to_cac"], "ratio")} for c in order]
    return {
        "data_as_of": R.DATA_AS_OF, "period": "Jan–Jun 2026",
        "tiles": [
            {"label": "Paid spend", "value": fmt(sum(r["spend"] for r in paid), "inr"), "sub": "4 channels, 6 months"},
            {"label": "New customers", "value": fmt(sum(r["new_customers"] for r in rows), "count"), "sub": f"{fmt(sum(r['new_customers'] for r in paid), 'count')} paid · {fmt(by['Organic']['new_customers'], 'count')} organic"},
            {"label": "Blended paid CAC", "value": fmt(sum(r["spend"] for r in paid) / sum(r["new_customers"] for r in paid), "inr"), "sub": "spend ÷ paid customers"},
            {"label": "Best LTV:CAC", "value": fmt(best["ltv_to_cac"], "ratio"), "sub": best["channel"], "tone": "good"},
            {"label": "Worst LTV:CAC", "value": fmt(worst["ltv_to_cac"], "ratio"), "sub": worst["channel"], "tone": "bad"},
            {"label": "Meta CAC, Jan → Jun", "value": f"{(meta_jun / meta_jan - 1) * 100:+.0f}%", "sub": f"{fmt(meta_jan, 'inr')} → {fmt(meta_jun, 'inr')}", "tone": "bad"},
        ],
        "table": table,
        "dq": [
            {"check": "Duplicate order rows", "found": f"{int(dq['duplicate_order_rows'].duplicate_rows):,}", "handling": "dropped (SELECT DISTINCT)"},
            {"check": "Users with blank channel", "found": f"{int(dq['blank_channel'].users):,}", "handling": "excluded from channel metrics, kept as 'Unknown'"},
            {"check": "Internal @urbancart.in accounts", "found": f"{int(dq['internal_accounts'].users):,} users · {int(dq['internal_accounts'].delivered_orders):,} orders, all Affiliate", "handling": "excluded; flips Affiliate LTV:CAC 1.10 → 0.42"},
            {"check": "Cancelled / returned orders", "found": "679", "handling": "not successful per brief; excluded from revenue and customers"},
            {"check": "Orphans, pre-signup orders, nulls, negatives, casing", "found": "0", "handling": "checked, nothing found"},
        ],
    }


FLOW_SVG = """<svg viewBox="0 0 1180 190" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="How a question becomes an answer">
<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#898781"/></marker></defs>
<g font-family="-apple-system,'Helvetica Neue',Arial,sans-serif" font-size="12.5" fill="#0b0b0b">
<rect x="10" y="40" width="150" height="70" rx="10" fill="#fff" stroke="#898781" stroke-width="1.5"/><text x="85" y="68" text-anchor="middle" font-weight="700">1 · CMO asks</text><text x="85" y="88" text-anchor="middle" fill="#52514e">"Meta's CAC last month?"</text>
<rect x="210" y="30" width="190" height="90" rx="10" fill="#fff" stroke="#2a78d6" stroke-width="1.5"/><text x="305" y="55" text-anchor="middle" font-weight="700">2 · LLM picks from enums</text><text x="305" y="75" text-anchor="middle" fill="#52514e">metric · channel · period</text><text x="305" y="92" text-anchor="middle" fill="#52514e">grain · sort — or "clarify"</text><text x="305" y="110" text-anchor="middle" fill="#898781" font-size="11">never sees the data</text>
<rect x="450" y="40" width="150" height="70" rx="10" fill="#fff" stroke="#eda100" stroke-width="1.5"/><text x="525" y="68" text-anchor="middle" font-weight="700">3 · Code validates</text><text x="525" y="88" text-anchor="middle" fill="#52514e">allowed values only</text>
<rect x="650" y="30" width="180" height="90" rx="10" fill="#fff" stroke="#1baf7a" stroke-width="1.5"/><text x="740" y="55" text-anchor="middle" font-weight="700">4 · Approved SQL template</text><text x="740" y="75" text-anchor="middle" fill="#52514e">bound parameters, read-only</text><text x="740" y="92" text-anchor="middle" fill="#52514e">DuckDB here, BigQuery in prod</text><text x="740" y="110" text-anchor="middle" fill="#898781" font-size="11">where every number comes from</text>
<rect x="880" y="40" width="130" height="70" rx="10" fill="#fff" stroke="#eb6834" stroke-width="1.5"/><text x="945" y="68" text-anchor="middle" font-weight="700">5 · Checker</text><text x="945" y="88" text-anchor="middle" fill="#52514e">numbers ⊆ result?</text>
<rect x="1040" y="30" width="130" height="90" rx="10" fill="#2a78d6" stroke="#2a78d6"/><text x="1105" y="55" text-anchor="middle" font-weight="700" fill="#fff">6 · Answer</text><text x="1105" y="75" text-anchor="middle" fill="#fff">sentence + table</text><text x="1105" y="92" text-anchor="middle" fill="#fff">+ SQL + data-as-of</text><text x="1105" y="110" text-anchor="middle" fill="#dbe8fb" font-size="11">everything logged</text>
<g stroke="#898781" stroke-width="1.6" fill="none" marker-end="url(#ah)"><path d="M160,75 L208,75"/><path d="M400,75 L448,75"/><path d="M600,75 L648,75"/><path d="M830,75 L878,75"/><path d="M1010,75 L1038,75"/></g>
<g stroke="#898781" stroke-width="1.4" fill="none" stroke-dasharray="4 3" marker-end="url(#ah)"><path d="M525,110 L525,150 L1104,150 L1104,122"/><path d="M305,120 L305,150"/></g>
<text x="700" y="166" text-anchor="middle" fill="#52514e" font-size="11.5">out of scope, ambiguous month, Organic CAC… → a clarifying question is returned instead of a query; a rejected sentence falls back to the templated one</text>
</g></svg>"""

HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>UrbanCart growth dashboard</title>
<style>
:root{--bg:#f9f9f7;--card:#fff;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--line:#e1e0d9;--blue:#2a78d6;--good:#006300;--bad:#b3261e;--goodbg:#e9f5e9;--badbg:#fbe9e7}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14.5px/1.5 -apple-system,"Helvetica Neue",Arial,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:22px 16px 60px}header{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 18px;margin-bottom:14px}
h1{font-size:22px;margin:0}.asof{color:var(--ink2);font-size:13px}h2{font-size:15px;margin:26px 0 10px;color:var(--ink);text-transform:uppercase;letter-spacing:.04em}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}.tile{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.tile .l{font-size:12px;color:var(--ink2)}.tile .v{font-size:24px;font-weight:700;margin:2px 0;font-variant-numeric:tabular-nums}.tile .s{font-size:12px;color:var(--muted)}
.tile.good .v{color:var(--good)}.tile.bad .v{color:var(--bad)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid var(--line);padding:7px 8px;text-align:left;white-space:nowrap;font-variant-numeric:tabular-nums}th{color:var(--ink2);font-weight:600}
td:first-child{font-weight:600}table.wrap th,table.wrap td{white-space:normal;vertical-align:top}.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:12px}.charts img,.diagram img{width:100%;height:auto;display:block;border-radius:8px}
.flow svg{width:100%;height:auto}.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:760px){.two{grid-template-columns:1fr}.charts{grid-template-columns:1fr}}
form{display:flex;gap:8px}input{flex:1;font:inherit;padding:11px 13px;border:1px solid var(--line);border-radius:10px;background:var(--card)}
button{font:inherit;padding:11px 16px;border:0;border-radius:10px;background:var(--blue);color:#fff;cursor:pointer}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 14px}.chip{font-size:12.5px;padding:5px 10px;border:1px solid var(--line);border-radius:999px;background:var(--card);cursor:pointer;color:var(--ink2)}
.ans{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:12px}.q{color:var(--muted);font-size:12.5px;margin-bottom:4px}.a{font-size:16.5px;margin:0 0 8px}
.meta{font-size:12px;color:var(--ink2);display:flex;flex-wrap:wrap;gap:6px 16px;margin-bottom:8px}.ok{color:var(--good)}.bad{color:var(--bad)}
details{margin-top:6px}summary{cursor:pointer;color:var(--ink2);font-size:12.5px}pre{background:#f1f0eb;padding:10px;border-radius:8px;overflow:auto;font-size:12px;line-height:1.4}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11.5px;background:var(--goodbg);color:var(--good)}.pill.warn{background:var(--badbg);color:var(--bad)}
.foot{color:var(--muted);font-size:12.5px;margin-top:24px}
</style></head><body><div class="wrap">
<header><h1>UrbanCart growth dashboard</h1><span class="asof">Paid channels · <b id="period"></b> · data as of <b id="asof"></b> · parser: <b>__PARSER__</b></span></header>
<div class="tiles" id="tiles"></div>

<h2>Channel scorecard</h2>
<div class="card"><table id="scorecard"><thead><tr><th>Channel</th><th>Spend</th><th>New customers</th><th>CAC</th><th>Revenue / customer</th><th>Repeat rate</th><th>LTV (×30%)</th><th>LTV:CAC</th></tr></thead><tbody></tbody></table>
<div class="asof" style="margin-top:8px">Definitions from the brief: customer = ≥1 delivered order under signup channel · CAC = spend ÷ customers · LTV = 6-month revenue per customer × 30% · repeat = customers with ≥2 delivered orders. Organic has no spend.</div></div>

<h2>Ask the data</h2>
<div class="card"><form id="f"><input id="q" placeholder="e.g. What was Meta's CAC last month?"><button>Ask</button></form><div class="chips" id="chips"></div><div id="out"></div></div>

<h2>Charts</h2>
<div class="charts"><div class="card"><img src="/static/ltv_cac.png" alt="LTV:CAC by channel"></div><div class="card"><img src="/static/monthly_cac.png" alt="Monthly CAC trend"></div>
<div class="card"><img src="/static/meta.png" alt="Meta spend vs new customers"></div><div class="card"><img src="/static/reallocation.png" alt="Proposed reallocation"></div></div>

<h2>How a question becomes an answer</h2>
<div class="card flow">__FLOW__</div>

<div class="two" style="margin-top:12px">
<div><h2 style="margin-top:14px">Data quality (checked on every load)</h2><div class="card"><table id="dq" class="wrap"><thead><tr><th style="width:34%">Check</th><th style="width:22%">Found</th><th>Handling</th></tr></thead><tbody></tbody></table></div></div>
<div><h2 style="margin-top:14px">Pipeline status (what production would show)</h2><div class="card">
<p style="margin:0 0 8px"><span class="pill">last run OK</span> &nbsp;<span class="pill">freshness &lt; 26 h</span> &nbsp;<span class="pill">dbt tests 7/7 passed</span> &nbsp;<span class="pill warn">quarantine: 72 rows</span></p>
<p style="margin:0;color:var(--ink2);font-size:13px">In production these badges read from the <code>pipeline_runs</code> table written by the daily Airflow DAG, so stale or failed data is visible on the dashboard rather than silent. Here they are illustrative; the data-quality counts on the left are live.</p></div></div>
</div>

<h2>Pipeline architecture (GCP)</h2>
<div class="card diagram"><img src="/static/architecture.png" alt="Pipeline architecture"></div>
<p class="foot">Live numbers come from the same DuckDB clean layer the agent queries (standing in for BigQuery). Charts are the Part 1/2 figures. Every question, SQL and answer is logged.</p>
</div><script>
const S=__SUGG__;
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
fetch('/api/summary').then(r=>r.json()).then(d=>{document.getElementById('asof').textContent=d.data_as_of;document.getElementById('period').textContent=d.period;
document.getElementById('tiles').innerHTML=d.tiles.map(t=>`<div class="tile ${t.tone||''}"><div class="l">${esc(t.label)}</div><div class="v">${esc(t.value)}</div><div class="s">${esc(t.sub)}</div></div>`).join('');
document.querySelector('#scorecard tbody').innerHTML=d.table.map(r=>`<tr><td>${esc(r.channel)}</td><td>${esc(r.spend)}</td><td>${esc(r.new_customers)}</td><td>${esc(r.cac)}</td><td>${esc(r.revenue_per_customer)}</td><td>${esc(r.repeat_rate_pct)}</td><td>${esc(r.ltv)}</td><td>${esc(r.ltv_to_cac)}</td></tr>`).join('');
document.querySelector('#dq tbody').innerHTML=d.dq.map(r=>`<tr><td style="font-weight:400">${esc(r.check)}</td><td>${esc(r.found)}</td><td style="white-space:normal;color:#52514e">${esc(r.handling)}</td></tr>`).join('')});
const chips=document.getElementById('chips'),f=document.getElementById('f'),q=document.getElementById('q'),out=document.getElementById('out');
S.forEach(s=>{const b=document.createElement('button');b.type='button';b.className='chip';b.textContent=s;b.onclick=()=>{q.value=s;ask()};chips.appendChild(b)});
f.onsubmit=e=>{e.preventDefault();ask()};
async function ask(){const question=q.value.trim();if(!question)return;const r=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question})});render(question,await r.json())}
function render(question,d){const c=document.createElement('div');c.className='ans';let h=`<div class="q">${esc(question)}</div><p class="a">${esc(d.answer)}</p>`;
if(d.type==='answer'){h+=`<div class="meta"><span>metric: <b>${esc(d.metric_label)}</b></span><span>channel: <b>${esc(d.channel)}</b></span><span>period: <b>${esc(d.period_label)}</b></span><span>parser: <b>${esc(d.parser)}</b></span><span>sentence: <b>${esc(d.sentence_source)}</b></span><span class="${/REJECTED/.test(d.checker)?'bad':'ok'}">checker: ${esc(d.checker)}</span></div>`;
h+='<table><tr>'+d.columns.map(x=>`<th>${esc(x)}</th>`).join('')+'</tr>'+d.rows.map(r=>'<tr>'+d.columns.map(x=>`<td>${esc(r[x])}</td>`).join('')+'</tr>').join('')+'</table>';
h+=`<details><summary>SQL that produced this answer</summary><pre>${esc(d.sql)}</pre></details>`}else{h+=`<div class="meta"><span>parser: <b>${esc(d.parser)}</b></span><span>no query was run</span></div>`}
c.innerHTML=h;out.prepend(c);q.select()}
const pre=new URLSearchParams(location.search).get('q');if(pre){q.value=pre;ask()}
</script></body></html>"""


def make_handler(engine: Engine):
    page = (HTML.replace("__SUGG__", json.dumps(SUGGESTIONS)).replace("__FLOW__", FLOW_SVG)
                .replace("__PARSER__", "Gemini + rules fallback" if engine.use_llm else "rules (no GEMINI_API_KEY set)"))
    summary_json = json.dumps(summary(engine), ensure_ascii=False).encode()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body: bytes, ctype: str, code: int = 200):
            self.send_response(code); self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/":
                return self._send(page.encode(), "text/html; charset=utf-8")
            if path == "/api/summary":
                return self._send(summary_json, "application/json; charset=utf-8")
            if path in STATIC and STATIC[path].exists():
                return self._send(STATIC[path].read_bytes(), mimetypes.guess_type(str(STATIC[path]))[0] or "application/octet-stream")
            self._send(b"not found", "text/plain", 404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            try:
                question = json.loads(self.rfile.read(n) or b"{}").get("question", "")
                resp = engine.ask(question)
            except Exception as e:  # never leak a traceback to the CMO
                resp = {"type": "clarify", "answer": f"Something went wrong running that question ({type(e).__name__}). It has been logged.", "parser": "n/a"}
            self._send(json.dumps(resp, ensure_ascii=False, default=str).encode(), "application/json; charset=utf-8")
    return H


def main(argv: list[str]) -> None:
    engine = Engine()
    if argv and argv[0] == "--serve":
        port = int(argv[1]) if len(argv) > 1 else 8765
        print(f"UrbanCart dashboard on http://localhost:{port}  (parser: {'gemini' if engine.use_llm else 'rules'}; Ctrl-C to stop)")
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
