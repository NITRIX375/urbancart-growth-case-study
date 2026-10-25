"""Reproduce every Part 1 table and every chart from data/raw/.

    python run_analysis.py

Writes Part1_Analysis/Part1_Analysis.md, Part1_Analysis/queries.sql,
Part1_Analysis/results/*.csv and the PNG charts under Part1_Analysis/charts and
Part2_Memo/charts. Fails loudly if any internal consistency check breaks.
"""
from pathlib import Path

from src import analysis as A, charts, report

ROOT = Path(__file__).resolve().parent


def consistency_checks(r: A.Results) -> None:
    # 1. the CAC inside the LTV:CAC query must equal the Q2 CAC for every channel
    q2 = r.q2.set_index("channel").cac
    for _, row in r.q4.iterrows():
        assert abs(row.cac - q2[row.channel]) < 1e-9, (row.channel, row.cac, q2[row.channel])
    # 2. the reconciliation must tie: sum of buckets == distinct customers
    buckets = r.q6.set_index("bucket").customers
    total = buckets.pop("total distinct customers (deduped orders)")
    assert buckets.sum() == total, (buckets.sum(), total)
    # 3. the pandas-only recomputation must match DuckDB to the paisa
    assert abs(r.pandas_crosscheck["google_cac"] - q2["Google Ads"]) < 1e-9
    assert r.pandas_crosscheck["google_customers"] == int(r.q2.set_index("channel").new_customers["Google Ads"])
    # 4. monthly new customers must sum to the H1 customer count per channel
    for ch in A.PAID:
        assert int(r.q5_customers.loc[ch].sum()) == int(r.q2.set_index("channel").new_customers[ch]), ch


if __name__ == "__main__":
    res = A.run_all(ROOT / "data" / "raw")
    consistency_checks(res)
    report.write_outputs(res, ROOT)
    charts.write_all(res, ROOT)
    print("OK — Part1_Analysis/Part1_Analysis.md, queries.sql, results/ and charts regenerated; all consistency checks passed.")
