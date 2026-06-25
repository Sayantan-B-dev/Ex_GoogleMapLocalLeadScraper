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
    python scraper_v1.py --resume     # resume: skips rows with website_status set
    python scraper_v1.py --fast       # homepage only, no shallow crawl
    python scraper_v1.py --all        # re-scan all without email, ignore website_status
"""

import csv
import logging
import re
import sys
import os
import time
import traceback
import threading
import signal
from collections import deque
from dataclasses import dataclass, field
from queue import Queue, Empty as QueueEmpty
from urllib.parse import urlparse, urljoin
import requests
from requests.exceptions import SSLError, ConnectionError, Timeout
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import ctypes
from rich.console import Console
from rich.live import Live
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
HARD_TIMEOUT = TIMEOUT + 3
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

log = logging.getLogger("scraper")

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


def make_layout(state: ScrapeState) -> Text:
    lines = []
    lines.append(f"[bold white]scraper_v1.py[/]  [bold cyan]{state.phase}[/]  ")
    lines.append(f"  mode: [yellow]{state.mode}[/]  threads: [bold]{THREADS}[/]  timeout: {TIMEOUT}s")

    pct = state.done / state.total if state.total else 0
    bar_w = 40
    filled = int(pct * bar_w)
    bar = f"[blue]{'█' * filled}[/][dim]{'█' * (bar_w - filled)}[/]"
    pct_str = f"{pct * 100:>5.1f}%"
    lines.append(f"  {bar}  {pct_str}  [bold]{state.done:,}/{state.total:,}[/]")

    elapsed = time.time() - state.start_ts
    rate = state.done / elapsed if elapsed > 0 else 0
    remaining = (state.total - state.done) / rate if rate > 0 else 0
    lines.append(
        f"  [green]Found:[/] {state.found:,}  "
        f"[yellow]No email:[/] {state.no_email:,}  "
        f"[red]Errors:[/] {state.errors:,}  |  "
        f"Elapsed: [bold]{_fmt_dur(elapsed)}[/]  "
        f"Rate: {rate:.1f}/s  "
        f"ETA: [bold]{_fmt_dur(remaining)}[/]"
    )

    threads = get_threads()
    active = [t for t in threads if t["status"] in ("fetching", "shallow")]
    idle = [t for t in threads if t["status"] not in ("fetching", "shallow")]
    lines.append(f"  [dim]──────────────────────────────────────────[/]")
    lines.append(f"  Threads [bold]{len(active)}[/] active, [dim]{len(idle)} idle[/]:")
    for t in active:
        site = t["website"].rstrip("/").split("//")[-1][:35] if t["website"] else "-"
        elapsed_str = f"{t['elapsed']:.1f}s".rjust(6)
        lines.append(f"    #[bold]{t['tid']+1:<2}[/] {site:<37} [cyan]fetching[/] {elapsed_str}")
    if idle:
        n = min(len(idle), 3)
        for t in idle[:n]:
            site = t["website"].rstrip("/").split("//")[-1][:35] if t["website"] else "-"
            r = f"  {t['result']}" if t["result"] else ""
            lines.append(f"    #[bold]{t['tid']+1:<2}[/] {site:<37} [dim]done[/]     {r}")
        if len(idle) > n:
            lines.append(f"    [dim]... {len(idle) - n} more done threads[/]")

    if state.log_lines:
        lines.append(f"  [dim]──────────────────────────────────────────[/]")
        for l in list(state.log_lines)[-6:]:
            lines.append(f"  {l}")

    return Text.from_markup("\n".join(lines))


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


def _hard_get(url, timeout=TIMEOUT, verify=True):
    """
    requests.get() in a dedicated daemon thread so a hard wall-clock
    timeout always applies.  The daemon thread is fire-and-forget if
    the deadline passes — Python never joins it on exit.
    """
    url_short = url.rstrip("/").split("/")[2] if "//" in url else url
    log.debug("REQ %s verify=%s", url_short, verify)
    result = [None]
    exc_info = [None]

    def worker():
        try:
            result[0] = requests.get(
                url, timeout=(timeout, timeout),
                headers={"User-Agent": USER_AGENT, "Connection": "close"},
                allow_redirects=True, verify=verify,
            )
        except BaseException as e:
            exc_info[0] = e

    t0 = time.time()
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=HARD_TIMEOUT)

    if t.is_alive():
        elapsed = time.time() - t0
        log.debug("HARD TIMEOUT %s %.1fs", url_short, elapsed)
        raise Timeout(f"Hard timeout {elapsed:.1f}s for {url_short}")

    elapsed = time.time() - t0
    if exc_info[0] is not None:
        e = exc_info[0]
        log.debug("FAIL %s %s %.1fs", url_short, type(e).__name__, elapsed)
        raise e

    log.debug("OK %s status=%d %.1fs", url_short, result[0].status_code, elapsed)
    return result[0]


def _swap_www(url):
    parsed = urlparse(url)
    host = parsed.netloc
    if host.startswith("www."):
        alt = host[4:]
    else:
        alt = "www." + host
    return url.replace(host, alt, 1)


def fetch_page(url):
    tid = threading.current_thread().name
    url_short = url.rstrip("/").split("/")[2] if "//" in url else url
    try:
        resp = _hard_get(url)
        if resp.status_code == 200:
            return resp.text, "ok"
        if resp.status_code in (403, 429):
            log.debug("[%s] 403/429 retry %s", tid, url_short)
            resp = _hard_get(url)
            if resp.status_code == 200:
                return resp.text, "ok"
        return "", f"status_{resp.status_code}"
    except SSLError:
        log.debug("[%s] SSLError retry verify=False %s", tid, url_short)
        try:
            resp = _hard_get(url, verify=False)
            if resp.status_code == 200:
                return resp.text, "ok"
            return "", f"status_{resp.status_code}"
        except Exception:
            return "", "ssl_error"
    except Timeout:
        log.debug("[%s] TIMEOUT %s", tid, url_short)
        return "", "timeout"
    except ConnectionError as e:
        status = classify_exception(e)
        log.debug("[%s] CONN_ERR %s => %s", tid, url_short, status)
        if status == "dns_error":
            alt = _swap_www(url)
            if alt:
                log.debug("[%s] DNS fallback %s", tid, alt.split("/")[2])
                try:
                    resp = _hard_get(alt)
                    if resp.status_code == 200:
                        return resp.text, "ok"
                except Exception:
                    pass
        return "", status
    except requests.RequestException:
        return "", "error"


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
    for page_url in sorted_urls[:MAX_SHALLOW_PAGES]:
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
    fh = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(fh)
    return logger


def worker(tid, task_queue, done_queue, shallow):
    threading.current_thread().name = f"W{tid}"
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
        except Exception as exc:
            log.debug("[W%d] UNCAUGHT %s: %s", tid, type(exc).__name__, exc)
            log.debug(traceback.format_exc().rstrip())
            emails, status = [], "error"
        elapsed = time.time() - start
        set_thread(tid, website=website, status="done", elapsed=elapsed, result=status)
        done_queue.put((idx, emails, status))
        task_queue.task_done()
        set_thread(tid, website="", status="idle", elapsed=0.0, result="")


def process_csv(input_path, output_path, resume=False, shallow=True, all_flag=False):
    global log
    log_path = os.path.join("log", os.path.basename(output_path).rsplit(".", 1)[0] + ".log")
    os.makedirs("log", exist_ok=True)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    attempted_in_log = set()
    if not all_flag and os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        site = parts[2].rstrip("/").split("/")[0]
                        if site and "." in site:
                            attempted_in_log.add(site)
        except Exception:
            pass

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
        status = row.get("website_status", "").strip()
        if website and not email:
            if not all_flag:
                if status:
                    continue
                site_domain = website.rstrip("/").split("//")[-1].split("/")[0]
                if site_domain in attempted_in_log:
                    row["website_status"] = "resumed (was in log)"
                    continue
            to_scrape.append(i)
        row.setdefault("website_status", "")
        row.setdefault("emails", "")

    mode_parts = []
    mode_parts.append("shallow crawl" if shallow else "homepage only")
    if resume:
        mode_parts.append("resume")
    if all_flag:
        mode_parts.append("--all")
    total_str = f"{input_path} -> {output_path}"
    state = ScrapeState(
        total=len(to_scrape),
        phase=total_str,
        mode=", ".join(mode_parts),
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

    SAVE_INTERVAL = 100

    def save_partial():
        tmp = output_path + ".partial"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp, output_path)

    try:
        with Live(make_layout(state), refresh_per_second=3, console=console, transient=True) as live:
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

                if processed % SAVE_INTERVAL == 0:
                    save_partial()

                live.update(make_layout(state))
    except KeyboardInterrupt:
        console.print("\n[yellow]Ctrl+C caught — saving partial results...[/]")
        save_partial()
        console.print(f"[yellow]Saved {processed}/{total_tasks} to {output_path}[/]")
        log.info("Interrupted at %s/%s — partial CSV saved", processed, total_tasks)
        return

    save_partial()

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
    all_flag = "--all" in sys.argv
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
        process_csv(inp, out, resume=resume, shallow=shallow, all_flag=all_flag)


if __name__ == "__main__":
    main()
