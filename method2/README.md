# method2 — gosom Docker (Go) Scraper

Uses [gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper) — a fast Go-based scraper in Docker. Same 432 P1 queries as method1 but with richer output (33+ fields including emails, coordinates, reviews).

---

## Files

| File | What it does |
|------|-------------|
| `run.sh` | Main runner (bash) — spawns parallel Docker containers, resume-safe, shows live per-query progress. |
| `run.bat` | Windows CMD runner (sequential, single batch). |
| `run.ps1` | Windows PowerShell runner (sequential, single batch). |
| `merge.py` | Merges all `output/batch_*.csv`, dedup on `(title, phone)`, prints quality report with email stats. |
| `queries.txt` | All 432 P1 queries (one per line). |

## Directories

| Directory | Purpose | Auto-created |
|-----------|---------|:-----------:|
| `batches/` | 9 batch files (`batch_00.txt`..`batch_08.txt`, 48 queries each) | ❌ Place manually |
| `output/` | Batch CSVs (`batch_00.csv`..`batch_08.csv`) + completed leads | ✅ by `run.sh` |
| `logs/` | Per-batch stdout logs (`batch_00.log`..`batch_08.log`) | ✅ by `run.sh` |
| `backup/` | Old batch backups, if any | ❌ Manual |
| `old/` | Legacy priority-based folder structure | ❌ Manual |

## How to Run

### Bash (Git Bash / WSL / Linux)
```bash
./run.sh                    # 3 parallel Docker containers
./run.sh --concurrent 4     # 4 parallel containers
```

Each container runs 4 internal queries (`-c 4`). With 3 containers = 12 simultaneous queries. Watch CPU temps — drop to `--concurrent 2` if needed.

### Windows CMD
```cmd
cmd //c run.bat
```

### Windows PowerShell
```powershell
powershell -ExecutionPolicy Bypass -File run.ps1
```

## Resume

The script skips any batch with an existing non-empty CSV. To re-run a specific batch, delete its CSV and rerun:

```bash
rm output/batch_04.csv
./run.sh
```

Kill stuck containers:
```bash
docker kill $(docker ps -q)
```

## Merge Results

```bash
python merge.py                                  # merges all output/batch_*.csv
python merge.py --pattern "batch_0*.csv" --output partial.csv   # first 10 batches
```

## Docker Path Quirk (Git Bash)

Paths with spaces need `MSYS_NO_PATHCONV=1` (already handled in `run.sh`). If running manually:

```bash
MSYS_NO_PATHCONV=1 docker run --rm \
  -v gmaps-playwright-cache:/opt \
  -v "/g/code/Web techs/projects/BlueEye/scraping_info/method2/queries.txt:/queries.txt:ro" \
  -v "/g/code/Web techs/projects/BlueEye/scraping_info/method2/output:/out" \
  gosom/google-maps-scraper \
  -input /queries.txt \
  -results /out/results.csv \
  -depth 20 -email -c 4 -exit-on-inactivity 3m
```

## Command Cheat Sheet

```bash
# Run all batches (resumes automatically)
./run.sh

# After scraping, merge
python merge.py --pattern "output/batch_*.csv" --output final.csv
```

## Schema (33+ columns)

`input_id, link, title, category, address, open_hours, popular_times, website, phone, plus_code, review_count, review_rating, reviews_per_rating, latitude, longitude, cid, status, descriptions, reviews_link, thumbnail, timezone, price_range, data_id, street_view_url, place_id, images, reservations, order_online, menu, owner, complete_address, credit_cards_accepted, about, user_reviews, user_reviews_extended, emails`
