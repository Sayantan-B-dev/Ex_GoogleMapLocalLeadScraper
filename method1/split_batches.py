"""Split priority query files into per-city batch files under batches/p{1,2,3}/
   Naming: p{phase}_{City}.txt (e.g. p1_Mumbai.txt, p2_Goa.txt)"""
from pathlib import Path

BASE = Path(__file__).parent
BATCHES = BASE / "batches"

for priority in [1, 2, 3]:
    src = BASE / f"priority_{priority}_queries.txt"
    if not src.exists():
        print(f"  SKIP: {src.name} not found")
        continue
    dst = BATCHES / f"p{priority}"
    dst.mkdir(parents=True, exist_ok=True)

    # Clear old files
    for old in dst.glob("*.txt"):
        old.unlink()

    cities = {}
    with open(src, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            city = line.split(" ", 1)[0]
            cities.setdefault(city, []).append(line)

    for city, queries in sorted(cities.items()):
        filename = f"p{priority}_{city}.txt"
        out = dst / filename
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(queries) + "\n")
        print(f"  {out.name}: {len(queries)} queries")

    city_count = len(cities)
    print(f"  => {city_count} city files in {dst}/\n")
