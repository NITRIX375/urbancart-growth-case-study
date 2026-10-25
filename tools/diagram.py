"""Draws Part3_Design/architecture.png with matplotlib (no graphviz needed)."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
BLUE, ORANGE, AQUA, YELLOW, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#6250d6"
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"]})

fig, ax = plt.subplots(figsize=(16, 9.2))
fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
ax.set_xlim(0, 16); ax.set_ylim(0, 9.2); ax.axis("off")

def box(x, y, w, h, title, body="", color=BLUE, fill=False, fs=10.5):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                       linewidth=1.6, edgecolor=color, facecolor=(color if fill else "white"), alpha=1, zorder=3)
    ax.add_patch(p)
    tc = "white" if fill else INK
    ax.text(x + w / 2, y + h - 0.28, title, ha="center", va="top", fontsize=fs, fontweight="bold", color=tc, zorder=4)
    if body:
        ax.text(x + w / 2, y + h - 0.62 - 0.32 * (title.count("\n")), body, ha="center", va="top", fontsize=8.6, color=(tc if fill else INK2), zorder=4, linespacing=1.35)

def arrow(x1, y1, x2, y2, color=MUTED, style="-|>", lw=1.6, ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=14, color=color, lw=lw, linestyle=ls, zorder=2))

# ---- title
ax.text(0.3, 8.85, "UrbanCart growth analytics on GCP: daily pipeline and self-serve layer", fontsize=15, fontweight="bold", color=INK, va="center")
ax.text(0.3, 8.45, "Left to right: sources land raw, get transformed and tested by dbt, and are read by a dashboard and a Slack agent that can only run approved metric templates.",
        fontsize=9.5, color=INK2, va="center")

# ---- orchestration band
box(0.3, 7.25, 12.1, 0.8, "Cloud Composer (Airflow) · daily 02:00 IST · extract → load raw → dbt staging → dbt marts → dbt tests → publish",
    "", color=VIOLET, fs=10)
# ---- sources
ax.text(1.35, 6.95, "SOURCES", ha="center", fontsize=8.5, color=MUTED, fontweight="bold")
srcs = [("GA4", "website activity"), ("Salesforce", "customers, orders"), ("MoEngage", "campaign engagement"), ("Google Ads", "spend"), ("Meta Ads", "spend")]
for i, (t, b) in enumerate(srcs):
    y = 5.95 - i * 1.0
    box(0.3, y, 2.1, 0.8, t, b, color=MUTED, fs=10)
# ---- ingestion
ax.text(4.3, 6.95, "INGESTION", ha="center", fontsize=8.5, color=MUTED, fontweight="bold")
box(3.3, 5.45, 2.0, 1.3, "GA4 native\nBigQuery export", "", color=BLUE)
box(3.3, 2.0, 2.0, 2.9, "Airbyte\nconnectors", "incremental syncs\nfor Salesforce, MoEngage,\nGoogle Ads, Meta Ads\n\nCloud Run extractor\nonly where no\nconnector exists", color=BLUE)
arrow(2.4, 6.35, 3.3, 6.1)
for i in range(1, 5):
    arrow(2.4, 6.35 - i * 1.0, 3.3, 3.45)
# ---- landing
ax.text(7.2, 6.95, "LANDING + WAREHOUSE", ha="center", fontsize=8.5, color=MUTED, fontweight="bold")
box(6.2, 4.9, 2.0, 1.85, "Cloud Storage", "raw/<source>/dt=…/\nimmutable, partitioned\nby load date", color=AQUA)
box(6.2, 2.0, 2.0, 2.4, "BigQuery\nraw_* datasets", "loaded as-is,\nno transformation", color=AQUA)
arrow(5.3, 6.1, 6.2, 5.9); arrow(5.3, 3.45, 6.2, 3.3); arrow(7.2, 4.9, 7.2, 4.4)
# ---- transform
ax.text(10.1, 6.95, "TRANSFORM + TEST (dbt)", ha="center", fontsize=8.5, color=MUTED, fontweight="bold")
box(9.1, 4.9, 2.0, 1.85, "staging", "typed · dedupe on order_id\ninternal-domain flag\nunknown-channel flag", color=ORANGE)
box(9.1, 2.6, 2.0, 1.8, "marts", "dim_customer · fct_orders\nfct_spend\nchannel_metrics_monthly", color=ORANGE)
box(9.1, 0.95, 2.0, 1.2, "quarantine", "rows failing soft tests\n+ Slack alert", color=ORANGE)
arrow(8.2, 3.2, 9.1, 5.6); arrow(10.1, 4.9, 10.1, 4.4); arrow(10.1, 2.6, 10.1, 2.15, ls="--")
ax.text(11.25, 2.35, "dbt tests: unique(order_id) · not_null(channel) · order_date ≥ signup_date\naccepted_values(status) · spend complete per channel×month · freshness\ncritical fail → stop DAG; soft fail → quarantine + alert",
        fontsize=7.4, color=INK2, va="top", ha="left", linespacing=1.4)
# ---- consumers
ax.text(14.1, 6.95, "SELF-SERVE", ha="center", fontsize=8.5, color=MUTED, fontweight="bold")
box(12.6, 5.2, 3.1, 1.55, "Looker Studio dashboard", "weekly view: spend, new customers,\nCAC, LTV:CAC, trend, DQ status\n'data as of' badge from pipeline_runs", color=BLUE, fill=True)
box(12.6, 2.6, 3.1, 2.3, "Slack agent (Claude)", "1 question → 2 pick metric + params\nfrom metric registry → 3 validate\n→ 4 run approved SQL template\n(read-only, limits) → 5 answer shows\nnumber + SQL + data-as-of\nLLM never writes free SQL\nor does arithmetic", color=BLUE, fill=True)
arrow(11.1, 3.5, 12.6, 5.95); arrow(11.1, 3.5, 12.6, 3.75)
# ---- bottom band
box(0.3, 0.05, 12.1, 0.85, "Secrets: Secret Manager + least-privilege service accounts (Workload Identity), nothing in code",
    "Failure visibility: Airflow on_failure → Slack #growth-data-alerts · freshness alert if marts > 26 h old · 'data as of' badge on the dashboard", color=VIOLET, fs=9)
ax.text(12.65, 0.47, "Agent testing: 40 golden questions with known\nanswers (≥95% exact) · dbt unit tests per template\n2-week shadow run · CMO UAT", fontsize=8, color=INK2, ha="left", va="center", linespacing=1.4)

fig.savefig(Path(__file__).resolve().parent.parent / "Part3_Design" / "architecture.png", dpi=170, bbox_inches="tight", facecolor=SURFACE)
print("architecture.png written")
