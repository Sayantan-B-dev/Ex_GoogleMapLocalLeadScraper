"""
scraper_v1.py — Multi-threaded email extractor from lead CSVs.
Reads p{1,2,3}_final.csv, fetches each website's homepage,
extracts emails via regex + Cloudflare email decoding,
optionally shallow-crawls internal links if homepage has no email.

Adds two columns to output:
  - website_status: ok | ok_no_email | dns_error | ssl_error | timeout | status_XXX | error
  - emails:         semicolon-separated found email(s)

Usage:
    python scraper_v1.py              # process all three files
    python scraper_v1.py p1_final.csv # process just one
    python scraper_v1.py --resume     # resume from existing output files
    python scraper_v1.py --fast       # homepage only, no shallow crawl
"""

import csv
import logging
import re
import sys
import os
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from threading import Lock
from urllib.parse import urlparse, urljoin

import requests
from requests.exceptions import SSLError, ConnectionError, Timeout

import ctypes

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
from rich.rule import Rule

# Enable ANSI/VT escape sequences on Windows 10+
kernel32 = ctypes.windll.kernel32
STD_OUTPUT_HANDLE = -11
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
mode = ctypes.c_uint32()
if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
    kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)

THREADS = 10
TIMEOUT = 15
MAX_RETRIES = 2
MAX_SHALLOW_PAGES = 3
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

SKIP_DOMAIN_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js"}
SKIP_EMAIL_DOMAINS = {"example.com", "domain.com", "domain.net", "yourdomain.com"}
PRIORITY_PATH_KEYWORDS = ["contact", "about", "email", "reach", "connect", "footer"]

console = Console(color_system="truecolor")


@dataclass
class ScrapeState:
    total: int = 0
    done: int = 0
    found: int = 0
    no_email: int = 0
    errors: int = 0
    start_ts: float = field(default_factory=time.time)
    phase: str = ""
    mode: str = ""
    log_lines: deque = field(default_factory=lambda: deque(maxlen=18))
    _lock: Lock = field(default_factory=Lock)

    def push(self, found, no_email, errors, log_line=None):
        with self._lock:
            self.done = found + no_email + errors
            self.found = found
            self.no_email = no_email
            self.errors = errors
            if log_line:
                self.log_lines.append(log_line)


def make_layout(state: ScrapeState) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
    )
    layout["body"].split_row(
        Layout(name="left", ratio=3),
        Layout(name="right", ratio=2),
    )
    layout["body"]["left"].split_column(
        Layout(name="progress", size=5),
        Layout(name="stats", size=5),
    )
    layout["body"]["right"].split_column(
        Layout(name="eta", size=5),
        Layout(name="log", ratio=1),
    )

    phase_display = f"[bold cyan]{state.phase}[/]"
    mode_display = f"[yellow]{state.mode}[/]"
    header = Panel(
        f"[bold white]scraper_v1.py[/]    {phase_display}    mode: {mode_display}    "
        f"[dim]threads: {THREADS}  timeout: {TIMEOUT}s[/]",
    )
    layout["header"].update(header)

    pct = state.done / state.total if state.total else 0
    progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=None),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("•"),
        TextColumn("{task.completed}/{task.total}"),
    )
    progress.add_task("Scraping", total=state.total, completed=state.done)
    layout["body"]["left"]["progress"].update(
        Panel(progress, title="Progress", border_style="blue")
    )

    stats_table = Table.grid(padding=(0, 2))
    stats_table.add_row(
        Text.assemble(("Found", "bold green"), f"  {state.found}"),
        Text.assemble(("No email", "bold yellow"), f"  {state.no_email}"),
        Text.assemble(("Errors", "bold red"), f"  {state.errors}"),
    )
    layout["body"]["left"]["stats"].update(
        Panel(stats_table, title="Results", border_style="green")
    )

    elapsed = time.time() - state.start_ts
    rate = state.done / elapsed if elapsed > 0 else 0
    remaining = (state.total - state.done) / rate if rate > 0 else 0

    eta_table = Table.grid(padding=(0, 2))
    eta_table.add_row(
        Text.assemble(("Elapsed", "bold"), f"  {_fmt_dur(elapsed)}"),
        Text.assemble(("Rate", "bold"), f"  {rate:.1f}/s"),
        Text.assemble(("ETA", "bold"), f"  {_fmt_dur(remaining)}"),
    )
    layout["body"]["right"]["eta"].update(
        Panel(eta_table, title="Timing", border_style="magenta")
    )

    log_content = "\n".join(state.log_lines) if state.log_lines else "[dim]waiting...[/]"
    layout["body"]["right"]["log"].update(
        Panel(log_content, title="Activity", border_style="dim")
    )

    return layout


def _fmt_dur(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _log_line(website, status, emails):
    site = website.rstrip("/").split("//")[-1][:45]
    if emails:
        em = "; ".join(emails)[:55]
        return f"[green]OK[/] {site} - [cyan]{em}[/]"
    if status == "ok_no_email":
        return f"[yellow]--[/] {site} - no email found"
    return f"[red]XX[/] {site} - [bold]{status}[/]"


def normalize_url(url):
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def decode_cfemail(hex_str):
    try:
        key = int(hex_str[:2], 16)
        data = bytes.fromhex(hex_str[2:])
        return "".join(chr(b ^ key) for b in data)
    except (ValueError, IndexError):
        return ""


def extract_emails(text):
    found = EMAIL_REGEX.findall(text)
    seen = set()
    result = []
    for e in found:
        e = e.lower().strip()
        local, domain = e.split("@", 1)
        if any(domain.endswith(ext) for ext in SKIP_DOMAIN_EXTS):
            continue
        if domain in SKIP_EMAIL_DOMAINS:
            continue
        if local.startswith(".") or local.endswith("."):
            continue
        if e not in seen:
            seen.add(e)
            result.append(e)

    cf_emails = re.findall(r'data-cfemail=["\']([a-fA-F0-9]+)["\']', text)
    for cf in cf_emails:
        decoded = decode_cfemail(cf)
        if decoded and decoded not in seen:
            seen.add(decoded)
            result.append(decoded)

    return result


def classify_exception(e):
    if isinstance(e, SSLError):
        return "ssl_error"
    if isinstance(e, Timeout):
        return "timeout"
    if isinstance(e, ConnectionError):
        msg = str(e).lower()
        if "getaddrinfo" in msg:
            return "dns_error"
        return "connection_error"
    return "error"


def get_internal_links(html, base_url):
    domain = urlparse(base_url).netloc
    scheme = urlparse(base_url).scheme
    links = set()
    for match in re.finditer(r'href=["\']([^"\']+)["\']', html):
        href = match.group(1).strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        if href.startswith("//"):
            href = scheme + ":" + href
        if not href.startswith(("http://", "https://")):
            href = urljoin(base_url, href)
        parsed = urlparse(href)
        if parsed.netloc and parsed.netloc != domain:
            continue
        if parsed.netloc == domain or not parsed.netloc:
            path = parsed.path.lower()
            if any(path.endswith(ext) for ext in
                   (".pdf", ".zip", ".doc", ".docx", ".xls", ".xlsx",
                    ".mp3", ".mp4", ".zip", ".rar", ".exe")):
                continue
            links.add(href)
    return links


def priority_score(url):
    path = urlparse(url).path.lower()
    score = 0
    for kw in PRIORITY_PATH_KEYWORDS:
        if kw in path:
            score += 10
    if path in ("", "/", "/index.html"):
        score = -10
    return -score


def fetch_page(url):
    for attempt in range(MAX_RETRIES):
        try:
            headers = {"User-Agent": USER_AGENT}
            resp = requests.get(
                url, timeout=TIMEOUT, headers=headers, allow_redirects=True
            )
            if resp.status_code == 200:
                return resp.text, "ok"
            if resp.status_code in (403, 429) and attempt == 0:
                headers["User-Agent"] = "curl/8.0"
                resp = requests.get(
                    url, timeout=TIMEOUT, headers=headers, allow_redirects=True
                )
                if resp.status_code == 200:
                    return resp.text, "ok"
            return "", f"status_{resp.status_code}"
        except SSLError:
            if attempt < MAX_RETRIES - 1:
                time.sleep(1.5)
            else:
                return "", "ssl_error"
        except Timeout:
            if attempt < MAX_RETRIES - 1:
                time.sleep(1.5)
            else:
                return "", "timeout"
        except ConnectionError as e:
            status = classify_exception(e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(1.5)
            else:
                return "", status
        except requests.RequestException:
            if attempt < MAX_RETRIES - 1:
                time.sleep(1.5)
            else:
                return "", "error"
    return "", "error"


def fetch_website_emails(website, shallow=True):
    url = normalize_url(website)
    if not url:
        return [], ""

    html, status = fetch_page(url)
    if status != "ok":
        return [], status

    emails = extract_emails(html)
    seen = set(emails)

    if emails:
        return emails, "ok"

    if shallow:
        internal_links = get_internal_links(html, url)
        if internal_links:
            sorted_links = sorted(internal_links, key=priority_score)
            to_fetch = [l for l in sorted_links if l != url][:MAX_SHALLOW_PAGES]
            for page_url in to_fetch:
                page_html, page_status = fetch_page(page_url)
                if page_status == "ok":
                    more_emails = extract_emails(page_html)
                    for e in more_emails:
                        if e not in seen:
                            seen.add(e)
                            emails.append(e)

    if emails:
        return emails, "ok"
    return [], "ok_no_email"


def process_csv(input_path, output_path, resume=False, shallow=True):
    log_path = output_path.rsplit(".", 1)[0] + ".log"
    log = setup_log(log_path)

    source = output_path if (resume and os.path.exists(output_path)) else input_path

    with open(source, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if resume and source == output_path:
        with open(input_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            input_rows = list(reader)
        if len(input_rows) > len(rows):
            existing_websites = {
                r.get("website", "").strip()
                for r in rows if r.get("website", "").strip()
            }
            for r in input_rows:
                w = r.get("website", "").strip()
                if w and w not in existing_websites:
                    rows.append(r)
                    existing_websites.add(w)

    if "website_status" not in fieldnames:
        try:
            idx = fieldnames.index("website")
            fieldnames = (
                fieldnames[: idx + 1]
                + ["website_status"]
                + fieldnames[idx + 1 :]
            )
        except ValueError:
            fieldnames = fieldnames + ["website_status"]

    if "emails" not in fieldnames:
        fieldnames = fieldnames + ["emails"]

    to_scrape = []
    for i, row in enumerate(rows):
        website = row.get("website", "").strip()
        email = row.get("emails", "").strip()
        if website and not email:
            to_scrape.append(i)
        row.setdefault("website_status", "")
        row.setdefault("emails", "")

    total_str = f"{input_path} -> {output_path}"
    state = ScrapeState(
        total=len(to_scrape),
        phase=total_str,
        mode="shallow crawl" if shallow else "homepage only",
    )

    if not to_scrape:
        console.print(f"[yellow]Nothing to scrape in {input_path}[/]")
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return

    log.info("Scraping started — %s URLs, %s threads, mode=%s", len(to_scrape), THREADS, state.mode)

    found = 0
    no_email = 0
    errors = 0

    with Live(make_layout(state), refresh_per_second=8, console=console) as live:
        with ThreadPoolExecutor(max_workers=THREADS) as executor:
            futures = {}
            for idx in to_scrape:
                website = rows[idx].get("website", "").strip()
                futures[executor.submit(fetch_website_emails, website, shallow)] = idx

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    emails, status = future.result()
                except Exception as e:
                    emails, status = [], "error"
                    log.warning("  Row %s exception: %s", idx, e)

                rows[idx]["emails"] = "; ".join(emails)
                rows[idx]["website_status"] = status
                website = rows[idx].get("website", "")

                if emails:
                    found += 1
                elif status in ("ok", "ok_no_email"):
                    no_email += 1
                else:
                    errors += 1

                logline = _log_line(website, status, emails)
                state.push(found, no_email, errors, log_line=logline)

                line = re.sub(r"\[.*?\]", "", logline).strip()
                log.info("  %s", line)

                live.update(make_layout(state))

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    elapsed = time.time() - state.start_ts
    console.print(f"\n[bold green]Done — {output_path}[/]")
    console.print(f"  Found: {found}  No email: {no_email}  Errors: {errors}")
    console.print(f"  Elapsed: {_fmt_dur(elapsed)}")
    log.info("Done — %s  found=%s no_email=%s errors=%s elapsed=%ss",
             output_path, found, no_email, errors, int(elapsed))


def setup_log(log_path):
    logger = logging.getLogger(log_path)
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(fh)
    return logger


def main():
    phases = [
        ("p1_final.csv", "p1_full.csv"),
        ("p2_final.csv", "p2_full.csv"),
        ("p3_final.csv", "p3_full.csv"),
    ]

    resume = "--resume" in sys.argv
    shallow = "--fast" not in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if args:
        matched = [(i, o) for i, o in phases if any(a in i for a in args)]
        if matched:
            phases = matched
        else:
            custom = []
            for arg in args:
                base, ext = os.path.splitext(arg)
                custom.append((arg, f"{base}_full{ext}"))
            phases = custom

    for inp, out in phases:
        if not os.path.exists(inp):
            console.print(f"[yellow]Warning: {inp} not found, skipping.[/]")
            continue
        process_csv(inp, out, resume=resume, shallow=shallow)


if __name__ == "__main__":
    main()
