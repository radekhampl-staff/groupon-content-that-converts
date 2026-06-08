# Operations Blueprint — Content That Converts

## Problem Statement

100 FTE write, vet, and edit Groupon deal content optimizing for throughput. Nobody measures whether content converts. There is no feedback loop between what gets written and what gets bought.

Analysis of 500 deals shows a clear, exploitable gap: structured descriptions convert **101% better** than generic templates. Combined content score (0→4) yields **+280% CVR**. The writing quality is the variable — not discount percentage, not category, not city.

---

## Current State → Target State

| Dimension | Today (100 FTE) | Target (5 FTE) |
|---|---|---|
| New deal copy | Human writes from scratch | System scores + writes draft; human approves edge cases |
| Live deal optimization | None | Weekly batch: rescore all live deals, queue underperformers |
| Quality signal | None (throughput = success) | content_score, CVR lift vs. holdout, hallucination rate |
| Feedback loop | None | CVR delta tracked per rewrite; examples feed back into prompts |
| Time to publish | Days | Minutes (score → rewrite → eval → approve) |

---

## System Components (built)

```
deals.csv
    │
    ▼
SCORER (scorer.py)          — rule-based, ~0ms/deal, r=0.644 vs CVR
    │ deals below threshold (score < 60)
    ▼
REWRITER (rewriter.py)      — Claude claude-sonnet-4-6, prompt-cached system prompt
    │                          prioritized by: total_views × CVR gap from category median
    ▼
EVALUATOR (evaluator.py)    — 4 independent signals, no single LLM self-judge:
    │   1. scorer_delta      rule-based: did score improve?
    │   2. specificity       heuristic: concrete nouns added, filler removed?
    │   3. hallucination     regex: no claims outside source fields?
    │   4. llm_judge         blind A/B via claude-haiku (cheap, randomized order)
    │
    ├── APPROVE → publish directly
    ├── FLAG    → human reviews (15–30 min/week total)
    └── REJECT  → log + discard
```

---

## Path from 100 FTE to Target State

### Phase 1 — Parallel run (Month 1–2)
- System rewrites **bottom 20% CVR** live deals (highest leverage, lowest risk — already underperforming)
- Human writers continue working; system output goes into a review queue
- Measure: do system rewrites get approved? Do they beat holdout CVR?
- **Gate**: approval rate > 70%, no hallucination incidents → move to Phase 2

### Phase 2 — New deal creation (Month 3–4)
- System generates **first draft** for all new deals at submission time
- Writers shift from "writing" to "reviewing and improving AI drafts"
- Expect 20–30% of drafts to need meaningful edits → writers still add value
- Headcount starts reducing through attrition (no forced layoffs at this stage)
- **Gate**: editor acceptance rate > 80%, CVR of system-drafted deals ≥ category baseline

### Phase 3 — Lights-out for standard deals (Month 5–6)
- System handles 80%+ of deals end-to-end: score → rewrite → eval → auto-publish for APPROVE
- Human review only for: FLAG verdicts, new categories, merchants with legal requirements, high-ticket deals (AOV > $300)
- 5 FTE remaining: 2 content strategists, 2 QA/ops, 1 data analyst

### Phase 4 — Continuous improvement (Ongoing)
- Weekly: collect CVR outcomes for published rewrites → feed examples back into prompts
- Monthly: retrain scoring weights from accumulating rewrite→CVR ground truth
- Quarterly: human-curated "best 50" rewrites reviewed for prompt refresh

---

## What Remains Human

| Task | Why human |
|---|---|
| High-ticket / high-risk deals (AOV > $300) | Brand risk, legal review needed |
| New merchant onboarding | Relationship, context gathering |
| FLAG verdicts from evaluator | Edge cases the system flags itself |
| Category playbook updates | Strategic judgment, not content execution |
| Hallucination incident response | Trust and brand integrity |
| Prompt engineering and model updates | System improvement over time |

The 5 remaining FTE are **system operators and quality directors**, not copywriters.

---

## Weekly KPIs

| Metric | What it measures | Target |
|---|---|---|
| **CVR lift** | Rewritten deals vs. holdout (same category/geo/week) | ≥ +15% at 90-day mark |
| **Acceptance rate** | % of rewrites auto-approved without human edit | ≥ 75% |
| **Hallucination rate** | % of rewrites flagged for ungrounded claims | < 1% |
| **Scorer→CVR r** | Does our proxy score still track actual CVR? | r ≥ 0.55 (monitor for drift) |
| **Queue throughput** | Rewrites processed per week | > 50 (ramp to 200 at Phase 3) |

If acceptance rate drops below 60% for two consecutive weeks → pause and audit prompt quality.  
If hallucination rate exceeds 2% in any week → immediate human review of all pending rewrites.

---

## Why This Gets Better Over Time

The system is not a one-shot prompt. It improves through three feedback loops:

**1. Example pool grows**
Every APPROVED rewrite with measured CVR lift becomes a candidate few-shot example. After 90 days, the system has 50–100 real before/after pairs with outcome labels — prompts become progressively more grounded.

**2. Scorer is recalibrated**
Current scorer weights are derived from cross-sectional analysis of 500 deals. After 6 months of rewrites with CVR outcomes, we have a longitudinal dataset: we know what *changed* and whether CVR went up. Regression on deltas replaces the rule-based weights with learned ones.

**3. Category playbooks emerge**
Content strategists (2 FTE) watch which rewrites consistently win or lose per category. They encode patterns into category-specific prompt sections. "What works in Automotive" differs from "what works in Travel" — the system learns this instead of using a generic template.

---

## Cost Model

| Item | Volume | Cost |
|---|---|---|
| Scoring | 500 deals/week | ~$0 (rule-based) |
| Rewriting (claude-sonnet-4-6 with caching) | 50 rewrites/week × ~1,200 tokens output | ~$3/week |
| Evaluating (claude-haiku for judge signal) | 50 evals/week × ~300 tokens | ~$0.10/week |
| **Total API cost** | | **< $5/week** |
| **FTE cost saved** | 95 FTE × ~$60k/yr avg | **~$5.7M/year** |

Even at 10× API cost overrun, the economics are not close.
