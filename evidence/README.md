# Evidence

Original preregistrations, results, reconnaissance records, and trial ledgers by market. The overview READMEs have been edited for English readability; the underlying records remain the evidence.

| Directory | Contents |
|---|---|
| `crypto/` | Eight preregistrations, eight results, reconnaissance, and a 130-trial ledger |
| `kr/` | Three Korean-market preregistrations and the STONKS-03 overview, benchmarks, and model catalog |
| `us/` | AI-STONKS v2 overview, ORB experiments, Alpha101, and daily swing research |

## Reading the ledger

Run this Python snippet from the repository root:

```python
import json

seen = {}
with open("evidence/crypto/ledger.jsonl", encoding="utf-8") as ledger:
    for line in ledger:
        if line.strip():
            record = json.loads(line)
            seen[record["fp"]] = record

rows = sorted(seen.values(), key=lambda record: -record["sharpe"])
print(f"Unique trials: {len(seen)}")
for record in rows[:15]:
    print(f"  {record['name']:<26}{record['sharpe']:+.2f}")
```

The fingerprint, `fp`, deduplicates reruns of the same rule. Rejected trials are retained so multiple-testing corrections count the full search.
