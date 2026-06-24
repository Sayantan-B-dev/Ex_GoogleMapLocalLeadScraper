# Deployment Options for Google Maps Scraper

You have 432 P1 queries, depth 20, with email crawling. Total runtime: **~9–14 hours** locally.
Below are three ways to run it without loading your PC.

---

## Option 1: Oracle Cloud ARM (Always Free — Recommended)

**Specs:** 4 vCPU (Ampere ARM), 24 GB RAM, 200 GB disk — **free forever**.
Can run Docker natively. No idle limits.

### Setup

1. **Sign up** at [cloud.oracle.com](https://cloud.oracle.com) (free tier, requires credit card for verification, not charged).

2. **Create an ARM instance:**
   - Region: pick one with ARM availability (check [here](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm))
   - Image: **Ubuntu 22.04** (or 24.04)
   - Shape: **VM.Standard.A1.Flex** (ARM)
   - Allocate **4 OCPUs, 24 GB RAM**
   - Add your SSH public key
   - Open ports 22 (SSH) in security list

3. **SSH in and install Docker:**

```bash
ssh ubuntu@<your-instance-ip>

# Install Docker
sudo apt update && sudo apt install -y docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
# Log out and back in
exit
ssh ubuntu@<your-instance-ip>

# Verify
docker --version
```

4. **Upload project & run:**

```bash
# From your local machine
scp -r /path/to/method2 ubuntu@<ip>:~/

# SSH back in and run
cd ~/method2
./run.sh
```

5. **Download results after done:**

```bash
scp ubuntu@<ip>:~/method2/output/*.csv /local/path/
```

**Estimated cost:** $0

---

## Option 2: Google Colab (Free, but limited)

**Runs method1's Playwright scraper (Python). No Docker needed.**
Colab disconnects after ~90 min of inactivity, so split into **2 batches of 4–5 batch files each**.

### Setup

1. Open [colab.research.google.com](https://colab.research.google.com)
2. Create a new notebook
3. Paste this:

```python
# Install Playwright
!pip install playwright nest-asyncio
!playwright install chromium

# Upload files
from google.colab import files
import os

os.makedirs("method1/input", exist_ok=True)
os.makedirs("method1/output", exist_ok=True)

print("Upload your batch file (e.g. p1_batch_1.txt)")
uploaded = files.upload()
for name, content in uploaded.items():
    with open(f"method1/input/{name}", "wb") as f:
        f.write(content)
```

4. Then run the scraper (you'll need `scraper.py` ported or run inline). Since method2 uses Docker (not available on Colab), you'd use method1's Playwright approach here.

**Limitations:**
- ~90 min cap — manual restart needed
- No Docker (method2 won't work)
- Session resets after disconnect
- Free GPU/CPU but shared resources

**Estimated cost:** $0

---

## Option 3: Hetzner Cloud VPS (~$2-3 one-time)

**Cheapest dedicated compute.** Use CX22 or CX32 for this workload.

### Pricing

| Plan | vCPU | RAM | Hourly | 14 hours |
|------|------|-----|--------|----------|
| CX22 | 2 | 4 GB | €0.009 | €0.13 |
| CX32 | 4 | 8 GB | €0.019 | €0.27 |
| CX42 | 8 | 16 GB | €0.037 | €0.52 |

A CX32 (4 vCPU) with 20 GB volume is fine. Expect **~€0.30 total**.

### Setup

1. **Sign up** at [hetzner.cloud](https://hetzner.cloud) (requires payment, ~€5-10 deposit)

2. **Create a project → Add server:**
   - Location: any (Nürnberg or Helsinki)
   - Image: **Ubuntu 22.04**
   - Type: **CX32** (or CX22 for slower/cheaper)
   - Volume: add a 20 GB volume (optional, for storage)
   - Add your SSH key

3. **Install Docker and run:**

```bash
ssh root@<your-server-ip>

# Install Docker
apt update && apt install -y docker.io
systemctl enable --now docker

# Upload and run
exit  # back to local

scp -r method2 root@<ip>:~/
ssh root@<ip>
cd ~/method2 && ./run.sh
```

4. **Download results:**

```bash
scp root@<ip>:~/method2/output/*.csv /local/path/
```

5. **Delete the server** after done (or it keeps billing).

**Estimated cost:** ~€0.30 (~$0.35)

---

## Comparison

| Option | Cost | Runtime Cap | Docker | Setup Time |
|--------|------|-------------|--------|------------|
| Oracle ARM | $0 | None | ✅ | 20 min |
| Google Colab | $0 | ~90 min | ❌ | 10 min |
| Hetzner VPS | ~$0.35 | None | ✅ | 15 min |

**Recommendation:** Oracle ARM if you want it free and permanent. Hetzner CX32 if you want it done in one shot with minimum hassle.
