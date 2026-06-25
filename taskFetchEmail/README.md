# Email Extractor — Method 3

Scrapes business websites from existing lead CSVs to extract email addresses.

**Location:** `taskFetchEmail/`

## Overview

Takes the `p{1,2,3}_final.csv` files (from method2), fetches each business's homepage, and extracts emails using regex + Cloudflare email protection decoding. Falls back to shallow crawling (contact/about pages) when the homepage has no email.

## Quick Start

```bash
cd taskFetchEmail

# Process all 3 files (default: shallow crawl)
python scraper_v1.py

# Homepage only (faster, misses splash-page emails)
python scraper_v1.py --fast

# Resume a partial run
python scraper_v1.py --resume

# Process a single file
python scraper_v1.py p1_final.csv
```

## Input / Output

Input CSVs live in `final/`, output goes to `full/`, logs to `log/`.

| File | Location | Rows | With Website | With Email |
|------|----------|-----:|:-----------:|:----------:|
| `p1_final.csv` | `final/` | 8,082 | 5,357 | 1,336 |
| `p2_final.csv` | `final/` | 2,745 | 1,617 | 0 |
| `p3_final.csv` | `final/` | 13,564 | 8,126 | 0 |
| **Total** | | **24,391** | **15,100** | **1,336** |
| `p1_full.csv` | `full/` | Output with `website_status` + `emails` columns |
| `p2_full.csv` | `full/` | ↑ |
| `p3_full.csv` | `full/` | ↑ |
| `p1_full.log` | `log/` | Per-URL log with found emails and errors |
| `p2_full.log` | `log/` | ↑ |
| `p3_full.log` | `log/`` | ↑ |

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
| Concurrency | 10 threads (adjustable) |
| Engine | `requests` + `BeautifulSoup` (lightweight, no browser) |
| Shallow crawl | Follows up to 3 internal links if homepage has no email |
| Cloudflare decode | Decodes `__cf_email__` obfuscated addresses |
| Email dedup | Per-row, with skip list for fake/sentry addresses |
| Resume | `--resume` flag picks up from partial output |
| TUI | Real-time progress bar, counts, and activity log via `rich` |
| Logging | Per-phase `.log` file with timestamps |

## Performance

| Load | Est. time (p1) | Est. time (all 3) |
|------|:-:|:-:|
| 10 threads, shallow | ~30-45 min | ~1.5-2 hr |
| 10 threads, fast | ~15-25 min | ~50-80 min |

CPU ~30-40%, RAM ~45-50%. Bottleneck is network I/O, not CPU.

## Files

```
taskFetchEmail/
├── README.md        # This file
├── scraper_v1.py    # Main email extraction script
├── final/           # Input CSVs (p{1,2,3}_final.csv)
├── full/            # Output CSVs (p{1,2,3}_full.csv)
└── log/             # Log files (p{1,2,3}_full.log)
```
