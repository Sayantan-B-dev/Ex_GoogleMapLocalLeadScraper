# Email Enrichment Analytics — full/ Directory

Complete analysis of `full/` CSVs (post `scraper_v1.py` email enrichment, 37 cols). Adds `website_status` + `emails` columns on top of method2 raw scrape data.

---

## Executive Summary

| Metric | Total | Rate |
|--------|-------|------|
| **Total rows** | 24,391 | 100% |
| **Has website** | 15,100 | 61.9% |
| **No website** | 9,291 | 38.1% |
| **Has phone** | 19,875 | 81.5% |
| **No phone** | 4,516 | 18.5% |
| **Has email** | 7,846 | 32.2% |
| **No email** | 16,545 | 67.8% |
| **All three (web+phone+email)** | 7,294 | 29.9% |

---

## Per-File Coverage

### p1_full.csv (8,082 rows)

| Metric | Count | % |
|--------|-------|---|
| Has website | 5,357 | 66.3% |
| No website | 2,725 | 33.7% |
| Has phone | 7,183 | 88.9% |
| No phone | 899 | 11.1% |
| Has email | 2,608 | 32.3% |
| No email | 5,474 | 67.7% |

### p2_full.csv (2,745 rows)

| Metric | Count | % |
|--------|-------|---|
| Has website | 1,617 | 58.9% |
| No website | 1,128 | 41.1% |
| Has phone | 2,274 | 82.8% |
| No phone | 471 | 17.2% |
| Has email | 1,005 | 36.6% |
| No email | 1,740 | 63.4% |

### p3_full.csv (13,564 rows)

| Metric | Count | % |
|--------|-------|---|
| Has website | 8,126 | 59.9% |
| No website | 5,438 | 40.1% |
| Has phone | 10,418 | 76.8% |
| No phone | 3,146 | 23.2% |
| Has email | 4,233 | 31.2% |
| No email | 9,331 | 68.8% |

---

## Intersection Analysis

### p1_full.csv

| Intersection | Count | % |
|-------------|-------|---|
| No website + no phone | 508 | 6.3% |
| No website + has phone | 2,217 | 27.4% |
| Has website + no phone | 391 | 4.8% |
| No website + has email | 0 | 0% |
| Has website + no email | 2,749 | 34.0% |
| Has website + has email | 2,608 | 32.3% |
| No email + no phone | 760 | 9.4% |
| **All three (web+phone+email)** | **2,469** | **30.6%** |

### p2_full.csv

| Intersection | Count | % |
|-------------|-------|---|
| No website + no phone | 381 | 13.9% |
| No website + has phone | 747 | 27.2% |
| Has website + no phone | 90 | 3.3% |
| No website + has email | 0 | 0% |
| Has website + no email | 612 | 22.3% |
| Has website + has email | 1,005 | 36.6% |
| No email + no phone | 419 | 15.3% |
| **All three (web+phone+email)** | **953** | **34.7%** |

### p3_full.csv

| Intersection | Count | % |
|-------------|-------|---|
| No website + no phone | 2,329 | 17.2% |
| No website + has phone | 3,109 | 22.9% |
| Has website + no phone | 817 | 6.0% |
| No website + has email | 0 | 0% |
| Has website + no email | 3,893 | 28.7% |
| Has website + has email | 4,233 | 31.2% |
| No email + no phone | 2,785 | 20.5% |
| **All three (web+phone+email)** | **3,872** | **28.6%** |

---

## Categorical Breakdown

### p1_full.csv

| Category | Count | % |
|----------|-------|---|
| (a) No website | 2,725 | 33.7% |
| (b) Website only | 252 | 3.1% |
| (c) Website + phone | 2,497 | 30.9% |
| (d) Website + email | 139 | 1.7% |
| (e) All three (web+phone+email) | **2,469** | **30.6%** |
| (f) Phone only | 2,217 | 27.4% |
| (g) Email only | 0 | 0% |
| (h) Phone + email (no web) | 0 | 0% |

### p2_full.csv

| Category | Count | % |
|----------|-------|---|
| (a) No website | 1,128 | 41.1% |
| (b) Website only | 38 | 1.4% |
| (c) Website + phone | 574 | 20.9% |
| (d) Website + email | 52 | 1.9% |
| (e) All three (web+phone+email) | **953** | **34.7%** |
| (f) Phone only | 747 | 27.2% |
| (g) Email only | 0 | 0% |
| (h) Phone + email (no web) | 0 | 0% |

### p3_full.csv

| Category | Count | % |
|----------|-------|---|
| (a) No website | 5,438 | 40.1% |
| (b) Website only | 456 | 3.4% |
| (c) Website + phone | 3,437 | 25.3% |
| (d) Website + email | 361 | 2.7% |
| (e) All three (web+phone+email) | **3,872** | **28.6%** |
| (f) Phone only | 3,109 | 22.9% |
| (g) Email only | 0 | 0% |
| (h) Phone + email (no web) | 0 | 0% |

---

## All Files Summary

| File | Total | Has Web | No Web | Has Phone | Has Email | All 3 |
|------|-------|---------|--------|-----------|-----------|-------|
| p1_full.csv | 8,082 | 5,357 | 2,725 | 7,183 | 2,608 | 2,469 |
| p2_full.csv | 2,745 | 1,617 | 1,128 | 2,274 | 1,005 | 953 |
| p3_full.csv | 13,564 | 8,126 | 5,438 | 10,418 | 4,233 | 3,872 |
| **TOTAL** | **24,391** | **15,100** | **9,291** | **19,875** | **7,846** | **7,294** |

---

## Row Type Summary (Combined)

| Category | Count | % of Total |
|----------|-------|-----------|
| (a) No website | 9,291 | 38.1% |
| (b) Website only | 746 | 3.1% |
| (c) Website + phone | 6,508 | 26.7% |
| (d) Website + email | 552 | 2.3% |
| (e) All three (web+phone+email) | **7,294** | **29.9%** |
| (f) Phone only | 6,073 | 24.9% |
| (g) Email only | 0 | 0% |
| (h) Phone + email (no web) | 0 | 0% |

---

## Email Enrichment Performance

| File | Rows | Websites Scraped | Emails Found | Email Rate |
|------|------|-----------------|-------------|-----------|
| p1_full | 8,082 | 5,357 | 2,608 | 32.3% (48.7% of sites) |
| p2_full | 2,745 | 1,617 | 1,005 | 36.6% (62.2% of sites) |
| p3_full | 13,564 | 8,126 | 4,233 | 31.2% (52.1% of sites) |
| **Total** | **24,391** | **15,100** | **7,846** | **32.2% (52.0% of sites)** |

- **52.0% of websites yielded at least one email** (7,846 emails from 15,100 sites).
- P2 had the best hit rate (62.2% of sites), P3 the lowest (52.1%).

---

## Columns (37 total)

```
input_id, link, title, category, address,
open_hours, popular_times, website, website_status, phone,
plus_code, review_count, review_rating, reviews_per_rating, latitude,
longitude, cid, status, descriptions, reviews_link,
thumbnail, timezone, price_range, data_id, street_view_url,
place_id, images, reservations, order_online, menu,
owner, complete_address, credit_cards_accepted, about, user_reviews,
user_reviews_extended, emails
```

**Key columns added by scraper_v1.py**:
- `website_status` — reachable / unreachable / redirect status of each website
- `emails` — extracted email addresses (semicolon-separated if multiple)

---

## Key Insights

1. **32.2% of all leads (7,846 out of 24,391) have at least one email** — strong enrichment from the raw scrape which only had 5.5%.
2. **52% of websites successfully yielded emails** — scraper_v1.py found emails on over half of all crawled sites.
3. **No emails were ever found without a website** — categories (g) and (h) are 0 across all files; email discovery is entirely dependent on having a URL.
4. **29.9% of all leads have the complete trifecta (web + phone + email)** — 7,294 high-value leads ready for outreach.
5. **Phone coverage is strong across all phases (76.8%–88.9%)** — most businesses have a phone number even without a website.
6. **~38% of leads have no website at all** — these 9,291 rows are unreachable for email enrichment and will never yield emails via this method.
