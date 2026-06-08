"""
Verification pass — sanity-check the main findings for confounders.
"""

import pandas as pd
import numpy as np
import re
import warnings
warnings.filterwarnings('ignore')

df = pd.read_csv('../data/deals.csv')

TEMPLATES = {
    'structured': r'What We Offer:|What Is Included:|What\'s Included:',
    'during_procedure': r'During the procedure',
    'retail_ships': r"What's Included: Product ships",
    'specific_other': None,
}
GENERIC_PATTERNS = [
    r'Experience the best that .+ has to offer',
    r'An opportunity to enjoy premium service',
    r"This is a deal you won't want to miss",
    r'Highly rated by Groupon customers',
    r'Save on this top-rated experience',
    r'Treat yourself or someone special',
    r'A great way to try something new',
    r'Looking for something special\? This deal',
]

def classify(desc):
    for name, pat in TEMPLATES.items():
        if name == 'specific_other': continue
        if pat and re.search(pat, str(desc), re.IGNORECASE):
            return 'structured'
    for pat in GENERIC_PATTERNS:
        if re.search(pat, str(desc), re.IGNORECASE):
            return 'generic'
    return 'structured'  # unmatched = treat as structured

df['desc_type'] = df['description'].apply(classify)

GENERIC_TITLE = [
    r'^Amazing .+? at .+', r'^Best .+? at .+', r'^Incredible .+? at .+',
    r'^Fantastic .+? at .+', r'^Must-Have Items', r'^Shop Smart',
    r'^Top Picks', r'^Wonderful .+? at .+', r'Experience at .+',
]
df['title_generic'] = df['title'].apply(
    lambda t: any(re.search(p, str(t), re.IGNORECASE) for p in GENERIC_TITLE)
)

# ── CHECK 1: Does structured description lift hold in EVERY category? ──────────
print("=" * 65)
print("CHECK 1 — Structured vs Generic CVR lift by category")
print("=" * 65)
results = []
for cat in sorted(df['category'].unique()):
    sub = df[df['category'] == cat]
    s = sub[sub.desc_type == 'structured']['cvr']
    g = sub[sub.desc_type == 'generic']['cvr']
    if len(s) >= 3 and len(g) >= 3:
        lift = (s.mean() / g.mean() - 1) * 100
        results.append({'category': cat, 'structured_cvr': s.mean(),
                        'generic_cvr': g.mean(), 'lift_pct': lift,
                        'n_structured': len(s), 'n_generic': len(g)})

res = pd.DataFrame(results).sort_values('lift_pct', ascending=False)
res['structured_cvr'] = res['structured_cvr'].round(5)
res['generic_cvr'] = res['generic_cvr'].round(5)
res['lift_pct'] = res['lift_pct'].round(1)
print(res.to_string(index=False))

# ── CHECK 2: Is image quality confounded by category? ─────────────────────────
print("\n" + "=" * 65)
print("CHECK 2 — Image quality distribution by category")
print("(check if high-image cats are also high-CVR cats)")
print("=" * 65)
img_cat = df.groupby('category').agg(
    avg_image=('image_quality_score', 'mean'),
    avg_cvr=('cvr', 'mean')
).round(3).sort_values('avg_cvr', ascending=False)
print(img_cat.to_string())

# Within-category image quality correlation
print("\n  Within-category image→CVR correlation:")
for cat in sorted(df['category'].unique()):
    sub = df[df['category'] == cat]
    r = sub['image_quality_score'].corr(sub['cvr'])
    print(f"    {cat:<20} r={r:.3f}  (n={len(sub)})")

# ── CHECK 3: Does title quality lift hold when controlling for desc type? ──────
print("\n" + "=" * 65)
print("CHECK 3 — Title lift controlling for description type")
print("=" * 65)
for dtype in ['structured', 'generic']:
    sub = df[df.desc_type == dtype]
    spec = sub[~sub.title_generic]['cvr'].mean()
    gen  = sub[sub.title_generic]['cvr'].mean()
    lift = (spec / gen - 1) * 100 if gen > 0 else 0
    print(f"  desc={dtype}: specific_title={spec:.5f}  generic_title={gen:.5f}  lift={lift:+.1f}%")

# ── CHECK 4: CVR outliers — are top performers just high-image-quality deals? ──
print("\n" + "=" * 65)
print("CHECK 4 — Top 20 CVR deals: what makes them tick?")
print("=" * 65)
top = df.nlargest(20, 'cvr')[['title', 'cvr', 'image_quality_score',
                               'desc_type', 'title_generic', 'category', 'price']].copy()
top['cvr'] = top['cvr'].round(4)
print(top.to_string(index=False))

print("\n  Top-20 image quality distribution:")
print(top['image_quality_score'].value_counts().sort_index().to_string())
print(f"\n  Top-20 desc_type='structured': {(top.desc_type=='structured').sum()}/20")
print(f"  Top-20 title_generic=False:    {(~top.title_generic).sum()}/20")

# ── CHECK 5: Data quality ──────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("CHECK 5 — Data quality")
print("=" * 65)
print(f"  Nulls per column: {df.isnull().sum()[df.isnull().sum()>0].to_dict()}")
print(f"  CVR range: {df.cvr.min():.5f} – {df.cvr.max():.5f}")
print(f"  Duplicate deal_ids: {df.deal_id.duplicated().sum()}")
print(f"  Deals with 0 orders across all 8 weeks: {(df[[f'weekly_orders_w{i}' for i in range(1,9)]].sum(axis=1)==0).sum()}")

# ── CHECK 6: Is structured copy concentrated in one geo? ──────────────────────
print("\n" + "=" * 65)
print("CHECK 6 — Structured vs Generic split across geos")
print("(ensure it's not a London/NY effect)")
print("=" * 65)
geo_split = df.groupby(['geo', 'desc_type'])['cvr'].mean().unstack('desc_type')
geo_split = geo_split.dropna()
geo_split['lift_pct'] = ((geo_split['structured'] / geo_split['generic']) - 1) * 100
print(geo_split.round(4).sort_values('lift_pct', ascending=False).to_string())

print("\n✓ Verification complete.")
