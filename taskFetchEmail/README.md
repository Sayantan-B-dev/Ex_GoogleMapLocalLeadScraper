# Email Extractor — Method 3

Scrapes business websites from existing lead CSVs to extract email addresses.

**Location:** `taskFetchEmail/`

## Overview

Takes the `p{1,2,3}_final.csv` files (from method2), fetches each business's homepage, and extracts emails using regex + Cloudflare email protection decoding. Falls back to shallow crawling (contact/about pages) when the homepage has no email.

## Quick Start

```bash
cd taskFetchEmail

# Process all 3 files (default: shallow crawl, 15 threads)
python scraper_v1.py

# Process a single file (by CSV path)
python scraper_v1.py final/p3_final.csv

# Resume a partial run (skips rows with existing website_status)
python scraper_v1.py --resume

# Resume a specific file
python scraper_v1.py --resume final/p3_final.csv

# Homepage only (faster, skips shallow crawl)
python scraper_v1.py --fast

# Re-scan all rows without email (ignores website_status)
python scraper_v1.py --all

# Analyze input CSV stats (websites, phones, emails)
python analyze_final.py
```

## Input / Output

Input CSVs live in `final/`, output goes to `full/`, logs to `log/`.
All three folders are gitignored — generated data is never committed.

| File | Location | Rows | With Website | With Email |
|------|----------|-----:|:-----------:|:----------:|
| `p1_final.csv` | `final/` | 8,082 | 5,357 | 0 |
| `p2_final.csv` | `final/` | 2,745 | 1,617 | 0 |
| `p3_final.csv` | `final/` | 13,564 | 8,126 | 0 |
| **Total** | | **24,391** | **15,100** | **0** |
| `p1_full.csv` | `full/` | Output with `website_status` + `emails` columns |
| `p2_full.csv` | `full/` | ↑ |
| `p3_full.csv` | `full/` | ↑ |
| `p1_full.log` | `log/` | Per-URL log with found emails and errors |
| `p2_full.log` | `log/` | ↑ |
| `p3_full.log` | `log/` | ↑ |

> Note: `emails` column exists but is empty in input CSVs (`final/`). Scraper fills it into `full/` output.
> Run `python analyze_final.py` for comprehensive breakdown (website/phone/email intersections).

### website_status values

| Status | Meaning |
|--------|---------|
| `ok` | Email found (homepage or shallow crawl) |
| `ok_no_email` | Page loaded, no email found |
| `dns_error` | DNS resolution failed |
| `ssl_error` | SSL certificate problem |
| `timeout` | Connection/read timed out |
| `status_XXX` | HTTP error (e.g. 404, 403) |
| `error` | Generic connection error |

Empty status for rows without a website.

## Features

| Feature | Detail |
|---------|--------|
| Concurrency | 15 threads (adjustable via `THREADS` constant) |
| Engine | `requests` + raw daemon threads (no `ThreadPoolExecutor` cleanup hangs) |
| Hard timeout | Every HTTP call wrapped in a daemon thread with 13s wall-clock timeout — cannot hang |
| Shallow crawl | Follows up to 5 internal/contact pages if homepage has no email |
| Contact discovery | Guesses `/contact`, `/about`, `/reach-us` etc. directly |
| Cloudflare decode | Decodes `__cf_email__` obfuscated addresses |
| Email dedup | Per-row, with skip list for fake/sentry addresses |
| Resume | `--resume` flag picks up from partial output; also falls back to log file |
| `--all` | Re-scrapes all rows without email, ignoring `website_status` |
| TUI | Per-thread live view + progress bar + stats + activity log via `rich` |
| Logging | Per-phase `.log` file with timestamps, appends across runs |

## Performance

| Load | Est. time (p1) | Est. time (all 3) |
|------|:-:|:-:|
| 10 threads, shallow | ~30-45 min | ~1.5-2 hr |
| 10 threads, fast | ~15-25 min | ~50-80 min |

CPU ~30-40%, RAM ~45-50%. Bottleneck is network I/O, not CPU.

## Files

```
taskFetchEmail/
├── README.md          # This file
├── scraper_v1.py      # Main email extraction script (15 threads, Rich TUI)
├── analyze_final.py   # CSV stats analyzer (website/phone/email breakdown)
├── final/             # Input CSVs (p{1,2,3}_final.csv) — gitignored
├── full/              # Output CSVs (p{1,2,3}_full.csv) — gitignored
└── log/               # Log files (p{1,2,3}_full.log) — gitignored
```

All three data folders (`final/`, `full/`, `log/`) are in `.gitignore`.
Generated files (CSVs, logs) live here and are never committed to git.
