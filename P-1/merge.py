import argparse
import pandas as pd
from pathlib import Path


def read_batch_csvs(input_dir, pattern="*.csv"):
    dir_path = Path(input_dir)
    files = sorted(dir_path.glob(pattern))
    if not files:
        print(f"No CSV files found in {input_dir}")
        return pd.DataFrame()
    print(f"Found {len(files)} CSV files")
    frames = []
    for f in files:
        try:
            df = pd.read_csv(f, encoding="utf-8-sig")
            frames.append(df)
            print(f"  {f.name}: {len(df)} rows")
        except Exception as e:
            print(f"  {f.name}: ERROR — {e}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def quality_report(df, total_before):
    total_after = len(df)
    duplicates = total_before - total_after
    dup_pct = (duplicates / total_before * 100) if total_before else 0
    phone_pct = (df["phone"].notna() & (df["phone"] != "")).sum() / total_after * 100 if total_after else 0
    website_pct = (df["website"].notna() & (df["website"] != "")).sum() / total_after * 100 if total_after else 0
    email_pct = (df["email"].notna() & (df["email"] != "")).sum() / total_after * 100 if total_after else 0

    print(f"\n{'='*50}")
    print("QUALITY REPORT")
    print(f"{'='*50}")
    print(f"  Total rows before dedup:   {total_before}")
    print(f"  Total rows after dedup:    {total_after}")
    print(f"  Duplicates removed:        {duplicates} ({dup_pct:.1f}%)")
    print(f"  With phone:                {phone_pct:.1f}%")
    print(f"  With website:              {website_pct:.1f}%")
    print(f"  With email:                {email_pct:.1f}%")
    print(f"{'='*50}")
    return {
        "total_before": total_before,
        "total_after": total_after,
        "duplicates": duplicates,
        "dup_pct": round(dup_pct, 1),
        "phone_pct": round(phone_pct, 1),
        "website_pct": round(website_pct, 1),
        "email_pct": round(email_pct, 1),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Merge batch CSVs, deduplicate, and report quality"
    )
    parser.add_argument(
        "--input-dir", default=None,
        help="Directory containing batch CSV files (default: output/)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Output CSV file path (default: priority_final.csv)"
    )
    parser.add_argument(
        "--pattern", default="p*_batch_*.csv",
        help="Glob pattern for batch CSV files (default: p*_batch_*.csv)"
    )
    args = parser.parse_args()

    base = Path(__file__).parent
    input_dir = args.input_dir or str(base / "output")
    output_path = args.output or str(base / "priority_final.csv")

    df = read_batch_csvs(input_dir, args.pattern)
    if df.empty:
        print("Nothing to merge.")
        return

    total_before = len(df)
    required_cols = ["name", "phone", "address"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"Warning: missing columns {missing}, dedup may be incomplete")
        dedup_cols = [c for c in required_cols if c in df.columns]
    else:
        dedup_cols = required_cols

    df.drop_duplicates(subset=dedup_cols, inplace=True, keep="first")
    df.reset_index(drop=True, inplace=True)

    stats = quality_report(df, total_before)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\nSaved: {output_path} ({len(df)} leads)")


if __name__ == "__main__":
    main()
