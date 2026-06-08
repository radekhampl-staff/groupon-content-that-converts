# How It Works — Business Overview

---

## Getting Started — From Clone to Running

### What you need before you begin

| Requirement | Details |
|---|---|
| **Python** | 3.9 or newer |
| **LLM API key** | Anthropic (`ANTHROPIC_API_KEY`) or OpenAI (`OPENAI_API_KEY`) — one is enough |
| **Your deals data** | A CSV file with your deal inventory (see format below) |

Scoring (Step 1) is fully rule-based — no API key needed.  
Steps 2–5 (write, SEO, evaluate, translate) make LLM calls and require a key.

---

### Step 1 — Install and launch

```bash
git clone <repo>
cd content-that-converts
pip install -r requirements.txt

# Set your API key
export ANTHROPIC_API_KEY=your_key_here
# or: export LLM_PROVIDER=openai && export OPENAI_API_KEY=your_key_here

# Launch the operator dashboard
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501). That's it — everything else happens inside the dashboard.

To switch LLM provider or override the model:
```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=your_key_here
export LLM_MODEL=gpt-4-turbo   # optional model override
```

---

### Step 2 — Load your data

In the dashboard, go to **Setup**:

- **Upload CSV** — drag and drop your deals file. The repo includes `data/deals.csv` (500 sample deals) — click "Use included sample data" to start immediately.
- **Connect Database** — enter a SQLAlchemy connection string and a SQL query. Supported: PostgreSQL, MySQL, SQLite, BigQuery, Snowflake.

The app validates your data on load and tells you exactly what's missing and what operations are available.

**Minimum columns required:**

| Column | Example |
|---|---|
| `deal_id` | `d04a54f4` |
| `title` | `Amazing Auto Service at MasterMech` |
| `description` | Full deal description text |
| `fine_print` | Legal/redemption terms |
| `category` | `Automotive` |
| `subcategory` | `Auto Repair` |
| `geo` | `Chicago` |
| `merchant_name` | `MasterMech Tire & Auto` |
| `price` | `49` |
| `value` | `120` |
| `option_names` | `Single visit, 3-visit pack` |
| `image_quality_score` | `3` (scale 1–5) |
| `num_options` | `2` |
| `cvr` | `0.043` |
| `weekly_udvs_w1` … `weekly_udvs_w8` | Weekly unique deal views |

See `data/data_dictionary.md` for the full column reference.

---

### Step 3 — Weekly run

Go to **Weekly Run** in the dashboard:

1. Set how many deals to rewrite (default: 20)
2. Click **▶ Run Full Pipeline**
3. Watch the progress: score → rewrite → SEO → evaluate
4. Check the summary: N approved / N flagged / N rejected

The whole run takes ~5–10 minutes for 20 deals.

---

### Step 4 — Review flagged deals

Go to **Review Queue**. For each flagged deal:

- Read original vs. rewritten copy side-by-side
- Check the 4 quality signals (score improvement, specificity, hallucination, LLM judge)
- Click **Approve**, **Reject**, or edit the text and **Save edits**

Typically 3–6 flagged deals per week. Each takes 2–3 minutes.

---

### Step 5 — Generate copy for a new deal

Go to **New Deal**. Fill in what you know about the merchant — merchant name and service description are the only required fields. Click **Generate**, optionally run the **SEO pass**, then save.

---

### Step 6 — Translate

Go to **Translations**. Select an approved deal (or paste text), choose markets, click **Translate**. Results saved to `results/translations/`.

---

### Where results are saved

| Output | Location |
|---|---|
| Deal scores | `results/scores.csv` |
| Rewrites + evaluations | `results/rewrites/<deal_id>.json` and `.eval.json` |
| Generated copy | `results/generated/<merchant-slug>.json` |
| Translations | `results/translations/<title-slug>.json` |

---

### Before going to production

- [ ] Hallucination rate < 1% — check the Report page, `hallucination` column
- [ ] Acceptance rate > 70% — if lower, the rewriter prompt may need tuning for your categories  
- [ ] Spot-check 5–10 rewrites manually before enabling auto-publish
- [ ] Confirm `LLM_MODEL` is set to the model you intend to pay for

---

### CLI alternative (advanced / headless)

All operations are also available as standalone scripts:

```bash
python system/pipeline.py --mode all --n 10        # full pipeline
python system/pipeline.py --mode score             # score only
python system/pipeline.py --mode rewrite --n 20   # rewrite only
python system/pipeline.py --mode evaluate          # evaluate only
python system/generator.py --merchant "..." --service "..."
python system/seo.py --from-json results/rewrites/<id>.json
python system/translator.py --from-json results/rewrites/<id>.json --markets DE,FR
```

---

## The Problem in One Sentence

100 people write deal descriptions, but nobody measures whether those descriptions actually sell. Analysis of 500 deals shows deals with specific, structured copy convert **2× better** than deals with generic filler text.

---

## What the System Does

```
Every week, the system runs five steps:

STEP 1 — FIND
Scans all live deals and gives each one a content quality score (0–100).
Flags the worst performers (typically 20–40 deals per week).
Prioritizes by: high traffic × low conversion = biggest revenue opportunity.

STEP 2 — WRITE
Two modes depending on whether a deal already exists:
  • Rewrite mode: takes an existing deal and improves its title + description.
  • Generator mode: creates title + description from scratch for new deals
    (only needs merchant name, category, service description, and price).
The AI follows proven patterns from your best-performing deals.
Takes about 10 seconds per deal.

STEP 3 — SEO PASS (separate step)
A second AI call focused only on search visibility:
  • Moves the primary keyword earlier in the title
  • Rewrites the first sentence of the description to include service + location naturally
  • Does NOT touch the rest of the copy — conversion structure stays intact
This is intentionally kept separate so SEO changes can be reviewed independently.

STEP 4 — CHECK
Runs 4 independent checks on each piece of copy:
  ✓ Did the quality score improve?
  ✓ Are there more specific details, fewer generic phrases?
  ✓ Did the AI invent any facts that weren't in the original?
  ✓ Does a second AI, reading both versions blind, prefer the new one?

Result: each deal gets a verdict.
  ✅ APPROVE → moves to Step 5
  ⚠ FLAG    → human reviews (takes 2–3 min)
  ❌ REJECT  → discarded, logged for analysis

STEP 5 — TRANSLATE
Approved copy is translated into each active market language:
  DE (German) · FR (French) · IT (Italian) · ES (Spanish) · NL (Dutch) · PL (Polish)
  English-market deals (US, UK, CA, AU, IE) are published as-is.
Merchant names, numbers, and fine print are never translated.
Each translation is a full LLM call — not a word-for-word machine translation.
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
| Rewrite existing deal copy | ✅ ~10 sec/deal | — |
| Generate copy for new deals from scratch | ✅ ~10 sec/deal | — |
| SEO optimization pass | ✅ Automatic | — |
| Check for invented facts | ✅ Automatic | — |
| Translate into 6 market languages | ✅ Automatic | — |
| Auto-publish approved copy | ✅ Automatic | — |
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

**Q: Does the SEO pass change what the AI wrote for conversion?**
A: Intentionally no. The SEO pass is a separate step that only touches the title keyword order and the opening sentence of the description. The three-section structure and all factual content remain exactly as written.

**Q: Which languages does translation support?**
A: German, French, Italian, Spanish, Dutch, and Polish — the six non-English active markets. English markets (US, UK, CA, AU, IE) are skipped automatically. Merchant names and fine print are never translated.

**Q: How do we measure if it's working?**
A: Rewrites are tracked against a holdout group (same category, same city, same week — no rewrite). After 90 days, we measure CVR lift. Target is ≥ +15%.
