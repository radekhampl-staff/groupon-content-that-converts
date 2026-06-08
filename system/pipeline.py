"""
End-to-end batch pipeline.

Modes:
  score    — score all 500 deals, save results/scores.csv
  rewrite  — rewrite bottom-N priority deals (calls Claude API)
  evaluate — evaluate all existing rewrites (calls Claude API for judge)
  report   — print summary of all eval results (no API calls)
  all      — score → rewrite → evaluate in one shot

Usage:
  python pipeline.py --mode score
  python pipeline.py --mode rewrite --n 20
  python pipeline.py --mode evaluate
  python pipeline.py --mode report
  python pipeline.py --mode all --n 10
"""

import os
import sys
import json
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from scorer    import score_all, score_deal
from rewriter  import get_priority_queue, rewrite_deal
from evaluator import evaluate_rewrite, print_eval


def run_score(df: pd.DataFrame) -> pd.DataFrame:
    print("\n[1/1] Scoring all deals...")
    scores = score_all(df)
    merged = df[["deal_id", "title", "category", "geo", "cvr",
                 "image_quality_score", "price"]].merge(scores)

    out = ROOT / "results" / "scores.csv"
    out.parent.mkdir(exist_ok=True)
    merged.sort_values("total_score").to_csv(out, index=False)

    corr = merged["total_score"].corr(merged["cvr"])
    print(f"  Scored {len(merged)} deals → {out}")
    print(f"  Score↔CVR correlation: r={corr:.3f}")
    print(f"  Rewrite recommended: {scores.rewrite_recommended.sum()}/{len(scores)}")
    return merged


def run_rewrite(df: pd.DataFrame, n: int, dry_run: bool = False) -> list[Path]:
    print(f"\n[1/1] Rewriting top-{n} priority deals...")
    queue = get_priority_queue(df, n)

    if queue.empty:
        print("  No deals meet rewrite criteria.")
        return []

    print(f"  {'title':<55} {'cvr':>6}  {'score':>5}  {'views':>6}")
    print("  " + "-" * 80)
    for _, row in queue.iterrows():
        print(f"  {row['title'][:54]:<55} {row['cvr']:>6.4f}  {row['total_score']:>5}  {row['total_views']:>6.0f}")

    if dry_run:
        print("\n  [dry-run] No API calls made.")
        return []

    out_dir = ROOT / "results" / "rewrites"
    out_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for i, (_, row) in enumerate(queue.iterrows(), 1):
        out_path = out_dir / f"{row['deal_id']}.json"
        if out_path.exists():
            print(f"  [{i}/{len(queue)}] skip (exists): {row['title'][:55]}")
            written.append(out_path)
            continue
        print(f"  [{i}/{len(queue)}] {row['title'][:55]}...")
        try:
            result = rewrite_deal(row)
            out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
            written.append(out_path)
            cache = result["usage"].get("cache_read_tokens", 0)
            print(f"         ✓  cache_read={cache} tokens")
        except Exception as e:
            print(f"         ✗  ERROR: {e}")

    print(f"\n  Done: {len(written)} rewrites saved → {out_dir}/")
    return written


def run_evaluate(df: pd.DataFrame) -> list[dict]:
    rewrite_dir = ROOT / "results" / "rewrites"
    files = sorted(rewrite_dir.glob("*.json"))
    files = [f for f in files if not f.name.endswith(".eval.json")]

    if not files:
        print("  No rewrite files found. Run --mode rewrite first.")
        return []

    print(f"\n[1/1] Evaluating {len(files)} rewrite(s)...")
    results = []
    for f in files:
        deal_id = f.stem
        print(f"  Evaluating {deal_id}...")
        try:
            result = evaluate_rewrite(f, df)
            results.append(result)
            print_eval(result)
        except Exception as e:
            print(f"  ✗ ERROR on {f.name}: {e}")

    return results


def run_report() -> None:
    rewrite_dir = ROOT / "results" / "rewrites"
    eval_files  = sorted(rewrite_dir.glob("*.eval.json"))

    if not eval_files:
        print("  No eval files found. Run --mode evaluate first.")
        return

    df = pd.read_csv(ROOT / "data" / "deals.csv")
    rows = []
    for ef in eval_files:
        data   = json.loads(ef.read_text())
        rw     = json.loads(ef.with_suffix("").with_suffix(".json").read_text())
        orig   = df[df.deal_id == data["deal_id"]]

        row = {
            "deal_id":        data["deal_id"],
            "verdict":        data["verdict"],
            "original_title": rw["original_title"],
            "new_title":      rw["new_title"],
            "cvr":            orig["cvr"].values[0] if not orig.empty else None,
        }
        for sig in data["signals"]:
            row[f"{sig['signal']}_passed"] = sig["passed"]
            row[f"{sig['signal']}_note"]   = sig["note"]
        rows.append(row)

    report = pd.DataFrame(rows)
    out = ROOT / "results" / "eval_report.csv"
    report.to_csv(out, index=False)

    print(f"\n{'='*60}")
    print(f"EVAL REPORT  ({len(report)} rewrites)")
    print(f"{'='*60}")
    for v in ["APPROVE", "FLAG", "REJECT"]:
        n = (report.verdict == v).sum()
        bar = "█" * n
        print(f"  {v:<8} {n:>3}  {bar}")

    print(f"\n  Per-signal pass rate:")
    for sig in ["scorer_delta", "specificity", "hallucination", "llm_judge"]:
        col = f"{sig}_passed"
        if col in report.columns:
            rate = report[col].mean() * 100
            print(f"    {sig:<18} {rate:.0f}%")

    print(f"\n  Full report → {out}")

    print(f"\n  Sample APPROVED rewrites:")
    approved = report[report.verdict == "APPROVE"][["original_title", "new_title", "cvr"]].head(3)
    for _, r in approved.iterrows():
        print(f"    BEFORE: {r['original_title']}")
        print(f"    AFTER:  {r['new_title']}")
        print(f"    CVR:    {r['cvr']:.4f}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Groupon content pipeline")
    parser.add_argument("--mode", choices=["score", "rewrite", "evaluate", "report", "all"],
                        required=True)
    parser.add_argument("--n",        type=int,  default=10, help="Deals to rewrite (rewrite mode)")
    parser.add_argument("--dry-run",  action="store_true",   help="Skip API calls")
    args = parser.parse_args()

    if args.mode in ("rewrite", "evaluate", "all"):
        provider = os.environ.get("LLM_PROVIDER", "anthropic")
        key_var  = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
        if not os.environ.get(key_var):
            print(f"ERROR: {key_var} not set. See .env.example for setup instructions.")
            sys.exit(1)

    df = pd.read_csv(ROOT / "data" / "deals.csv")
    print(f"Loaded {len(df)} deals  |  mode={args.mode}  |  {datetime.now():%Y-%m-%d %H:%M}")

    if args.mode == "score":
        run_score(df)

    elif args.mode == "rewrite":
        run_rewrite(df, args.n, dry_run=args.dry_run)

    elif args.mode == "evaluate":
        run_evaluate(df)

    elif args.mode == "report":
        run_report()

    elif args.mode == "all":
        run_score(df)
        run_rewrite(df, args.n, dry_run=args.dry_run)
        if not args.dry_run:
            run_evaluate(df)
            run_report()


if __name__ == "__main__":
    main()
