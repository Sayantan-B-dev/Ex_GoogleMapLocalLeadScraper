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

| | Method 1 (Playwright) | Method 2 (gosom Docker) |
|---|---|---|
| Engine | Python + Playwright | Go + Docker |
| Results/query | 60–180 | ~80–180 |
| Fields/lead | 11 | 33+ |
| Speed | 2–4 min/query | 5–8 min/query |
| Concurrency | 5 parallel browsers | 4 parallel queries |
| Total time (432 queries) | ~7–14h | ~9–14h |
| Resume granularity | Per-query (`.done`) | Per-batch (CSV check) |
| Setup complexity | Python + Playwright install | Docker only |
| RAM usage | ~1GB/browser (5 = 5GB) | ~500MB total |

## Directory Structure

```
scraping_info/
├── README.md
├── DEPLOY.md          # Cloud deployment guide (Oracle, Colab, VPS)
├── AGENTS.md          # Full project state
├── method1/
│   ├── scraper.py     # Playwright scraper
│   ├── run_all.py     # Parallel orchestrator
│   ├── merge.py       # Merge + dedup + quality report
│   ├── view.html      # CSV + live progress viewer
│   ├── details.html   # Quick batch viewer
│   ├── priority_1_queries.txt  # All P1 queries (432)
│   ├── p1_batch_1..5.txt       # P1 batch files
│   ├── p2_batch_1..5.txt       # P2 batch files
│   ├── p3_batch_1..5.txt       # P3 batch files
│   └── google_maps_leads.csv   # Legacy export (do not modify)
└── method2/
    ├── run.sh          # Main runner (bash)
    ├── run.bat         # CMD runner
    ├── run.ps1         # PowerShell runner
    ├── merge.py        # Merge + dedup for gosom schema
    ├── queries.txt     # All P1 queries (432)
    └── batches/        # 9 batch files (48 queries each)
        ├── batch_00.txt
        └── ...
```

## Quick Start

```bash
# Method 2 — recommended for first run
cd method2 && ./run.sh

# After it finishes, merge results
python merge.py --pattern "output/batch_*.csv" --output final.csv
```

View the CSV by opening `method1/view.html` in a browser and dragging the file in.

## Acknowledgments

- **[gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper)** — MIT-licensed Go tool used in Method 2. Massive thanks to [gosom](https://github.com/gosom) and contributors for building and maintaining this excellent scraper. ⭐ the repo if you find it useful!
