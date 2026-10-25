"""Part 1 engine.

Loads the three raw CSVs into DuckDB, runs the data-quality checks, builds the
clean layer (dedupe + flags), and computes every Part 1 metric with the SQL in
queries.py. Numbers are kept unrounded here and rounded only when displayed
(money -> nearest rupee, percentages -> one decimal), as the brief asks.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from src import queries as Q

MARGIN = 0.30                      # contribution margin given in the brief
PAID = ["Google Ads", "Meta Ads", "Affiliate", "Influencer"]
ALL_CHANNELS = PAID + ["Organic"]
MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
MONTH_LABEL = dict(zip(MONTHS, ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]))


# ----------------------------------------------------------------- formatting
def inr(x: float) -> str:
    """Indian-style grouping, nearest rupee: 400000 -> ₹4,00,000."""
    n = int(round(float(x)))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-" if n < 0 else "") + "₹" + s


def pct(x: float) -> str:
    return f"{float(x):.1f}%"


def num(x: float) -> str:
    return f"{int(round(float(x))):,}"


def ratio(x: float) -> str:
    return f"{float(x):.2f}"


def md_table(df: pd.DataFrame, fmt: dict | None = None, index: bool = False) -> str:
    """Render a DataFrame as a GitHub-markdown table, applying per-column formatters."""
    fmt = fmt or {}
    d = df.reset_index() if index else df.copy()
    cols = list(d.columns)
    rows = []
    for _, r in d.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if c in fmt and pd.notna(v):
                cells.append(fmt[c](v))
            elif pd.isna(v):
                cells.append("–")
            elif isinstance(v, float):
                cells.append(f"{v:,.1f}")
            else:
                cells.append(str(v))
        rows.append("| " + " | ".join(cells) + " |")
    header = "| " + " | ".join(str(c) for c in cols) + " |"
    sep = "|" + "|".join("---" for _ in cols) + "|"
    return "\n".join([header, sep, *rows])


# -------------------------------------------------------------------- engine
@dataclass
class Results:
    dq: dict                     # name -> DataFrame (one row each, or status mix)
    q2: pd.DataFrame
    q3: pd.DataFrame
    q4: pd.DataFrame
    q5_long: pd.DataFrame
    q5_cac: pd.DataFrame         # pivot channel x month
    q5_customers: pd.DataFrame
    q5_spend: pd.DataFrame
    q5_change: pd.DataFrame      # Jan -> Jun change per channel
    q6: pd.DataFrame
    affiliate_before_after: pd.DataFrame
    return_rate: pd.DataFrame
    conversion: pd.DataFrame
    repeat_by_month: pd.DataFrame
    spend_by_quarter: pd.DataFrame
    pandas_crosscheck: dict


def connect(data_dir: Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for sql in Q.LOAD_RAW.values():
        con.execute(sql.format(data_dir=str(data_dir), margin=MARGIN))
    return con


def run_sql(con, sql: str) -> pd.DataFrame:
    return con.execute(sql.format(margin=MARGIN, data_dir="")).df()


def build_clean(con) -> None:
    for sql in Q.BUILD_CLEAN.values():
        con.execute(sql)


def pandas_crosscheck(data_dir: Path) -> dict:
    """Independent recomputation of Google Ads CAC with pandas only (no SQL), for Q6."""
    users = pd.read_csv(data_dir / "users.csv")
    orders = pd.read_csv(data_dir / "orders.csv").drop_duplicates()
    clean_users = users[users.acquisition_channel.notna()
                        & ~users.email.str.lower().str.endswith("@urbancart.in")]
    google_users = clean_users[clean_users.acquisition_channel == "Google Ads"].user_id
    delivered = orders[(orders.status == "delivered") & orders.user_id.isin(google_users)]
    customers = delivered.user_id.nunique()
    spend = pd.read_csv(data_dir / "marketing_spend.csv").query("channel == 'Google Ads'").spend_inr.sum()
    return {"google_customers": int(customers), "google_spend": float(spend),
            "google_cac": float(spend) / customers, "google_signups": int((clean_users.acquisition_channel == "Google Ads").sum())}


def run_all(data_dir: Path) -> Results:
    con = connect(data_dir)
    dq = {name: run_sql(con, sql) for name, sql in Q.DQ.items()}
    build_clean(con)

    q2 = run_sql(con, Q.Q2_ACQUISITION_COST)
    q3 = run_sql(con, Q.Q3_CUSTOMER_VALUE)
    q4 = run_sql(con, Q.Q4_LTV_CAC)
    q5 = run_sql(con, Q.Q5_MONTHLY_CAC)
    q6 = run_sql(con, Q.Q6_RECONCILIATION)

    piv = lambda col: (q5.pivot(index="channel", columns="month", values=col)
                       .reindex(PAID)[MONTHS].rename(columns=MONTH_LABEL))
    q5_cac, q5_customers, q5_spend = piv("cac"), piv("new_customers"), piv("spend_inr")
    q5_change = pd.DataFrame({
        "channel": PAID,
        "cac_jan": q5_cac["Jan"].values, "cac_jun": q5_cac["Jun"].values,
    })
    q5_change["abs_change"] = q5_change.cac_jun - q5_change.cac_jan
    q5_change["pct_change"] = 100 * (q5_change.cac_jun / q5_change.cac_jan - 1)
    q5_change["spend_jan"] = q5_spend["Jan"].values
    q5_change["spend_jun"] = q5_spend["Jun"].values
    q5_change["spend_pct_change"] = 100 * (q5_change.spend_jun / q5_change.spend_jan - 1)
    q5_change["cust_jan"] = q5_customers["Jan"].values
    q5_change["cust_jun"] = q5_customers["Jun"].values
    q5_change = q5_change.sort_values("pct_change", ascending=False).reset_index(drop=True)

    return Results(
        dq=dq, q2=q2, q3=q3, q4=q4, q5_long=q5, q5_cac=q5_cac, q5_customers=q5_customers,
        q5_spend=q5_spend, q5_change=q5_change, q6=q6,
        affiliate_before_after=run_sql(con, Q.AFFILIATE_BEFORE_AFTER),
        return_rate=run_sql(con, Q.RETURN_RATE_BY_CHANNEL),
        conversion=run_sql(con, Q.CONVERSION_BY_CHANNEL),
        repeat_by_month=run_sql(con, Q.REPEAT_BY_SIGNUP_MONTH),
        spend_by_quarter=run_sql(con, Q.SPEND_BY_QUARTER),
        pandas_crosscheck=pandas_crosscheck(data_dir),
    )


def queries_sql_text() -> str:
    out = ["-- UrbanCart case study: every SQL statement used in Part 1, in execution order.",
           "-- Dialect: DuckDB. {margin} = 0.30 (contribution margin from the brief).", ""]
    for section, group in Q.ORDERED:
        out.append(f"-- {'=' * 76}\n-- {section}\n-- {'=' * 76}")
        for name, sql in group.items():
            body = sql.replace("{data_dir}", "data/raw").replace("{{", "{").replace("}}", "}") \
                      .replace("{margin}", str(MARGIN))
            out.append(f"-- [{name}]\n{body.strip()};\n")
    return "\n".join(out)
