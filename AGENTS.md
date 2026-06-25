# AGENTS.md — Project State & Conventions

## Goal
Scrape Google Maps for event/wedding business leads across **27 Indian cities**, 2,025 queries total. Two independent methods.

---

## Structure

```
scraping_info/
├── DEPLOY.md            # Cloud deployment guide
├── AGENTS.md            # This file
├── README.md            # Project overview
├── method1/             # Playwright (Python) — custom scraper
│   ├── scraper.py
│   ├── run_all.py
│   ├── split_batches.py
│   ├── merge.py
│   ├── view.html + details.html
│   └── priority_{1,2,3}_queries.txt
├── method2/             # gosom Docker (Go) — primary scraper
│   ├── run.sh / run.bat / run.ps1
│   ├── merge.py
│   ├── view.html
│   ├── queries.txt
│   ├── batches/ (batch_00..08.txt)
│   ├── output/ (batch_*.csv + final.csv)
│   └── backup/
└── taskFetchEmail/      # Method 3 — email enrichment via requests
    ├── README.md
    ├── scraper_v1.py    # 10-threaded email extractor + Rich TUI
    ├── p1_final.csv     # P1 input (8,082 rows, 5,357 websites)
    ├── p2_final.csv     # P2 input (2,745 rows, 1,617 websites)
    ├── p3_final.csv     # P3 input (13,564 rows, 8,126 websites)
    └── p{1,2,3}_full.*  # Output CSVs + logs (generated)
```

---

## Methods Comparison

| | Method 1 (Playwright) | Method 2 (gosom Docker) | Method 3 (Email Extractor) |
|---|---|---|---|
| Engine | Python + Playwright | Go + Docker | Python + requests + bs4 |
| Purpose | Full scrape | Full scrape | Email enrichment |
| Queries | 2,025 total | 432 (P1 only) | N/A (enriches method2 CSVs) |
| Fields/lead | 11 | 33+ | Adds website_status + emails |
| Resume | Per-query (.done) | Per-batch (CSV check) | --resume flag |
| Concurrency | 3 browsers | 3 containers × -c 4 | 10 threads |
| Speed | ~2–4 min/query | ~5–8 min/query | ~3–6s/website |
| Total leads (P1) | N/A | **5,874** | Adds emails to 5,357 P1 sites |

---

## Quick Commands

### Method 1
```bash
cd method1
python split_batches.py                         # generate city batches
python run_all.py --phase 1                     # scrape P1 (3 scrapers)
python run_all.py --phase 1 --max-concurrent 5  # faster, more CPU
python merge.py                                 # merge all CSVs
```

### Method 2
```bash
cd method2
./run.sh                          # 3 parallel Docker containers
./run.sh --concurrent 2           # lighter on CPU
python merge.py                   # merge batch_*.csv → final.csv
```

### Method 3 (Email Enrichment)
```bash
cd taskFetchEmail
python scraper_v1.py              # all 3 files, shallow crawl
python scraper_v1.py p1_final.csv # single file
python scraper_v1.py --fast       # homepage only
python scraper_v1.py --resume     # resume partial output
```

### Merge
```bash
# Method 1
python method1/merge.py

# Method 2
python method2/merge.py
```

---

## State

- **P1 method2 scraping:** ✅ Complete — 5,874 leads in `method2/p1_final.csv` (9 batches, 0.8% duplicates)
- **P1 method1:** 🔄 Not started
- **P2, P3:** ❌ Not started (both methods)
- **P1 email enrichment:** 🔄 Running — `taskFetchEmail/scraper_v1.py` processing 5,357 P1 websites
- **P2/P3 email enrichment:** ❌ Not started (waiting for P1 to finish)
- **Deploy:** Ready for cloud via DEPLOY.md

---

## Key Conventions

| Rule | Detail |
|------|--------|
| Legacy file | `method1/google_maps_leads.csv` — **NEVER modify** |
| Runtime dirs | `output/`, `profiles/`, `logs/`, `batches/` — gitignored, auto-created |
| Batch naming | `p{phase}_{City}.txt` (method1), `batch_{nn}.txt` (method2) |
| Output nesting | `output/csv/p{phase}/` + `output/logs/p{phase}/` (method1) |
| Dedup method1 | `(name, phone, address)` |
| Dedup method2 | `(title, phone)` |
| PC temps | 70–75°C is safe; throttle at 95–100°C |

---

## Scenario: User asks "what did we do so far?"

**Answer this concisely:** We scraped P1 using method2 (gosom Docker) — 9 batches, 5,874 leads merged. Method 1 is ready but unused. P1 email enrichment is running in `taskFetchEmail/` via `scraper_v1.py`. P2/P3 pending. DEPLOY.md guides cloud deployment. View results by opening `method2/view.html` in a browser and dragging `p1_final.csv`.

---

## Scenario: User asks to resume P1 method2

**Answer:** Already done — `method2/p1_final.csv` has 5,874 leads. No resume needed.

---

## Scenario: User wants to scrape more

1. **Method 1 P1:** `cd method1 && python run_all.py --phase 1` (generates city batches first if needed)
2. **Method 2 P2/P3:** Would need new query files and batches for method2. Currently only P1 queries exist in `method2/queries.txt`.

---

## Scenario: User asks about email enrichment

**Answer:** Run `python taskFetchEmail/scraper_v1.py` to extract emails from the existing lead CSVs. Uses 10 threads, Rich TUI, shallow crawl, Cloudflare email decode. Outputs `p{1,2,3}_full.csv` with `website_status` + `emails` columns. Use `--resume` to continue partial runs.
