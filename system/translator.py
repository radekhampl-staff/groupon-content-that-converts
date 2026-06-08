"""
Translation pass — translates deal copy into active market languages (DE, FR, IT, ES, NL, PL).

Runs after rewriter.py / generator.py (and optionally after seo.py).
Translates title + description into one or more target languages while
preserving the conversion structure, brand names, and fine print formatting.

Active markets and their languages:
  US, CA, AU, IE → English (no-op)
  UK             → English (no-op)
  DE             → German
  FR             → French
  IT             → Italian
  ES             → Spanish
  NL             → Dutch
  PL             → Polish

Usage:
  python translator.py --from-json results/rewrites/deal123.json --markets DE,FR,IT
  python translator.py --title "..." --description "..." --markets ES,PL
  python translator.py --from-json results/generated/acme.json --all-markets
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


MARKETS = {
    "DE": "German",
    "FR": "French",
    "IT": "Italian",
    "ES": "Spanish",
    "NL": "Dutch",
    "PL": "Polish",
}

ENGLISH_MARKETS = {"US", "CA", "AU", "IE", "UK"}


def build_system_prompt(target_language: str) -> str:
    return f"""You are a professional localizer for deal pages.

## Your task
Translate the deal title and description into {target_language}.

## Rules
1. Preserve the "What We Offer / Why You Should Grab This Offer / Good to Know" structure exactly
2. Keep merchant names, brand names, and proper nouns in their original form
3. Keep all numbers, prices, measurements, and time durations as-is
4. Keep the fine print untouched — reproduce it in the original language (it is legal text)
5. Translate naturally for a native {target_language} speaker — not word-for-word
6. Preserve the persuasive, benefit-focused tone. Do not make it sound like a machine translation.
7. If a phrase has no natural equivalent, adapt it to a local idiom that carries the same meaning

## Output format
{{"title": "...", "description": "..."}}

JSON only. No markdown. No explanation outside the JSON."""


def build_user_message(title: str, description: str) -> str:
    return f"""Translate this deal copy.

TITLE:
{title}

DESCRIPTION:
{description}

Output JSON only."""


def translate_deal(title: str, description: str, market: str) -> dict:
    language = MARKETS[market]
    client = get_client()
    system = build_system_prompt(language)
    user = build_user_message(title, description)

    response = client.complete(system, user, max_tokens=1200, cache_system=True)

    raw = response.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    parsed = json.loads(raw)

    return {
        "market":      market,
        "language":    language,
        "title":       parsed["title"],
        "description": parsed["description"],
        "usage": {
            "input_tokens":      response.input_tokens,
            "output_tokens":     response.output_tokens,
            "cache_read_tokens": response.cache_read_tokens,
        },
    }


def translate_to_markets(title: str, description: str, markets: list[str]) -> dict:
    results = {}
    for market in markets:
        market = market.strip().upper()
        if market in ENGLISH_MARKETS:
            print(f"  [{market}] English market — skipping translation")
            results[market] = {"market": market, "language": "English", "title": title, "description": description}
            continue
        if market not in MARKETS:
            print(f"  [{market}] Unknown market — skipping")
            continue
        print(f"  [{market}] Translating to {MARKETS[market]}...")
        results[market] = translate_deal(title, description, market)
        tokens = results[market]["usage"]
        print(f"         ✓ tokens: input={tokens['input_tokens']}, output={tokens['output_tokens']}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Translate deal copy into active market languages (DE, FR, IT, ES, NL, PL).")
    parser.add_argument("--from-json",   metavar="FILE", help="Load title+desc from rewriter/generator/seo JSON output")
    parser.add_argument("--title",       help="Deal title (English)")
    parser.add_argument("--description", help="Deal description (English)")
    parser.add_argument("--markets",     help="Comma-separated market codes, e.g. DE,FR,IT,ES")
    parser.add_argument("--all-markets", action="store_true", help="Translate into all non-English markets")
    parser.add_argument("--output",      help="Save result to this JSON file")
    args = parser.parse_args()

    if args.from_json:
        data = json.loads(Path(args.from_json).read_text())
        title       = data.get("title") or data.get("new_title", "")
        description = data.get("description") or data.get("new_desc", "")
    else:
        if not args.title or not args.description:
            parser.error("--title and --description are required (or use --from-json)")
        title, description = args.title, args.description

    if args.all_markets:
        markets = list(MARKETS.keys())
    elif args.markets:
        markets = args.markets.split(",")
    else:
        parser.error("Specify --markets DE,FR,... or --all-markets")

    print(f"Translating: {title[:70]}...")
    results = translate_to_markets(title, description, markets)

    for market, res in results.items():
        print(f"\n=== {market} ({res['language']}) ===")
        print(f"Title: {res['title']}")
        print(f"Description:\n{res['description']}")

    if args.output:
        Path(args.output).write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"\nSaved → {args.output}")
    else:
        slug = re.sub(r"[^a-z0-9]+", "-", title[:40].lower()).strip("-")
        out_dir = ROOT / "results" / "translations"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{slug}.json"
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"\nSaved → {out_path}")
