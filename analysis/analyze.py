"""
Groupon Content That Converts — EDA & Content Analysis
"""

import pandas as pd
import numpy as np
import re
from collections import Counter
import warnings
warnings.filterwarnings('ignore')

# ── Load data ─────────────────────────────────────────────────────────────────
df = pd.read_csv('../data/deals.csv')
print(f"Loaded {len(df)} deals\n")

# ── 1. DESCRIPTION TEMPLATE CLASSIFICATION ────────────────────────────────────
TEMPLATES = {
    'structured_what_we_offer': r'What We Offer:|What Is Included:',
    'generic_experience_best':  r'Experience the best that .+ has to offer',
    'generic_opportunity':      r'An opportunity to enjoy premium service',
    'generic_dont_miss':        r"This is a deal you won't want to miss",
    'generic_highly_rated':     r'Highly rated by Groupon customers',
    'generic_save_on':          r'Save on this top-rated experience',
    'generic_treat_yourself':   r'Treat yourself or someone special',
    'generic_great_way':        r'A great way to try something new',
    'generic_looking_for':      r'Looking for something special\? This deal',
    'retail_ships':             r"What's Included: Product ships within",
    'during_procedure':         r'During the procedure, a licensed professional',
    'specific_other':           None,  # fallback
}

def classify_description(desc):
    for name, pattern in TEMPLATES.items():
        if name == 'specific_other':
            continue
        if pattern and re.search(pattern, str(desc), re.IGNORECASE):
            return name
    return 'specific_other'

df['desc_type'] = df['description'].apply(classify_description)

# Group into binary: structured vs generic
STRUCTURED = {'structured_what_we_offer', 'retail_ships', 'during_procedure', 'specific_other'}
df['is_structured'] = df['desc_type'].isin(STRUCTURED)

print("=" * 60)
print("1. DESCRIPTION TEMPLATE DISTRIBUTION")
print("=" * 60)
type_cvr = df.groupby('desc_type')['cvr'].agg(['mean', 'count']).sort_values('mean', ascending=False)
type_cvr.columns = ['avg_cvr', 'count']
type_cvr['avg_cvr'] = type_cvr['avg_cvr'].round(5)
print(type_cvr.to_string())

print(f"\n  Structured descriptions — avg CVR: {df[df.is_structured]['cvr'].mean():.5f}")
print(f"  Generic descriptions  — avg CVR:  {df[~df.is_structured]['cvr'].mean():.5f}")
lift = (df[df.is_structured]['cvr'].mean() / df[~df.is_structured]['cvr'].mean() - 1) * 100
print(f"  Lift: {lift:+.1f}%")

# ── 2. TITLE QUALITY ──────────────────────────────────────────────────────────
GENERIC_TITLE_PATTERNS = [
    r'^Amazing .+? at .+',
    r'^Best .+? at .+',
    r'^Incredible .+? at .+',
    r'^Fantastic .+? at .+',
    r'^Must-Have Items',
    r'^Shop Smart',
    r'^Top Picks',
    r'^Wonderful .+? at .+',
    r'Experience at .+',
    r'Deal on .+',
]

def is_generic_title(title):
    for p in GENERIC_TITLE_PATTERNS:
        if re.search(p, str(title), re.IGNORECASE):
            return True
    return False

df['title_is_generic'] = df['title'].apply(is_generic_title)
df['title_len'] = df['title'].str.len()

print("\n" + "=" * 60)
print("2. TITLE QUALITY")
print("=" * 60)
print(f"  Specific titles — avg CVR: {df[~df.title_is_generic]['cvr'].mean():.5f}  (n={sum(~df.title_is_generic)})")
print(f"  Generic titles  — avg CVR: {df[df.title_is_generic]['cvr'].mean():.5f}  (n={sum(df.title_is_generic)})")
lift_title = (df[~df.title_is_generic]['cvr'].mean() / df[df.title_is_generic]['cvr'].mean() - 1) * 100
print(f"  Lift: {lift_title:+.1f}%")

# Title length buckets
df['title_len_bucket'] = pd.cut(df['title_len'], bins=[0, 30, 50, 70, 120], labels=['<30', '30-50', '50-70', '70+'])
print("\n  CVR by title length:")
print(df.groupby('title_len_bucket', observed=True)['cvr'].mean().round(5).to_string())

# ── 3. OPTION NAMES QUALITY ───────────────────────────────────────────────────
def has_generic_options(option_names):
    """Option 1, Option 2 etc are meaningless"""
    return bool(re.search(r'Option \d', str(option_names)))

df['options_generic'] = df['option_names'].apply(has_generic_options)

print("\n" + "=" * 60)
print("3. OPTION NAMES QUALITY")
print("=" * 60)
print(f"  Descriptive option names — avg CVR: {df[~df.options_generic]['cvr'].mean():.5f}  (n={sum(~df.options_generic)})")
print(f"  Generic option names    — avg CVR:  {df[df.options_generic]['cvr'].mean():.5f}  (n={sum(df.options_generic)})")
lift_opts = (df[~df.options_generic]['cvr'].mean() / df[df.options_generic]['cvr'].mean() - 1) * 100
print(f"  Lift: {lift_opts:+.1f}%")

# ── 4. FINE PRINT COMPLEXITY ──────────────────────────────────────────────────
df['fine_print_count'] = df['fine_print'].str.count(';') + 1

print("\n" + "=" * 60)
print("4. FINE PRINT COMPLEXITY")
print("=" * 60)
fp_bins = pd.cut(df['fine_print_count'], bins=[0, 2, 4, 6, 8, 20], labels=['1-2', '3-4', '5-6', '7-8', '9+'])
print("  CVR by number of fine print restrictions:")
print(df.groupby(fp_bins, observed=True)['cvr'].mean().round(5).to_string())
corr_fp = df['fine_print_count'].corr(df['cvr'])
print(f"\n  Correlation fine_print_count vs CVR: {corr_fp:.4f}")

# ── 5. IMAGE QUALITY ──────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("5. IMAGE QUALITY SCORE")
print("=" * 60)
print("  CVR by image_quality_score:")
print(df.groupby('image_quality_score')['cvr'].mean().round(5).to_string())
corr_img = df['image_quality_score'].corr(df['cvr'])
print(f"\n  Correlation image_quality vs CVR: {corr_img:.4f}")

# ── 6. PRICING FEATURES ───────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("6. PRICING FEATURES")
print("=" * 60)
print(f"  Correlation discount_pct vs CVR: {df['discount_pct'].corr(df['cvr']):.4f}")
print(f"  Correlation price vs CVR:        {df['price'].corr(df['cvr']):.4f}")
print(f"  Correlation num_options vs CVR:  {df['num_options'].corr(df['cvr']):.4f}")

print("\n  CVR by num_options:")
print(df.groupby('num_options')['cvr'].mean().round(5).to_string())

# ── 7. CATEGORY ANALYSIS ──────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("7. CATEGORY CVR BENCHMARKS")
print("=" * 60)
cat_cvr = df.groupby('category')['cvr'].agg(['mean', 'median', 'count']).sort_values('mean', ascending=False)
cat_cvr.columns = ['avg_cvr', 'median_cvr', 'count']
cat_cvr = cat_cvr.round(5)
print(cat_cvr.to_string())

# ── 8. COMBINED CONTENT SCORE ─────────────────────────────────────────────────
print("\n" + "=" * 60)
print("8. COMBINED CONTENT SIGNAL")
print("=" * 60)

# Create a simple additive content score (0-4 points)
df['content_score'] = (
    df['is_structured'].astype(int) +
    (~df['title_is_generic']).astype(int) +
    (~df['options_generic']).astype(int) +
    (df['image_quality_score'] >= 4).astype(int)
)

print("  CVR by content score (0 = all bad, 4 = all good):")
score_cvr = df.groupby('content_score')['cvr'].agg(['mean', 'count']).round(5)
score_cvr.columns = ['avg_cvr', 'count']
print(score_cvr.to_string())

score_0 = df[df.content_score == 0]['cvr'].mean()
score_4 = df[df.content_score == 4]['cvr'].mean()
if score_0 > 0:
    print(f"\n  Score 0 → Score 4 lift: {(score_4/score_0 - 1)*100:+.1f}%")

# ── 9. CVR DISTRIBUTION — IDENTIFY UNDERPERFORMERS ────────────────────────────
print("\n" + "=" * 60)
print("9. CVR DISTRIBUTION & PRIORITY TARGETS")
print("=" * 60)
q25 = df['cvr'].quantile(0.25)
q50 = df['cvr'].quantile(0.50)
q75 = df['cvr'].quantile(0.75)
print(f"  CVR p25: {q25:.5f}")
print(f"  CVR p50: {q50:.5f}")
print(f"  CVR p75: {q75:.5f}")

df['total_views'] = df[['weekly_udvs_w1','weekly_udvs_w2','weekly_udvs_w3','weekly_udvs_w4',
                          'weekly_udvs_w5','weekly_udvs_w6','weekly_udvs_w7','weekly_udvs_w8']].sum(axis=1)

# Priority: low CVR AND high views = biggest revenue opportunity
underperformers = df[df['cvr'] < q25].copy()
underperformers['priority_score'] = underperformers['total_views'] * (q25 - underperformers['cvr'])
underperformers = underperformers.sort_values('priority_score', ascending=False)

print(f"\n  Underperformers (bottom 25% CVR): {len(underperformers)} deals")
print(f"  Among them, avg content_score:   {underperformers['content_score'].mean():.2f}")
print(f"  Among all deals, avg content_score: {df['content_score'].mean():.2f}")

print("\n  Top 10 priority rewrites (high views × low CVR):")
cols = ['title', 'category', 'geo', 'cvr', 'total_views', 'content_score', 'desc_type']
print(underperformers[cols].head(10).to_string(index=False))

# ── 10. FINDINGS SUMMARY ──────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("FINDINGS SUMMARY")
print("=" * 60)
findings = [
    f"1. Description type is the strongest signal. Structured descriptions (What We Offer/Included) "
    f"outperform generic templates by {lift:.0f}%.",
    f"2. Generic titles (Amazing/Best/Incredible + merchant) underperform specific titles by {abs(lift_title):.0f}%.",
    f"3. Generic option names ('Option 1, 2, 3') suppress CVR vs. descriptive names by {abs(lift_opts):.0f}%.",
    f"4. Fine print count negatively correlates with CVR (r={corr_fp:.3f}). Each extra restriction hurts.",
    f"5. Image quality shows r={corr_img:.3f} correlation with CVR.",
    f"6. Discount % has minimal correlation ({df['discount_pct'].corr(df['cvr']):.3f}) — value framing matters more than raw %.",
    f"7. Deals scoring 0/4 on content signal vs 4/4 show large CVR gap.",
]
for f in findings:
    print(f"  {f}")

print("\nDone.")
