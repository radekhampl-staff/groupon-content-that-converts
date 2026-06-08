"""
Claude-powered deal rewriter.

Uses prompt caching on the system prompt (static across all calls).
Few-shot examples are pulled from the top-CVR deals in the dataset.

Usage:
  python rewriter.py --deal <deal_id>          # rewrite a single deal
  python rewriter.py --batch 20                # rewrite top-20 priority deals
  python rewriter.py --batch 20 --dry-run      # show what would be rewritten
"""

import os
import re
import sys
import json
import argparse
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))
from scorer     import score_deal, score_all
from llm_client import get_client

# ── Few-shot examples (pulled from high-CVR deals in dataset) ─────────────────
# Selected: one per major category, all CVR > 0.08, all structured descriptions

FEW_SHOT_EXAMPLES = [
    {
        "category": "Automotive",
        "title_before": "Amazing Auto Service at TopGear Garage",
        "title_after": "Windshield Chip Repair — Up to 3 Chips at TopGear Garage",
        "description_after": (
            "What We Offer: A comprehensive vehicle service performed by trained technicians "
            "using manufacturer-approved parts and fluids. Service includes a detailed inspection "
            "report emailed to you upon completion, so you have a clear record of your vehicle's "
            "condition. No appointment necessary — walk-ins welcome 7 days a week. "
            "Why You Should Grab This Offer: We've serviced over 10,000 vehicles in Manchester "
            "and consistently earn top ratings for speed, quality, and transparency. Our customers "
            "appreciate that we explain what we find, recommend only what's needed, and never "
            "pressure you into additional services. Every job is backed by a 12-month or "
            "12,000-mile warranty on parts and labor. "
            "Good to Know: Most services completed in 30-60 minutes. Comfortable waiting area "
            "with complimentary Wi-Fi, coffee, and snacks. Shuttle service available within "
            "5 miles for longer services."
        ),
    },
    {
        "category": "Food & Drink",
        "title_before": "Amazing Dining Experience at Silver Grill",
        "title_after": "Family Meal Deal — 2 Entrees, 2 Sides & Dessert at Silver Grill",
        "description_after": (
            "What We Offer: This deal is valid toward our full food and drink menu during the "
            "specified hours. Choose from appetizers, entrees, and desserts crafted fresh daily "
            "by our kitchen team. Our menu features a mix of house specialties and seasonal "
            "rotating dishes — there's something for every palate. Full bar available with craft "
            "cocktails, local beers, and a curated wine list. "
            "Why You Should Grab This Offer: Whether it's date night, a family dinner, or a "
            "casual meal with friends, this deal gives you the flexibility to order what you "
            "want from our complete menu. Our restaurant is known for generous portions, fresh "
            "ingredients, and a warm atmosphere that keeps customers coming back. "
            "Good to Know: Located in the heart of Los Angeles. Walk-ins welcome. Outdoor "
            "seating available seasonally. Ask about our loyalty program for returning guests."
        ),
    },
    {
        "category": "Home Services",
        "title_before": "Best Home Service at HomeFirst",
        "title_after": "Initial Pest Treatment + 30-Day Follow-Up at HomeFirst Cleaning Co.",
        "description_after": (
            "What We Offer: Our licensed, bonded, and insured professionals arrive at your home "
            "with all necessary supplies and equipment — you don't need to provide anything. "
            "The service includes a thorough walkthrough before we begin, the service itself, "
            "and a final inspection with you to ensure everything meets your standards. "
            "We clean up after ourselves. "
            "Why You Should Grab This Offer: We've served over 2,000 homes in Manchester and "
            "maintain a 4.7-star rating. Every technician is background-checked, drug-tested, "
            "and has an average of 8 years of experience. We offer a 100% satisfaction "
            "guarantee — if you're not happy, we come back and fix it at no charge. "
            "Good to Know: Serving the area within 30 miles. Online booking with 2-hour "
            "arrival windows. Service takes approximately 1-3 hours depending on home size."
        ),
    },
    {
        "category": "Beauty & Spas",
        "title_before": "Amazing Hair Service at Orchid Wellness Center",
        "title_after": "Before & After Hair Transformation w/ Balayage & Deep Conditioning at Orchid Wellness Center",
        "description_after": (
            "What We Offer: This deal includes a full consultation to identify your specific "
            "hair goals, followed by a customized treatment performed by a licensed stylist "
            "with over 10 years of experience. All products used are professional-grade and "
            "salon-approved. The session begins with a hair analysis, followed by the "
            "treatment itself, and ends with a personalized at-home care plan. "
            "Before and after photos are taken so you can see your transformation. "
            "Why You Should Grab This Offer: Whether you're looking for a subtle refresh or a "
            "dramatic change, this treatment is designed to deliver visible results. Our "
            "specialists tailor every session to your hair type — no cookie-cutter approach. "
            "Good to Know: Located in Houston with free parking and complimentary refreshments "
            "in the waiting area. Open 7 days a week with evening appointments available. "
            "Online booking at our website — same-week availability."
        ),
    },
]


def build_system_prompt() -> str:
    examples_text = ""
    for ex in FEW_SHOT_EXAMPLES:
        examples_text += f"""
### Example ({ex['category']})
BEFORE title: {ex['title_before']}
AFTER title:  {ex['title_after']}
AFTER description:
{ex['description_after']}
---"""

    return f"""You are a conversion-rate-focused copywriter for Groupon deal pages.

## Your task
Rewrite a deal's title and description to increase conversion rate.

## What works (from analysis of 500 real deals)
1. **Structured descriptions** using "What We Offer / Why You Should Grab This Offer / Good to Know" convert 101% better than generic templates.
2. **Specific titles** that name the exact service convert 71% better than "Amazing X at Y" or "Best X at Y".
3. **Concrete details** (specific numbers, credentials, amenities, timing) outperform vague claims.

## What to avoid
- "Experience the best that [city] has to offer..."
- "Amazing/Best/Incredible/Fantastic [service] at [merchant]"
- "Save on this top-rated experience in [city]..."
- "Treat yourself or someone special to this offer..."
- Generic filler that could apply to any deal in the same category

## Title rules
- Name the SPECIFIC service/product, not the category
- Include key differentiators (duration, quantity, technique, before/after)
- Keep it under 90 characters
- Good: "60-Min Facial w/ Microdermabrasion & LED Light Therapy at Sapphire Wellness Center"
- Bad:  "Amazing Beauty Service at Sapphire Wellness Center"

## Description structure (3 sections, no headers needed — just flow naturally)
1. **What We Offer**: What's included, duration, equipment, products used, process
2. **Why You Should Grab This Offer**: Ratings, years in business, # clients served, guarantee, what makes them different
3. **Good to Know**: Location logistics, parking, hours, booking method, availability

## Hard rules
1. DO NOT add any factual claims not present in the provided deal fields (title, description, category, geo, merchant_name, option_names, price, value)
2. DO NOT modify or rewrite the fine_print — it is legal text and must stay exactly as is
3. Match the approximate length of the original description (±30%)
4. Respond with valid JSON only — no markdown, no explanation outside the JSON

## Output format
{{"title": "...", "description": "...", "rationale": "1-2 sentences on what you changed and why"}}

## Examples of good rewrites
{examples_text}
"""


def build_user_message(row: pd.Series) -> str:
    return f"""Rewrite this deal's title and description.

DEAL FIELDS:
- deal_id: {row['deal_id']}
- category: {row['category']} / {row['subcategory']}
- geo: {row['geo']}
- merchant_name: {row['merchant_name']}
- price: {row['price']} (value: {row['value']}, discount: {int(row['discount_pct']*100)}%)
- num_options: {row['num_options']}
- option_names: {row['option_names']}

CURRENT TITLE:
{row['title']}

CURRENT DESCRIPTION:
{row['description']}

FINE PRINT (do not touch):
{row['fine_print']}

Output JSON only."""


def rewrite_deal(row: pd.Series) -> dict:
    """Call LLM to rewrite a single deal. Returns result dict."""
    client = get_client()
    system = build_system_prompt()
    user   = build_user_message(row)

    response = client.complete(system, user, max_tokens=1024, cache_system=True)

    raw = response.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    parsed = json.loads(raw)

    return {
        "deal_id":        row["deal_id"],
        "original_title": row["title"],
        "original_desc":  row["description"],
        "new_title":      parsed["title"],
        "new_desc":       parsed["description"],
        "rationale":      parsed.get("rationale", ""),
        "usage": {
            "input_tokens":      response.input_tokens,
            "output_tokens":     response.output_tokens,
            "cache_read_tokens": response.cache_read_tokens,
        },
    }


def get_priority_queue(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Return top-n deals to rewrite: highest views × CVR gap from category median."""
    scores_df = score_all(df)
    merged = df.merge(scores_df[["deal_id", "total_score", "rewrite_recommended"]])

    view_cols = [f"weekly_udvs_w{i}" for i in range(1, 9)]
    merged["total_views"] = merged[view_cols].sum(axis=1)

    cat_median = merged.groupby("category")["cvr"].median().rename("cat_median_cvr")
    merged = merged.merge(cat_median, on="category")

    merged["priority"] = merged["total_views"] * (merged["cat_median_cvr"] - merged["cvr"]).clip(lower=0)
    merged = merged[merged["rewrite_recommended"]].sort_values("priority", ascending=False)
    return merged.head(n)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--deal",      help="Rewrite a single deal_id")
    parser.add_argument("--batch",     type=int, default=10, help="Rewrite top-N priority deals")
    parser.add_argument("--dry-run",   action="store_true", help="Show queue without calling API")
    args = parser.parse_args()

    df = pd.read_csv(ROOT / "data" / "deals.csv")
    out_dir = ROOT / "results" / "rewrites"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.deal:
        row = df[df.deal_id == args.deal]
        if row.empty:
            print(f"Deal {args.deal} not found.")
            sys.exit(1)
        row = row.iloc[0]
        print(f"Rewriting: {row['title']}")
        result = rewrite_deal(row)
        path = out_dir / f"{args.deal}.json"
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"\n--- NEW TITLE ---\n{result['new_title']}")
        print(f"\n--- NEW DESC ---\n{result['new_desc']}")
        print(f"\n--- RATIONALE ---\n{result['rationale']}")
        print(f"\nSaved → {path}")

    else:
        queue = get_priority_queue(df, args.batch)
        print(f"\nPriority queue ({len(queue)} deals):")
        print(queue[["title", "category", "geo", "cvr", "total_views", "total_score"]].to_string(index=False))

        if args.dry_run:
            print("\n[dry-run] Skipping API calls.")
            sys.exit(0)

        total_cost_tokens = 0
        for i, (_, row) in enumerate(queue.iterrows(), 1):
            out_path = out_dir / f"{row['deal_id']}.json"
            if out_path.exists():
                print(f"[{i}/{len(queue)}] skip (exists): {row['title'][:60]}")
                continue
            print(f"[{i}/{len(queue)}] rewriting: {row['title'][:60]}...")
            try:
                result = rewrite_deal(row)
                out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
                cache_hit = result["usage"]["cache_read_tokens"]
                total_cost_tokens += result["usage"]["input_tokens"]
                print(f"         ✓ cache_read={cache_hit} tokens")
            except Exception as e:
                print(f"         ✗ ERROR: {e}")

        print(f"\nDone. Results in {out_dir}/")
        print(f"Total input tokens used: {total_cost_tokens:,}")
