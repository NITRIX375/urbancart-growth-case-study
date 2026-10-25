"""The Part 2 recommendation as data, so the memo chart and the memo text share one source."""

BASELINE_QUARTER = "Q2 2026 (Apr–Jun)"
Q2_SPEND = {"Meta Ads": 339_000, "Google Ads": 205_000, "Affiliate": 170_000, "Influencer": 154_000}
PROPOSED = {"Meta Ads": 289_000, "Google Ads": 251_400, "Affiliate": 0, "Influencer": 154_000}

TOTAL_Q2 = sum(Q2_SPEND.values())          # 868,000
TOTAL_PROPOSED = sum(PROPOSED.values())    # 694,400
CUT = TOTAL_Q2 - TOTAL_PROPOSED            # 173,600 = exactly 20% of Q2
assert abs(CUT / TOTAL_Q2 - 0.20) < 1e-9, CUT / TOTAL_Q2
