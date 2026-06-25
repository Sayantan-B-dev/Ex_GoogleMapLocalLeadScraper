# method1 — Playwright (Python) Scraper

Custom Python scraper using Playwright to control a real Chrome browser. Covers **P1** (16 services × 27 cities = 432 queries), **P2** (12 × 27 = 324), and **P3** (47 × 27 = 1269).

---

## Files

| File | What it does |
|------|-------------|
| `scraper.py` | Core scraper — launches browser, searches Google Maps, scrolls results, clicks cards, extracts details. Supports resume via `.done` file. |
| `run_all.py` | Orchestrator — spawns up to 5 parallel `scraper.py` processes, shows live progress, writes `output/progress.json`. |
| `split_batches.py` | Reads `priority_{1,2,3}_queries.txt`, splits queries by city into `batches/p{phase}/*.txt`. |
| `merge.py` | Merges all CSVs from `output/csv/p*/`, dedup on `(name, phone, address)`, prints quality report. |
| `view.html` | CSV drag-drop viewer + live scraping dashboard (reads `output/progress.json` every 10s). |
| `details.html` | Minimal batch viewer — dropdown picker + load button. |
| `genarate_search_terms.py` | Query generation script (already run, output in `priority_*.txt`). |
| `google_maps_leads.csv` | Legacy export (160 leads). **Do not modify.** |
| `priority_{1,2,3}_queries.txt` | All queries for each priority (source files for `split_batches.py`). |
| `queryinfo.txt` | Query stats document. |

## Directories

| Directory | Purpose | Auto-created |
|-----------|---------|:-----------:|
| `batches/p{1,2,3}/` | Per-city batch files (`p1_Mumbai.txt`, `p2_Goa.txt`, etc.) | ✅ by `split_batches.py` |
| `output/csv/p{1,2,3}/` | Output CSVs (`.csv`) + done trackers (`.done`) | ✅ by `run_all.py` |
| `output/logs/p{1,2,3}/` | Scraper stdout logs (`.log`) | ✅ by `run_all.py` |
| `profiles/` | Chrome persistent profiles per batch | ✅ by `run_all.py` |

## How to Run

### 1. Generate batches (once)
```bash
python split_batches.py
```

### 2. Run scraping
```bash
python run_all.py --phase 1       # P1: 27 city batches (432 queries)
python run_all.py --phase 2       # P2: 27 city batches (324 queries)
python run_all.py --phase 3       # P3: 27 city batches (1269 queries)
```

Defaults to 5 concurrent scrapers. Override with `--max-concurrent 3`.

### 3. Scrape a single batch manually
```bash
python scraper.py --input batches/p1/p1_Mumbai.txt --output "output/csv/p1/p1_Mumbai.csv"
```

| Flag | Description |
|------|-------------|
| `--input` | Query batch file (required) |
| `--output` | Output CSV path (required) |
| `--profile` | Chrome profile dir for persistent session |
| `--headless` | Run without visible browser |
| `--done` | `.done` file path (default: `{output}.done`) |

### 4. Merge results
```bash
python merge.py                                    # merges all output/csv/p*/
python merge.py --pattern "p1_*.csv" --output p1_final.csv   # merge only P1
```

## Command Cheat Sheet

```bash
# Full P1 run
python split_batches.py && python run_all.py --phase 1

# After scraping, merge
python merge.py

# View results
# Open view.html in browser → drag in any CSV
```

## Schema (11 columns)

`search_query, name, category, rating, reviews, address, phone, website, email, city, state, maps_url`
