# Groupon — Content That Converts

Case study submission: automated system that scores, rewrites, and evaluates Groupon deal content to replace manual copywriting at scale.

## Key Finding

**Description type is the single strongest CVR signal.** Structured descriptions ("What We Offer / What's Included / Good to Know") outperform generic templates by **+101% CVR** — consistent across all 8 categories and all 15 geos. Combining all four content signals (description + title + options + image) yields **+280% CVR** between worst and best scoring deals.

| Signal | Impact |
|---|---|
| Description type (structured vs. generic) | +101% CVR |
| Image quality score (r = 0.46) | Strongest numeric signal |
| Title specificity | +71% CVR |
| Combined content score 0→4 | +280% CVR |
| Discount % | No signal (r = 0.08) |

## Repo Structure

```
├── data/
│   ├── deals.csv              # 500 deals, 8 weeks performance data
│   └── data_dictionary.md
├── analysis/
│   ├── analyze.py             # EDA + content signal analysis
│   └── verify.py              # Cross-category/geo robustness checks
├── system/
│   ├── scorer.py              # Rule-based content quality scorer (0–100)
│   ├── rewriter.py            # Claude API rewriter
│   ├── evaluator.py           # Multi-signal eval (scorer delta + LLM judge + hallucination check)
│   └── pipeline.py            # End-to-end batch pipeline
├── results/
│   └── rewrites/              # JSON: original + rewrite + scores
├── blueprint.md               # Operations blueprint (100 FTE → target state)
└── requirements.txt
```

## Quickstart

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key

# Run analysis
python analysis/analyze.py

# Score all deals
python system/scorer.py

# Rewrite bottom-quartile deals
python system/pipeline.py --mode rewrite --threshold 0.25

# Evaluate rewrites
python system/pipeline.py --mode evaluate
```

## System Architecture

```
deals.csv → SCORER → [low-score deals] → REWRITER → EVALUATOR → approved rewrites
                                                          ↓
                                              flag edge cases for human review
```

### Scorer
Rule-based, ~0ms/deal. Classifies description template, title genericness, option name quality, fine print count. Outputs 0–100 score with per-dimension breakdown.

### Rewriter
Claude API (`claude-sonnet-4-6`). System prompt includes category-specific best practices and high-CVR examples from the dataset. Rewrites title + description only — fine print is never modified.

### Evaluator
Multi-signal — not a single LLM judge:
1. **Scorer delta** — new score vs. original
2. **LLM blind A/B** — Claude rates both versions without knowing which is original
3. **Hallucination check** — rewrite cannot add claims not present in source fields
4. **Specificity heuristic** — counts concrete nouns added

## Operations Blueprint

See [`blueprint.md`](blueprint.md) for the full path from 100 FTE → 5 FTE.

**Weekly KPIs:**
- CVR lift: rewritten deals vs. holdout control (same category/geo)
- Acceptance rate: % of rewrites approved without human edit
- Hallucination rate: % flagged for false claims
- Scorer→CVR correlation: does our proxy score track real conversion?
