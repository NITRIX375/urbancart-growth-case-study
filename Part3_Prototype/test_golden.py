"""Golden-question tests: known answers from Part 1. Runs on the rule-based parser so it needs no API key.
Set GOLDEN_USE_GEMINI=1 to run the same suite through Gemini (needs a key; respects free-tier rate limits poorly).

    python -m unittest Part3_Prototype.test_golden -v
"""
import csv
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from Part3_Prototype.engine import Engine  # noqa: E402

import os
ENGINE = Engine(use_llm=bool(os.environ.get("GOLDEN_USE_GEMINI")))

GOLDEN = [  # (question, number that must appear in the answer, channel that must be the first row or None)
    ("What was Meta's CAC in March?",                   "₹789",      "Meta Ads"),
    ("What was Meta's CAC last month?",                 "₹1,115",    "Meta Ads"),
    ("What is Google Ads CAC?",                         "₹611",      "Google Ads"),
    ("Affiliate repeat purchase rate",                  "8.1%",      "Affiliate"),
    ("Which channel has the best LTV:CAC?",             "1.14",      "Google Ads"),
    ("Which channel has the worst LTV:CAC?",            "0.42",      "Affiliate"),
    ("How much did we spend on Influencer in Q2?",      "₹1,54,000", "Influencer"),
    ("Revenue per customer for Organic",                "₹1,903",    "Organic"),
    ("Meta new customers in April",                     "123",       "Meta Ads"),
    ("LTV of Influencer",                               "₹857",      "Influencer"),
    ("Total paid spend in Q2",                          "₹8,68,000", None),
    ("Which channel is cheapest on CAC?",               "₹611",      "Google Ads"),
    ("Meta CAC by month",                               "₹491",      "Meta Ads"),
    ("Meta CAC by month",                               "₹1,115",    "Meta Ads"),
]
CLARIFY = [
    "What was the weather yesterday?",
    "What was Meta's CAC in July?",
    "Organic CAC",
    "Which channel is the worst?",          # no metric
]


class Golden(unittest.TestCase):
    def test_golden_answers(self):
        for q, number, first_channel in GOLDEN:
            with self.subTest(q=q):
                r = ENGINE.ask(q)
                self.assertEqual(r["type"], "answer", r["answer"])
                self.assertIn(number, r["answer"])            # phrasing-independent: the number must be there
                if first_channel:
                    self.assertEqual(r["rows"][0]["channel"], first_channel)

    def test_clarifies_instead_of_guessing(self):
        for q in CLARIFY:
            with self.subTest(q=q):
                r = ENGINE.ask(q)
                self.assertEqual(r["type"], "clarify", r["answer"])
                self.assertIsNone(r["sql"])

    def test_every_h1_metric_matches_part1_tables(self):
        q2 = {r["channel"]: r for r in csv.DictReader((ROOT / "Part1_Analysis/results/q2.csv").read_text().splitlines())}
        q3 = {r["channel"]: r for r in csv.DictReader((ROOT / "Part1_Analysis/results/q3.csv").read_text().splitlines())}
        q4 = {r["channel"]: r for r in csv.DictReader((ROOT / "Part1_Analysis/results/q4.csv").read_text().splitlines())}
        for ch in ["Google Ads", "Meta Ads", "Affiliate", "Influencer", "Organic"]:
            rpc = ENGINE.ask(f"{ch} revenue per customer")["rows"][0]["revenue_per_customer"]
            self.assertEqual(rpc, ENGINE_fmt(float(q3[ch]["revenue_per_customer"]), "inr"), ch)
            rep = ENGINE.ask(f"{ch} repeat rate")["rows"][0]["repeat_rate_pct"]
            self.assertEqual(rep, f"{float(q3[ch]['repeat_rate_pct']):.1f}%", ch)
            if ch != "Organic":
                self.assertEqual(ENGINE.ask(f"{ch} CAC")["rows"][0]["cac"], ENGINE_fmt(float(q2[ch]["cac"]), "inr"), ch)
                self.assertEqual(ENGINE.ask(f"{ch} LTV:CAC")["rows"][0]["ltv_to_cac"], f"{float(q4[ch]['ltv_to_cac']):.2f}", ch)

    def test_checker_rejects_foreign_numbers(self):
        from Part3_Prototype.engine import numbers_in
        facts = '{"values": {"Meta Ads": "₹789"}, "period": "March 2026"}'
        self.assertTrue(numbers_in("Meta's CAC in March 2026 was ₹789.") <= numbers_in(facts))
        self.assertFalse(numbers_in("Meta's CAC in March 2026 was ₹790.") <= numbers_in(facts))
        self.assertFalse(numbers_in("Meta's CAC was ₹789, up 12% on February.") <= numbers_in(facts))

    def test_every_question_is_logged(self):
        before = len(ENGINE.log)
        ENGINE.ask("Google CAC in May")
        self.assertEqual(len(ENGINE.log), before + 1)
        self.assertIn("sql", ENGINE.log[-1])


def ENGINE_fmt(v, unit):
    from Part3_Prototype.engine import fmt
    return fmt(v, unit)


if __name__ == "__main__":
    unittest.main(verbosity=2)
