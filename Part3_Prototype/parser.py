"""Question -> {metric, channel, period, grain, sort} or a clarification.

Two parsers with the same output contract:
  * rules_parse  - deterministic keyword parser; always available, used by the tests.
  * gemini_parse - Google Gemini via REST (stdlib only), constrained to a JSON schema whose
                   every field is an enum from registry.py. Falls back to rules_parse on any error.
Neither parser ever sees the data or produces a number.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from . import registry as R

INTENT_FIELDS = ["intent", "metric", "channel", "period", "grain", "sort", "clarification"]
CHANNEL_WORDS = {"google": "Google Ads", "meta": "Meta Ads", "facebook": "Meta Ads", "instagram": "Meta Ads",
                 "affiliate": "Affiliate", "influencer": "Influencer", "organic": "Organic"}
METRIC_PATTERNS = [  # order matters: more specific first
    (r"ltv\s*[:/]\s*cac|ltv to cac|ltv-to-cac|return on (ad )?spend|roas|\broi\b|pay(s)? (for|back) itself|break-?even", "ltv_to_cac"),
    (r"\bltv\b|lifetime value", "ltv"),
    (r"\bcac\b|acquisition cost|cost per (new )?(customer|acquisition)|cost (us |to )?(to )?(get|acquire|win)", "cac"),
    (r"repeat|reorder|re-order|second order|retention", "repeat_rate_pct"),
    (r"revenue per customer|avg(erage)? revenue|arpu|revenue/customer|worth per customer|revenue each", "revenue_per_customer"),
    (r"\bspend\b|\bspent\b|budget|\bcost\b(?! per)", "spend"),
    (r"new customers?|customers? (acquired|did we get|came)|how many customers|acquisitions?", "new_customers"),
]
MONTH_WORDS = {"jan": "2026-01", "feb": "2026-02", "mar": "2026-03", "apr": "2026-04", "may": "2026-05", "jun": "2026-06",
               "january": "2026-01", "february": "2026-02", "march": "2026-03", "april": "2026-04", "june": "2026-06"}
OUT_OF_RANGE_MONTHS = ["jul", "aug", "sep", "oct", "nov", "dec", "july", "august", "september", "october", "november", "december"]


def _load_dotenv() -> None:
    for p in [Path(__file__).resolve().parent / ".env", Path(__file__).resolve().parent.parent / ".env"]:
        if p.exists():
            for line in p.read_text().splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def gemini_key() -> str | None:
    _load_dotenv()
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


# ------------------------------------------------------------------ rules
def rules_parse(q: str) -> dict:
    t = q.lower()
    out = {"intent": "lookup", "metric": "none", "channel": "none", "period": "none", "grain": "total", "sort": "none", "clarification": ""}
    for m_pat, metric in METRIC_PATTERNS:
        if re.search(m_pat, t):
            out["metric"] = metric
            break
    found = [c for w, c in CHANNEL_WORDS.items() if re.search(rf"\b{w}", t)]
    if re.search(r"all channels|each channel|every channel|per channel|by channel|which channel|across channels|rank|compare|total paid|overall paid", t) \
            or re.search(r"\b(best|worst|highest|lowest|cheapest|most expensive|top)\b", t):
        out["channel"] = "all"
    elif found:
        out["channel"] = sorted(set(found), key=found.index)[0]
    if re.search(r"\b(best|highest|top|cheapest)\b", t):
        out["sort"] = "best"
    elif re.search(r"\b(worst|lowest|most expensive)\b", t):
        out["sort"] = "worst"
    if any(re.search(rf"\b{w}\b", t) for w in OUT_OF_RANGE_MONTHS):
        return {**out, "intent": "clarify",
                "clarification": "The data covers January to June 2026 only. Which of those months do you mean?"}
    if re.search(r"last month|previous month|past month", t):
        out["period"] = R.MONTHS[-1]
    elif re.search(r"\bq1\b|first quarter|jan[a-z]*\s*(-|to|–)\s*mar", t):
        out["period"] = "Q1"
    elif re.search(r"\bq2\b|second quarter|last quarter|this quarter|apr[a-z]*\s*(-|to|–)\s*jun", t):
        out["period"] = "Q2"
    elif re.search(r"\bh1\b|jan[a-z]*\s*(-|to|–)\s*jun|first half|whole period|overall|so far|year to date|ytd|in total", t):
        out["period"] = "H1"
    else:
        for w, m in MONTH_WORDS.items():
            if re.search(rf"\b{w}\b", t):
                out["period"] = m
                break
    if re.search(r"by month|monthly|each month|per month|month by month|trend|over time", t):
        out["grain"] = "month"
        if out["period"] == "none":
            out["period"] = "H1"
    return out


# ----------------------------------------------------------------- gemini
SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "intent": {"type": "STRING", "enum": ["lookup", "clarify"]},
        "metric": {"type": "STRING", "enum": list(R.METRICS) + ["none"]},
        "channel": {"type": "STRING", "enum": R.CHANNELS + ["all", "none"]},
        "period": {"type": "STRING", "enum": list(R.PERIODS) + ["none"]},
        "grain": {"type": "STRING", "enum": ["total", "month"]},
        "sort": {"type": "STRING", "enum": ["none", "best", "worst"]},
        "clarification": {"type": "STRING"},
    },
    "required": INTENT_FIELDS,
}
SYSTEM = f"""You translate a marketing leader's question about UrbanCart's paid channels into ONE metric lookup.
You never answer with numbers; you only choose from the allowed values. The data covers January–June 2026
(data as of {R.DATA_AS_OF}); "last month" means 2026-06. "This quarter"/"last quarter" means Q2. If no period is
mentioned use H1 (Jan–Jun). Use channel "all" for best/worst/compare/every-channel questions.
Metrics and definitions:
""" + "\n".join(f"- {k}: {v['definition']}" for k, v in R.METRICS.items()) + """
Channels: Google Ads, Meta Ads (also called Facebook/Instagram), Affiliate, Influencer, Organic (no spend).
Use grain "month" when the question asks for a trend / by month.
If the question is outside this scope (not about these metrics, channels or months), set intent="clarify"
and write a short clarification question. Return only the JSON object."""


def gemini_parse(q: str, timeout: float = 45.0) -> tuple[dict, str | None]:
    """Returns (intent dict, error). On error the caller falls back to rules_parse."""
    key = gemini_key()
    if not key:
        return {}, "no GEMINI_API_KEY"
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"systemInstruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": q}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "responseSchema": SCHEMA}}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)
        out = {k: parsed.get(k, "none" if k != "clarification" else "") for k in INTENT_FIELDS}
        if out["grain"] not in ("total", "month"):
            out["grain"] = "total"
        return out, None
    except urllib.error.HTTPError as e:
        return {}, f"Gemini HTTP {e.code}: {e.read().decode()[:200]}"
    except (OSError, KeyError, IndexError, ValueError) as e:  # OSError covers URLError, socket.timeout, connection errors
        return {}, f"Gemini error: {e}"


def gemini_phrase(question: str, facts: dict, timeout: float = 45.0) -> tuple[str | None, str | None]:
    """Ask Gemini for ONE sentence using only the supplied facts. The caller verifies every number."""
    key = gemini_key()
    if not key:
        return None, "no GEMINI_API_KEY"
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    system = ("Write ONE plain sentence (max 35 words) that answers the question for a busy CMO using ONLY the numbers in the "
              "facts JSON, copied exactly as written (same rounding, same ₹ and % symbols). Never calculate, convert, "
              "round or add any number that is not in the facts. No preamble.")
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": f"Question: {question}\nFacts: {json.dumps(facts, ensure_ascii=False)}"}]}],
            "generationConfig": {"temperature": 0}}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        return data["candidates"][0]["content"]["parts"][0]["text"].strip(), None
    except urllib.error.HTTPError as e:
        return None, f"Gemini HTTP {e.code}: {e.read().decode()[:200]}"
    except (OSError, KeyError, IndexError, ValueError) as e:  # OSError covers URLError, socket.timeout, connection errors
        return None, f"Gemini error: {e}"
