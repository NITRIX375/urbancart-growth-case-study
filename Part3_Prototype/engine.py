"""Validate the parsed intent, run the approved SQL template on DuckDB (standing in for
BigQuery), verify the phrasing, and log everything. No number in any answer is produced
by a language model: every figure comes from the query result.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import analysis as A                         # noqa: E402  (clean layer + formatters)
from Part3_Prototype import parser as P, registry as R  # noqa: E402

NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def fmt(value, unit: str) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return "–"
    return {"inr": A.inr, "count": A.num, "pct": A.pct, "ratio": A.ratio}[unit](value)


def numbers_in(text: str) -> set[str]:
    return {t.replace(",", "") for t in NUM.findall(text)}


class Engine:
    def __init__(self, data_dir: Path = ROOT / "data" / "raw", use_llm: bool | None = None):
        self.con = A.connect(data_dir)
        A.build_clean(self.con)
        self.con.execute(R.CHANNEL_MONTH_VIEW)
        self.use_llm = (P.gemini_key() is not None) if use_llm is None else use_llm
        self.log: list[dict] = []

    # ------------------------------------------------------------ public
    def ask(self, question: str) -> dict:
        intent, parser_used, llm_error = {}, "rules", None
        if self.use_llm:
            intent, llm_error = P.gemini_parse(question)
            parser_used = "gemini" if not llm_error else "rules (gemini unavailable)"
        if not intent:
            intent = P.rules_parse(question)
        resp = self._answer(question, intent)
        resp.update(question=question, parser=parser_used, llm_error=llm_error, data_as_of=R.DATA_AS_OF, intent=intent)
        self.log.append(resp)
        return resp

    # ---------------------------------------------------------- internals
    def _clarify(self, message: str) -> dict:
        return {"type": "clarify", "answer": message, "rows": [], "columns": [], "sql": None}

    def _answer(self, question: str, it: dict) -> dict:
        if it.get("intent") == "clarify":
            return self._clarify(it.get("clarification") or "Could you rephrase? I answer questions about spend, new customers, CAC, "
                                 "revenue per customer, repeat rate, LTV and LTV:CAC by channel for Jan–Jun 2026.")
        metric = it.get("metric", "none")
        if metric not in R.METRICS:
            return self._clarify("Which metric do you mean? I can answer: " + ", ".join(m["label"] for m in R.METRICS.values())
                                 + " — by channel, for any month Jan–Jun 2026, Q1, Q2 or the whole period.")
        spec = R.METRICS[metric]
        channel = it.get("channel", "none")
        if channel == "none":
            channel = "all"
        if channel not in R.CHANNELS + ["all"]:
            return self._clarify("Which channel? Google Ads, Meta Ads, Affiliate, Influencer, Organic, or all.")
        if spec["paid_only"] and channel == "Organic":
            return self._clarify(f"Organic has no marketing spend, so {spec['label']} is not defined for it. "
                                 "I can give Organic's new customers, revenue per customer, repeat rate or LTV.")
        period = it.get("period", "none")
        if period == "none":
            period = "H1"
        if period not in R.PERIODS:
            return self._clarify("The data covers January to June 2026. Which month, Q1, Q2 or the whole period?")
        grain = it.get("grain", "total")
        sort = it.get("sort", "none")
        channels = [channel] if channel != "all" else (R.PAID if spec["paid_only"] else R.CHANNELS)
        months = R.PERIODS[period]

        sql, params, shown = R.build_sql(channels, months, grain)
        cur = self.con.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        if sort != "none" and grain == "total":
            lower_is_better = metric in ("cac", "spend")
            rows.sort(key=lambda r: (r[metric] is None, r[metric] or 0), reverse=(sort == "best") != lower_is_better)

        unit = spec["unit"]
        table = self._table(rows, metric, grain)
        facts = self._facts(rows, metric, period, grain, channel)
        sentence = self._sentence(rows, metric, period, grain, channel, sort)
        source, check = "template", "n/a"
        if self.use_llm and sentence:
            llm_sentence, err = P.gemini_phrase(question, facts)
            if llm_sentence:
                if numbers_in(llm_sentence) <= numbers_in(json.dumps(facts, ensure_ascii=False)):
                    sentence, source, check = llm_sentence, "gemini", "passed: every number is in the query result"
                else:
                    source, check = "template (gemini sentence rejected)", "REJECTED: sentence contained a number not in the query result"
            else:
                source, check = "template (gemini unavailable)", err
        return {"type": "answer", "answer": sentence, "metric": metric, "metric_label": spec["label"], "unit": unit,
                "period": period, "period_label": R.PERIOD_LABEL[period], "channel": channel, "grain": grain,
                "columns": table["columns"], "rows": table["rows"], "sql": shown, "params": params,
                "sentence_source": source, "checker": check, "facts": facts}

    def _table(self, rows, metric, grain):
        cols = (["channel"] + (["month"] if grain == "month" else []) + [metric]
                + [c for c in ("spend", "new_customers", "cac", "revenue_per_customer", "repeat_rate_pct", "ltv", "ltv_to_cac")
                   if c != metric])
        units = {"spend": "inr", "new_customers": "count", "cac": "inr", "revenue_per_customer": "inr",
                 "repeat_rate_pct": "pct", "ltv": "inr", "ltv_to_cac": "ratio"}
        out = []
        for r in rows:
            d = {}
            for c in cols:
                v = r[c]
                d[c] = fmt(v, units[c]) if c in units else (R.MONTH_NAMES.get(v, v) if c == "month" else v)
            out.append(d)
        return {"columns": cols, "rows": out}

    def _facts(self, rows, metric, period, grain, channel):
        unit = R.METRICS[metric]["unit"]
        f = {"metric": R.METRICS[metric]["label"], "period": R.PERIOD_LABEL[period], "data_as_of": R.DATA_AS_OF}
        if grain == "month":
            f["by_month"] = {r["channel"] + " " + R.MONTH_NAMES[r["month"]]: fmt(r[metric], unit) for r in rows}
        else:
            f["values"] = {r["channel"]: fmt(r[metric], unit) for r in rows}
            if metric in ("spend", "new_customers") and channel == "all":
                tot = sum(r[metric] or 0 for r in rows)
                f["total"] = fmt(tot, unit)
        return f

    def _sentence(self, rows, metric, period, grain, channel, sort):
        spec = R.METRICS[metric]; unit = spec["unit"]; label = spec["label"]; pl = R.PERIOD_LABEL[period]
        if not rows:
            return f"No data for that selection ({pl})."
        if grain == "month":
            if channel == "all":
                return f"Monthly {label} for every channel, {pl}, is in the table below."
            parts = ", ".join(f"{R.MONTH_NAMES[r['month']][:3]} {fmt(r[metric], unit)}" for r in rows)
            return f"{channel} {label} by month ({pl}): {parts}."
        if channel != "all":
            r = rows[0]; v = fmt(r[metric], unit)
            why = {
                "cac": f" (spend {fmt(r['spend'], 'inr')} ÷ {fmt(r['new_customers'], 'count')} new customers)",
                "ltv_to_cac": f" (LTV {fmt(r['ltv'], 'inr')} ÷ CAC {fmt(r['cac'], 'inr')})",
                "ltv": f" (revenue per customer {fmt(r['revenue_per_customer'], 'inr')} × 30% margin)",
                "revenue_per_customer": f" (delivered revenue {fmt(r['revenue'], 'inr')} ÷ {fmt(r['new_customers'], 'count')} customers)",
                "repeat_rate_pct": f" ({fmt(r['repeaters'], 'count')} of {fmt(r['new_customers'], 'count')} customers ordered twice or more)",
            }.get(metric, "")
            return f"{channel} {label} for {pl} was {v}{why}."
        listing = ", ".join(f"{r['channel']} {fmt(r[metric], unit)}" for r in rows)
        if sort == "best":
            return f"Best {label} for {pl}: {rows[0]['channel']} at {fmt(rows[0][metric], unit)}. Ranking: {listing}."
        if sort == "worst":
            return f"Worst {label} for {pl}: {rows[0]['channel']} at {fmt(rows[0][metric], unit)}. Ranking: {listing}."
        if metric in ("spend", "new_customers"):
            tot = fmt(sum(r[metric] or 0 for r in rows), unit)
            return f"Total {label} for {pl}: {tot} ({listing})."
        return f"{label.capitalize()} for {pl}: {listing}."
