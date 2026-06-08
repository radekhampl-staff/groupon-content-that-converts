# Data Dictionary — deals.csv

| Field | Type | Description |
|---|---|---|
| `deal_id` | string (UUID) | Unique identifier for each deal |
| `category` | string | Primary category (8 categories: Beauty, Health & Fitness, Food & Drink, Things to Do, Travel, Home Services, Auto, Retail) |
| `subcategory` | string | Subcategory within the primary category |
| `geo` | string | City where the deal is available |
| `title` | string | Deal headline shown to customers |
| `description` | string | Body copy describing the deal (2-4 sentences) |
| `fine_print` | string | Redemption rules and restrictions, semicolon-separated |
| `num_options` | integer | Number of pricing options available (1-4) |
| `option_names` | string | Comma-separated names of each pricing option |
| `price` | integer | Selling price in local currency |
| `value` | integer | Original value before discount |
| `discount_pct` | float | Discount percentage (derived: 1 - price/value) |
| `merchant_name` | string | Name of the merchant offering the deal |
| `image_quality_score` | integer | Image quality rating (1-5) |
| `days_live` | integer | Number of days the deal has been active |
| `weekly_udvs_w1` - `w8` | integer | Unique deal views per week (w1 = most recent) |
| `weekly_orders_w1` - `w8` | integer | Number of orders placed, per week |
| `cvr` | float | Conversion rate: total orders / total unique deal views over 8 weeks |
| `aov` | float | Average order value over the measurement period |
| `refund_rate` | float | Percentage of orders that were refunded |
