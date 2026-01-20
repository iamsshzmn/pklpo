import json
from collections import Counter

path = "docs/query_result_2025-11-19T09_21_49.83166435Z.json"
data = json.load(open(path, encoding="utf-8"))
rows = len(data)
counts: Counter[str] = Counter()
for row in data:
    for key, value in row.items():
        if value in (None, "", "NaN", "nan"):
            counts[key] += 1
missing = sorted(counts.items(), key=lambda x: x[1], reverse=True)
print("rows", rows)
print("columns with >0 missing (top 40):")
for key, count in missing[:40]:
    if count > 0:
        print(f"{key}: {count}")
