"""All charts. Static PNGs for the memo / PDFs.

Colour follows the entity (each channel always has the same hue across every
chart), assigned in a fixed order from a colour-blind-validated categorical
palette. One axis per chart; two measures of different scale get two panels.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import ticker

from src.analysis import PAID, Results, inr
from src import recommendation as R

SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
CHANNEL_COLOR = {"Google Ads": "#2a78d6", "Meta Ads": "#eb6834", "Affiliate": "#1baf7a",
                 "Influencer": "#eda100", "Organic": "#e87ba4"}

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
    "font.size": 10, "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlecolor": INK,
    "axes.titlelocation": "left", "legend.frameon": False, "figure.dpi": 150, "savefig.dpi": 200,
})


def _finish(fig, ax, subtitle: str | None = None, source: str = "Source: UrbanCart users/orders/marketing_spend, Jan–Jun 2026, after cleaning"):
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, color=INK2, fontsize=9.5, va="bottom")
    fig.text(0.01, 0.01, source, color=MUTED, fontsize=8)
    fig.tight_layout(rect=(0, 0.035, 1, 1))


def lakh(v):
    return f"₹{v / 1e5:.2f}L"


def chart_ltv_cac(r: Results, out: Path):
    q4 = r.q4.sort_values("ltv_to_cac")
    naive_aff = float(r.affiliate_before_after.iloc[0].ltv_to_cac)
    labels = list(q4.channel) + ["Affiliate as reported\n(incl. 35 test accounts)"]
    vals = list(q4.ltv_to_cac) + [naive_aff]
    fig, ax = plt.subplots(figsize=(8, 4.4))
    colors = [CHANNEL_COLOR[c] for c in q4.channel] + [CHANNEL_COLOR["Affiliate"]]
    bars = ax.barh(labels, vals, color=colors, height=0.55, zorder=3)
    bars[-1].set_alpha(0.25); bars[-1].set_hatch("////"); bars[-1].set_edgecolor(CHANNEL_COLOR["Affiliate"])
    ax.axvline(1.0, color=INK2, lw=1, ls=(0, (4, 3)), zorder=2)
    ax.text(1.0, -0.62, " break-even (LTV = CAC)", color=INK2, fontsize=9, va="center")
    ax.set_ylim(-0.85, len(labels) - 0.45)
    for b, v in zip(bars, vals):
        ax.text(v + 0.02, b.get_y() + b.get_height() / 2, f"{v:.2f}", va="center", color=INK, fontsize=10, fontweight="bold")
    ax.set_xlim(0, 1.45); ax.xaxis.grid(True, color=GRID, lw=0.8, zorder=0); ax.set_axisbelow(True)
    ax.set_xlabel("LTV : CAC"); ax.tick_params(axis="y", length=0, labelcolor=INK)
    ax.set_title("Only Google Ads earns back what it costs to acquire a customer", pad=22)
    _finish(fig, ax, "LTV:CAC by paid channel, Jan–Jun 2026 · LTV = 6-month revenue per customer × 30% margin")
    fig.savefig(out); plt.close(fig)


def chart_monthly_cac(r: Results, out: Path):
    months = list(r.q5_cac.columns)
    fig, ax = plt.subplots(figsize=(8, 4.4))
    for ch in ["Google Ads", "Affiliate", "Influencer", "Meta Ads"]:
        y = r.q5_cac.loc[ch].values
        lw = 2.8 if ch == "Meta Ads" else 2
        ax.plot(months, y, color=CHANNEL_COLOR[ch], lw=lw, marker="o", ms=5, label=ch, zorder=3)
        ax.text(len(months) - 1 + 0.12, y[-1], f"{ch}  {inr(y[-1])}", color=INK, fontsize=9, va="center",
                fontweight="bold" if ch == "Meta Ads" else "normal")
    ax.text(0 - 0.12, r.q5_cac.loc["Meta Ads"].values[0], inr(r.q5_cac.loc["Meta Ads"].values[0]), color=INK, fontsize=9,
            va="center", ha="right", fontweight="bold")
    ax.set_xlim(-0.6, len(months) - 1 + 1.9); ax.set_ylim(0, 1250)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"₹{v:,.0f}"))
    ax.yaxis.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True); ax.set_ylabel("CAC (spend ÷ new customers who signed up that month)")
    ax.legend(loc="upper left", ncol=4, fontsize=9, labelcolor=INK2)
    ax.set_title("Meta's cost per new customer more than doubled; the other three held flat", pad=22)
    _finish(fig, ax, "Monthly CAC by paid channel, Jan–Jun 2026 · Meta spend +115% over the period, Meta new customers 110 to 104")
    fig.savefig(out); plt.close(fig)


def chart_meta_spend_vs_customers(r: Results, out: Path):
    months = list(r.q5_cac.columns)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 3.6), sharex=True)
    sp, cu = r.q5_spend.loc["Meta Ads"].values, r.q5_customers.loc["Meta Ads"].values
    a1.bar(months, sp, color=CHANNEL_COLOR["Meta Ads"], width=0.55, zorder=3)
    a1.set_title("Meta monthly spend", fontsize=11); a1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"₹{v / 1e3:.0f}k"))
    for i, v in enumerate(sp):
        a1.text(i, v + 2000, f"{v / 1e3:.0f}k", ha="center", color=INK, fontsize=9)
    a2.bar(months, cu, color=CHANNEL_COLOR["Meta Ads"], width=0.55, zorder=3)
    a2.set_title("Meta new customers (by signup month)", fontsize=11)
    for i, v in enumerate(cu):
        a2.text(i, v + 2, f"{int(v)}", ha="center", color=INK, fontsize=9)
    for a in (a1, a2):
        a.yaxis.grid(True, color=GRID, lw=0.8); a.set_axisbelow(True); a.tick_params(axis="x", length=0)
    a1.set_ylim(0, 135000); a2.set_ylim(0, 150)
    fig.suptitle("Meta: spend more than doubled, new customers did not move", x=0.01, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.text(0.01, 0.01, "Source: marketing_spend.csv and clean customers, Jan–Jun 2026", color=MUTED, fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 0.93)); fig.savefig(out); plt.close(fig)


def chart_reallocation(out: Path):
    chans = ["Meta Ads", "Google Ads", "Affiliate", "Influencer"]
    cur = [R.Q2_SPEND[c] for c in chans]; new = [R.PROPOSED[c] for c in chans]
    fig, ax = plt.subplots(figsize=(8, 4.4))
    y = range(len(chans)); h = 0.34
    b1 = ax.barh([i + h / 2 + 0.02 for i in y], cur, height=h, color=AXIS, label=f"{R.BASELINE_QUARTER} actual", zorder=3)
    b2 = ax.barh([i - h / 2 - 0.02 for i in y], new, height=h, color="#2a78d6", label="Proposed next quarter", zorder=3)
    for b, v in list(zip(b1, cur)) + list(zip(b2, new)):
        ax.text(v + 4000, b.get_y() + b.get_height() / 2, lakh(v) if v else "₹0 (cut)", va="center", color=INK, fontsize=9.5)
    deltas = {c: R.PROPOSED[c] - R.Q2_SPEND[c] for c in chans}
    for i, c in enumerate(chans):
        d = deltas[c]
        txt = "unchanged" if d == 0 else f"{'+' if d > 0 else '−'}{lakh(abs(d))}"
        ax.text(398000, i, txt, va="center", ha="right", color=("#006300" if d > 0 else INK2), fontsize=9.5, fontweight="bold")
    ax.set_yticks(list(y)); ax.set_yticklabels(chans, color=INK); ax.tick_params(axis="y", length=0); ax.invert_yaxis()
    ax.set_xlim(0, 400000); ax.xaxis.set_major_locator(ticker.MultipleLocator(100000))
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"₹{v / 1e5:.0f}L"))
    ax.xaxis.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2, fontsize=9, labelcolor=INK2)
    ax.set_title(f"Proposed budget: {lakh(R.TOTAL_Q2)} to {lakh(R.TOTAL_PROPOSED)} per quarter (−20%)", pad=22)
    _finish(fig, ax, "Cut Affiliate to zero, trim Meta to its early-Q2 run-rate, reinvest part of the saving in Google Ads",
            source="Baseline = Apr–Jun 2026 spend from marketing_spend.csv")
    fig.savefig(out); plt.close(fig)


def write_all(r: Results, root: Path) -> None:
    p1, p2 = root / "Part1_Analysis" / "charts", root / "Part2_Memo" / "charts"
    p1.mkdir(parents=True, exist_ok=True); p2.mkdir(parents=True, exist_ok=True)
    chart_ltv_cac(r, p2 / "1_ltv_cac_by_channel.png")
    chart_monthly_cac(r, p2 / "2_monthly_cac_trend.png")
    chart_reallocation(p2 / "3_proposed_reallocation.png")
    chart_meta_spend_vs_customers(r, p1 / "meta_spend_vs_new_customers.png")
