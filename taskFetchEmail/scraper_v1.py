"""
scraper_v1.py — Multi-threaded email extractor from lead CSVs.
Reads p{1,2,3}_final.csv, fetches each website's homepage,
extracts emails via regex + Cloudflare email decoding,
optionally shallow-crawls internal links + common contact paths
if homepage has no email.

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
import threading
from collections import deque
from dataclasses import dataclass, field
from queue import Queue, Empty as QueueEmpty
from urllib.parse import urlparse, urljoin

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import SSLError, ConnectionError, Timeout
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import ctypes

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text

kernel32 = ctypes.windll.kernel32
STD_OUTPUT_HANDLE = -11
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
mode = ctypes.c_uint32()
if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
    kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)

THREADS = 15
TIMEOUT = 10
MAX_SHALLOW_PAGES = 5
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

SKIP_DOMAIN_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js"}
SKIP_EMAIL_DOMAINS = {"example.com", "domain.com", "domain.net", "yourdomain.com"}
PRIORITY_PATH_KEYWORDS = ["contact", "about", "email", "reach", "connect", "footer"]

COMMON_CONTACT_PATHS = [
    "/contact", "/contact-us", "/contactus", "/contact.html",
    "/contact-us.html", "/about", "/about-us", "/aboutus",
    "/reach-us", "/get-in-touch", "/enquiry", "/connect",
    "/support", "/help", "/info", "/feedback",
]

console = Console(color_system="truecolor")

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})
adapter = HTTPAdapter(pool_connections=THREADS * 2, pool_maxsize=THREADS * 4,
                      max_retries=0, pool_block=False)
_session.mount("https://", adapter)
_session.mount("http://", adapter)

_thread_status = [
    {"tid": i, "website": "", "status": "idle", "elapsed": 0.0, "result": ""}
    for i in range(THREADS)
]
_thread_lock = threading.Lock()


def set_thread(tid, **kw):
    with _thread_lock:
        _thread_status[tid].update(kw)


def get_threads():
    with _thread_lock:
        return list(_thread_status)


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
    log_lines: deque = field(default_factory=lambda: deque(maxlen=12))
    _lock: threading.Lock = field(default_factory=threading.Lock)

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
        Layout(name="threads", ratio=2),
        Layout(name="bottom", size=10),
    )

    phase_display = f"[bold cyan]{state.phase}[/]"
    mode_display = f"[yellow]{state.mode}[/]"
    layout["header"].update(Panel(
        f"[bold white]scraper_v1.py[/]    {phase_display}    mode: {mode_display}    "
        f"[dim]threads: {THREADS}  timeout: {TIMEOUT}s[/]",
    ))

    threads = get_threads()
    active_count = sum(1 for t in threads if t["status"] in ("fetching", "shallow"))
    table = Table(
        show_header=True, header_style="bold", box=None,
        padding=(0, 1), collapse_padding=True,
    )
    table.add_column("#", width=2)
    table.add_column("Website", width=45, no_wrap=True)
    table.add_column("Status", width=10)
    table.add_column("Time", width=8)
    table.add_column("Result", width=25, no_wrap=True)

    for t in threads:
        site = t["website"].rstrip("/").split("//")[-1][:42] if t["website"] else "-"
        if t["status"] == "idle":
            st = Text("idle", style="dim")
        elif t["status"] == "fetching":
            st = Text("fetching", style="bold cyan")
        elif t["status"] == "done":
            st = Text("done", style="green")
        else:
            st = Text(t["status"], style="dim")
        elapsed = f"{t['elapsed']:.1f}s" if t["elapsed"] else "-"
        result = t["result"][:23] if t["result"] else ""
        table.add_row(str(t["tid"] + 1), site, st, elapsed, result)

    layout["threads"].update(Panel(
        table, title=f"Threads ({active_count}/{THREADS} active)",
        border_style="blue",
    ))

    bottom = Layout()
    bottom.split_row(
        Layout(name="progress", ratio=2),
        Layout(name="stats", ratio=1),
        Layout(name="timing", ratio=1),
        Layout(name="log", ratio=2),
    )

    prog = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=None),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("•"),
        TextColumn("{task.completed}/{task.total}"),
    )
    prog.add_task("Scraping", total=state.total, completed=state.done)
    bottom["progress"].update(Panel(prog, title="Progress", border_style="blue"))

    st = Table.grid(padding=(0, 1))
    st.add_row(
        Text.assemble(("Found", "bold green"), f"  {state.found}"),
        Text.assemble(("No email", "bold yellow"), f"  {state.no_email}"),
        Text.assemble(("Errors", "bold red"), f"  {state.errors}"),
    )
    bottom["stats"].update(Panel(st, title="Results", border_style="green"))

    elapsed = time.time() - state.start_ts
    rate = state.done / elapsed if elapsed > 0 else 0
    remaining = (state.total - state.done) / rate if rate > 0 else 0
    tim = Table.grid(padding=(0, 1))
    tim.add_row(
        Text.assemble(("Elapsed", "bold"), f"  {_fmt_dur(elapsed)}"),
        Text.assemble(("Rate", "bold"), f"  {rate:.1f}/s"),
        Text.assemble(("ETA", "bold"), f"  {_fmt_dur(remaining)}"),
    )
    bottom["timing"].update(Panel(tim, title="Timing", border_style="magenta"))

    log_content = "\n".join(state.log_lines) if state.log_lines else "[dim]waiting...[/]"
    bottom["log"].update(Panel(log_content, title="Activity", border_style="dim"))

    layout["bottom"].update(bottom)
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


def _do_get(url, verify=True):
    return _session.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT},
                        allow_redirects=True, verify=verify)


def fetch_page(url):
    try:
        resp = _do_get(url)
        if resp.status_code == 200:
            return resp.text, "ok"
        if resp.status_code in (403, 429):
            resp = _do_get(url)
            if resp.status_code == 200:
                return resp.text, "ok"
        return "", f"status_{resp.status_code}"
    except SSLError:
        try:
            resp = _do_get(url, verify=False)
            if resp.status_code == 200:
                return resp.text, "ok"
            return "", f"status_{resp.status_code}"
        except Exception:
            return "", "ssl_error"
    except Timeout:
        return "", "timeout"
    except ConnectionError as e:
        status = classify_exception(e)
        if status == "dns_error":
            alt = _swap_www(url)
            if alt:
                try:
                    resp = _do_get(alt)
                    if resp.status_code == 200:
                        return resp.text, "ok"
                except Exception:
                    pass
        return "", status
    except requests.RequestException:
        return "", "error"


def _swap_www(url):
    parsed = urlparse(url)
    host = parsed.netloc
    if host.startswith("www."):
        alt = host[4:]
    else:
        alt = "www." + host
    return url.replace(host, alt, 1)


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


def get_contact_candidate_urls(base_url):
    candidates = set()
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for path in COMMON_CONTACT_PATHS:
        candidates.add(base + path)
    return candidates


def priority_score(url):
    path = urlparse(url).path.lower()
    score = 0
    for kw in PRIORITY_PATH_KEYWORDS:
        if kw in path:
            score += 10
    if path in ("", "/", "/index.html"):
        score = -10
    return -score


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

    if not shallow:
        return [], "ok_no_email"

    discovered = set()
    discovered |= get_internal_links(html, url)
    discovered |= get_contact_candidate_urls(url)
    discovered.discard(url)

    if not discovered:
        return [], "ok_no_email"

    sorted_urls = sorted(discovered, key=priority_score)
    to_fetch = sorted_urls[:MAX_SHALLOW_PAGES]

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


def setup_log(log_path):
    logger = logging.getLogger(log_path)
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(fh)
    return logger


def worker(tid, task_queue, done_queue, shallow):
    while True:
        item = task_queue.get()
        if item is None:
            task_queue.task_done()
            break
        idx, website = item
        set_thread(tid, website=website, status="fetching", elapsed=0.0, result="")
        start = time.time()
        try:
            emails, status = fetch_website_emails(website, shallow)
        except Exception:
            emails, status = [], "error"
        elapsed = time.time() - start
        set_thread(tid, website=website, status="done", elapsed=elapsed, result=status)
        done_queue.put((idx, emails, status))
        task_queue.task_done()
        set_thread(tid, website="", status="idle", elapsed=0.0, result="")


def process_csv(input_path, output_path, resume=False, shallow=True):
    log_path = os.path.join("log", os.path.basename(output_path).rsplit(".", 1)[0] + ".log")
    os.makedirs("log", exist_ok=True)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
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

    task_queue = Queue()
    done_queue = Queue()
    threads = []
    for i in range(THREADS):
        t = threading.Thread(target=worker, args=(i, task_queue, done_queue, shallow), daemon=True)
        t.start()
        threads.append(t)

    for idx in to_scrape:
        task_queue.put((idx, rows[idx].get("website", "").strip()))

    found = 0
    no_email = 0
    errors = 0
    processed = 0
    total_tasks = len(to_scrape)

    with Live(make_layout(state), refresh_per_second=8, console=console) as live:
        while processed < total_tasks:
            try:
                idx, emails, status = done_queue.get(timeout=0.1)
            except QueueEmpty:
                live.update(make_layout(state))
                continue

            rows[idx]["emails"] = "; ".join(emails)
            rows[idx]["website_status"] = status
            website = rows[idx].get("website", "")

            if emails:
                found += 1
            elif status in ("ok", "ok_no_email"):
                no_email += 1
            else:
                errors += 1
            processed += 1

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


def main():
    phases = [
        ("final/p1_final.csv", "full/p1_full.csv"),
        ("final/p2_final.csv", "full/p2_full.csv"),
        ("final/p3_final.csv", "full/p3_full.csv"),
    ]

    resume = "--resume" in sys.argv
    shallow = "--fast" not in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if args:
        matched = [(i, o) for i, o in phases if any(a in i or a in os.path.basename(i) for a in args)]
        if matched:
            phases = matched
        else:
            custom = []
            for arg in args:
                base, ext = os.path.splitext(arg)
                out = f"{base}_full{ext}"
                if "final" in arg:
                    out = out.replace("final", "full", 1)
                custom.append((arg, out))
            phases = custom

    for inp, out in phases:
        if not os.path.exists(inp):
            console.print(f"[yellow]Warning: {inp} not found, skipping.[/]")
            continue
        process_csv(inp, out, resume=resume, shallow=shallow)


if __name__ == "__main__":
    main()
