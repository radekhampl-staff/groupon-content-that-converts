"""
CSV / DataFrame validation for the Content That Converts pipeline.

Returns tiered capabilities based on which columns are present,
plus actionable error and warning messages.
"""

import pandas as pd

SCORING_COLUMNS = [
    "deal_id", "title", "description", "fine_print",
    "option_names", "image_quality_score",
]

REWRITE_COLUMNS = SCORING_COLUMNS + [
    "category", "subcategory", "geo", "merchant_name",
    "price", "value", "num_options",
]

PRIORITY_COLUMNS = REWRITE_COLUMNS + [
    "cvr",
] + [f"weekly_udvs_w{i}" for i in range(1, 9)]

# Numeric columns and their valid (min, max) ranges — None means unbounded
NUMERIC_RANGES = {
    "image_quality_score": (1, 5),
    "price":               (0, None),
    "value":               (0, None),
    "cvr":                 (0, 1),
}


class ValidationResult:
    def __init__(self):
        self.errors:       list[str] = []
        self.warnings:     list[str] = []
        self.capabilities: set[str]  = set()

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def validate_dataframe(df: pd.DataFrame) -> ValidationResult:
    vr = ValidationResult()

    if df is None or df.empty:
        vr.errors.append("The file contains no data rows.")
        return vr

    cols = set(df.columns.tolist())

    # ── Tier 1: scoring ───────────────────────────────────────────────────────
    missing_scoring = [c for c in SCORING_COLUMNS if c not in cols]
    if missing_scoring:
        vr.errors.append(
            f"Missing columns required for scoring: {', '.join(missing_scoring)}"
        )
        return vr

    vr.capabilities.add("score")

    # ── Tier 2: rewriting ─────────────────────────────────────────────────────
    missing_rewrite = [c for c in REWRITE_COLUMNS if c not in cols]
    if missing_rewrite:
        vr.warnings.append(
            f"Missing columns needed for rewriting ({', '.join(missing_rewrite)}). "
            "Only scoring will be available."
        )
    else:
        vr.capabilities.add("rewrite")

        # ── Tier 3: priority queue ────────────────────────────────────────────
        missing_priority = [c for c in PRIORITY_COLUMNS if c not in cols]
        if missing_priority:
            vr.warnings.append(
                f"Missing columns for priority ordering ({', '.join(missing_priority)}). "
                "Deals will be rewritten in score order, not by revenue impact."
            )
        else:
            vr.capabilities.add("priority")

    # ── Numeric validation ────────────────────────────────────────────────────
    for col, (min_val, max_val) in NUMERIC_RANGES.items():
        if col not in cols:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        n_invalid = int(series.isna().sum()) - int(df[col].isna().sum())
        if n_invalid > 0:
            vr.warnings.append(
                f"Column '{col}' has {n_invalid} non-numeric value(s). These rows will be skipped."
            )
        if min_val is not None and (series.dropna() < min_val).any():
            vr.warnings.append(f"Column '{col}' has values below {min_val}.")
        if max_val is not None and (series.dropna() > max_val).any():
            vr.warnings.append(f"Column '{col}' has values above {max_val}.")

    # ── Duplicate IDs ─────────────────────────────────────────────────────────
    if "deal_id" in cols:
        dupes = int(df["deal_id"].duplicated().sum())
        if dupes > 0:
            vr.warnings.append(
                f"{dupes} duplicate deal_id value(s) found. Only the first occurrence will be used."
            )

    # ── Empty critical text fields ────────────────────────────────────────────
    for col in ["title", "description"]:
        if col in cols:
            n_empty = int(df[col].isna().sum()) + int((df[col] == "").sum())
            if n_empty > 0:
                vr.warnings.append(f"{n_empty} row(s) have an empty '{col}' field.")

    return vr
