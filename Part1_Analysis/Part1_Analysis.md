# Part 1 — Analysis

**Tools.** DuckDB SQL for every metric (`queries.sql` has each statement in execution order), pandas for pivots and an
independent cross-check, matplotlib for charts. `python run_analysis.py` regenerates this file, the tables and the charts from `data/raw/`.

**Definitions applied exactly as the brief states.** A *customer* is a user with at least one **delivered** order, counted under
their `acquisition_channel`. CAC = total channel spend ÷ customers from that channel. Revenue per customer = delivered revenue ÷
customers (Jan–Jun). Repeat rate = % of customers with ≥ 2 delivered orders. LTV = revenue per customer × 30%. LTV:CAC = LTV ÷ CAC.
Money is rounded to the nearest rupee and percentages to one decimal **only at display time**.

**Population.** After cleaning, 2,678 users have a delivered order: 2,603 across the five channels,
40 with no channel, 35 internal test accounts. Channel metrics use the 2,603.

---

## 1. Data quality

Four issues were found. Rows are flagged, not deleted, so every exclusion is visible and reversible (`src/queries.py`, clean layer).

| # | Issue | Rows affected | How handled |
|---|---|---|---|
| 1 | Exact duplicate rows in orders.csv (same order_id, every column identical) | 206 of 5,684 rows (3.6%); 5,478 unique orders remain | Dropped with `SELECT DISTINCT` before any count. 0 order_ids had conflicting values, so this is a re-export, not two versions of an order. |
| 2 | Blank `acquisition_channel` in users.csv | 72 users (1.4%); 81 orders, 40 customers, ₹85,089 delivered revenue | Cannot be attributed to a channel. Excluded from every channel metric and shown as an 'Unknown channel' row in the Q6 reconciliation so totals still tie. |
| 3 | Internal / test accounts: email on the company's own domain `@urbancart.in` | 35 users, **all tagged Affiliate**; 285 delivered orders (6–11 per account, avg order ₹2,736 vs ₹1,169 overall) | Excluded from all metrics. This is the issue that matters most: with these accounts in, Affiliate's LTV:CAC is 1.10; without them it is 0.42 (table below). |
| 4 | Cancelled and returned orders | 315 cancelled + 364 returned of 5,478 unique orders (12.4%) | Not 'successful' per the brief. Excluded from revenue, customer counts and repeat rate. Kept for the cancel/return-rate check in the supporting tables. |

**Why issue 3 matters — Affiliate with and without the 35 internal accounts**

| Affiliate metrics | Customers | Revenue per customer | Repeat rate | CAC | LTV:CAC |
|---|---|---|---|---|---|
| with internal accounts (naive) | 540 | ₹2,339 | 14.1% | ₹641 | 1.10 |
| without internal accounts (clean) | 505 | ₹957 | 8.1% | ₹685 | 0.42 |

The 35 accounts place 285 large, always-delivered orders between them. Left in, they make Affiliate look like
the second-best channel. Removed, Affiliate is the worst on every measure.

**Checks that passed** (run so the reader knows they were looked for):

- orphan orders (user_id not in users.csv): **0**
- orders dated before the user's signup: **0**
- null dates / values / status in orders: **0**; null fields in users: **0**
- zero or negative order values: **0** (range ₹199–₹3,991, no extreme outliers)
- duplicate user_ids: **0**; duplicate emails: **0**
- casing / whitespace variants: none — 3 status values, 5 channel values, all canonical
- spend table complete: **24 rows** = 4 channels × 6 months, total ₹15,90,000 (the brief's 'about ₹16 lakh')
- signups or orders outside Jan–Jun 2026: **0**
- users who never ordered: 2,097 (41%) — normal, not an error

---

## 2. Acquisition cost (paid channels, Jan–Jun 2026)

| Channel | Total spend | New customers | CAC |
|---|---|---|---|
| Google Ads | ₹4,00,000 | 655 | ₹611 |
| Affiliate | ₹3,46,000 | 505 | ₹685 |
| Meta Ads | ₹5,47,000 | 675 | ₹810 |
| Influencer | ₹2,97,000 | 307 | ₹967 |

---

## 3. Customer value (all channels, including Organic)

| Channel | Customers | Delivered revenue | Revenue per customer | Repeat purchase rate |
|---|---|---|---|---|
| Influencer | 307 | ₹8,77,469 | ₹2,858 | 73.0% |
| Google Ads | 655 | ₹15,13,880 | ₹2,311 | 57.7% |
| Organic | 461 | ₹8,77,167 | ₹1,903 | 55.7% |
| Meta Ads | 675 | ₹11,24,892 | ₹1,667 | 44.7% |
| Affiliate | 505 | ₹4,83,387 | ₹957 | 8.1% |

Organic customers (461) carry no spend, so they appear here but not in CAC or LTV:CAC.

---

## 4. Return on spend

| Channel | Revenue per customer | LTV (× 30%) | CAC | LTV:CAC |
|---|---|---|---|---|
| Google Ads | ₹2,311 | ₹693 | ₹611 | 1.14 |
| Influencer | ₹2,858 | ₹857 | ₹967 | 0.89 |
| Meta Ads | ₹1,667 | ₹500 | ₹810 | 0.62 |
| Affiliate | ₹957 | ₹287 | ₹685 | 0.42 |

**Best: Google Ads at 1.14. Worst: Affiliate at 0.42.**
Only Google Ads returns more contribution than it costs. Note that "LTV" here is six months of revenue × 30%, so every
figure is a floor; the *ranking* is what the recommendation rests on.

---

## 5. Trend — CAC by month (new customers grouped by signup month)

| Channel | Jan | Feb | Mar | Apr | May | Jun |
|---|---|---|---|---|---|---|
| Google Ads | ₹592 | ₹621 | ₹596 | ₹602 | ₹644 | ₹611 |
| Meta Ads | ₹491 | ₹618 | ₹789 | ₹886 | ₹958 | ₹1,115 |
| Affiliate | ₹709 | ₹709 | ₹728 | ₹633 | ₹667 | ₹682 |
| Influencer | ₹981 | ₹980 | ₹913 | ₹960 | ₹964 | ₹1,000 |

Change from January to June:

| Channel | CAC Jan | CAC Jun | Change (₹) | Change (%) | Spend change Jan→Jun (%) |
|---|---|---|---|---|---|
| Meta Ads | ₹491 | ₹1,115 | +₹624 | +127.2% | +114.8% |
| Google Ads | ₹592 | ₹611 | +₹19 | +3.2% | -25.7% |
| Influencer | ₹981 | ₹1,000 | +₹19 | +2.0% | +2.0% |
| Affiliate | ₹709 | ₹682 | -₹27 | -3.9% | -26.2% |

**Meta Ads is getting more expensive: ₹491 in January to ₹1,115 in June, +₹624 (+127%).**
Its monthly spend rose +115% (₹54,000 → ₹1,16,000) while new customers stayed flat
(110 → 104), the signature of a saturated channel. Every other channel moved within a few percent (Google Ads +3.2%; Influencer +2.0%; Affiliate -3.9%).

*Cohort caveat.* June signups had at most 30 days to place an order, so June CAC is slightly overstated for every channel and the
June repeat rate collapses (below). Meta's trend holds without June: January to May is ₹491 → ₹958 (+95%).

| Signup month | Customers | Repeat rate |
|---|---|---|
| 2026-01 | 456 | 55.5% |
| 2026-02 | 432 | 57.4% |
| 2026-03 | 401 | 53.6% |
| 2026-04 | 481 | 54.3% |
| 2026-05 | 463 | 43.8% |
| 2026-06 | 370 | 5.9% |

Supporting monthly detail — spend and new customers by signup month:

| Channel | Jan | Feb | Mar | Apr | May | Jun |
|---|---|---|---|---|---|---|
| Google Ads | ₹74,000 | ₹59,000 | ₹62,000 | ₹74,000 | ₹76,000 | ₹55,000 |
| Meta Ads | ₹54,000 | ₹68,000 | ₹86,000 | ₹1,09,000 | ₹1,14,000 | ₹1,16,000 |
| Affiliate | ₹61,000 | ₹56,000 | ₹59,000 | ₹69,000 | ₹56,000 | ₹45,000 |
| Influencer | ₹51,000 | ₹50,000 | ₹42,000 | ₹48,000 | ₹54,000 | ₹52,000 |

| Channel | Jan | Feb | Mar | Apr | May | Jun |
|---|---|---|---|---|---|---|
| Google Ads | 125 | 95 | 104 | 123 | 118 | 90 |
| Meta Ads | 110 | 110 | 109 | 123 | 119 | 104 |
| Affiliate | 86 | 79 | 81 | 109 | 84 | 66 |
| Influencer | 52 | 51 | 46 | 50 | 56 | 52 |

---

## 6. Sanity check — Google Ads CAC = ₹611

I verified this number four independent ways:

1. **Reconciliation.** Every user with a delivered order must land in exactly one bucket:
   505 + 655 + 307 + 675 + 461 + 40 (unknown) + 35 (internal) = 2,678 = the 2,678 distinct customers in the deduped orders table. It ties.

| Bucket | Customers |
|---|---|
| Affiliate | 505 |
| Google Ads | 655 |
| Influencer | 307 |
| Meta Ads | 675 |
| Organic | 461 |
| internal / test accounts | 35 |
| unknown channel | 40 |
| total distinct customers (deduped orders) | 2,678 |

2. **Hand arithmetic.** Google spend = 74k + 59k + 62k + 74k + 76k + 55k = ₹4,00,000; ₹4,00,000 ÷ 655 = 610.69 → ₹611.
3. **Second tool.** Recomputed in pandas with no SQL (`pandas_crosscheck` in `src/analysis.py`): 655 customers,
   CAC 610.69. Identical to the DuckDB result to the paisa; `run_analysis.py` asserts this on every run, and also asserts
   that the CAC used inside the LTV:CAC query equals the Q2 CAC (that assertion caught a fan-out join bug during development).
4. **Plausibility.** 655 customers from 1,100 Google signups is a 59.5% signup-to-customer
   rate, in line with the other channels (table below), and a ₹611 CAC is the cheapest of the four, consistent with intent-driven search traffic.

---

## Supporting tables

Cancel/return rate by channel (clean users) — a second, independent signal on Affiliate traffic quality:

| Channel | Orders | Cancelled or returned |
|---|---|---|
| Affiliate | 913 | 40.2% |
| Meta Ads | 1,192 | 9.7% |
| Google Ads | 1,293 | 6.8% |
| Organic | 892 | 6.3% |
| Influencer | 822 | 5.7% |

Signup → customer conversion by channel:

| Channel | Signups | Customers | Signup → customer |
|---|---|---|---|
| Google Ads | 1,100 | 655 | 59.5% |
| Organic | 828 | 461 | 55.7% |
| Meta Ads | 1,300 | 675 | 51.9% |
| Influencer | 600 | 307 | 51.2% |
| Affiliate | 1,200 | 505 | 42.1% |

Spend by quarter (the baseline used for the 20% cut in Part 2):

| Channel | Q1 (Jan–Mar) | Q2 (Apr–Jun) | H1 total |
|---|---|---|---|
| Meta Ads | ₹2,08,000 | ₹3,39,000 | ₹5,47,000 |
| Google Ads | ₹1,95,000 | ₹2,05,000 | ₹4,00,000 |
| Affiliate | ₹1,76,000 | ₹1,70,000 | ₹3,46,000 |
| Influencer | ₹1,43,000 | ₹1,54,000 | ₹2,97,000 |

---

## Assumptions

- A customer belongs to their signup `acquisition_channel` for the whole period (last-touch at signup), as the brief defines.
- Overall CAC uses Jan–Jun totals; the monthly CAC in Q5 matches each month's spend to customers who *signed up* that month, as instructed.
- Revenue is the `order_value` of delivered orders; no discount, shipping or COGS data is available, hence the brief's flat 30% margin.
- `@urbancart.in` emails are treated as internal/test traffic. Had they been genuine, they would still be 35 accounts generating
  285 orders at 2.3× the average basket — an outlier population that should not drive a budget decision.
- Unknown-channel customers (40) are excluded rather than redistributed; spreading them pro-rata would not change any ranking.
- The six-month window truncates LTV for late cohorts; all LTV figures are floors and are compared only against each other.
