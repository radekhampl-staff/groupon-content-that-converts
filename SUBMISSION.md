# Submission — Content That Converts

Repo: https://github.com/radekhampl-staff/groupon-content-that-converts

---

## Assignment deliverables

The brief asked for three things: analysis of what drives conversion in the deal data, a working proof-of-concept system, and an operations blueprint for transitioning from 100 FTE to 5 FTE. All three are here.

---

## 1. Analysis — what actually drives CVR

**TL;DR:** How a deal is written matters far more than how it's priced.

Run it yourself:
```bash
cd analysis && python3 analyze.py
cd analysis && python3 verify.py
```

### Key findings

**Description type is the single strongest signal.**
Deals using a structured format ("What We Offer / Why You Should Grab This Offer / Good to Know") convert **+101% better** than deals using generic templates ("Experience the best that [city] has to offer...", "Treat yourself or someone special..."). This holds across every category and every geo in the dataset — no exceptions.

| Description type | Avg CVR | Count |
|---|---|---|
| Structured (What We Offer / Included) | 0.0494 | 218 |
| Generic templates (8 variants) | 0.0244 | 282 |

Category-by-category, the lift ranges from +74% (Retail) to +144% (Health & Fitness). Geo-by-geo, it holds across all 15 cities — from +35% (San Francisco) to +166% (Manchester). This is not a confounded signal.

**Title specificity adds another +71% CVR lift.**
Generic title patterns ("Amazing X at Y", "Best X at Y", "Incredible X at Y") underperform specific titles by 71%. Among the top 20 highest-CVR deals in the dataset: 20/20 have structured descriptions and 20/20 have specific titles. Not a single top performer uses a generic template.

**Discount percentage has almost no signal (r = 0.076).**
This is the counter-intuitive finding. Groupon's product is built around discounts, but deeper discounts don't meaningfully predict conversion. Content quality does. A deal at 30% off with great copy converts better than a deal at 70% off with generic filler.

**Combined content score: 0→4 = +280% CVR.**
Combining four binary signals (structured description, specific title, descriptive option names, image quality ≥ 4) into a 0–4 score:

| Score | Avg CVR | Count |
|---|---|---|
| 0 | 0.017 | 7 |
| 1 | 0.017 | 86 |
| 2 | 0.027 | 157 |
| 3 | 0.041 | 184 |
| 4 | 0.066 | 66 |

**One notable finding outside the scope of this system:** image quality has r = 0.458 correlation with CVR within categories — a meaningfully strong signal. The text rewriter can't fix images, but this suggests a parallel image quality initiative would compound the returns from content optimization.

---

## 2. The system

### How it works

```
deals.csv (or database)
    │
    ▼
SCORER          rule-based, ~0ms/deal, r = 0.644 vs CVR
    │  flags deals scoring < 60/100
    ▼
REWRITER        rewrites title + description using proven patterns
    │           prioritised by: total_views × CVR gap from category median
    ▼
SEO PASS        separate LLM call — keyword placement in title + opening sentence only
    │           conversion structure is never touched by the SEO step
    ▼
EVALUATOR       4 independent signals:
    │   1. scorer_delta   — did the content score improve?
    │   2. specificity    — concrete details added, filler removed?
    │   3. hallucination  — no claims invented outside source fields?
    │   4. llm_judge      — blind A/B, does a second LLM prefer the new version?
    │
    ├── APPROVE → ready to publish
    ├── FLAG    → operator reviews (~2 min each)
    └── REJECT  → logged, discarded

TRANSLATOR      approved copy translated into DE, FR, IT, ES, NL, PL
```

### On the evaluator design

Using a single LLM to judge its own output is a known failure mode — it tends to prefer its own generation regardless of quality. The four-signal approach avoids this: three signals are deterministic (scorer, specificity checker, hallucination detector), and the fourth (LLM judge) uses a second call with randomized A/B order to control for position bias. A rewrite needs to pass at least 3/4 signals to be approved.

### On the scorer

The scorer (r = 0.644 vs CVR) doesn't use the LLM at all — it's rule-based pattern matching on title, description, option names, and image quality. This means scoring 500 deals costs nothing and runs in under a second. The LLM is called only for the ~220 deals that score below threshold and are candidates for rewriting.

### Running it

```bash
git clone https://github.com/radekhampl-staff/groupon-content-that-converts.git
cd groupon-content-that-converts
pip install -r requirements.txt

# Pick your LLM provider — Anthropic or OpenAI, either works:
export ANTHROPIC_API_KEY=your_key
# — or —
# export LLM_PROVIDER=openai
# export OPENAI_API_KEY=your_key

streamlit run app.py
```

Open http://localhost:8501 → Setup → load `data/deals.csv` → Weekly Run. The repo includes 500 sample deals so the full pipeline runs immediately without connecting any external data source.

CLI equivalent for headless/automation use:
```bash
python system/pipeline.py --mode all --n 20
```

---

## 3. Operations blueprint

Full detail in [`blueprint.md`](blueprint.md). Summary:

**Target state:** 5 people managing the system, not writing copy. Weekly operator time ≈ 30 minutes (reviewing flagged edge cases). Everything else is automated.

**4-phase rollout:**

| Phase | Timeline | Gate to proceed |
|---|---|---|
| Pilot | Month 1–2 | Acceptance rate > 60%, zero hallucination incidents |
| Scale | Month 3–4 | Acceptance rate > 70%, CVR lift measurable |
| Steady state | Month 5+ | Auto-publish enabled for APPROVE verdicts |
| Self-improving | Month 7+ | Outcome-based few-shot examples in production |

**Weekly KPIs:**

| Metric | Target |
|---|---|
| CVR lift vs holdout (90-day) | ≥ +15% |
| Acceptance rate (auto-approved) | ≥ 75% |
| Hallucination rate | < 1% |
| Score ↔ CVR correlation | r ≥ 0.55 |

**What remains human:** edge case review (~30 min/week), category writing guidelines (monthly), merchant complaints, system retraining decisions (quarterly).

**Cost model:** at 20 rewrites/week with prompt caching, LLM costs are under $10/week — versus an estimated $5.7M/year for 100 FTE at current scale.

**How the system improves over time:**
1. After 90 days, rewrites with confirmed CVR lift become few-shot examples — the rewriter learns from real outcomes, not just general writing advice
2. After 6 months, the rule-based scorer weights get replaced with data-driven ones trained on actual conversion data
3. Category playbooks: what converts in Automotive differs from what converts in Spa — these patterns get encoded into the prompts over time

---

## What was added beyond the brief

Four things in the repo weren't in the assignment. Brief explanation of each:

**Streamlit operator dashboard** — the brief asked for a working PoC, which the CLI delivers. But the automation mindset question is really about whether a non-technical operator can use this without a developer. A 5-person team managing a weekly pipeline needs a UI. The dashboard covers the full weekly flow: load data, run pipeline, review flagged deals, generate copy for new deals, translate, report.

**SEO pass as a separate step** — during rewriter development it became clear that SEO and CVR optimization pull in opposite directions. Combining them in one prompt produces compromise copy. Keeping them separate means each step can be reviewed independently, and the SEO layer can be skipped for markets where it's less relevant.

**Translation into 6 Groupon markets** — German, French, Italian, Spanish, Dutch, Polish. Once approved copy exists, translation costs one LLM call per market. English markets (US, UK, CA, AU, IE) are skipped automatically.

**Generator for new deals** — the brief focused on rewriting existing deals. The same patterns should apply to copy written from scratch. The generator is a standalone tool, not integrated into the weekly pipeline, so it doesn't add complexity to the core flow.

All four are optional. The core system (scorer + rewriter + evaluator + pipeline) answers the brief directly and runs independently.

---

## File map

| File | What it does |
|---|---|
| `app.py` | Streamlit operator dashboard |
| `system/scorer.py` | Rule-based content quality scorer (0–100) |
| `system/rewriter.py` | LLM rewriter with prompt caching and few-shot examples |
| `system/generator.py` | Creates copy from scratch for new deals |
| `system/seo.py` | SEO keyword-placement pass (title + opening sentence only) |
| `system/evaluator.py` | 4-signal evaluator |
| `system/translator.py` | Translates approved copy into 6 market languages |
| `system/pipeline.py` | CLI pipeline (score → rewrite → evaluate → report) |
| `system/llm_client.py` | Provider-agnostic LLM client (Anthropic / OpenAI) |
| `system/validator.py` | Input validation with tiered capability detection |
| `analysis/analyze.py` | EDA + content signal analysis |
| `analysis/verify.py` | Cross-category/geo robustness checks |
| `blueprint.md` | Full operations blueprint |
| `HOW_IT_WORKS.md` | Business overview + operator getting-started guide |
