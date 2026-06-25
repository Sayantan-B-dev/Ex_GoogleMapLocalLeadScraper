# Google Maps Lead Scraper

Scrapes Google Maps for event/wedding businesses across Indian cities. Two independent methods.

## Data

- **432 P1 queries** (9 batches of 48) targeting cities like Mumbai, Delhi, Bangalore, etc.
- Queries: `Mumbai Event Management Company`, `Delhi Wedding Planner`, etc.
- Each query returns **~80–180 leads** → **~35k–78k total leads**
- Columns: name, phone, email, website, address, rating, reviews, category, city, state, maps_url

---

## Method 1: Playwright (Python)

**Location:** `method1/`

Custom Python script using Playwright to control a real browser.

### Run

```bash
cd method1

# Single batch
python scraper.py --input p1_batch_1.txt --output output/p1_batch_1.csv

# All batches (5 parallel browsers)
python run_all.py --phase 1
```

### Features
| Feature | Details |
|---------|---------|
| Results/query | **60–180** (aggressive scrolling) |
| Email extraction | ✅ From business websites |
| Resume | ✅ `.done` file tracks completed queries |
| Profiles | ✅ Persistent Chrome profiles per batch |
| Columns | `search_query, name, category, rating, reviews, address, phone, website, email, city, state, maps_url` |
| Speed | ~2–4 min/query |

### Pros & Cons

| Pros | Cons |
|------|------|
| High results per query | Slower (real browser) |
| Clean consistent schema | Requires Python + Playwright |
| Per-query resume (granular) | Resource heavy (~1GB RAM per browser) |
| No Docker needed | 5 parallel browsers = ~5GB RAM |

### Merge

```bash
python merge.py --pattern "output/p*_batch_*.csv" --output final.csv
```

---

## Method 3: Email Extractor (requests + Rich TUI)

**Location:** `taskFetchEmail/`

Lightweight email extraction from already-scraped lead CSVs. Fetches each business's homepage, extracts emails via regex + Cloudflare decoding, optionally shallow-crawls internal pages.

### Run

```bash
cd taskFetchEmail
python scraper_v1.py              # all 3 files, shallow crawl
python scraper_v1.py --fast       # homepage only
python scraper_v1.py --resume     # resume partial output
```

### Features

| Feature | Detail |
|---------|--------|
| Concurrency | 10 threads, network-bound |
| Engine | `requests` + `BeautifulSoup` (no browser) |
| Email extraction | Regex + Cloudflare email protection decode |
| Shallow crawl | Follows 3 internal links if homepage has no email |
| TUI | Live progress bar, counts, activity log via `rich` |
| Resume | `--resume` flag picks up from partial output |
| Status column | `website_status`: ok / dns_error / ssl_error / status_XXX |

### Input/Output

| Phase | Input | Output | Websites to scan |
|-------|-------|--------|:----------------:|
| P1 | `p1_final.csv` | `p1_full.csv` | 5,357 |
| P2 | `p2_final.csv` | `p2_full.csv` | 1,617 |
| P3 | `p3_final.csv` | `p3_full.csv` | 8,126 |

---

## Method 2: gosom Docker (Go)

**Location:** `method2/`

Uses [gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper) — a fast Go tool in Docker.

### Run

```bash
cd method2
./run.sh
```

Or on Windows:
```cmd
cmd //c run.bat
# or
powershell -ExecutionPolicy Bypass -File run.ps1
```

### Features
| Feature | Details |
|---------|---------|
| Results/query | **~80–180** (depth 20) |
| Email extraction | ✅ `-email` flag crawls business websites |
| Resume | ✅ Skips batch if CSV has data rows |
| Concurrency | `-c 4` (4 parallel queries) |
| Columns | **33+ fields** — title, phone, website, emails, address, rating, reviews, hours, popular times, coordinates, place_id, images, reviews_with_text, etc. |
| Speed | ~5–8 min/query (depth 20 + email) |
| Live progress | ✓ Query name + lead count shown in terminal |

### Pros & Cons

| Pros | Cons |
|------|------|
| Fast Go binary in Docker | Heavy (needs Docker) |
| 33+ fields per lead | Batch-level resume only |
| Parallel queries (-c 4) | ~9–14h runtime for all 432 |
| Clean per-query terminal output | Some queries get fewer results in sparse areas |

### Output Schema (33+ fields)

Key columns: `title, phone, website, emails, address, category, review_count, review_rating, latitude, longitude, place_id, plus_code, price_range, open_hours, popular_times, about, street_view_url, images, reviews_link, user_reviews, user_reviews_extended, complete_address, credit_cards_accepted, reservations, order_online, menu, owner, timezone, cid, status, descriptions, thumbnail, data_id, input_id, link`

### Directory Notes

| Path | Auto-created | By |
|------|:-----------:|---|
| `output/` | ✅ | `run.sh` (`mkdir -p`) |
| `logs/` | ✅ | `run.sh` (`mkdir -p`) |
| `batches/` | ❌ | Place batch files manually |
| `old/` | ❌ | Create manually if needed |

### Merge

```bash
python merge.py --pattern "output/batch_*.csv" --output final.csv
```

---

## Comparison

| | Method 1 (Playwright) | Method 2 (gosom Docker) | Method 3 (Email Extractor) |
|---|---|---|---|
| Engine | Python + Playwright | Go + Docker | Python + requests |
| Purpose | Full scrape | Full scrape | Email enrichment |
| Fields/lead | 11 | 33+ | Adds emails to existing CSVs |
| Concurrency | 5 browsers | 4 queries | 10 threads |
| Setup | Python + Playwright | Docker | Python + requests |
| RAM | ~5GB | ~500MB | ~200MB |

## Directory Structure

```
scraping_info/
├── README.md
├── DEPLOY.md            # Cloud deployment guide (Oracle, Colab, VPS)
├── AGENTS.md            # Full project state
├── method1/             # Playwright (Python) — custom scraper
│   ├── scraper.py
│   ├── run_all.py
│   ├── merge.py
│   ├── view.html + details.html
│   └── priority_{1,2,3}_queries.txt
├── method2/             # gosom Docker (Go) — primary scraper
│   ├── run.sh / run.bat / run.ps1
│   ├── merge.py
│   ├── view.html
│   ├── queries.txt
│   └── batches/
└── taskFetchEmail/      # Method 3 — email enrichment
    ├── README.md
    ├── scraper_v1.py
    ├── p1_final.csv → p1_full.csv (+ p1_full.log)
    ├── p2_final.csv → p2_full.csv (+ p2_full.log)
    └── p3_final.csv → p3_full.csv (+ p3_full.log)
```

## Quick Start

```bash
# Method 2 — recommended for first run
cd method2 && ./run.sh

# After it finishes, merge results
python merge.py --pattern "output/batch_*.csv" --output final.csv

# Extract emails from the merged leads
cd ../taskFetchEmail && python scraper_v1.py
```

View the CSV by opening `method2/view.html` or `method1/view.html` in a browser and dragging the file in.

## Acknowledgments

- **[gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper)** — MIT-licensed Go tool used in Method 2. Massive thanks to [gosom](https://github.com/gosom) and contributors for building and maintaining this excellent scraper. ⭐ the repo if you find it useful!
