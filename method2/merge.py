import argparse
import pandas as pd
from pathlib import Path


def read_csvs(input_dir, pattern="*.csv"):
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

    phone_col = "phone"
    website_col = "website"
    email_col = "emails"

    if phone_col in df.columns:
        phone_pct = (df[phone_col].notna() & (df[phone_col] != "")).sum() / total_after * 100
    else:
        phone_pct = 0

    if website_col in df.columns:
        website_pct = (df[website_col].notna() & (df[website_col] != "")).sum() / total_after * 100
    else:
        website_pct = 0

    if email_col in df.columns:
        email_pct = (df[email_col].notna() & (df[email_col] != "")).sum() / total_after * 100
    else:
        email_pct = 0

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
        description="Merge method2 batch CSVs, deduplicate, and report quality"
    )
    parser.add_argument(
        "--input-dir", default=None,
        help="Directory containing batch CSV files (default: output/)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Output CSV file path (default: final.csv)"
    )
    parser.add_argument(
        "--pattern", default="batch_*.csv",
        help="Glob pattern for batch CSV files (default: batch_*.csv)"
    )
    args = parser.parse_args()

    base = Path(__file__).parent
    input_dir = args.input_dir or str(base / "output")
    output_path = args.output or str(base / "final.csv")

    df = read_csvs(input_dir, args.pattern)
    if df.empty:
        print("Nothing to merge.")
        return

    total_before = len(df)

    # Dedup on title+phone (gosom schema uses 'title' for name)
    dedup_cols = []
    for col in ["title", "name", "phone"]:
        if col in df.columns:
            dedup_cols.append(col)
    if not dedup_cols:
        print("No dedup columns found, using first row only")
        dedup_cols = [df.columns[0]]

    df.drop_duplicates(subset=dedup_cols, inplace=True, keep="first")
    df.reset_index(drop=True, inplace=True)

    stats = quality_report(df, total_before)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\nSaved: {output_path} ({len(df)} leads)")


if __name__ == "__main__":
    main()
