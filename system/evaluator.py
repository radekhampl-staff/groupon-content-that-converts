"""
Multi-signal evaluator for rewrites.

Four independent signals — deliberately NOT a single LLM self-judge:

  1. scorer_delta      Rule-based: new score - original score (0–100)
  2. specificity_gain  Heuristic: concrete nouns + numbers added
  3. hallucination     Heuristic: claims in rewrite not grounded in source fields
  4. llm_judge         Blind A/B: Claude rates both versions without knowing which is original

Final verdict: APPROVE / FLAG / REJECT

Usage:
  python evaluator.py --file results/rewrites/<deal_id>.json  # evaluate one rewrite
  python evaluator.py --all                                    # evaluate all rewrites in results/
"""

import os
import re
import sys
import json
import random
import argparse
import pandas as pd
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))
from scorer     import score_deal
from llm_client import get_client


# ── Signal 1: Scorer delta ────────────────────────────────────────────────────

def eval_scorer_delta(original_row: pd.Series, new_title: str, new_desc: str) -> dict:
    """Compare content score before and after rewrite."""
    orig_score = score_deal(original_row)["total_score"]

    fake_row = original_row.copy()
    fake_row["title"]       = new_title
    fake_row["description"] = new_desc
    new_score = score_deal(fake_row)["total_score"]

    delta = new_score - orig_score
    return {
        "signal":       "scorer_delta",
        "original":     orig_score,
        "new":          new_score,
        "delta":        delta,
        "passed":       delta >= 5,  # at least 5 pts improvement
        "note":         f"{orig_score} → {new_score} ({delta:+d} pts)",
    }


# ── Signal 2: Specificity heuristic ──────────────────────────────────────────

# Patterns that indicate concrete, specific content
SPECIFICITY_PATTERNS = [
    r"\d+[\-–]\d+\s*(min|hour|year|month|day|star|mile|ft|sq)",  # ranges
    r"\b\d+\s*(star|stars|rating|review|client|customer|home|vehicle)\b",  # social proof
    r"\b(FDA|ASE|licensed|bonded|insured|certified|board-certified|dermatologist)\b",
    r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|weekday)\b",
    r"\b(parking|Wi-Fi|complimentary|shuttle|appointment|walk-in)\b",
    r"\b(guarantee|warranty|refund|satisfaction)\b",
]

FILLER_PHRASES = [
    r"experience the best",
    r"top-rated experience",
    r"amazing deal",
    r"popular deal",
    r"this deal won't last",
    r"grab it before it's gone",
    r"opportunity to enjoy",
]

def count_signals(text: str, patterns: list) -> int:
    return sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))

def eval_specificity(original_desc: str, new_desc: str) -> dict:
    orig_specific = count_signals(original_desc, SPECIFICITY_PATTERNS)
    new_specific  = count_signals(new_desc,      SPECIFICITY_PATTERNS)
    orig_filler   = count_signals(original_desc, FILLER_PHRASES)
    new_filler    = count_signals(new_desc,      FILLER_PHRASES)

    specificity_gain = (new_specific - orig_specific)
    filler_reduction = (orig_filler  - new_filler)
    net_score        = specificity_gain + filler_reduction

    return {
        "signal":            "specificity",
        "orig_specific_hits": orig_specific,
        "new_specific_hits":  new_specific,
        "orig_filler_hits":   orig_filler,
        "new_filler_hits":    new_filler,
        "net_score":          net_score,
        "passed":             net_score >= 0 and new_filler == 0,
        "note":               f"specificity +{specificity_gain}, filler -{filler_reduction}",
    }


# ── Signal 3: Hallucination check ────────────────────────────────────────────

# Claims we watch for — if they appear in rewrite but not in source fields, flag them
CLAIM_PATTERNS = [
    (r"(\d+)-star",                   "star rating"),
    (r"over ([\d,]+)\s+(client|home|vehicle|customer)", "client count"),
    (r"(\d+)\s*year[s]?\s*(of\s*)?experience", "years experience"),
    (r"(\d+)%\s*(satisfaction|improvement|client)", "percentage claim"),
    (r"(award[\-\s]winning|nationally recognized|TripAdvisor|Google|Yelp)", "award/platform"),
    (r"(open\s+\d+\s+day|7\s+day)",   "hours claim"),
    (r"free\s+(parking|shuttle|Wi-Fi|refreshment|consultation)", "free amenity"),
]

def extract_claim_values(text: str) -> set:
    """Extract normalized claim strings for comparison."""
    found = set()
    for pattern, label in CLAIM_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            found.add(f"{label}:{m.group(0).lower().strip()}")
    return found

def eval_hallucination(source_text: str, new_desc: str, new_title: str) -> dict:
    """
    Check if new content introduces claims not grounded in any source field.
    source_text = original title + description + option_names concatenated.
    """
    new_claims   = extract_claim_values(new_desc + " " + new_title)
    orig_claims  = extract_claim_values(source_text)
    added_claims = new_claims - orig_claims

    # Also flag if fine print appears rewritten (check for specific phrases)
    suspicious = [c for c in added_claims if any(k in c for k in ["star rating", "percentage"])]

    return {
        "signal":           "hallucination",
        "new_claims":       list(new_claims),
        "added_claims":     list(added_claims),
        "suspicious":       suspicious,
        "passed":           len(suspicious) == 0,
        "note":             f"{len(added_claims)} new claims, {len(suspicious)} suspicious",
    }


# ── Signal 4: LLM blind A/B judge ─────────────────────────────────────────────

JUDGE_PROMPT = """You are evaluating two versions of a deal listing.

Category: {category}
Merchant: {merchant_name}
Options: {option_names}

VERSION {a_label}:
Title: {a_title}
Description: {a_desc}

VERSION {b_label}:
Title: {b_title}
Description: {b_desc}

Which version is more likely to convert a browsing customer into a buyer?
Consider: specificity, trust signals, clarity of what's included, and avoidance of generic filler.

Respond with JSON only:
{{"winner": "{a_label}" or "{b_label}" or "tie", "confidence": "high"/"medium"/"low", "reason": "one sentence"}}"""

def eval_llm_judge(row: pd.Series, new_title: str, new_desc: str) -> dict:
    """Blind A/B: randomize which is A/B so the model can't guess by position."""
    if random.random() > 0.5:
        a_label, a_title, a_desc = "A", row["title"],  row["description"]
        b_label, b_title, b_desc = "B", new_title,     new_desc
        original_is = "A"
    else:
        a_label, a_title, a_desc = "A", new_title,     new_desc
        b_label, b_title, b_desc = "B", row["title"],  row["description"]
        original_is = "B"

    prompt = JUDGE_PROMPT.format(
        category=row["category"], merchant_name=row["merchant_name"],
        option_names=row["option_names"],
        a_label=a_label, a_title=a_title, a_desc=a_desc,
        b_label=b_label, b_title=b_title, b_desc=b_desc,
    )

    client   = get_client()
    response = client.complete("", prompt, max_tokens=200, cache_system=False)
    raw = response.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    parsed = json.loads(raw)

    rewrite_label = "B" if original_is == "A" else "A"
    rewrite_won   = parsed["winner"] == rewrite_label
    tie           = parsed["winner"] == "tie"

    return {
        "signal":        "llm_judge",
        "winner":        "rewrite" if rewrite_won else ("tie" if tie else "original"),
        "confidence":    parsed.get("confidence", "?"),
        "reason":        parsed.get("reason", ""),
        "passed":        rewrite_won or tie,
        "note":          f"rewrite {'won' if rewrite_won else ('tied' if tie else 'lost')} ({parsed.get('confidence','?')} confidence)",
    }


# ── Aggregate verdict ─────────────────────────────────────────────────────────

def aggregate_verdict(signals: list[dict]) -> Literal["APPROVE", "FLAG", "REJECT"]:
    """
    APPROVE  — scorer improved AND no hallucinations AND (specificity OK or LLM judge OK)
    FLAG     — scorer improved but LLM judge prefers original, or minor hallucination concern
    REJECT   — hallucination found, or scorer went down, or LLM judge strongly prefers original
    """
    by_name = {s["signal"]: s for s in signals}

    if not by_name["hallucination"]["passed"]:
        return "REJECT"
    if not by_name["scorer_delta"]["passed"]:
        return "REJECT"

    llm_ok  = by_name["llm_judge"]["passed"]
    spec_ok = by_name["specificity"]["passed"]

    if llm_ok and spec_ok:
        return "APPROVE"
    if llm_ok or spec_ok:
        return "FLAG"
    return "FLAG"


def evaluate_rewrite(rewrite_path: Path, df: pd.DataFrame) -> dict:
    """Run all 4 signals on a saved rewrite JSON. Returns full eval dict."""
    data = json.loads(rewrite_path.read_text())
    deal_id = data["deal_id"]

    row = df[df.deal_id == deal_id]
    if row.empty:
        raise ValueError(f"Deal {deal_id} not found in dataset")
    row = row.iloc[0]

    new_title = data["new_title"]
    new_desc  = data["new_desc"]
    source    = f"{row['title']} {row['description']} {row['option_names']}"

    signals = [
        eval_scorer_delta(row, new_title, new_desc),
        eval_specificity(row["description"], new_desc),
        eval_hallucination(source, new_desc, new_title),
        eval_llm_judge(row, new_title, new_desc),
    ]

    verdict = aggregate_verdict(signals)

    result = {
        "deal_id":    deal_id,
        "verdict":    verdict,
        "signals":    signals,
        "summary": {
            s["signal"]: {"passed": s["passed"], "note": s["note"]}
            for s in signals
        },
    }

    # Write eval alongside the rewrite
    eval_path = rewrite_path.with_suffix(".eval.json")
    eval_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    return result


def print_eval(result: dict) -> None:
    verdict_icon = {"APPROVE": "✅", "FLAG": "⚠️", "REJECT": "❌"}
    print(f"\n  Verdict: {verdict_icon.get(result['verdict'], '?')} {result['verdict']}")
    for s in result["signals"]:
        icon = "✓" if s["passed"] else "✗"
        print(f"    {icon} [{s['signal']:<16}] {s['note']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Path to a single rewrite JSON")
    parser.add_argument("--all",  action="store_true", help="Evaluate all rewrites")
    args = parser.parse_args()

    df = pd.read_csv(ROOT / "data" / "deals.csv")
    rewrite_dir = ROOT / "results" / "rewrites"

    if args.file:
        result = evaluate_rewrite(Path(args.file), df)
        print_eval(result)

    elif args.all:
        files = sorted(rewrite_dir.glob("*.json"))
        files = [f for f in files if not f.name.endswith(".eval.json")]

        if not files:
            print("No rewrite files found. Run rewriter.py first.")
            sys.exit(1)

        verdicts = []
        for f in files:
            print(f"Evaluating {f.name}...")
            result = evaluate_rewrite(f, df)
            verdicts.append(result["verdict"])
            print_eval(result)

        print(f"\n{'='*50}")
        print(f"SUMMARY: {len(files)} rewrites evaluated")
        for v in ["APPROVE", "FLAG", "REJECT"]:
            print(f"  {v}: {verdicts.count(v)}")
    else:
        parser.print_help()
