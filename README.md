# Content That Converts

Automated system that scores, rewrites, and evaluates deal content to increase conversion rate.
Replaces manual copywriting at scale — designed to go from 100 FTE to 5 FTE.

## Key Finding

**Description type is the single strongest CVR signal.** Structured descriptions
("What We Offer / Why You Should Grab This Offer / Good to Know") outperform
generic templates by **+101% CVR** — consistent across all 8 categories and 15 geos.

| Signal | CVR impact |
|---|---|
| Description type (structured vs. generic) | +101% |
| Title specificity | +71% |
| Combined content score (0→4) | +280% |
| Discount % | No signal (r = 0.08) |

---

## Quick Start

```bash
git clone <repo>
cd content-that-converts
pip install -r requirements.txt

# Pick your LLM provider — Anthropic or OpenAI, either works:
export ANTHROPIC_API_KEY=your_key_here
# — or —
# export LLM_PROVIDER=openai
# export OPENAI_API_KEY=your_key_here

# Launch the operator dashboard
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) → **Setup** → load `data/deals.csv` → **Weekly Run**.

---

## System Architecture

```
deals.csv  (or database)
    │
    ▼
SCORER (scorer.py)          rule-based, ~0 ms/deal, r = 0.644 vs CVR
    │  deals scoring < 60
    ▼
REWRITER  (rewriter.py)     rewrites existing deals
    or                      prioritised by: total_views × CVR gap from category median
GENERATOR (generator.py)    creates copy from scratch for new deals
    │
    ▼
SEO PASS  (seo.py)          separate LLM call — keyword placement in title + opening sentence only
    │                       conversion structure is never touched
    ▼
EVALUATOR (evaluator.py)    4 independent signals:
    │   1. scorer_delta     did the content score improve?
    │   2. specificity      concrete details added, filler removed?
    │   3. hallucination    no claims invented outside source fields?
    │   4. llm_judge        blind A/B — does a second LLM prefer the new version?
    │
    ├── APPROVE → ready to publish
    ├── FLAG    → operator reviews (~2 min)
    └── REJECT  → logged, discarded

TRANSLATOR (translator.py)  translate approved copy into DE, FR, IT, ES, NL, PL
```

**Provider-agnostic:** set `LLM_PROVIDER=anthropic` or `LLM_PROVIDER=openai`.
Override any model with `LLM_MODEL=<model-name>`.

---

## Repo Structure

```
├── app.py                     # Streamlit operator dashboard (main interface)
├── data/
│   ├── deals.csv              # 500 deals, 8 weeks of performance data
│   └── data_dictionary.md
├── system/
│   ├── scorer.py              # Rule-based content quality scorer (0–100)
│   ├── rewriter.py            # Rewrites existing deal copy
│   ├── generator.py           # Creates copy from scratch for new deals
│   ├── seo.py                 # SEO keyword-placement pass (runs after rewrite/generate)
│   ├── evaluator.py           # Multi-signal evaluator (scorer delta + hallucination + LLM judge)
│   ├── translator.py          # Translates approved copy into market languages (DE, FR, IT, ES, NL, PL)
│   ├── pipeline.py            # CLI pipeline (score → rewrite → evaluate → report)
│   ├── llm_client.py          # Provider-agnostic LLM client (Anthropic / OpenAI)
│   └── validator.py           # CSV / DataFrame validation with tiered capability detection
├── analysis/
│   ├── analyze.py             # EDA + content signal analysis
│   └── verify.py              # Cross-category/geo robustness checks
├── results/
│   ├── scores.csv             # Latest scoring run
│   ├── rewrites/              # JSON: original + rewrite + eval signals
│   ├── generated/             # JSON: from-scratch generated deals
│   └── translations/          # JSON: translated copy per market
├── blueprint.md               # Operations blueprint: 100 FTE → 5 FTE path
├── HOW_IT_WORKS.md            # Business overview + operator getting-started guide
└── requirements.txt
```

---

## CLI Usage (alternative to the dashboard)

```bash
# Score all deals
python system/pipeline.py --mode score

# Rewrite top 20 priority deals
python system/pipeline.py --mode rewrite --n 20

# Evaluate all rewrites
python system/pipeline.py --mode evaluate

# Full pipeline in one shot
python system/pipeline.py --mode all --n 10

# Generate copy for a new deal (no existing description needed)
python system/generator.py \
  --merchant "TopGear Garage" --category "Automotive" \
  --geo "Manchester" --service "Windshield chip repair, up to 3 chips" \
  --price 49 --value 120

# SEO pass on a rewrite result
python system/seo.py --from-json results/rewrites/<deal_id>.json

# Translate into specific markets
python system/translator.py --from-json results/rewrites/<deal_id>.json --markets DE,FR,IT
```

---

## Weekly KPIs

| Metric | Target |
|---|---|
| CVR lift (rewritten vs. holdout, 90 days) | ≥ +15% |
| Acceptance rate (auto-approved) | ≥ 75% |
| Hallucination rate | < 1% |
| Score ↔ CVR correlation | r ≥ 0.55 |

See [`blueprint.md`](blueprint.md) for the full 100 FTE → 5 FTE transition plan.  
See [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) for the operator guide.
