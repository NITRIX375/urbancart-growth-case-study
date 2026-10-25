# UrbanCart: which paid channel to cut

Take-home case study for the Data & AI Engineer (Growth & Analytics) role. Everything here is reproducible from the raw CSVs with one command.

## The answer in 30 seconds

**Cut Affiliate to zero and trim Meta; protect Google and hold Influencer.** Paid spend falls from ₹8.68L to ₹6.94L a quarter (−20%).

| Channel | Spend (Jan–Jun) | New customers | CAC | Revenue / customer | Repeat rate | LTV:CAC |
|---|---|---|---|---|---|---|
| Google Ads | ₹4,00,000 | 655 | ₹611 | ₹2,311 | 57.7% | **1.14** |
| Influencer | ₹2,97,000 | 307 | ₹967 | ₹2,858 | 73.0% | 0.89 |
| Meta Ads | ₹5,47,000 | 675 | ₹810 | ₹1,667 | 44.7% | 0.62 |
| Affiliate | ₹3,46,000 | 505 | ₹685 | ₹957 | 8.1% | **0.42** |
| Organic | – | 461 | – | ₹1,903 | 55.7% | – |

Three things in the raw data change the answer if missed: 206 duplicate order rows, 72 users with no channel, and 35 internal `@urbancart.in` test accounts that are all tagged Affiliate and place 285 orders between them. With those accounts in, Affiliate looks like the second-best channel (LTV:CAC 1.10); without them it is the worst (0.42). Meta's CAC rose 127% from January to June while its spend doubled and its new-customer count stayed flat.

## What is where

| Path | Contents |
|---|---|
| `Part1_Analysis/Part1_Analysis.md` / `.pdf` | Data-quality report, answers Q1–Q6 with tables, sanity check, assumptions |
| `Part1_Analysis/Part1_Analysis.ipynb` | The same analysis as an executed notebook |
| `Part1_Analysis/queries.sql` | Every SQL statement, in execution order (DuckDB) |
| `Part1_Analysis/results/` | Unrounded result tables as CSV |
| `Part2_Memo/Part2_Memo.md` / `.pdf` | 250-word memo to the CMO with three charts (`charts/`) |
| `Part3_Design/Part3_Design_Note.md` / `.pdf` | Pipeline + self-serve design note with `architecture.png` |
| `AI_Use_Note.md` | Which AI tools were used, for what, and what they got wrong |
| `Reflection.md` | Answer to the final-step question |
| `src/` | `queries.py` (SQL), `analysis.py` (engine), `report.py` (Markdown), `charts.py`, `recommendation.py` |
| `tools/` | `diagram.py` (architecture figure), `build_notebook.py`, `md2pdf.py` (Markdown → PDF via pandoc + headless Chrome) |
| `data/raw/` | The three CSVs exactly as received |

## Reproduce

```bash
pip install -r requirements.txt
python run_analysis.py        # regenerates Part 1 tables, queries.sql, results/ and all charts; asserts internal consistency
```

Definitions follow the brief exactly: a customer has at least one **delivered** order and is counted under their signup channel; CAC = spend ÷ customers; LTV = six-month revenue per customer × 30%; repeat rate = share of customers with two or more delivered orders. Money is rounded to the nearest rupee and percentages to one decimal at display time only.
