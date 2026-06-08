"""
New deal generator — creates title + description from scratch.

Unlike rewriter.py, this does NOT require an existing deal in the dataset.
It only needs basic merchant/deal information provided by the user.

Usage:
  python generator.py \
    --merchant "TopGear Garage" \
    --category "Automotive" \
    --subcategory "Auto Repair" \
    --geo "Manchester" \
    --service "Windshield chip repair, up to 3 chips" \
    --options "1 chip, 2 chips, 3 chips" \
    --price 49 \
    --value 120 \
    --fine-print "Not valid on holidays. Expires 90 days after purchase."

  python generator.py --from-json input.json   # load fields from a JSON file
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
from llm_client import get_client

FEW_SHOT_EXAMPLES = [
    {
        "category": "Automotive",
        "inputs": "merchant=TopGear Garage, service=Windshield chip repair up to 3 chips, geo=Manchester, price=49, value=120",
        "title": "Windshield Chip Repair — Up to 3 Chips at TopGear Garage",
        "description": (
            "What We Offer: A fast, professional windshield chip repair performed by trained "
            "technicians using manufacturer-approved resin. Each chip is filled, cured, and "
            "polished — most repairs are invisible to the naked eye and structurally sound. "
            "Service covers up to 3 chips per visit. No appointment necessary — walk-ins "
            "welcome 7 days a week. "
            "Why You Should Grab This Offer: Chip repair prevents cracks from spreading, "
            "saving you from a full windshield replacement that can cost 10× more. TopGear "
            "Garage has serviced over 10,000 vehicles in Manchester and consistently earns "
            "top ratings for speed and transparency. Every repair is backed by a 12-month "
            "warranty. "
            "Good to Know: Most repairs completed in 20–30 minutes. Comfortable waiting area "
            "with complimentary Wi-Fi and coffee. Shuttle available within 5 miles for longer services."
        ),
    },
    {
        "category": "Beauty & Spas",
        "inputs": "merchant=Orchid Wellness Center, service=Balayage + deep conditioning treatment, geo=Houston, price=89, value=220",
        "title": "Balayage & Deep Conditioning Treatment at Orchid Wellness Center",
        "description": (
            "What We Offer: A full consultation to identify your hair goals, followed by a "
            "customized balayage performed by a licensed stylist with 10+ years of experience. "
            "Includes a professional deep conditioning treatment and personalized at-home care plan. "
            "Before and after photos taken so you can see your transformation. "
            "Why You Should Grab This Offer: Every session is tailored to your hair type — "
            "no cookie-cutter approach. Orchid Wellness Center is known for natural-looking "
            "color with minimal damage. "
            "Good to Know: Located in Houston with free parking. Open 7 days a week including "
            "evenings. Online booking available — same-week appointments typically available."
        ),
    },
]


def build_system_prompt() -> str:
    examples_text = ""
    for ex in FEW_SHOT_EXAMPLES:
        examples_text += f"""
### Example ({ex['category']})
Inputs: {ex['inputs']}
Title: {ex['title']}
Description:
{ex['description']}
---"""

    return f"""You are a conversion-rate-focused copywriter for deal pages.

## Your task
Write a NEW deal title and description from scratch based on the merchant information provided.
There is no existing copy — you are creating it for the first time.

## What works (from analysis of 500 real deals)
1. **Structured descriptions** using "What We Offer / Why You Should Grab This Offer / Good to Know" convert 101% better than generic templates.
2. **Specific titles** that name the exact service convert 71% better than vague category labels.
3. **Concrete details** (credentials, timing, guarantees, amenities) outperform vague claims.

## What to avoid
- "Experience the best that [city] has to offer..."
- "Amazing/Best/Incredible/Fantastic [service] at [merchant]"
- Generic filler that could apply to any deal in the same category
- Fabricating specific statistics or awards not mentioned in the inputs

## Title rules
- Name the SPECIFIC service/product, not the category
- Include key differentiators (duration, quantity, technique)
- Keep it under 90 characters

## Description structure
1. **What We Offer**: What's included, duration, process, equipment/products used
2. **Why You Should Grab This Offer**: What makes this merchant worth choosing
3. **Good to Know**: Location, parking, hours, booking method

## Hard rules
1. DO NOT invent specific facts (star ratings, years in business, client counts) unless provided in the inputs
2. DO NOT modify the fine_print — reproduce it exactly as given
3. Target ~150–250 words for the description
4. Respond with valid JSON only — no markdown, no explanation outside the JSON

## Output format
{{"title": "...", "description": "...", "rationale": "1-2 sentences on key copy decisions"}}

## Examples
{examples_text}
"""


def build_user_message(fields: dict) -> str:
    discount_pct = ""
    if fields.get("price") and fields.get("value"):
        pct = round((1 - float(fields["price"]) / float(fields["value"])) * 100)
        discount_pct = f" ({pct}% off)"

    return f"""Generate a new deal title and description from scratch.

DEAL INPUTS:
- merchant_name: {fields.get('merchant', '')}
- category: {fields.get('category', '')} / {fields.get('subcategory', '')}
- geo: {fields.get('geo', '')}
- service / what's included: {fields.get('service', '')}
- options: {fields.get('options', '')}
- price: {fields.get('price', '')}{discount_pct} (value: {fields.get('value', '')})
- additional context: {fields.get('context', 'none provided')}

FINE PRINT (reproduce exactly in your output — do not alter):
{fields.get('fine_print', 'None provided.')}

Output JSON only."""


def generate_deal(fields: dict) -> dict:
    client = get_client()
    system = build_system_prompt()
    user = build_user_message(fields)

    response = client.complete(system, user, max_tokens=1024, cache_system=True)

    raw = response.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    parsed = json.loads(raw)

    return {
        "inputs":      fields,
        "new_title":   parsed["title"],
        "new_desc":    parsed["description"],
        "rationale":   parsed.get("rationale", ""),
        "usage": {
            "input_tokens":      response.input_tokens,
            "output_tokens":     response.output_tokens,
            "cache_read_tokens": response.cache_read_tokens,
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate new deal copy from scratch.")
    parser.add_argument("--from-json",   metavar="FILE", help="Load all fields from a JSON file")
    parser.add_argument("--merchant",    help="Merchant name")
    parser.add_argument("--category",    help="Category (e.g. Automotive)")
    parser.add_argument("--subcategory", help="Subcategory (e.g. Auto Repair)")
    parser.add_argument("--geo",         help="City / region")
    parser.add_argument("--service",     help="What the deal includes")
    parser.add_argument("--options",     help="Deal options / tiers")
    parser.add_argument("--price",       type=float, help="Deal price")
    parser.add_argument("--value",       type=float, help="Retail value")
    parser.add_argument("--fine-print",  help="Fine print / legal text")
    parser.add_argument("--context",     help="Any extra merchant context")
    parser.add_argument("--output",      help="Save result to this JSON file")
    args = parser.parse_args()

    if args.from_json:
        fields = json.loads(Path(args.from_json).read_text())
    else:
        if not args.merchant or not args.service:
            parser.error("--merchant and --service are required (or use --from-json)")
        fields = {
            "merchant":    args.merchant,
            "category":    args.category or "",
            "subcategory": args.subcategory or "",
            "geo":         args.geo or "",
            "service":     args.service,
            "options":     args.options or "",
            "price":       args.price or "",
            "value":       args.value or "",
            "fine_print":  args.fine_print or "",
            "context":     args.context or "",
        }

    print(f"Generating copy for: {fields.get('merchant')} — {fields.get('service')[:60]}...")
    result = generate_deal(fields)

    print(f"\n--- TITLE ---\n{result['new_title']}")
    print(f"\n--- DESCRIPTION ---\n{result['new_desc']}")
    print(f"\n--- RATIONALE ---\n{result['rationale']}")
    print(f"\nTokens: input={result['usage']['input_tokens']}, output={result['usage']['output_tokens']}, cache_read={result['usage']['cache_read_tokens']}")

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"Saved → {args.output}")
    else:
        out_dir = ROOT / "results" / "generated"
        out_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", fields.get("merchant", "deal").lower()).strip("-")
        out_path = out_dir / f"{slug}.json"
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"Saved → {out_path}")
