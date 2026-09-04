"""오픈인터레스트·롱숏비율 수집 — **가격에서 안 나오는 정보.**

109 시행이 전부 OHLCV + 펀딩 + 테이커였다. 이건 처음으로 **포지션** 자료다.
누가 얼마나 들고 있고, 그게 개인인지 상위 트레이더인지.

## 왜 따로 받나

`data/futures/um/daily/metrics/` 는 **일별 파일만** 있다(월별 묶음 없음).
하루치가 5 분봉 288 행 · 11KB. 전 유니버스면 60 만 요청, 6GB 다.

그래서 **원본을 안 남긴다.** 받아서 일별 요약으로 접고 심볼당 JSON 하나만 쓴다.
디스크 6GB → 수 MB.

## 필드

| CSV 열 | 뜻 | 접는 법 |
|---|---|---|
| `sum_open_interest_value` | 미결제약정 (USD) | **종가 시점 값** |
| `count_toptrader_long_short_ratio` | 상위 트레이더 계정 롱숏비 | 하루 평균 |
| `count_long_short_ratio` | **전체 계정** 롱숏비 (= 개인) | 하루 평균 |
| `sum_taker_long_short_vol_ratio` | 테이커 롱숏 거래량비 | 하루 평균 |

`count_toptrader` 와 `count_long_short` 의 **차이**가 이른바 스마트-덤 스프레드다.
"""
from __future__ import annotations

import csv
import io
import json
import statistics as st
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree

from .feed import CACHE, DUMP, NS, S3, TIMEOUT, _q

PREFIX = "data/futures/um/daily/metrics"
OUT = CACHE / "oi"


def days(symbol: str) -> list[str]:
    """그 심볼의 metrics 파일이 있는 날짜(`YYYY-MM-DD`) 목록."""
    out, token = [], None
    pre = f"{PREFIX}/{_q(symbol)}/"
    while True:
        url = f"{S3}?list-type=2&prefix={pre}"
        if token:
            url += f"&continuation-token={urllib.parse.quote(token, safe='')}"
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            root = ElementTree.fromstring(r.read())
        for k in root.findall(f"{NS}Contents/{NS}Key"):
            n = k.text.rsplit("/", 1)[-1]
            if n.endswith(".zip"):
                out.append(n[:-4].rsplit("-", 3)[-3:])
        token = root.findtext(f"{NS}NextContinuationToken")
        if not token:
            return sorted("-".join(p) for p in out)


def _fold(blob: bytes) -> list[float] | None:
    """5 분봉 하루치를 숫자 넷으로 접는다. 빈 파일이면 None."""
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        raw = z.read(z.namelist()[0]).decode("utf-8")
    rows = list(csv.reader(io.StringIO(raw)))
    if rows and not rows[0][0][:1].isdigit():
        rows = rows[1:]
    oi, top, acct, taker = [], [], [], []
    for r in rows:
        if len(r) < 8:
            continue
        try:
            oi.append(float(r[3]))
            top.append(float(r[4]))
            acct.append(float(r[6]))
            taker.append(float(r[7]))
        except ValueError:
            continue
    if not oi:
        return None
    # OI 는 **하루 마지막 값**(스톡), 비율은 평균(플로우).
    return [oi[-1], st.fmean(top), st.fmean(acct), st.fmean(taker)]


def collect(symbol: str) -> dict:
    """심볼 하나의 전 기간. 이미 받은 날은 건너뛴다(재실행 가능)."""
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{urllib.parse.quote(symbol, safe='')}.json"
    have = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    todo = [d for d in days(symbol) if d not in have]
    for d in todo:
        fn = f"{symbol}-metrics-{d}.zip"
        url = f"{DUMP}/{PREFIX}/{_q(symbol)}/{_q(fn)}"
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
                v = _fold(r.read())
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            v = None
        if v:
            have[d] = v
    if todo:
        p.write_text(json.dumps(have, separators=(",", ":")), encoding="utf-8")
    return have


def warm(symbols: list[str], workers: int = 24) -> dict:
    """병렬 수집. 실패는 **모으고 계속한다** — 하나가 죽어도 전체가 멈추면 안 된다."""
    bad, done = {}, {"n": 0, "days": 0}

    def one(s):
        try:
            r = collect(s)
            done["n"] += 1
            done["days"] += len(r)
            if done["n"] % 50 == 0:
                print(f"  {done['n']}/{len(symbols)} 심볼 · 누적 {done['days']:,} 일",
                      flush=True)
        except Exception as e:                      # noqa: BLE001
            bad[s] = f"{type(e).__name__}: {e}"

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, symbols))
    return {"symbols": done["n"], "days": done["days"], "failed": bad}


def load(symbol: str) -> dict:
    """수집된 일별 요약. 없으면 빈 dict."""
    p = OUT / f"{urllib.parse.quote(symbol, safe='')}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def main(argv: list[str] | None = None) -> int:
    from .feed import all_symbols
    syms = all_symbols()
    print(f"오픈인터레스트 수집 시작 — 심볼 {len(syms)}")
    print("일별 파일만 있어 요청이 많다. 원본은 안 남기고 일별 요약만 저장한다.\n")
    r = warm(syms)
    print(f"\n완료 — 심볼 {r['symbols']} · 총 {r['days']:,} 일 · 실패 {len(r['failed'])}")
    for s, e in list(r["failed"].items())[:5]:
        print(" ", s, e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
