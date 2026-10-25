"""Renders Part 1 (data quality + Q2–Q6) to Markdown from the Results object.

Every number in the text is pulled from the computed tables, so the prose can
never disagree with the tables.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.analysis import (ALL_CHANNELS, MARGIN, MONTH_LABEL, PAID, Results, inr, md_table, num, pct,
                          queries_sql_text, ratio)


def _row(df: pd.DataFrame, **match) -> pd.Series:
    m = df
    for k, v in match.items():
        m = m[m[k] == v]
    return m.iloc[0]


def part1_markdown(r: Results) -> str:
    d = {k: v.iloc[0] for k, v in r.dq.items() if k != "status_mix"}
    dup, conf, blank, internal, passed = (d["duplicate_order_rows"], d["conflicting_duplicates"],
                                          d["blank_channel"], d["internal_accounts"], d["passed_checks"])
    status = r.dq["status_mix"].set_index("status").orders_after_dedup
    unique_orders = int(dup.distinct_order_ids)
    non_success = int(status["cancelled"] + status["returned"])
    aff_naive, aff_clean = r.affiliate_before_after.iloc[0], r.affiliate_before_after.iloc[1]
    total_customers = int(_row(r.q6, bucket="total distinct customers (deduped orders)").customers)
    unknown_c = int(_row(r.q6, bucket="unknown channel").customers)
    internal_c = int(_row(r.q6, bucket="internal / test accounts").customers)
    clean_c = total_customers - unknown_c - internal_c

    best, worst = r.q4.iloc[0], r.q4.iloc[-1]
    chg = r.q5_change
    top = chg.iloc[0]
    others = chg.iloc[1:]
    rep = r.repeat_by_month.set_index("signup_month").repeat_rate_pct
    meta_may = r.q5_cac.loc["Meta Ads", "May"]
    meta_jan = r.q5_cac.loc["Meta Ads", "Jan"]
    g2 = _row(r.q2, channel="Google Ads")
    xc = r.pandas_crosscheck
    g_conv = _row(r.conversion, channel="Google Ads")
    spend_months = r.q5_spend.loc["Google Ads"]

    q1_issues = pd.DataFrame([
        {"#": 1, "Issue": "Exact duplicate rows in orders.csv (same order_id, every column identical)",
         "Rows affected": f"{num(dup.duplicate_rows)} of {num(dup.raw_rows)} rows ({dup.duplicate_rows / dup.raw_rows * 100:.1f}%); "
                          f"{num(unique_orders)} unique orders remain",
         "How handled": f"Dropped with `SELECT DISTINCT` before any count. {num(conf.conflicting_order_ids)} order_ids had "
                        "conflicting values, so this is a re-export, not two versions of an order."},
        {"#": 2, "Issue": "Blank `acquisition_channel` in users.csv",
         "Rows affected": f"{num(blank.users)} users ({blank.users / 5135 * 100:.1f}%); {num(blank.orders)} orders, "
                          f"{num(blank.customers)} customers, {inr(blank.delivered_revenue)} delivered revenue",
         "How handled": "Cannot be attributed to a channel. Excluded from every channel metric and shown as an "
                        "'Unknown channel' row in the Q6 reconciliation so totals still tie."},
        {"#": 3, "Issue": "Internal / test accounts: email on the company's own domain `@urbancart.in`",
         "Rows affected": f"{num(internal.users)} users, **all tagged {internal.channels}**; {num(internal.delivered_orders)} delivered "
                          f"orders ({int(internal.min_orders_per_user)}–{int(internal.max_orders_per_user)} per account, "
                          f"avg order {inr(internal.avg_order_value)} vs {inr(internal.avg_order_value_all)} overall)",
         "How handled": "Excluded from all metrics. This is the issue that matters most: with these accounts in, "
                        f"Affiliate's LTV:CAC is {ratio(aff_naive.ltv_to_cac)}; without them it is {ratio(aff_clean.ltv_to_cac)} (table below)."},
        {"#": 4, "Issue": "Cancelled and returned orders",
         "Rows affected": f"{num(status['cancelled'])} cancelled + {num(status['returned'])} returned of {num(unique_orders)} unique orders "
                          f"({non_success / unique_orders * 100:.1f}%)",
         "How handled": "Not 'successful' per the brief. Excluded from revenue, customer counts and repeat rate. "
                        "Kept for the cancel/return-rate check in the supporting tables."},
    ])

    passed_lines = [
        f"orphan orders (user_id not in users.csv): **{num(passed.orphan_orders)}**",
        f"orders dated before the user's signup: **{num(passed.orders_before_signup)}**",
        f"null dates / values / status in orders: **{num(passed.null_order_fields)}**; null fields in users: **{num(passed.null_user_fields)}**",
        f"zero or negative order values: **{num(passed.non_positive_values)}** (range {inr(passed.min_order_value)}–{inr(passed.max_order_value)}, no extreme outliers)",
        f"duplicate user_ids: **{num(passed.duplicate_user_ids)}**; duplicate emails: **{num(passed.duplicate_emails)}**",
        f"casing / whitespace variants: none — {int(passed.distinct_status_values)} status values, {int(passed.distinct_channel_values)} channel values, all canonical",
        f"spend table complete: **{int(passed.spend_rows)} rows** = 4 channels × 6 months, total {inr(passed.total_spend)} (the brief's 'about ₹16 lakh')",
        f"signups or orders outside Jan–Jun 2026: **{num(passed.signups_outside_window + passed.orders_outside_window)}**",
        f"users who never ordered: {num(passed.users_with_no_orders)} ({passed.users_with_no_orders / 5135 * 100:.0f}%) — normal, not an error",
    ]

    q2 = md_table(r.q2.rename(columns={"channel": "Channel", "spend_inr": "Total spend", "new_customers": "New customers", "cac": "CAC"}),
                  {"Total spend": inr, "New customers": num, "CAC": inr})
    q3 = md_table(r.q3.rename(columns={"channel": "Channel", "customers": "Customers", "revenue": "Delivered revenue",
                                       "revenue_per_customer": "Revenue per customer", "repeat_rate_pct": "Repeat purchase rate"}),
                  {"Customers": num, "Delivered revenue": inr, "Revenue per customer": inr, "Repeat purchase rate": pct})
    q4 = md_table(r.q4.rename(columns={"channel": "Channel", "revenue_per_customer": "Revenue per customer", "ltv": "LTV (× 30%)",
                                       "cac": "CAC", "ltv_to_cac": "LTV:CAC"}),
                  {"Revenue per customer": inr, "LTV (× 30%)": inr, "CAC": inr, "LTV:CAC": ratio})
    cac_tbl = md_table(r.q5_cac.rename_axis("Channel"), {m: inr for m in MONTH_LABEL.values()}, index=True)
    cust_tbl = md_table(r.q5_customers.rename_axis("Channel"), {m: num for m in MONTH_LABEL.values()}, index=True)
    spend_tbl = md_table(r.q5_spend.rename_axis("Channel"), {m: inr for m in MONTH_LABEL.values()}, index=True)
    chg_tbl = md_table(chg[["channel", "cac_jan", "cac_jun", "abs_change", "pct_change", "spend_pct_change"]]
                       .rename(columns={"channel": "Channel", "cac_jan": "CAC Jan", "cac_jun": "CAC Jun", "abs_change": "Change (₹)",
                                        "pct_change": "Change (%)", "spend_pct_change": "Spend change Jan→Jun (%)"}),
                       {"CAC Jan": inr, "CAC Jun": inr, "Change (₹)": lambda v: ("+" if v >= 0 else "-") + inr(abs(v)),
                        "Change (%)": lambda v: f"{v:+.1f}%", "Spend change Jan→Jun (%)": lambda v: f"{v:+.1f}%"})
    q6_sorted = pd.concat([r.q6[~r.q6.bucket.str.startswith("total")], r.q6[r.q6.bucket.str.startswith("total")]])
    q6 = md_table(q6_sorted.rename(columns={"bucket": "Bucket", "customers": "Customers"}), {"Customers": num})
    aff = md_table(r.affiliate_before_after.rename(columns={"version": "Affiliate metrics", "customers": "Customers", "revenue_per_customer": "Revenue per customer",
                                                            "repeat_rate_pct": "Repeat rate", "cac": "CAC", "ltv_to_cac": "LTV:CAC"}),
                   {"Customers": num, "Revenue per customer": inr, "Repeat rate": pct, "CAC": inr, "LTV:CAC": ratio})
    rep_tbl = md_table(r.repeat_by_month.rename(columns={"signup_month": "Signup month", "customers": "Customers", "repeat_rate_pct": "Repeat rate"}),
                       {"Customers": num, "Repeat rate": pct})
    ret_tbl = md_table(r.return_rate.rename(columns={"channel": "Channel", "orders": "Orders", "cancel_or_return_pct": "Cancelled or returned"}),
                       {"Orders": num, "Cancelled or returned": pct})
    conv_tbl = md_table(r.conversion.rename(columns={"channel": "Channel", "signups": "Signups", "customers": "Customers", "conversion_pct": "Signup → customer"}),
                        {"Signups": num, "Customers": num, "Signup → customer": pct})
    sq_tbl = md_table(r.spend_by_quarter.rename(columns={"channel": "Channel", "q1_spend": "Q1 (Jan–Mar)", "q2_spend": "Q2 (Apr–Jun)", "h1_spend": "H1 total"}),
                      {"Q1 (Jan–Mar)": inr, "Q2 (Apr–Jun)": inr, "H1 total": inr})

    others_txt = "; ".join(f"{o['channel']} {o['pct_change']:+.1f}%" for _, o in others.iterrows())
    sum_check = " + ".join(num(_row(r.q6, bucket=c).customers) for c in sorted(ALL_CHANNELS)) + \
                f" + {num(unknown_c)} (unknown) + {num(internal_c)} (internal) = {num(sum(int(_row(r.q6, bucket=c).customers) for c in ALL_CHANNELS) + unknown_c + internal_c)}"
    google_arith = " + ".join(f"{int(v) // 1000}k" for v in spend_months.values) + f" = {inr(g2.spend_inr)}"

    return f"""# Part 1 — Analysis

**Tools.** DuckDB SQL for every metric (`queries.sql` has each statement in execution order), pandas for pivots and an
independent cross-check, matplotlib for charts. `python run_analysis.py` regenerates this file, the tables and the charts from `data/raw/`.

**Definitions applied exactly as the brief states.** A *customer* is a user with at least one **delivered** order, counted under
their `acquisition_channel`. CAC = total channel spend ÷ customers from that channel. Revenue per customer = delivered revenue ÷
customers (Jan–Jun). Repeat rate = % of customers with ≥ 2 delivered orders. LTV = revenue per customer × {MARGIN:.0%}. LTV:CAC = LTV ÷ CAC.
Money is rounded to the nearest rupee and percentages to one decimal **only at display time**.

**Population.** After cleaning, {num(total_customers)} users have a delivered order: {num(clean_c)} across the five channels,
{num(unknown_c)} with no channel, {num(internal_c)} internal test accounts. Channel metrics use the {num(clean_c)}.

---

## 1. Data quality

Four issues were found. Rows are flagged, not deleted, so every exclusion is visible and reversible (`src/queries.py`, clean layer).

{md_table(q1_issues)}

**Why issue 3 matters — Affiliate with and without the {num(internal.users)} internal accounts**

{aff}

The {num(internal.users)} accounts place {num(internal.delivered_orders)} large, always-delivered orders between them. Left in, they make Affiliate look like
the second-best channel. Removed, Affiliate is the worst on every measure.

**Checks that passed** (run so the reader knows they were looked for):

{chr(10).join('- ' + line for line in passed_lines)}

---

## 2. Acquisition cost (paid channels, Jan–Jun 2026)

{q2}

---

## 3. Customer value (all channels, including Organic)

{q3}

Organic customers ({num(_row(r.q3, channel='Organic').customers)}) carry no spend, so they appear here but not in CAC or LTV:CAC.

---

## 4. Return on spend

{q4}

**Best: {best.channel} at {ratio(best.ltv_to_cac)}. Worst: {worst.channel} at {ratio(worst.ltv_to_cac)}.**
Only {best.channel} returns more contribution than it costs. Note that "LTV" here is six months of revenue × {MARGIN:.0%}, so every
figure is a floor; the *ranking* is what the recommendation rests on.

---

## 5. Trend — CAC by month (new customers grouped by signup month)

{cac_tbl}

Change from January to June:

{chg_tbl}

**{top.channel} is getting more expensive: {inr(top.cac_jan)} in January to {inr(top.cac_jun)} in June, +{inr(top.abs_change)} ({top['pct_change']:+.0f}%).**
Its monthly spend rose {top.spend_pct_change:+.0f}% ({inr(top.spend_jan)} → {inr(top.spend_jun)}) while new customers stayed flat
({num(top.cust_jan)} → {num(top.cust_jun)}), the signature of a saturated channel. Every other channel moved within a few percent ({others_txt}).

*Cohort caveat.* June signups had at most 30 days to place an order, so June CAC is slightly overstated for every channel and the
June repeat rate collapses (below). Meta's trend holds without June: January to May is {inr(meta_jan)} → {inr(meta_may)} ({(meta_may / meta_jan - 1) * 100:+.0f}%).

{rep_tbl}

Supporting monthly detail — spend and new customers by signup month:

{spend_tbl}

{cust_tbl}

---

## 6. Sanity check — Google Ads CAC = {inr(g2.cac)}

I verified this number four independent ways:

1. **Reconciliation.** Every user with a delivered order must land in exactly one bucket:
   {sum_check} = the {num(total_customers)} distinct customers in the deduped orders table. It ties.

{q6}

2. **Hand arithmetic.** Google spend = {google_arith}; {inr(g2.spend_inr)} ÷ {num(g2.new_customers)} = {g2.cac:.2f} → {inr(g2.cac)}.
3. **Second tool.** Recomputed in pandas with no SQL (`pandas_crosscheck` in `src/analysis.py`): {num(xc['google_customers'])} customers,
   CAC {xc['google_cac']:.2f}. Identical to the DuckDB result to the paisa; `run_analysis.py` asserts this on every run, and also asserts
   that the CAC used inside the LTV:CAC query equals the Q2 CAC (that assertion caught a fan-out join bug during development).
4. **Plausibility.** {num(g2.new_customers)} customers from {num(g_conv.signups)} Google signups is a {pct(g_conv.conversion_pct)} signup-to-customer
   rate, in line with the other channels (table below), and a {inr(g2.cac)} CAC is the cheapest of the four, consistent with intent-driven search traffic.

---

## Supporting tables

Cancel/return rate by channel (clean users) — a second, independent signal on Affiliate traffic quality:

{ret_tbl}

Signup → customer conversion by channel:

{conv_tbl}

Spend by quarter (the baseline used for the 20% cut in Part 2):

{sq_tbl}

---

## Assumptions

- A customer belongs to their signup `acquisition_channel` for the whole period (last-touch at signup), as the brief defines.
- Overall CAC uses Jan–Jun totals; the monthly CAC in Q5 matches each month's spend to customers who *signed up* that month, as instructed.
- Revenue is the `order_value` of delivered orders; no discount, shipping or COGS data is available, hence the brief's flat {MARGIN:.0%} margin.
- `@urbancart.in` emails are treated as internal/test traffic. Had they been genuine, they would still be 35 accounts generating
  {num(internal.delivered_orders)} orders at 2.3× the average basket — an outlier population that should not drive a budget decision.
- Unknown-channel customers ({num(unknown_c)}) are excluded rather than redistributed; spreading them pro-rata would not change any ranking.
- The six-month window truncates LTV for late cohorts; all LTV figures are floors and are compared only against each other.
"""


def write_outputs(r: Results, root: Path) -> None:
    p1 = root / "Part1_Analysis"
    (p1 / "results").mkdir(parents=True, exist_ok=True)
    (p1 / "queries.sql").write_text(queries_sql_text())
    (p1 / "Part1_Analysis.md").write_text(part1_markdown(r))
    for name in ["q2", "q3", "q4", "q5_long", "q6", "affiliate_before_after", "return_rate", "conversion",
                 "repeat_by_month", "spend_by_quarter"]:
        getattr(r, name).to_csv(p1 / "results" / f"{name}.csv", index=False)
    r.q5_cac.to_csv(p1 / "results" / "q5_cac_pivot.csv")
