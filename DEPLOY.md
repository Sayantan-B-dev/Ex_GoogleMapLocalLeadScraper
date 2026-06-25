# Deployment Guide — Google Maps Lead Scraper

You have **2,025 queries** across 3 priorities. Total runtime locally:
- **Method 1 (Playwright):** ~7–14h (depends on concurrency, headless mode)
- **Method 2 (gosom Docker):** ~9–14h (depends on `--concurrent` and `-c 4`)

Running this on your PC for 10+ hours at 70–75°C is safe (CPUs throttle at 95–100°C), but for convenience, reliability, and zero power bills, deploy to the cloud.

---

## Option 1: Oracle Cloud ARM (Always Free — Recommended)

**Specs:** 4 vCPU (Ampere Ampere A1), 24 GB RAM, 200 GB disk — **free forever**. No idle limits. Runs Docker natively.

### 1. Sign Up

Go to [cloud.oracle.com](https://cloud.oracle.com) → **Create Free Account**. Requires credit card for identity verification (not charged unless you upgrade). You get $300 in credits + Always Free resources.

### 2. Create an ARM Instance

| Field | Value |
|-------|-------|
| Image | **Ubuntu 22.04** (or 24.04 LTS) |
| Shape | **VM.Standard.A1.Flex** (ARM) |
| OCPUs | **4** (max for free) |
| Memory | **24 GB** (max for free) |
| Boot volume | **200 GB** |
| SSH keys | **Paste your public key** (`id_rsa.pub`) |

**Region tip:** ARM availability varies. Try **Mumbai**, **Hyderabad**, **São Paulo**, or **Frankfurt** if your primary region shows "Out of capacity." Create a **compartment** first if prompted.

### 3. SSH & Install Docker

```bash
ssh ubuntu@<your-instance-public-ip>

# Update & install Docker
sudo apt update && sudo apt install -y docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker $USER

# Log out and back in for group to take effect
exit
ssh ubuntu@<your-instance-ip>

# Verify
docker --version
```

### 4. Upload Project

```bash
# From your local machine
scp -r /path/to/scraping_info ubuntu@<ip>:~/

# Alternatively, use rsync (faster for subsequent runs):
rsync -avz --progress /path/to/scraping_info/ ubuntu@<ip>:~/scraping_info/
```

### 5. Run Method 2 (Docker)

```bash
ssh ubuntu@<ip>
cd ~/scraping_info/method2

# Run all 9 batches with 3 parallel containers
./run.sh --concurrent 3
```

### 6. Run Method 1 (Playwright) — Optional

Method 1 needs Chromium which works on ARM:

```bash
ssh ubuntu@<ip>
cd ~/scraping_info/method1

# Install dependencies
pip install playwright pandas nest-asyncio
playwright install chromium

# Generate city batches
python split_batches.py

# Run with 3 parallel scrapers
python run_all.py --phase 1 --max-concurrent 3

# After P1, run P2 (+ maybe P3)
python run_all.py --phase 2 --max-concurrent 3
python run_all.py --phase 3 --max-concurrent 3
```

### 7. Download Results

```bash
# Method 2 results
scp -r ubuntu@<ip>:~/scraping_info/method2/output/*.csv /local/path/method2/

# Method 1 results
scp -r ubuntu@<ip>:~/scraping_info/method1/output/csv/ /local/path/method1/
```

### 8. Keep Alive (tmux)

SSH disconnects kill running processes. Use `tmux`:

```bash
sudo apt install -y tmux
tmux new -s scrape

# Inside tmux — run your scraper
cd ~/scraping_info/method2 && ./run.sh

# Detach: Ctrl+B then D
# Reattach: tmux attach -t scrape
# List sessions: tmux ls
```

### Estimated Cost

**$0** — everything is within Oracle's Always Free tier.

---

## Option 2: Hetzner Cloud VPS (~$0.35 one-time)

Cheapest dedicated compute. Good for a single 14-hour run.

### Pricing

| Plan | vCPU | RAM | Hourly | 14 hours |
|------|------|-----|--------|----------|
| CX22 | 2 | 4 GB | €0.009 | €0.13 |
| CX32 | 4 | 8 GB | €0.019 | €0.27 |
| CX42 | 8 | 16 GB | €0.037 | €0.52 |

A **CX32** (4 vCPU, 8 GB) is ideal. Total: **~€0.27 (~$0.30)**.

### Setup

1. **Sign up** at [hetzner.cloud](https://hetzner.cloud) (requires ~€5 deposit)
2. **Create project → Add server:**
   - Image: **Ubuntu 22.04**
   - Type: **CX32** (or CX42 for faster)
   - Add your SSH key
3. **SSH in & install Docker:**

```bash
ssh root@<server-ip>
apt update && apt install -y docker.io tmux
systemctl enable --now docker
```

4. **Upload & run:**

```bash
# Local machine
rsync -avz --progress /path/to/scraping_info/ root@<ip>:~/scraping_info/

# SSH back
ssh root@<ip>
tmux new -s scrape
cd ~/scraping_info/method2 && ./run.sh
# Ctrl+B, D to detach
```

5. **Download & delete server:**

```bash
scp root@<ip>:~/scraping_info/method2/output/*.csv /local/path/
```

Then **delete the server** in Hetzner dashboard (or it keeps billing).

### Estimated Cost

**~€0.30 (~$0.35)** for CX32 at 14 hours.

---

## Option 3: Google Colab (Free, Limited)

Use Colab for **method1 only** (no Docker). Best for testing small batches, not full runs.

### Limitations

- **~90 min runtime cap** — session disconnects
- **No Docker** — method2 won't work
- **No persistent storage** — files lost on disconnect
- **Shared CPU** — slower than dedicated

### Setup

1. Open [colab.research.google.com](https://colab.research.google.com)
2. **Runtime → Change runtime type → CPU** (free GPU not needed)
3. Install dependencies:

```python
!pip install playwright nest-asyncio pandas
!playwright install chromium
```

4. Upload your batch file + `scraper.py`:

```python
from google.colab import files
import os
os.makedirs("input", exist_ok=True)

print("Upload scraper.py")
files.upload()

print("Upload batch file (e.g. p1_Mumbai.txt)")
files.upload()
```

5. Run:

```python
!python scraper.py --input p1_Mumbai.txt --output results.csv --headless
```

6. Download results:

```python
files.download("results.csv")
```

### Estimated Cost

**$0** — but only practical for 1–2 batches per session.

---

## Option 4: GitHub Codespaces (Free Hours)

If you have a GitHub account, you get **60 free hours/month** (2-core) or **30 hours/month** (4-core) on Codespaces.

### Setup

1. Open your repo on GitHub → **Code → Create codespace on main**
2. Terminal opens in browser with full VS Code

```bash
# Docker is pre-installed
cd method2
./run.sh --concurrent 2
```

3. Results persist as long as the codespace exists. Download via VS Code file explorer.

### Estimated Cost

**$0** — within free tier hours.

---

## Option 5: AWS EC2 / Azure VM

Use only if you already have credits. Not cost-effective for a one-time job.

| Provider | Cheapest option | 14h cost |
|----------|----------------|----------|
| AWS EC2 t4g.medium (2 vCPU ARM, 4 GB) | ~$0.033/h | ~$0.46 |
| Azure B2s (2 vCPU, 4 GB) | ~$0.041/h | ~$0.57 |
| Google Cloud e2-medium (2 vCPU, 4 GB) | ~$0.024/h | ~$0.34 |

Setup is similar to Hetzner — create VM → install Docker → upload → run.

---

## Comparison

| Option | Cost | Time Cap | Docker | Persistent | Setup Time |
|--------|------|----------|--------|------------|------------|
| Oracle ARM | $0 | None | ✅ | ✅ | 20 min |
| Hetzner CX32 | ~$0.35 | None | ✅ | ✅ | 15 min |
| Google Colab | $0 | ~90 min | ❌ | ❌ | 10 min |
| GitHub Codespaces | $0 | ~60 h/mo | ✅ | ✅ | 5 min |
| AWS EC2 t4g | ~$0.46 | None | ✅ | ✅ | 20 min |

## Quick Decision

- **Don't want to pay?** → Oracle ARM (free forever) or GitHub Codespaces (free hours)
- **Want it done in one shot with zero hassle?** → Hetzner CX32 (~$0.35)
- **Just testing a few queries?** → Colab (free)
- **Already have AWS/Azure credits?** → Use those

## Dockerfile for Method 1 (Playwright)

If you want to run method1 anywhere with just `docker run`:

```dockerfile
FROM python:3.11-slim

RUN pip install playwright nest-asyncio pandas && \
    playwright install chromium

WORKDIR /app
COPY method1/ .

CMD ["python", "run_all.py", "--phase", "1"]
```

Build and run:

```bash
docker build -t maps-scraper -f Dockerfile .
docker run --rm maps-scraper
```
