# AI-use note

- **Tools used:** Claude Code (Claude Fable 5.1) in the terminal, for the DuckDB SQL and Python scaffolding, the chart code, first drafts of the memo and design note, and proofreading. No other AI tools.
- **How I checked it:** every metric is recomputed independently (pandas with no SQL vs DuckDB) and `run_analysis.py` asserts on every run that the two agree, that the reconciliation ties, and that the CAC inside the LTV:CAC query equals the Q2 CAC.
- **What it got wrong:** its first LTV:CAC query joined monthly spend to customers *before* aggregating, so the join fanned out and "CAC" came back as total spend (LTV:CAC 0.0017 instead of 1.14). I caught it because that CAC no longer matched Q2, rewrote the query to aggregate spend and customers separately before joining, and turned the comparison into a permanent assertion.
- **A second slip:** its first data profile counted the internal accounts' orders before de-duplicating (310 instead of the correct 285); de-duplication now happens first in the clean layer, so every downstream count inherits it.
