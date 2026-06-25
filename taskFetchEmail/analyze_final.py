"""
analyze_final.py — Rich-powered CSV analyzer for final/ folder.
Scans all CSVs and prints detailed stats: website/phone/email intersections.

Usage:
    python analyze_final.py              # analyze all CSVs in final/
    python analyze_final.py p1_final.csv  # analyze specific file(s)
"""

import csv
import os
import sys
import ctypes

kernel32 = ctypes.windll.kernel32
STD_OUTPUT_HANDLE = -11
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
mode = ctypes.c_uint32()
if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
    kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich import box

if sys.stdout.encoding and sys.stdout.encoding.upper() not in ("UTF-8", "UTF8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
console = Console(color_system="truecolor", legacy_windows=False, force_terminal=True)

FINAL_DIR = os.path.join(os.path.dirname(__file__), "final")


def pct_bar(val, total, width=15):
    """Render a colored progress bar for the percentage."""
    frac = val / total if total else 0
    filled = round(frac * width)
    empty = width - filled
    if frac >= 0.8:
        color = "green"
    elif frac >= 0.5:
        color = "yellow"
    elif frac >= 0.2:
        color = "orange1"
    else:
        color = "red"
    bar = "━" * filled + "─" * empty
    return f"[{color}]{bar}[/]"


def pct_fmt(val, total):
    if not total:
        return "  -  "
    return f"{val / total * 100:5.1f}%"


def make_stat_row(label, val, total, style=""):
    """Return a list of renderables for a stat row."""
    bar = pct_bar(val, total)
    pct = pct_fmt(val, total)
    return [
        Text(label, style=style),
        Text(f"{val:,}", style=style + " bold"),
        Text.from_markup(bar),
        Text(pct, style=style),
    ]


def analyze(path):
    name = os.path.basename(path)
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    fn = [c for c in reader.fieldnames if c]
    total = len(rows)

    wk = "website" if "website" in (rows[0] if rows else {}) else "Website"
    pk = "phone" if "phone" in (rows[0] if rows else {}) else "Phone"
    ek = "email" if "email" in (rows[0] if rows else {}) else ("emails" if "emails" in (rows[0] if rows else {}) else "Email")

    def w(r): return r.get(wk, "").strip()
    def p(r): return r.get(pk, "").strip()
    def e(r): return r.get(ek, "").strip()

    has_web = sum(1 for r in rows if w(r))
    has_phone = sum(1 for r in rows if p(r))
    has_email = sum(1 for r in rows if e(r))
    no_web = total - has_web
    no_phone = total - has_phone
    no_email = total - has_email

    nwnp = sum(1 for r in rows if not w(r) and not p(r))
    nwhp = sum(1 for r in rows if not w(r) and p(r))
    hwnp = sum(1 for r in rows if w(r) and not p(r))

    nwhe = sum(1 for r in rows if not w(r) and e(r))
    hwne = sum(1 for r in rows if w(r) and not e(r))
    hwhe = sum(1 for r in rows if w(r) and e(r))

    nene = sum(1 for r in rows if not e(r) and not p(r))
    all3 = sum(1 for r in rows if w(r) and p(r) and e(r))

    a = sum(1 for r in rows if not w(r))
    b = sum(1 for r in rows if w(r) and not p(r) and not e(r))
    c = sum(1 for r in rows if w(r) and p(r) and not e(r))
    d = sum(1 for r in rows if w(r) and not p(r) and e(r))
    f_ = sum(1 for r in rows if not w(r) and p(r) and not e(r))
    g_ = sum(1 for r in rows if not w(r) and not p(r) and e(r))
    h_ = sum(1 for r in rows if not w(r) and p(r) and e(r))

    # ── Build Rich output ──────────────────────────────────────
    sections = []

    # 1. Coverage table
    t1 = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    t1.add_column("Metric", style="bold", width=30)
    t1.add_column("Count", justify="right", width=10)
    t1.add_column("Bar", width=17)
    t1.add_column("%", justify="right", width=8)

    t1.add_row(*make_stat_row("Has website", has_web, total, "cyan"))
    t1.add_row(*make_stat_row("No website", no_web, total, "dim"))
    t1.add_row(*make_stat_row("Has phone", has_phone, total, "green"))
    t1.add_row(*make_stat_row("No phone", no_phone, total, "dim"))
    t1.add_row(*make_stat_row("Has email", has_email, total,
                              "green" if has_email else "red"))
    t1.add_row(*make_stat_row("No email", no_email, total, "dim"))
    sections.append(Panel(t1, title="[bold]Coverage[/]", border_style="blue"))

    # 2. Intersection table
    t2 = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    t2.add_column("Intersection", style="bold", width=30)
    t2.add_column("Count", justify="right", width=10)
    t2.add_column("Bar", width=17)
    t2.add_column("%", justify="right", width=8)

    t2.add_row(*make_stat_row("No website + no phone", nwnp, total, "dim"))
    t2.add_row(*make_stat_row("No website + has phone", nwhp, total, "yellow"))
    t2.add_row(*make_stat_row("Has website + no phone", hwnp, total, "yellow"))
    t2.add_row(Text("-" * 60, style="dim"), "", "", "")
    t2.add_row(*make_stat_row("No website + has email", nwhe, total, "dim"))
    t2.add_row(*make_stat_row("Has website + no email", hwne, total,
                              "yellow" if hwne else "dim"))
    t2.add_row(*make_stat_row("Has website + has email", hwhe, total,
                              "green" if hwhe else "dim"))
    t2.add_row(Text("-" * 60, style="dim"), "", "", "")
    t2.add_row(*make_stat_row("No email + no phone", nene, total, "dim"))
    t2.add_row(*make_stat_row("All three (web+phone+email)", all3, total,
                              "green bold" if all3 else "dim"))
    sections.append(Panel(t2, title="[bold]Intersections[/]", border_style="green"))

    # 3. Categorical breakdown
    t3 = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    t3.add_column("Category", style="bold", width=30)
    t3.add_column("Count", justify="right", width=10)
    t3.add_column("Bar", width=17)
    t3.add_column("%", justify="right", width=8)

    labels_colors = [
        ("(a) No website", a, "red"),
        ("(b) Website only", b, "yellow"),
        ("(c) Website + phone", c, "yellow"),
        ("(d) Website + email", d, "green"),
        ("(e) All three (web+phone+email)", all3, "green bold"),
        ("(f) Phone only", f_, "yellow"),
        ("(g) Email only", g_, "green"),
        ("(h) Phone + email (no web)", h_, "green"),
    ]
    for label, val, style in labels_colors:
        t3.add_row(*make_stat_row(label, val, total, style if val else "dim"))
    sections.append(Panel(t3, title="[bold]Categorical Breakdown[/]", border_style="magenta"))

    # 4. Columns
    col_lines = []
    for i in range(0, len(fn), 5):
        chunk = fn[i:i+5]
        col_lines.append(", ".join(chunk))
    col_text = "\n".join(col_lines)
    sections.append(Panel(col_text, title=f"[bold]Columns ({len(fn)})[/]", border_style="dim"))

    # ── Header ─────────────────────────────────────────────
    header = Panel(
        f"[bold cyan]{name}[/]    "
        f"[white]Total rows:[/] [bold]{total:,}[/]    "
        f"[dim]Columns: {len(fn)}[/]",
        border_style="bright_blue",
    )
    console.print()
    console.print(header)

    # Print sections in two-column layout when possible
    if len(sections) >= 2:
        console.print(Columns(sections[:2], equal=True))
    if len(sections) >= 4:
        console.print(Columns(sections[2:4], equal=True))
    elif len(sections) >= 3:
        console.print(sections[2])
    console.print()

    return {
        "name": name, "total": total, "has_web": has_web, "no_web": no_web,
        "has_phone": has_phone, "no_phone": no_phone,
        "has_email": has_email, "no_email": no_email,
        "no_web_no_phone": nwnp, "no_web_has_phone": nwhp, "has_web_no_phone": hwnp,
        "no_web_has_email": nwhe, "has_web_no_email": hwne, "has_web_has_email": hwhe,
        "no_email_no_phone": nene, "all_three": all3,
        "cat_no_website": a, "cat_website_only": b, "cat_website_phone": c,
        "cat_website_email": d, "cat_all_three": all3,
        "cat_phone_only": f_, "cat_email_only": g_, "cat_phone_email": h_,
    }


def main():
    if not os.path.isdir(FINAL_DIR):
        console.print(f"[red]ERROR:[/] final/ folder not found at: {FINAL_DIR}")
        sys.exit(1)

    paths = []
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if args:
        for arg in args:
            p = arg if os.path.isabs(arg) else os.path.join(FINAL_DIR, arg)
            if os.path.exists(p):
                paths.append(p)
            else:
                console.print(f"[yellow]WARN:[/] {arg} not found, skipping")
    else:
        paths = sorted(
            os.path.join(FINAL_DIR, f)
            for f in os.listdir(FINAL_DIR)
            if f.endswith(".csv")
        )

    if not paths:
        console.print("[red]ERROR:[/] No CSV files found in final/")
        sys.exit(1)

    results = []
    for p in paths:
        results.append(analyze(p))

    if len(results) > 1:
        # Summary table
        t = Table(show_header=True, header_style="bold", box=box.SIMPLE)
        t.add_column("File", style="cyan", width=20)
        t.add_column("Total", justify="right", width=8)
        t.add_column("Has Web", justify="right", width=8)
        t.add_column("No Web", justify="right", width=8)
        t.add_column("Has Phone", justify="right", width=10)
        t.add_column("Has Email", justify="right", width=10)
        t.add_column("All 3", justify="right", width=8)

        tt = tr = tw = tp = te = ta = 0
        for r in results:
            tt += r["total"]
            tw += r["has_web"]
            tp += r["has_phone"]
            te += r["has_email"]
            ta += r["all_three"]
            t.add_row(
                r["name"], f"{r['total']:,}", f"{r['has_web']:,}",
                f"{r['no_web']:,}", f"{r['has_phone']:,}",
                f"{r['has_email']:,}", f"{r['all_three']:,}",
            )
        t.add_row(
            Text("TOTAL", style="bold white"),
            Text(f"{tt:,}", style="bold"),
            Text(f"{tw:,}", style="bold"),
            Text(f"{tt - tw:,}", style="bold"),
            Text(f"{tp:,}", style="bold"),
            Text(f"{te:,}", style="bold green" if te else "bold"),
            Text(f"{ta:,}", style="bold green" if ta else "bold"),
        )
        console.print(Panel(t, title="[bold]Summary — All Files[/]", border_style="bright_yellow"))
        console.print()


if __name__ == "__main__":
    main()
