"""
Content Quality Scorer — rule-based, ~0ms per deal.

Dimensions (total 100 pts):
  description   0–40   (strongest CVR signal from analysis)
  title         0–25   (+71% lift for specific vs. generic)
  image         0–20   (r=0.46 with CVR — not rewritable, but scored for triage)
  options       0–10   (descriptive names vs. "Option 1, 2, 3")
  fine_print    0–5    (penalty for excessive restrictions)

Usage:
  python scorer.py                         # score all 500 deals → results/scores.csv
  python scorer.py --deal <deal_id>        # score a single deal (verbose)
"""

import re
import sys
import argparse
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent.parent

# ── Description templates and their scores ────────────────────────────────────
# Based on empirical CVR ranking from analyze.py

DESC_RULES: list[tuple[str, int, str]] = [
    # (regex, score/40, label)
    (r"What We Offer:|What Is Included:|What's Included: [A-Z]", 40, "structured_what_we_offer"),
    (r"During the procedure, a licensed professional",             35, "clinical_procedure"),
    (r"What's Included: Product ships within",                     32, "retail_ships"),
    (r"Looking for something special\? This deal has you covered", 18, "generic_looking_for"),
    (r"Treat yourself or someone special to this offer",           16, "generic_treat_yourself"),
    (r"A great way to try something new without breaking",         14, "generic_great_way"),
    (r"Highly rated by Groupon customers",                         13, "generic_highly_rated"),
    (r"This is a deal you won't want to miss",                     12, "generic_dont_miss"),
    (r"An opportunity to enjoy premium service",                   11, "generic_opportunity"),
    (r"Experience the best that .{2,30} has to offer",             10, "generic_experience_best"),
    (r"Save on this top-rated experience",                          9, "generic_save_on"),
]

GENERIC_TITLE_PATTERNS = [
    r"^Amazing .{3,40} at .+",
    r"^Best .{3,40} at .+",
    r"^Incredible .{3,40} at .+",
    r"^Fantastic .{3,40} at .+",
    r"^Wonderful .{3,40} at .+",
    r"^Must-Have Items",
    r"^Shop Smart",
    r"^Top Picks",
    r"^Enjoy a Fantastic .+",
    r"^Create Lasting Memories at .+",
    r"^Make Your Weekend Special at .+",
    r"^Explore & Enjoy at .+",
    r"^Fun for Everyone at .+",
    r"^Thrill & Excitement at .+",
]


def score_description(desc: str) -> tuple[int, str]:
    """Returns (score 0–40, label)."""
    for pattern, score, label in DESC_RULES:
        if re.search(pattern, str(desc), re.IGNORECASE):
            return score, label
    return 22, "unclassified"  # unknown but not obviously generic


def score_title(title: str) -> tuple[int, str]:
    """Returns (score 0–25, label)."""
    for p in GENERIC_TITLE_PATTERNS:
        if re.search(p, str(title), re.IGNORECASE):
            return 8, "generic"
    # Bonus for longer, more specific titles
    length = len(str(title))
    if length >= 60:
        return 25, "specific_long"
    elif length >= 40:
        return 22, "specific_medium"
    else:
        return 18, "specific_short"


def score_image(image_quality: int) -> tuple[int, str]:
    """Returns (score 0–20, label). Direct mapping from 1–5 scale."""
    mapping = {1: 0, 2: 5, 3: 10, 4: 17, 5: 20}
    s = mapping.get(int(image_quality), 10)
    return s, f"{image_quality}/5"


def score_options(option_names: str) -> tuple[int, str]:
    """Returns (score 0–10, label)."""
    if re.search(r"Option \d", str(option_names), re.IGNORECASE):
        return 2, "generic_numbered"
    if re.search(r"^(1 Session|Standard|Basic|Complete)$", str(option_names).strip()):
        return 6, "minimal_descriptive"
    return 10, "descriptive"


def score_fine_print(fine_print: str) -> tuple[int, str]:
    """Returns (score 0–5, label). Fewer restrictions = better."""
    count = str(fine_print).count(";") + 1
    if count <= 2:
        return 5, f"{count} restrictions"
    elif count <= 4:
        return 4, f"{count} restrictions"
    elif count <= 6:
        return 3, f"{count} restrictions"
    elif count <= 8:
        return 2, f"{count} restrictions"
    else:
        return 1, f"{count} restrictions"


def score_deal(row) -> dict:
    """Score a single deal. Returns full breakdown dict."""
    desc_score,  desc_label  = score_description(row["description"])
    title_score, title_label = score_title(row["title"])
    img_score,   img_label   = score_image(row["image_quality_score"])
    opt_score,   opt_label   = score_options(row["option_names"])
    fp_score,    fp_label    = score_fine_print(row["fine_print"])

    total = desc_score + title_score + img_score + opt_score + fp_score

    # Dims that have the most headroom (biggest gap from max)
    gaps = {
        "description": (40 - desc_score, desc_label),
        "title":       (25 - title_score, title_label),
        "image":       (20 - img_score,   img_label),
        "options":     (10 - opt_score,   opt_label),
        "fine_print":  (5  - fp_score,    fp_label),
    }
    copy_gaps = {k: v for k, v in gaps.items() if k not in ("image", "fine_print")}
    priority_dims = sorted(copy_gaps, key=lambda k: copy_gaps[k][0], reverse=True)

    return {
        "deal_id":            row["deal_id"],
        "total_score":        total,
        "rewrite_recommended": total < 60,
        "dimensions": {
            "description": {"score": desc_score, "max": 40, "label": desc_label},
            "title":       {"score": title_score, "max": 25, "label": title_label},
            "image":       {"score": img_score,   "max": 20, "label": img_label},
            "options":     {"score": opt_score,   "max": 10, "label": opt_label},
            "fine_print":  {"score": fp_score,    "max": 5,  "label": fp_label},
        },
        "priority_copy_dims": priority_dims,
    }


def score_all(df: pd.DataFrame) -> pd.DataFrame:
    """Score all deals, return flat dataframe."""
    records = []
    for _, row in df.iterrows():
        s = score_deal(row)
        records.append({
            "deal_id":             s["deal_id"],
            "total_score":         s["total_score"],
            "rewrite_recommended": s["rewrite_recommended"],
            "desc_score":          s["dimensions"]["description"]["score"],
            "desc_label":          s["dimensions"]["description"]["label"],
            "title_score":         s["dimensions"]["title"]["score"],
            "title_label":         s["dimensions"]["title"]["label"],
            "img_score":           s["dimensions"]["image"]["score"],
            "opt_score":           s["dimensions"]["options"]["score"],
            "fp_score":            s["dimensions"]["fine_print"]["score"],
            "priority_dims":       ", ".join(s["priority_copy_dims"]),
        })
    return pd.DataFrame(records)


def print_deal_verbose(row: pd.Series, result: dict) -> None:
    dims = result["dimensions"]
    print(f"\n{'='*60}")
    print(f"  {row['title']}")
    print(f"  {row['category']} / {row['geo']}   CVR={row.get('cvr', '?')}")
    print(f"{'='*60}")
    print(f"  TOTAL SCORE: {result['total_score']}/100  "
          f"{'⚠ rewrite recommended' if result['rewrite_recommended'] else '✓ OK'}")
    print(f"\n  Breakdown:")
    for dim, d in dims.items():
        bar = "█" * d["score"] + "░" * (d["max"] - d["score"])
        print(f"    {dim:<12} {d['score']:>3}/{d['max']}  {bar}  [{d['label']}]")
    print(f"\n  Priority copy dims: {result['priority_copy_dims']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--deal", help="Score a single deal_id (verbose)")
    args = parser.parse_args()

    df = pd.read_csv(ROOT / "data" / "deals.csv")

    if args.deal:
        row = df[df.deal_id == args.deal]
        if row.empty:
            print(f"Deal {args.deal} not found.")
            sys.exit(1)
        result = score_deal(row.iloc[0])
        print_deal_verbose(row.iloc[0], result)
    else:
        scores = score_all(df)
        merged = df[["deal_id", "title", "category", "geo", "cvr", "image_quality_score"]].merge(scores)

        out = ROOT / "results" / "scores.csv"
        out.parent.mkdir(exist_ok=True)
        merged.sort_values("total_score").to_csv(out, index=False)

        print(f"Scored {len(merged)} deals → {out}")
        print(f"\nScore distribution:")
        bins = [0, 40, 60, 75, 100]
        labels = ["<40 (critical)", "40–59 (rewrite)", "60–74 (improve)", "75–100 (good)"]
        merged["bucket"] = pd.cut(merged["total_score"], bins=bins, labels=labels)
        print(merged["bucket"].value_counts().sort_index().to_string())

        print(f"\nRewrite recommended: {scores.rewrite_recommended.sum()}/{len(scores)} deals")

        # CVR validation: does score correlate with actual CVR?
        corr = merged["total_score"].corr(merged["cvr"])
        print(f"\nScore↔CVR correlation (validation): r={corr:.3f}")
