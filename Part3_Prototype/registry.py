"""Metric registry: the Part 1 definitions, each answerable by ONE parameterised SQL template.

The LLM (or the rule-based parser) may only choose a metric, a channel, a period, a
grain and a sort order from the enums below. Everything else is code.
"""
from __future__ import annotations

MARGIN = 0.30
DATA_AS_OF = "2026-06-30"                       # max order_date in the source data
MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
MONTH_NAMES = {"2026-01": "January", "2026-02": "February", "2026-03": "March",
               "2026-04": "April", "2026-05": "May", "2026-06": "June"}
PERIODS = {**{m: [m] for m in MONTHS},
           "Q1": MONTHS[:3], "Q2": MONTHS[3:], "H1": MONTHS}
PERIOD_LABEL = {**{m: f"{MONTH_NAMES[m]} 2026" for m in MONTHS},
                "Q1": "Q1 2026 (Jan–Mar)", "Q2": "Q2 2026 (Apr–Jun)", "H1": "Jan–Jun 2026"}
PAID = ["Google Ads", "Meta Ads", "Affiliate", "Influencer"]
CHANNELS = PAID + ["Organic"]

METRICS = {
    "spend":                {"label": "spend",                "unit": "inr",   "paid_only": True,
                             "definition": "marketing spend in rupees"},
    "new_customers":        {"label": "new customers",        "unit": "count", "paid_only": False,
                             "definition": "users with at least one delivered order, counted under their signup channel"},
    "cac":                  {"label": "CAC",                  "unit": "inr",   "paid_only": True,
                             "definition": "spend ÷ new customers"},
    "revenue_per_customer": {"label": "revenue per customer", "unit": "inr",   "paid_only": False,
                             "definition": "delivered revenue ÷ new customers"},
    "repeat_rate_pct":      {"label": "repeat purchase rate", "unit": "pct",   "paid_only": False,
                             "definition": "% of customers with two or more delivered orders"},
    "ltv":                  {"label": "LTV",                  "unit": "inr",   "paid_only": False,
                             "definition": f"revenue per customer × {MARGIN:.0%} contribution margin"},
    "ltv_to_cac":           {"label": "LTV:CAC",              "unit": "ratio", "paid_only": True,
                             "definition": "LTV ÷ CAC"},
}

# One view over the clean layer (built once per connection), one template for every metric.
CHANNEL_MONTH_VIEW = """
CREATE OR REPLACE VIEW channel_month AS
WITH nc AS (
    SELECT acquisition_channel AS channel, signup_month AS month,
           COUNT(*)                                             AS new_customers,
           SUM(revenue)                                         AS revenue,
           COUNT(*) FILTER (WHERE delivered_orders >= 2)        AS repeaters
    FROM customers_clean GROUP BY 1, 2),
sp AS (SELECT channel, month, spend_inr FROM spend)
SELECT COALESCE(nc.channel, sp.channel) AS channel, COALESCE(nc.month, sp.month) AS month,
       sp.spend_inr, nc.new_customers, nc.revenue, nc.repeaters
FROM nc FULL OUTER JOIN sp ON nc.channel = sp.channel AND nc.month = sp.month"""

TEMPLATE = """
SELECT channel{month_col},
       SUM(spend_inr)                                            AS spend,
       SUM(new_customers)                                        AS new_customers,
       SUM(revenue)                                              AS revenue,
       SUM(repeaters)                                            AS repeaters,
       SUM(spend_inr) / SUM(new_customers)                       AS cac,
       SUM(revenue) / SUM(new_customers)                         AS revenue_per_customer,
       100.0 * SUM(repeaters) / SUM(new_customers)               AS repeat_rate_pct,
       {margin} * SUM(revenue) / SUM(new_customers)              AS ltv,
       ({margin} * SUM(revenue) / SUM(new_customers))
           / (SUM(spend_inr) / SUM(new_customers))               AS ltv_to_cac
FROM channel_month
WHERE month IN ({month_params}) AND channel IN ({channel_params})
GROUP BY channel{month_col}
ORDER BY channel{month_col}"""


def build_sql(channels: list[str], months: list[str], grain: str) -> tuple[str, list, str]:
    """Return (sql with ? placeholders, parameter list, sql with literals for display)."""
    month_col = ", month" if grain == "month" else ""
    sql = TEMPLATE.format(month_col=month_col, margin=MARGIN,
                          month_params=", ".join("?" * len(months)), channel_params=", ".join("?" * len(channels)))
    params = list(months) + list(channels)
    shown = TEMPLATE.format(month_col=month_col, margin=MARGIN,
                            month_params=", ".join(f"'{m}'" for m in months),
                            channel_params=", ".join(f"'{c}'" for c in channels))
    return sql.strip(), params, shown.strip()
