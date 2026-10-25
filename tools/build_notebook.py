"""Builds Part1_Analysis/Part1_Analysis.ipynb from the same engine, then executes it so outputs render on GitHub."""
import subprocess
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parent.parent
nb = nbf.v4.new_notebook()
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
cells = [
    md("# Part 1 — Analysis (executed notebook)\n\nSame engine as `run_analysis.py`: DuckDB SQL from `src/queries.py`, pandas for pivots and an independent cross-check. "
       "Money is rounded to the nearest rupee and percentages to one decimal at display time only. The narrative answers are in `Part1_Analysis.md` / `.pdf`; this notebook shows the tables with the code that produced them."),
    code("import sys\nfrom pathlib import Path\nROOT = Path.cwd().resolve()\nROOT = ROOT if (ROOT / 'src').exists() else ROOT.parent\nsys.path.insert(0, str(ROOT))\n\n"
         "import pandas as pd\nfrom IPython.display import Image, display\nfrom src import analysis as A, queries as Q\n"
         "pd.set_option('display.width', 200); pd.set_option('display.max_columns', 30)\n\n"
         "res = A.run_all(ROOT / 'data' / 'raw')\n\n"
         "def show(df, money=(), pct=(), ratio=(), index=False):\n    d = df.copy()\n    for c in money: d[c] = d[c].map(A.inr)\n    for c in pct: d[c] = d[c].map(A.pct)\n    for c in ratio: d[c] = d[c].map(A.ratio)\n    display(d if index else d.reset_index(drop=True))"),
    md("## 1. Data quality\n\nFour issues found (duplicate order rows, blank channel, internal test accounts, non-delivered orders) plus the checks that passed. The SQL for each check is printed above its result."),
    code("for name in ['duplicate_order_rows', 'conflicting_duplicates', 'blank_channel', 'internal_accounts', 'status_mix', 'passed_checks']:\n    print(Q.DQ[name].strip().splitlines()[0].strip())\n    display(res.dq[name].round(2))"),
    md("**Why the internal accounts matter** — Affiliate with and without the 35 `@urbancart.in` accounts:"),
    code("print(Q.AFFILIATE_BEFORE_AFTER.strip().splitlines()[0].strip())\nshow(res.affiliate_before_after, money=['revenue_per_customer', 'cac'], pct=['repeat_rate_pct'], ratio=['ltv_to_cac'])"),
    md("## 2. Acquisition cost (paid channels)"),
    code("print(Q.Q2_ACQUISITION_COST)\nshow(res.q2, money=['spend_inr', 'cac'])"),
    md("## 3. Customer value (all channels, including Organic)"),
    code("print(Q.Q3_CUSTOMER_VALUE)\nshow(res.q3, money=['revenue', 'revenue_per_customer'], pct=['repeat_rate_pct'])"),
    md("## 4. Return on spend (LTV:CAC)"),
    code("print(Q.Q4_LTV_CAC.replace('{margin}', str(A.MARGIN)))\nshow(res.q4, money=['revenue_per_customer', 'ltv', 'cac'], ratio=['ltv_to_cac'])\n"
         "print(f'Best: {res.q4.iloc[0].channel} ({res.q4.iloc[0].ltv_to_cac:.2f}); worst: {res.q4.iloc[-1].channel} ({res.q4.iloc[-1].ltv_to_cac:.2f})')"),
    md("## 5. Trend — monthly CAC by signup-month cohort"),
    code("print(Q.Q5_MONTHLY_CAC)\nshow(res.q5_cac.rename_axis('channel'), money=list(res.q5_cac.columns), index=True)\n"
         "show(res.q5_change[['channel', 'cac_jan', 'cac_jun', 'abs_change', 'pct_change', 'spend_pct_change']], money=['cac_jan', 'cac_jun', 'abs_change'], pct=['pct_change', 'spend_pct_change'])\n"
         "display(Image(filename=str(ROOT / 'Part1_Analysis' / 'charts' / 'meta_spend_vs_new_customers.png'), width=820))\n"
         "display(Image(filename=str(ROOT / 'Part2_Memo' / 'charts' / '2_monthly_cac_trend.png'), width=820))"),
    md("Cohort truncation check — repeat rate by signup month (June signups had at most 30 days to repeat):"),
    code("show(res.repeat_by_month, pct=['repeat_rate_pct'])"),
    md("## 6. Sanity check — Google Ads CAC\n\nReconciliation of every customer into one bucket, hand arithmetic, an independent pandas-only recomputation, and a plausibility check."),
    code("print(Q.Q6_RECONCILIATION)\ndisplay(res.q6)\n"
         "g = res.q2.set_index('channel').loc['Google Ads']\n"
         "print(f\"Hand arithmetic: {A.inr(g.spend_inr)} / {int(g.new_customers)} = {g.cac:.2f} -> {A.inr(g.cac)}\")\n"
         "print('pandas-only recomputation:', res.pandas_crosscheck)\n"
         "assert abs(res.pandas_crosscheck['google_cac'] - g.cac) < 1e-9\n"
         "show(res.conversion, pct=['conversion_pct'])"),
    md("## Supporting tables"),
    code("show(res.return_rate, pct=['cancel_or_return_pct'])\nshow(res.spend_by_quarter, money=['q1_spend', 'q2_spend', 'h1_spend'])\n"
         "display(Image(filename=str(ROOT / 'Part2_Memo' / 'charts' / '1_ltv_cac_by_channel.png'), width=820))"),
]
nb.cells = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out = ROOT / "Part1_Analysis" / "Part1_Analysis.ipynb"
nbf.write(nb, out)
subprocess.run([sys_exe := __import__("sys").executable, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute", "--inplace",
                "--ExecutePreprocessor.timeout=180", str(out)], check=True, cwd=ROOT)
print("notebook built and executed:", out.relative_to(ROOT))
