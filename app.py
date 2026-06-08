"""
Content That Converts — Streamlit operator dashboard.

Run:
  streamlit run app.py
"""

import json
import os
import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "system"))

from validator import validate_dataframe, SCORING_COLUMNS, REWRITE_COLUMNS, PRIORITY_COLUMNS


# ── Helpers ────────────────────────────────────────────────────────────────────

def api_ready() -> bool:
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    key = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
    return bool(os.environ.get(key))


def api_provider() -> str:
    return os.environ.get("LLM_PROVIDER", "anthropic")


@st.cache_resource
def _import_modules() -> dict:
    """Import and cache system modules once per app session."""
    from scorer    import score_all
    from rewriter  import rewrite_deal, get_priority_queue
    from evaluator import evaluate_rewrite
    from generator import generate_deal
    from seo       import run_seo_pass
    from translator import translate_to_markets, MARKETS
    return dict(
        score_all=score_all,
        rewrite_deal=rewrite_deal,
        get_priority_queue=get_priority_queue,
        evaluate_rewrite=evaluate_rewrite,
        generate_deal=generate_deal,
        run_seo_pass=run_seo_pass,
        translate_to_markets=translate_to_markets,
        MARKETS=MARKETS,
    )


def load_modules() -> dict:
    """Return cached system modules, showing a clear error if import fails."""
    try:
        return _import_modules()
    except Exception as e:
        st.error(f"**Missing dependency:** {e}\n\nRun `pip install -r requirements.txt` and restart.")
        st.stop()


def pending_review_count() -> int:
    rewrite_dir = ROOT / "results" / "rewrites"
    if not rewrite_dir.exists():
        return 0
    return sum(
        1 for f in rewrite_dir.glob("*.eval.json")
        if json.loads(f.read_text()).get("verdict") == "FLAG"
    )


def _set_dataframe(df: pd.DataFrame, source_label: str):
    vr = validate_dataframe(df)
    st.session_state.df = df
    st.session_state.validation = vr
    st.session_state.data_source_label = source_label


# ── Page: Setup ────────────────────────────────────────────────────────────────

def page_setup():
    st.title("Setup")
    st.caption("Connect your data source and configure your LLM API key.")

    with st.expander("📖 How This System Works", expanded=st.session_state.get("df") is None):
        st.markdown("""
| Step | What happens | Needs API? | Time |
|---|---|---|---|
| **1. Score** | Every deal gets a content quality score (0–100). Lowest scores = biggest opportunity. | No | ~0 ms/deal |
| **2. Write** | Worst-scoring deals are rewritten. New deals can be created from scratch. | Yes | ~10 s/deal |
| **3. SEO pass** | Second AI call: moves primary keyword earlier in title and opening sentence only. | Yes | ~5 s/deal |
| **4. Evaluate** | 4 independent checks: quality improved? specific details added? nothing invented? second AI prefers new version? | Yes | ~5 s/deal |
| **5. Translate** | Approved copy → DE, FR, IT, ES, NL, PL. English markets skipped automatically. | Yes | ~8 s/market |

**Weekly routine for the operator:** open Weekly Run on Monday → click Run → review flagged deals (~2 min each). That's it.
        """)

    st.divider()

    # ── API status ─────────────────────────────────────────────────────────────
    if api_ready():
        st.success(f"✅ API key detected — provider: **{api_provider()}**")
    else:
        provider = api_provider()
        key_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
        st.warning(f"""
**⚠️ No API key set.** Steps 2–5 won't work until you add one.

```bash
export {key_var}=your_key_here
# then restart:  streamlit run app.py
```

To switch providers:
```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=your_key_here
```

Step 1 (scoring) works without an API key.
        """)

    st.divider()

    # ── Data source tabs ───────────────────────────────────────────────────────
    tab_csv, tab_db = st.tabs(["📄 Upload CSV", "🗄️ Connect Database"])

    with tab_csv:
        st.markdown(
            "Upload your deals CSV. "
            "The repo includes a sample file (`data/deals.csv`, 500 deals) — use it to test immediately."
        )
        if st.button("Use included sample data"):
            sample = ROOT / "data" / "deals.csv"
            if sample.exists():
                _set_dataframe(pd.read_csv(sample), "sample data (data/deals.csv)")
                st.rerun()
            else:
                st.error("Sample file not found at `data/deals.csv`.")

        uploaded = st.file_uploader("Or upload your own CSV", type=["csv"])
        if uploaded:
            try:
                _set_dataframe(pd.read_csv(uploaded), f"uploaded: {uploaded.name}")
                st.rerun()
            except Exception as e:
                st.error(f"Could not read file: {e}")

        with st.expander("Required CSV columns"):
            st.markdown("**Minimum (scoring only):**")
            st.code(", ".join(SCORING_COLUMNS))
            st.markdown("**For rewriting:**")
            st.code(", ".join(c for c in REWRITE_COLUMNS if c not in SCORING_COLUMNS))
            st.markdown("**For priority ordering (highest CVR impact first):**")
            st.code("cvr, weekly_udvs_w1 … weekly_udvs_w8")

    with tab_db:
        st.markdown("""
Connect to any SQL database. The query must return the required columns.

**Supported connection strings:**
| Database | Connection string format |
|---|---|
| PostgreSQL | `postgresql://user:password@host:5432/database` |
| MySQL | `mysql+pymysql://user:password@host/database` |
| SQLite | `sqlite:///path/to/file.db` |
| BigQuery | `bigquery://project/dataset` *(needs `pip install sqlalchemy-bigquery`)* |
| Snowflake | `snowflake://user:pass@account/db` *(needs `pip install snowflake-sqlalchemy`)* |

Connection details are kept in memory only — never written to disk.
        """)

        conn_str = st.text_input(
            "Connection string",
            type="password",
            placeholder="postgresql://user:pass@localhost/mydb",
        )
        query = st.text_area(
            "SQL query",
            placeholder="SELECT * FROM deals WHERE is_active = true",
            height=80,
        )

        if st.button("Connect & Load", disabled=not (conn_str and query)):
            try:
                from sqlalchemy import create_engine, text
                with st.spinner("Connecting..."):
                    engine = create_engine(conn_str)
                    with engine.connect() as conn:
                        df = pd.read_sql(text(query), conn)
                _set_dataframe(df, "database")
                st.rerun()
            except ImportError:
                st.error("SQLAlchemy not installed. Run: `pip install sqlalchemy`")
            except Exception as e:
                st.error(f"**Connection failed:** {e}")

    # ── Validation results ─────────────────────────────────────────────────────
    if st.session_state.get("df") is not None:
        df  = st.session_state.df
        vr  = st.session_state.validation
        src = st.session_state.get("data_source_label", "—")

        st.divider()
        st.subheader("Loaded Data")

        c1, c2, c3 = st.columns(3)
        c1.metric("Deals", f"{len(df):,}")
        c2.metric("Columns", len(df.columns))
        c3.metric("Source", src)

        if vr.errors:
            for msg in vr.errors:
                st.error(f"❌ {msg}")

        if vr.warnings:
            for msg in vr.warnings:
                st.warning(f"⚠️ {msg}")

        if vr.is_valid:
            caps = vr.capabilities
            st.markdown("**Available operations with this data:**")
            for label, cap in [
                ("Score all deals", "score"),
                ("Rewrite existing deals", "rewrite"),
                ("Priority-ordered rewrites (highest revenue impact first)", "priority"),
            ]:
                st.markdown(f"- {'✅' if cap in caps else '❌'} {label}")

        st.dataframe(df.head(5), use_container_width=True)


# ── Page: Weekly Run ───────────────────────────────────────────────────────────

def page_weekly_run():
    st.title("Weekly Run")

    df = st.session_state.get("df")
    if df is None:
        st.warning("No data loaded. Go to **Setup** first.")
        return

    vr = st.session_state.get("validation")
    if vr and "score" not in vr.capabilities:
        st.error("Data is missing required columns for scoring. Check **Setup**.")
        return

    m = load_modules()

    st.markdown("""
**What this does:** scores all deals → rewrites the worst performers → runs SEO pass →
evaluates every rewrite → saves results. Run this Monday morning.

Approvals land automatically in `results/`. Flagged deals appear in **Review Queue**.
    """)

    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        n_rewrites = st.slider("Deals to rewrite", 5, 50, 20, 5)
    with col2:
        skip_seo  = st.checkbox("Skip SEO pass", value=False)
    with col3:
        dry_run   = st.checkbox("Dry run (no API calls)", value=False)

    if not api_ready() and not dry_run:
        st.error("API key not set. Enable **Dry run** or add your key (see Setup).")
        return

    if vr and "rewrite" not in vr.capabilities and not dry_run:
        st.warning("Data is missing rewrite columns. Only scoring will run.")

    if st.button("▶ Run Full Pipeline", type="primary", use_container_width=True):
        _run_pipeline(df, m, n_rewrites, skip_seo, dry_run, vr)


def _run_pipeline(df, m, n_rewrites, skip_seo, dry_run, vr):
    results_dir = ROOT / "results"
    rewrite_dir = results_dir / "rewrites"
    results_dir.mkdir(exist_ok=True)
    rewrite_dir.mkdir(exist_ok=True)

    # Step 1 — Score
    with st.spinner("Step 1 / 4 — Scoring all deals..."):
        scores_df = m["score_all"](df)
        full = df.merge(scores_df[["deal_id", "total_score", "rewrite_recommended"]])
        full.to_csv(results_dir / "scores.csv", index=False)

    n_flag = int(scores_df["rewrite_recommended"].sum())
    st.success(f"✅ Scored {len(df):,} deals — **{n_flag}** flagged for rewrite")

    if dry_run:
        st.info("Dry run: stopping after scoring. No API calls made.")
        preview = full[full["rewrite_recommended"]][["title", "category", "geo", "total_score"]]
        st.dataframe(preview.head(n_rewrites), use_container_width=True)
        return

    if vr and "rewrite" not in vr.capabilities:
        st.info("Rewriting skipped — missing columns. See Setup for details.")
        return

    # Step 2 — Rewrite
    try:
        queue = m["get_priority_queue"](df, n_rewrites)
    except Exception:
        queue = full[full["rewrite_recommended"]].head(n_rewrites)

    if queue.empty:
        st.info("No deals meet the rewrite threshold this week.")
        return

    st.markdown(f"**Step 2 / 4 — Rewriting {len(queue)} deals...**")
    progress    = st.progress(0)
    status      = st.empty()
    written_paths: list[Path] = []

    for i, (_, row) in enumerate(queue.iterrows()):
        out_path = rewrite_dir / f"{row['deal_id']}.json"
        label    = str(row["title"])[:55]

        if out_path.exists():
            status.text(f"[{i+1}/{len(queue)}] Already done: {label}")
            written_paths.append(out_path)
        else:
            status.text(f"[{i+1}/{len(queue)}] Rewriting: {label}...")
            try:
                result = m["rewrite_deal"](row)

                if not skip_seo:
                    seo = m["run_seo_pass"](
                        result["new_title"], result["new_desc"],
                        str(row.get("category", "")), str(row.get("geo", "")),
                    )
                    result["new_title"]   = seo["title"]
                    result["new_desc"]    = seo["description"]
                    result["seo_changes"] = seo.get("seo_changes", "")

                out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
                written_paths.append(out_path)
            except Exception as e:
                st.warning(f"⚠️ Failed on `{row['deal_id']}`: {e}")

        progress.progress((i + 1) / len(queue))

    status.empty()
    st.success(f"✅ {len(written_paths)} rewrites saved")

    # Step 3 — Evaluate
    st.markdown("**Step 3 / 4 — Evaluating rewrites...**")
    progress2  = st.progress(0)
    status2    = st.empty()
    verdicts: dict[str, int] = {"APPROVE": 0, "FLAG": 0, "REJECT": 0}

    for i, path in enumerate(written_paths):
        eval_path = path.with_suffix(".eval.json")
        if eval_path.exists():
            v = json.loads(eval_path.read_text()).get("verdict", "FLAG")
            verdicts[v] = verdicts.get(v, 0) + 1
        else:
            status2.text(f"[{i+1}/{len(written_paths)}] Evaluating {path.stem[:30]}...")
            try:
                result  = m["evaluate_rewrite"](path, df)
                verdicts[result["verdict"]] = verdicts.get(result["verdict"], 0) + 1
            except Exception as e:
                st.warning(f"⚠️ Eval failed on `{path.name}`: {e}")
        progress2.progress((i + 1) / len(written_paths))

    status2.empty()
    st.success("✅ Evaluation complete")

    # Summary
    st.divider()
    st.subheader("This Week's Results")
    c1, c2, c3 = st.columns(3)
    c1.metric("✅ Auto-approved", verdicts["APPROVE"])
    c2.metric("⚠️ Needs review",  verdicts["FLAG"])
    c3.metric("❌ Rejected",       verdicts["REJECT"])

    if verdicts["FLAG"] > 0:
        st.info(f"👉 {verdicts['FLAG']} deal(s) need your review — go to **Review Queue**.")


# ── Page: Review Queue ─────────────────────────────────────────────────────────

def page_review():
    st.title("Review Queue")

    df = st.session_state.get("df")
    if df is None:
        st.warning("No data loaded. Go to **Setup** first.")
        return

    rewrite_dir = ROOT / "results" / "rewrites"
    if not rewrite_dir.exists():
        st.info("No rewrites yet. Run **Weekly Run** first.")
        return

    flagged: list[tuple[Path, dict, dict]] = []
    for eval_path in sorted(rewrite_dir.glob("*.eval.json")):
        ev = json.loads(eval_path.read_text())
        if ev.get("verdict") != "FLAG":
            continue
        rw_path = eval_path.with_suffix("").with_suffix(".json")
        if rw_path.exists():
            flagged.append((eval_path, ev, json.loads(rw_path.read_text())))

    if not flagged:
        st.success("✅ Nothing to review. All deals are approved or rejected.")
        return

    st.markdown(f"**{len(flagged)} deal(s) waiting for your decision.** Each takes about 2–3 minutes.")
    st.divider()

    for eval_path, ev, rw in flagged:
        deal_id = ev["deal_id"]
        orig_title = rw.get("original_title", deal_id)

        with st.expander(f"📋 {orig_title}", expanded=True):
            left, right = st.columns(2)

            with left:
                st.markdown("**Original**")
                st.markdown(f"**{rw.get('original_title', '')}**")
                st.text_area(
                    "original_desc", rw.get("original_desc", ""),
                    height=220, disabled=True, label_visibility="collapsed",
                    key=f"orig_{deal_id}",
                )

            with right:
                st.markdown("**Rewritten** *(editable)*")
                new_title = st.text_input(
                    "new_title", rw.get("new_title", ""),
                    label_visibility="collapsed", key=f"title_{deal_id}",
                )
                new_desc = st.text_area(
                    "new_desc", rw.get("new_desc", ""),
                    height=220, label_visibility="collapsed", key=f"desc_{deal_id}",
                )

            # Quality signals
            signals = ev.get("signals", [])
            if signals:
                st.markdown("**Quality checks:**")
                sig_cols = st.columns(len(signals))
                for i, sig in enumerate(signals):
                    icon = "✅" if sig["passed"] else "❌"
                    sig_cols[i].markdown(f"{icon} **{sig['signal']}**  \n{sig['note']}")

            if rw.get("seo_changes"):
                st.caption(f"SEO: {rw['seo_changes']}")
            if rw.get("rationale"):
                st.caption(f"Rationale: {rw['rationale']}")

            # Action buttons
            b1, b2, b3, _ = st.columns([1, 1, 1.4, 2])

            if b1.button("✅ Approve", key=f"approve_{deal_id}", type="primary"):
                _write_verdict(eval_path, rw, ev, "APPROVE", new_title, new_desc)
                st.rerun()

            if b2.button("❌ Reject", key=f"reject_{deal_id}"):
                _write_verdict(eval_path, rw, ev, "REJECT", new_title, new_desc)
                st.rerun()

            if b3.button("💾 Save edits & keep flagged", key=f"save_{deal_id}"):
                rw["new_title"] = new_title
                rw["new_desc"]  = new_desc
                eval_path.with_suffix("").with_suffix(".json").write_text(
                    json.dumps(rw, indent=2, ensure_ascii=False)
                )
                st.success("Saved. Re-run evaluation to refresh signals.")


def _write_verdict(eval_path, rw, ev, verdict, new_title, new_desc):
    ev["verdict"]           = verdict
    ev["operator_decision"] = True
    eval_path.write_text(json.dumps(ev, indent=2, ensure_ascii=False))

    rw["new_title"] = new_title
    rw["new_desc"]  = new_desc
    eval_path.with_suffix("").with_suffix(".json").write_text(
        json.dumps(rw, indent=2, ensure_ascii=False)
    )


# ── Page: New Deal ─────────────────────────────────────────────────────────────

def page_generator():
    st.title("New Deal")
    st.markdown("Generate title and description from scratch. No existing copy needed — just fill in what you know about the merchant.")

    if not api_ready():
        st.error("API key required. Add it in Setup and restart the app.")
        return

    m = load_modules()

    with st.form("gen_form"):
        c1, c2 = st.columns(2)
        with c1:
            merchant    = st.text_input("Merchant name *",    placeholder="TopGear Garage")
            category    = st.text_input("Category *",         placeholder="Automotive")
            subcategory = st.text_input("Subcategory",        placeholder="Auto Repair")
            geo         = st.text_input("City / Region",      placeholder="Manchester")
        with c2:
            service  = st.text_area("What's included *",      placeholder="Windshield chip repair, up to 3 chips", height=90)
            options  = st.text_input("Deal options / tiers",  placeholder="1 chip, 2 chips, 3 chips")
            price    = st.number_input("Deal price ($)",       min_value=0.0, step=1.0)
            value    = st.number_input("Retail value ($)",    min_value=0.0, step=1.0)

        fine_print = st.text_input("Fine print", placeholder="Not valid on holidays. Expires 90 days after purchase.")
        context    = st.text_area("Extra context (optional)", placeholder="Family-owned since 1998, specialises in European cars", height=60)
        submitted  = st.form_submit_button("✨ Generate", type="primary")

    if submitted:
        if not merchant or not service:
            st.error("Merchant name and service description are required.")
        else:
            with st.spinner("Generating deal copy..."):
                try:
                    result = m["generate_deal"]({
                        "merchant": merchant, "category": category,
                        "subcategory": subcategory, "geo": geo,
                        "service": service, "options": options,
                        "price": price, "value": value,
                        "fine_print": fine_print, "context": context,
                    })
                    st.session_state["last_generated"] = result
                except Exception as e:
                    st.error(f"Generation failed: {e}")

    result = st.session_state.get("last_generated")
    if result:
        st.divider()
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown("**Title**")
            st.markdown(f"**{result['new_title']}**")
            if result.get("rationale"):
                st.caption(result["rationale"])
            if result.get("seo_changes"):
                st.caption(f"SEO: {result['seo_changes']}")
        with c2:
            st.markdown("**Description**")
            st.text_area("desc", result["new_desc"], height=220,
                         label_visibility="collapsed", disabled=True, key="gen_preview")

        bc1, bc2, _ = st.columns([1, 1, 4])

        if bc1.button("🔍 Run SEO pass"):
            with st.spinner("Optimising for search..."):
                try:
                    inp = result.get("inputs", {})
                    seo = m["run_seo_pass"](
                        result["new_title"], result["new_desc"],
                        inp.get("category", ""), inp.get("geo", ""),
                    )
                    result.update(new_title=seo["title"], new_desc=seo["description"],
                                  seo_changes=seo.get("seo_changes", ""))
                    st.session_state["last_generated"] = result
                    st.rerun()
                except Exception as e:
                    st.error(f"SEO pass failed: {e}")

        if bc2.button("💾 Save"):
            out_dir = ROOT / "results" / "generated"
            out_dir.mkdir(parents=True, exist_ok=True)
            slug = re.sub(r"[^a-z0-9]+", "-",
                          result["inputs"].get("merchant", "deal").lower()).strip("-")
            path = out_dir / f"{slug}.json"
            path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
            st.success(f"Saved → `{path}`")


# ── Page: Translations ─────────────────────────────────────────────────────────

def page_translations():
    st.title("Translations")
    st.markdown("Translate approved deal copy into active market languages (DE, FR, IT, ES, NL, PL).")

    if not api_ready():
        st.error("API key required.")
        return

    m      = load_modules()
    MARKETS = m["MARKETS"]

    tab_approved, tab_manual = st.tabs(["From approved rewrites", "Enter manually"])

    with tab_approved:
        rewrite_dir = ROOT / "results" / "rewrites"
        approved: list[tuple[str, str, str]] = []

        if rewrite_dir.exists():
            for ep in sorted(rewrite_dir.glob("*.eval.json")):
                ev = json.loads(ep.read_text())
                if ev.get("verdict") == "APPROVE":
                    rw_p = ep.with_suffix("").with_suffix(".json")
                    if rw_p.exists():
                        rw = json.loads(rw_p.read_text())
                        approved.append((ev["deal_id"], rw.get("new_title", ""), rw.get("new_desc", "")))

        if not approved:
            st.info("No approved rewrites yet. Run the pipeline and approve some deals first.")
        else:
            opts   = {f"{t[:65]} ({did[:8]})": (t, d) for did, t, d in approved}
            sel    = st.selectbox("Select deal", list(opts.keys()))
            title, desc = opts[sel]
            _translation_ui(m, MARKETS, title, desc)

    with tab_manual:
        title = st.text_input("Title (English)")
        desc  = st.text_area("Description (English)", height=150)
        if title and desc:
            _translation_ui(m, MARKETS, title, desc)


def _translation_ui(m, MARKETS, title: str, desc: str):
    st.markdown("**Markets:**")
    cols = st.columns(len(MARKETS))
    selected = {
        code: cols[i].checkbox(f"{code}  {lang}", value=True)
        for i, (code, lang) in enumerate(MARKETS.items())
    }
    targets = [c for c, checked in selected.items() if checked]

    if st.button("🌍 Translate", type="primary", disabled=not targets):
        with st.spinner(f"Translating into {len(targets)} market(s)..."):
            try:
                results = m["translate_to_markets"](title, desc, targets)

                for market, res in results.items():
                    with st.expander(f"{market} — {res['language']}", expanded=True):
                        st.markdown(f"**{res['title']}**")
                        st.text(res["description"])

                out_dir  = ROOT / "results" / "translations"
                out_dir.mkdir(parents=True, exist_ok=True)
                slug     = re.sub(r"[^a-z0-9]+", "-", title[:40].lower()).strip("-")
                out_path = out_dir / f"{slug}.json"
                out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
                st.success(f"Saved → `{out_path}`")
            except Exception as e:
                st.error(f"Translation failed: {e}")


# ── Page: Report ───────────────────────────────────────────────────────────────

def page_report():
    st.title("Report")

    results_dir = ROOT / "results"

    # Score distribution
    scores_path = results_dir / "scores.csv"
    if scores_path.exists():
        scores = pd.read_csv(scores_path)
        st.subheader("Score Distribution")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total deals",            f"{len(scores):,}")
        c2.metric("Rewrite recommended",    int(scores["rewrite_recommended"].sum()))
        c3.metric("Average score",          f"{scores['total_score'].mean():.0f} / 100")
        st.bar_chart(scores["total_score"].value_counts().sort_index())
    else:
        st.info("No scores yet. Run **Weekly Run** first.")

    # Evaluation summary
    rewrite_dir = results_dir / "rewrites"
    if not rewrite_dir or not rewrite_dir.exists():
        return

    eval_files = list(rewrite_dir.glob("*.eval.json"))
    if not eval_files:
        return

    st.divider()
    st.subheader("Evaluation Summary")

    rows = []
    for ef in eval_files:
        ev  = json.loads(ef.read_text())
        rw_path = ef.with_suffix("").with_suffix(".json")
        title = json.loads(rw_path.read_text()).get("original_title", ef.stem) if rw_path.exists() else ef.stem
        row = {
            "Deal":     title[:60],
            "Verdict":  ev["verdict"],
            "Decision": "Operator" if ev.get("operator_decision") else "Auto",
        }
        for sig in ev.get("signals", []):
            row[sig["signal"]] = "✅" if sig["passed"] else "❌"
        rows.append(row)

    report_df = pd.DataFrame(rows)
    total     = len(report_df)
    approved  = int((report_df["Verdict"] == "APPROVE").sum())
    flagged   = int((report_df["Verdict"] == "FLAG").sum())
    rejected  = int((report_df["Verdict"] == "REJECT").sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ Approved",      approved)
    c2.metric("⚠️ Flagged",       flagged)
    c3.metric("❌ Rejected",       rejected)
    c4.metric("Acceptance rate",  f"{approved / total * 100:.0f}%" if total else "—",
              help="Target: ≥ 75%. Below 60% for two weeks → audit prompts.")

    st.dataframe(report_df, use_container_width=True)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Content That Converts",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    for key in ("df", "validation", "data_source_label", "last_generated"):
        if key not in st.session_state:
            st.session_state[key] = None

    with st.sidebar:
        st.title("📈 Content That Converts")
        st.caption("Deal copy automation")
        st.divider()

        # Status
        df = st.session_state.get("df")
        if df is not None:
            st.success(f"🟢 {len(df):,} deals loaded")
        else:
            st.error("🔴 No data — go to Setup")

        if api_ready():
            st.success(f"🟢 API ready ({api_provider()})")
        else:
            st.warning("🟡 No API key")

        n_pending = pending_review_count()
        if n_pending:
            st.warning(f"⚠️ {n_pending} deal(s) need review")

        st.divider()

        page = st.radio(
            "nav",
            ["🗄️ Setup", "⚙️ Weekly Run", "📋 Review Queue",
             "✏️ New Deal", "🌍 Translations", "📊 Report"],
            label_visibility="collapsed",
        )

    pages = {
        "🗄️ Setup":        page_setup,
        "⚙️ Weekly Run":   page_weekly_run,
        "📋 Review Queue": page_review,
        "✏️ New Deal":     page_generator,
        "🌍 Translations": page_translations,
        "📊 Report":       page_report,
    }
    pages[page]()


if __name__ == "__main__":
    main()
