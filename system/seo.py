"""
SEO optimization pass — runs AFTER rewriter.py or generator.py.

Takes an already-written title + description and optimizes them for search
without touching conversion structure or inventing new facts.

What it changes:
  - Title: moves primary keyword earlier, adds location if missing
  - Description opening sentence: front-loads searchable terms
  - Does NOT restructure the body, change the 3-section format, or alter fine print

Usage:
  python seo.py --title "Amazing Service at Acme" --description "..." --category "Beauty & Spas" --geo "Chicago"
  python seo.py --from-json results/rewrites/deal123.json   # reads new_title + new_desc from rewrite output
  python seo.py --from-json results/generated/acme.json     # same for generator output
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))
from llm_client import get_client


def build_system_prompt() -> str:
    return """You are an SEO specialist optimizing deal pages for organic search.

## Your task
You receive a deal title and description that have already been written for conversion.
Your job is to improve their search visibility WITHOUT changing their conversion effectiveness.

## What you are allowed to change
- Title: reorder words so the primary search term appears earlier; add location if absent and it fits under 90 chars
- Description first sentence only: rewrite it to front-load the most searchable phrase naturally
- Nothing else — the body structure, section headers, and all factual content must remain intact

## What you must NOT do
- Invent facts, credentials, or details not present in the input
- Change the "What We Offer / Why You Should Grab / Good to Know" structure
- Stuff keywords unnaturally (no "buy cheap windshield repair windshield chip Chicago")
- Exceed 90 characters in the title
- Touch the fine print

## SEO rules for deal pages
1. Primary keyword = [specific service] + [location] (e.g. "Windshield Chip Repair Chicago")
2. Put the service before the merchant name in the title
3. The description's first sentence should read naturally but contain the service + city
4. Avoid stop words at the start of the title ("A", "The", "Get", "Save on")

## Output format
{"title": "...", "description": "...", "seo_changes": "1-2 sentences describing what you changed and why"}

JSON only. No markdown."""


def build_user_message(title: str, description: str, category: str, geo: str) -> str:
    return f"""Optimize this deal copy for search.

CATEGORY: {category}
GEO: {geo}

CURRENT TITLE:
{title}

CURRENT DESCRIPTION:
{description}

Output JSON only."""


def run_seo_pass(title: str, description: str, category: str = "", geo: str = "") -> dict:
    client = get_client()
    system = build_system_prompt()
    user = build_user_message(title, description, category, geo)

    response = client.complete(system, user, max_tokens=1024, cache_system=True)

    raw = response.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    parsed = json.loads(raw)

    return {
        "title_before_seo":  title,
        "desc_before_seo":   description,
        "title":             parsed["title"],
        "description":       parsed["description"],
        "seo_changes":       parsed.get("seo_changes", ""),
        "usage": {
            "input_tokens":      response.input_tokens,
            "output_tokens":     response.output_tokens,
            "cache_read_tokens": response.cache_read_tokens,
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SEO optimization pass for deal copy.")
    parser.add_argument("--from-json",   metavar="FILE", help="Load title+desc from rewriter/generator JSON output")
    parser.add_argument("--title",       help="Deal title")
    parser.add_argument("--description", help="Deal description")
    parser.add_argument("--category",    default="", help="Deal category")
    parser.add_argument("--geo",         default="", help="City / region")
    parser.add_argument("--output",      help="Save result to this JSON file")
    args = parser.parse_args()

    if args.from_json:
        data = json.loads(Path(args.from_json).read_text())
        title = data.get("new_title") or data.get("title", "")
        description = data.get("new_desc") or data.get("description", "")
        category = data.get("inputs", {}).get("category", "") or data.get("category", "")
        geo = data.get("inputs", {}).get("geo", "") or data.get("geo", "")
    else:
        if not args.title or not args.description:
            parser.error("--title and --description are required (or use --from-json)")
        title, description, category, geo = args.title, args.description, args.category, args.geo

    print(f"Running SEO pass on: {title[:70]}...")
    result = run_seo_pass(title, description, category, geo)

    print(f"\n--- TITLE (before) ---\n{result['title_before_seo']}")
    print(f"\n--- TITLE (after SEO) ---\n{result['title']}")
    print(f"\n--- DESCRIPTION (after SEO) ---\n{result['description']}")
    print(f"\n--- SEO CHANGES ---\n{result['seo_changes']}")
    print(f"\nTokens: input={result['usage']['input_tokens']}, output={result['usage']['output_tokens']}, cache_read={result['usage']['cache_read_tokens']}")

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"Saved → {args.output}")
