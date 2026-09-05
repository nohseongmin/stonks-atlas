# 증거

각 시장의 **사전등록·결과·원장** 원본. 요약이 아니라 실행 당시 문서 그대로다.

| 폴더 | 내용 |
|---|---|
| `crypto/` | 사전등록 8 · 결과 8 · 정찰 기록 · **원장 130 시행**(`ledger.jsonl`) |
| `kr/` | 한국 사전등록 3 + STONKS-03 README·벤치마크·외부모델 목록 |
| `us/` | ai-stonks-v2 README (ORB 8 실험 · Alpha101 · 일봉스윙 전문) |

## 원장 읽는 법

```bash
python -c "
import json
seen = {}
for line in open('evidence/crypto/ledger.jsonl', encoding='utf-8'):
    if line.strip():
        r = json.loads(line); seen[r['fp']] = r
rows = sorted(seen.values(), key=lambda r: -r['sharpe'])
print(f'고유 시행 {len(seen)}')
for r in rows[:15]:
    print(f\"  {r['name']:<26}{r['sharpe']:+.2f}\")
"
```

**지문(`fp`)으로 중복을 제거한다.** 같은 규칙 재실행은 새 시행이 아니다.
기각도 전부 들어 있다 — 안 넣으면 다중검정 벌점이 거짓말이 된다.
