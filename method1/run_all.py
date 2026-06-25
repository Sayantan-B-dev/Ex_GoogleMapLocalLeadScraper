import argparse
import subprocess
import sys
import os
import time
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
PROFILES_DIR = BASE_DIR / "profiles"
BATCHES_DIR = BASE_DIR / "batches"


def ensure_dirs():
    for phase in [1, 2, 3]:
        (OUTPUT_DIR / "csv" / f"p{phase}").mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "logs" / f"p{phase}").mkdir(parents=True, exist_ok=True)
        (BATCHES_DIR / f"p{phase}").mkdir(parents=True, exist_ok=True)
    PROFILES_DIR.mkdir(exist_ok=True)


def batch_label(batch_file):
    return batch_file.replace(".txt", "")


def get_counts(batch_file, phase):
    label = batch_label(batch_file)
    csv_path = OUTPUT_DIR / "csv" / f"p{phase}" / f"{label}.csv"
    done_path = OUTPUT_DIR / "csv" / f"p{phase}" / f"{label}.done"
    leads = 0
    if csv_path.exists():
        try:
            import pandas as pd
            df = pd.read_csv(csv_path)
            leads = len(df)
        except:
            pass
    done_q = 0
    if done_path.exists():
        with open(done_path, encoding="utf-8") as f:
            done_q = sum(1 for line in f if line.strip())
    return leads, done_q


def write_progress(phase, batch_files, processes, completed):
    total_queries = 0
    total_done = 0
    total_leads = 0
    batches = []

    for batch in batch_files:
        label = batch_label(batch)
        leads, done_q = get_counts(batch, phase)
        if batch in completed:
            status = "done"
        elif batch in processes:
            status = "running"
        else:
            status = "waiting"
        total_queries += done_q
        total_done += done_q
        total_leads += leads
        batches.append({
            "label": label,
            "status": status,
            "queries_done": done_q,
            "leads": leads,
        })

    progress = {
        "phase": phase,
        "total_batches": len(batch_files),
        "batches": batches,
        "total_queries_done": total_done,
        "total_leads": total_leads,
        "timestamp": time.time(),
    }
    with open(OUTPUT_DIR / "progress.json", "w") as f:
        json.dump(progress, f, indent=2)


def launch_scraper(batch_file, phase):
    label = batch_label(batch_file)
    input_path = BATCHES_DIR / f"p{phase}" / batch_file
    csv_dir = OUTPUT_DIR / "csv" / f"p{phase}"
    log_dir = OUTPUT_DIR / "logs" / f"p{phase}"
    output_path = csv_dir / f"{label}.csv"
    done_path = csv_dir / f"{label}.done"
    log_file = log_dir / f"{label}.log"
    profile_path = PROFILES_DIR / f"{label}"

    csv_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(BASE_DIR / "scraper.py"),
        "--input", str(input_path),
        "--output", str(output_path),
        "--profile", str(profile_path),
        "--done", str(done_path),
    ]

    log_fh = open(log_file, "w", encoding="utf-8")

    print(f"  Starting: {label}")
    print(f"    CSV: {output_path}")
    print(f"    Log: {log_file}")

    proc = subprocess.Popen(
        cmd,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc, log_fh, label


def main():
    parser = argparse.ArgumentParser(
        description="Orchestrate parallel Google Maps scraping"
    )
    parser.add_argument(
        "--phase", type=int, required=True, choices=[1, 2, 3],
        help="Priority phase to run (1, 2, or 3)"
    )
    parser.add_argument(
        "--max-concurrent", type=int, default=3,
        help="Max concurrent scraper processes (default: 2)"
    )
    args = parser.parse_args()

    ensure_dirs()

    batch_dir = BATCHES_DIR / f"p{args.phase}"
    if not batch_dir.exists():
        print(f"Error: {batch_dir} not found. Run split_batches.py first.")
        sys.exit(1)
    batch_files = sorted([f.name for f in batch_dir.glob("*.txt")])
    if not batch_files:
        print(f"Error: No batch files found in {batch_dir}")
        sys.exit(1)
    max_workers = min(args.max_concurrent, len(batch_files))

    print(f"\n{'='*60}")
    print(f"Phase {args.phase}: {len(batch_files)} batches")
    print(f"Max concurrent: {max_workers}")
    print(f"{'='*60}\n")

    processes = {}
    completed = set()

    while len(completed) < len(batch_files):
        while len(processes) < max_workers:
            remaining = [b for b in batch_files if b not in completed and b not in processes]
            if not remaining:
                break
            batch = remaining[0]
            proc, log_fh, label = launch_scraper(batch, args.phase)
            processes[batch] = (proc, log_fh, label)

        if not processes:
            break

        finished = []
        for batch, (proc, log_fh, label) in processes.items():
            ret = proc.poll()
            if ret is not None:
                log_fh.close()
                status = "OK" if ret == 0 else f"FAILED (exit {ret})"
                print(f"  [{status}] {label}")
                finished.append(batch)
                completed.add(batch)

        for batch in finished:
            del processes[batch]

        write_progress(args.phase, batch_files, processes, completed)

        if processes:
            time.sleep(5)

    write_progress(args.phase, batch_files, {}, completed)

    print(f"\n{'='*60}")
    print(f"Phase {args.phase} complete — {len(completed)} batches done")
    print(f"{'='*60}")

    print("\nOutput files:")
    csv_dir = OUTPUT_DIR / "csv" / f"p{args.phase}"
    for batch in batch_files:
        label = batch_label(batch)
        csv_path = csv_dir / f"{label}.csv"
        count = 0
        if csv_path.exists():
            try:
                import pandas as pd
                df = pd.read_csv(csv_path)
                count = len(df)
            except:
                pass
        print(f"  {csv_path.name}: {count} leads")


if __name__ == "__main__":
    main()
