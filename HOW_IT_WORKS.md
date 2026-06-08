# How It Works — Business Overview

## The Problem in One Sentence

Groupon has 100 people writing deal descriptions, but nobody measures whether those descriptions actually sell. Analysis of 500 deals shows deals with specific, structured copy convert **2× better** than deals with generic filler text.

---

## What the System Does

```
Every week, the system runs three steps:

STEP 1 — FIND
Scans all live deals and gives each one a content quality score (0–100).
Flags the worst performers (typically 20–40 deals per week).
Prioritizes by: high traffic × low conversion = biggest revenue opportunity.

STEP 2 — FIX
Sends each flagged deal to an AI that rewrites the title and description.
The AI follows proven patterns from your best-performing deals.
Takes about 10 seconds per deal.

STEP 3 — CHECK
Runs 4 independent checks on each rewrite:
  ✓ Did the quality score improve?
  ✓ Are there more specific details, fewer generic phrases?
  ✓ Did the AI invent any facts that weren't in the original?
  ✓ Does a second AI, reading both versions blind, prefer the new one?

Result: each rewrite gets a verdict.
  ✅ APPROVE → goes live automatically
  ⚠ FLAG    → human reviews (takes 2–3 min)
  ❌ REJECT  → discarded, logged for analysis
```

---

## What Good Copy Looks Like vs. Bad Copy

### ❌ Bad (generic — 9,000+ deals look like this)
**Title:** Amazing Auto Service at MasterMech Tire & Auto

**Description:** Save on this top-rated experience in Los Angeles. Whether you're a local or just visiting, this deal offers real value. Simple redemption — just show your voucher. See fine print for full details.

---

### ✅ Good (specific — converts 2× better)
**Title:** Windshield Chip Repair — Up to 3 Chips at TopGear Garage

**Description:** What We Offer: Repair of up to 3 windshield chips using resin injection by an ASE-certified technician. No appointment needed — drive in, wait in our lounge, done in 20 minutes. Why You Should Grab This Offer: We've serviced over 10,000 vehicles with a 12-month warranty on all work. Customers rate us 4.8 stars for speed and transparency. Good to Know: Open 7 days. Free Wi-Fi and coffee while you wait. Shuttle available within 5 miles.

---

## Weekly Flow for Operations Team

```
Monday morning — system runs automatically
    │
    ▼
Dashboard shows:
  • N deals scored below threshold
  • N rewrites generated
  • N approved / N flagged / N rejected
    │
    ├── APPROVED deals → already live (no action needed)
    │
    ├── FLAGGED deals → operator reviews each one (~2 min each)
    │     Click APPROVE or EDIT → goes live
    │     Click REJECT → discarded
    │
    └── REJECTED deals → logged for weekly review
          Analyst checks: is this a prompt issue? A bad data issue?
          → Feed learnings back into system

Friday — weekly report
  • CVR lift: did rewritten deals convert better than control?
  • Acceptance rate: how many rewrites needed no human edits?
  • Any hallucination incidents?
```

---

## What Humans Do vs. What the System Does

| Task | System | Human |
|---|---|---|
| Score all 500 deals weekly | ✅ Automatic | — |
| Identify the 20–40 biggest opportunities | ✅ Automatic | — |
| Generate rewrite drafts | ✅ ~10 sec/deal | — |
| Check for invented facts | ✅ Automatic | — |
| Auto-publish approved rewrites | ✅ Automatic | — |
| Review flagged edge cases | — | ✅ ~30 min/week |
| Update category writing guidelines | — | ✅ Monthly |
| Handle merchant complaints | — | ✅ As needed |
| Decide when system needs retraining | — | ✅ Quarterly |

---

## How the System Gets Smarter Over Time

The system is not a static tool. It has three feedback loops:

**1. Learning from outcomes**
After 90 days, we know which rewrites actually increased conversion. Those become new examples in the AI's instructions — the system learns what "good" looks like for your specific deals, not just generic writing advice.

**2. Score recalibration**
The quality scorer is currently based on patterns from 500 deals. After 6 months of rewrites with measured outcomes, we replace the rule-based weights with data-driven ones trained on your actual conversion data.

**3. Category playbooks**
The content team writes down what works per category. "What converts in Automotive" differs from "what converts in Spa." These get encoded into the AI's instructions, making rewrites progressively more targeted.

---

## Rollout Phases

| Phase | Timeline | What changes |
|---|---|---|
| **Pilot** | Month 1–2 | System rewrites bottom-20% CVR deals. Writers review all output. Build trust. |
| **Scale** | Month 3–4 | System drafts all new deals. Writers shift to reviewing AI output instead of writing from scratch. |
| **Steady state** | Month 5+ | System auto-publishes approved rewrites. Human team = 5 people managing the system, not writing copy. |

---

## Questions & Answers

**Q: What if the AI writes something wrong about a merchant?**
A: The hallucination check catches claims not present in the original deal data. Any deal with a suspicious new claim gets REJECTED automatically, never published. FLAGGED deals go to human review before going live.

**Q: What if the AI makes things worse?**
A: Every rewrite is compared to the original on four independent signals. A rewrite needs to pass at least 3/4 to be approved. If the quality score drops or a second AI prefers the original, it's flagged or rejected.

**Q: Can we use this with our existing AI provider?**
A: Yes. The system is provider-agnostic. Set `LLM_PROVIDER=openai` (or `anthropic`) and your own API key. No vendor lock-in.

**Q: How do we measure if it's working?**
A: Rewrites are tracked against a holdout group (same category, same city, same week — no rewrite). After 90 days, we measure CVR lift. Target is ≥ +15%.
