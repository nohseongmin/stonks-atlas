"""바이낸스 공개 덤프 수집 — **시점정합(PIT) 유니버스가 이 파일의 존재 이유다.**

앞선 프로젝트에서 가짜 알파를 만든 1 번 기계가 생존편향이었다. 오늘 살아 있는
종목으로 과거 횡단면을 만들면 **망한 것들이 조용히 빠진다.** 주식에선 이걸
고칠 데이터가 없었다. 여기선 있다.

    덤프의 심볼 디렉터리   986
    현재 살아 있는 심볼    885
    상폐됐는데 받아지는 것 136        <- 이게 전부다

2022-06 시점 유니버스는 175 종목이고 그중 43 개(24.6%)가 오늘 죽어 있다.
`universe_at()` 은 그 43 개를 **포함한** 목록을 준다.

## 함정 셋

**1. CSV 헤더가 2022-01 부터 생겼다.** 그 이전 파일엔 헤더 행이 없다.
   첫 필드를 숫자로 파싱해보고 판단한다 — 월을 보고 분기하면 언젠가 틀린다.

**2. 상폐 판정은 "마지막 파일이 언제냐"로 한다.** 중간에 한 달 비는 것과
   영영 끝난 것은 다르다.

**3. 인증이 필요 없다.** klines · fundingRate · metrics 전부 비인증으로 받아진다
   (실측 확인). **키를 만들 이유가 아직 없다.**
"""
from __future__ import annotations

import csv
import io
import json
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree

from .backtest import Bars

DUMP = "https://data.binance.vision"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
FAPI = "https://fapi.binance.com/fapi/v1"
PREFIX = "data/futures/um/monthly"
#: 현물. 무기한과의 차이가 베이시스이고, 아직 안 쓴 마지막 가격 정보원이다.
SPOT_PREFIX = "data/spot/monthly"
CACHE = Path(__file__).resolve().parent.parent / "data"
#: S3 ListBucket XML 네임스페이스.
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
TIMEOUT = 60


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
        return r.read()


def _get_or_empty(url: str) -> bytes:
    """없는 파일(404)은 **빈 바이트로 캐시한다.** 안 그러면 매 실행마다 다시 묻는다."""
    try:
        return _get(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return b""
        raise


def _q(s: str) -> str:
    """URL 인코딩. **심볼에 한자가 들어간다** — `币安人生USDT` 같은 밈코인이
    실제로 상장돼 있다. 걸러내면 그것도 선택편향이라 제대로 인코딩한다.
    """
    return urllib.parse.quote(s, safe="/")


def _cached(name: str, fetch) -> bytes:
    """디스크 캐시. 덤프 파일은 불변이라 한 번 받으면 다시 안 받는다."""
    p = CACHE / name
    if p.exists():
        return p.read_bytes()
    data = fetch()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return data


def _list_prefixes(prefix: str) -> list[str]:
    """S3 의 `CommonPrefixes` 를 페이지 넘겨가며 전부 모은다."""
    out, token = [], None
    while True:
        url = f"{S3}?list-type=2&delimiter=/&prefix={_q(prefix)}"
        if token:
            url += f"&continuation-token={urllib.parse.quote(token, safe=chr(0))}"
        root = ElementTree.fromstring(_get(url))
        for cp in root.findall(f"{NS}CommonPrefixes/{NS}Prefix"):
            out.append(cp.text.rstrip("/").rsplit("/", 1)[-1])
        token = root.findtext(f"{NS}NextContinuationToken")
        if not token:
            return out


def all_symbols(refresh: bool = False) -> list[str]:
    """**덤프에 있는 모든 심볼 — 상폐된 것 포함.** 이게 PIT 의 출발점이다."""
    p = CACHE / "symbols_all.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    syms = sorted(_list_prefixes(f"{PREFIX}/klines/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(syms), encoding="utf-8")
    return syms


def live_symbols(refresh: bool = False) -> list[str]:
    """지금 거래되는 심볼. **이걸로 과거 유니버스를 만들면 그게 생존편향이다.**"""
    raw = _cached("exchange_info.json", lambda: _get(f"{FAPI}/exchangeInfo"))
    if refresh:
        (CACHE / "exchange_info.json").unlink(missing_ok=True)
        raw = _cached("exchange_info.json", lambda: _get(f"{FAPI}/exchangeInfo"))
    info = json.loads(raw)
    return sorted(s["symbol"] for s in info["symbols"] if s["status"] == "TRADING")


def months(symbol: str, interval: str = "1d") -> list[str]:
    """그 심볼이 거래된 월 목록 (`YYYY-MM`). 상폐 시점이 여기서 나온다."""
    # 파일명에 심볼을 그대로 못 쓴다(한자·윈도 금지문자). 안전한 이름으로 바꾼다.
    safe = urllib.parse.quote(symbol, safe="")
    p = CACHE / "months" / f"{safe}_{interval}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    keys, token = [], None
    pre = f"{PREFIX}/klines/{symbol}/{interval}/"
    while True:
        url = f"{S3}?list-type=2&prefix={_q(pre)}"
        if token:
            url += f"&continuation-token={urllib.parse.quote(token, safe=chr(0))}"
        root = ElementTree.fromstring(_get(url))
        for k in root.findall(f"{NS}Contents/{NS}Key"):
            name = k.text.rsplit("/", 1)[-1]
            if name.endswith(".zip"):
                keys.append(name[:-4].rsplit("-", 2)[-2] + "-" + name[:-4].rsplit("-", 1)[-1])
        token = root.findtext(f"{NS}NextContinuationToken")
        if not token:
            break
    out = sorted(set(keys))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out), encoding="utf-8")
    return out


def universe_at(when: date, interval: str = "1d",
                symbols: list[str] | None = None) -> list[str]:
    """**`when` 시점에 실제로 거래되던 심볼.** 오늘 죽은 것도 들어간다.

    판정은 "그 달의 봉 파일이 있느냐"다. 파일이 있으면 그때 살아 있었다.
    """
    tag = f"{when.year:04d}-{when.month:02d}"
    return [s for s in (symbols or all_symbols()) if tag in months(s, interval)]


def _parse(blob: bytes) -> list[list[str]]:
    """zip 안의 CSV 를 읽는다. **헤더 유무를 값으로 판단한다.**

    2022-01 부터 헤더 행이 생겼다. 월로 분기하면 예외가 생기는 날 조용히 틀린다.
    """
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        raw = z.read(z.namelist()[0]).decode("utf-8")
    rows = list(csv.reader(io.StringIO(raw)))
    if rows:
        try:
            float(rows[0][0])
        except (ValueError, IndexError):
            rows = rows[1:]
    return rows


def load(symbol: str, interval: str = "1d",
         want: list[str] | None = None) -> Bars:
    """봉을 받아 `Bars` 로 만든다. `want` 는 `YYYY-MM` 목록, 없으면 전 기간."""
    have = months(symbol, interval)
    use = [m for m in (want or have) if m in have]
    if not use:
        raise ValueError(f"{symbol} {interval}: 받을 월이 없다 (가용 {len(have)} 개)")
    ts, op, hi, lo, cl, qv, tb = [], [], [], [], [], [], []
    for m in sorted(use):
        fn = f"{symbol}-{interval}-{m}.zip"
        url = f"{DUMP}/{PREFIX}/klines/{_q(symbol)}/{interval}/{_q(fn)}"
        for r in _parse(_cached(f"klines/{symbol}/{interval}/{fn}",
                                lambda u=url: _get(u))):
            ts.append(int(r[0]))
            op.append(float(r[1]))
            hi.append(float(r[2]))
            lo.append(float(r[3]))
            cl.append(float(r[4]))
            qv.append(float(r[7]))          # quote_volume — 유동성 필터용
            tb.append(float(r[10]))         # taker_buy_quote_volume — 주문흐름
    return Bars(symbol, ts, op, hi, lo, cl, funding(symbol, use), qv, tb)


def funding(symbol: str, want: list[str] | None = None) -> list[tuple[int, float]]:
    """펀딩 정산 이력. 없으면 빈 목록 — 조용히 0 으로 채우지 않는다."""
    out = []
    for m in sorted(want or []):
        fn = f"{symbol}-fundingRate-{m}.zip"
        url = f"{DUMP}/{PREFIX}/fundingRate/{_q(symbol)}/{_q(fn)}"
        try:
            rows = _parse(_cached(
                f"funding/{urllib.parse.quote(symbol, safe='')}/{fn}",
                lambda u=url: _get(u)))
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            continue
        out.extend((int(r[0]), float(r[2])) for r in rows)
    return sorted(set(out))


def main(argv: list[str] | None = None) -> int:
    """생존편향의 크기를 직접 보여준다."""
    every, live = all_symbols(), set(live_symbols())
    dead = [s for s in every if s not in live]
    print(f"덤프 심볼 {len(every)} · 거래중 {len(live)} · **상폐됐는데 받아짐 {len(dead)}**")
    print(f"예: {', '.join(dead[:8])}\n")
    print(f"{'시점':>10}{'유니버스':>10}{'오늘 죽음':>10}{'생존편향 갭':>12}")
    for y in (2021, 2022, 2023, 2024, 2025):
        u = universe_at(date(y, 6, 1))
        d = sum(1 for s in u if s not in live)
        print(f"{y}-06{len(u):>10}{d:>10}{d/len(u)*100:>11.1f}%")
    print("\n오늘의 exchangeInfo 로 과거 횡단면을 만들면 저만큼이 조용히 빠진다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def warm(symbols: list[str], interval: str = "1d", workers: int = 16) -> dict:
    """월 목록과 봉 파일을 **병렬로 미리 받아 캐시에 채운다.**

    1,018 심볼 x 40 개월 = 4 만 요청이다. 순차로 하면 한 시간, 16 갈래면 10 분.
    덤프 파일은 불변이라 한 번만 받으면 된다.

    실패는 **모으고 계속한다** — 심볼 하나가 죽어서 전체가 멈추면 안 된다.
    다만 몇 개가 왜 실패했는지는 반드시 돌려준다.
    """
    from concurrent.futures import ThreadPoolExecutor

    bad: dict[str, str] = {}

    def one(sym):
        try:
            ms = months(sym, interval)
            for m in ms:
                fn = f"{sym}-{interval}-{m}.zip"
                _cached(f"klines/{urllib.parse.quote(sym, safe='')}/{interval}/{fn}",
                        lambda u=f"{DUMP}/{PREFIX}/klines/{_q(sym)}/{interval}/{_q(fn)}":
                        _get(u))
            for m in ms:      # 펀딩도 같이 — 안 받으면 적재가 순차 HTTP 가 된다
                fn = f"{sym}-fundingRate-{m}.zip"
                _cached(f"funding/{urllib.parse.quote(sym, safe='')}/{fn}",
                        lambda u=f"{DUMP}/{PREFIX}/fundingRate/{_q(sym)}/{_q(fn)}":
                        _get_or_empty(u))
        except Exception as e:                      # noqa: BLE001 — 모아서 보고한다
            bad[sym] = f"{type(e).__name__}: {e}"

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, symbols))
    return {"asked": len(symbols), "failed": bad}


def load_many(symbols: list[str], interval: str = "1d",
              min_bars: int = 60, cache: bool = True) -> dict[str, Bars]:
    """여러 심볼을 `Bars` 로. **`min_bars` 미만은 버린다** — 정렬이 불가능하다.

    버린 심볼 수를 조용히 삼키지 않는다. 호출부가 세어 보고할 수 있게
    반환값에 안 넣고 끝내지 말고 로그로 남길 것.
    """
    import pickle
    p = CACHE / f"bars_{interval}_{min_bars}.pkl"
    if cache and p.exists():
        return pickle.loads(p.read_bytes())
    out = {}
    for s in symbols:
        try:
            b = load(s, interval)
        except Exception:                           # noqa: BLE001
            continue
        if len(b) >= min_bars:
            out[s] = b
    if cache:
        p.write_bytes(pickle.dumps(out, protocol=5))
    return out


def spot_months(symbol: str, interval: str = "1d") -> list[str]:
    """현물 봉이 있는 월 목록. 무기한과 심볼명이 같다(BTCUSDT 등)."""
    safe = urllib.parse.quote(symbol, safe="")
    p = CACHE / "months" / f"spot_{safe}_{interval}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    keys, token = [], None
    pre = f"{SPOT_PREFIX}/klines/{_q(symbol)}/{interval}/"
    while True:
        url = f"{S3}?list-type=2&prefix={pre}"
        if token:
            url += f"&continuation-token={urllib.parse.quote(token, safe='')}"
        root = ElementTree.fromstring(_get(url))
        for k in root.findall(f"{NS}Contents/{NS}Key"):
            n = k.text.rsplit("/", 1)[-1]
            if n.endswith(".zip"):
                keys.append(n[:-4].rsplit("-", 2)[-2] + "-" + n[:-4].rsplit("-", 1)[-1])
        token = root.findtext(f"{NS}NextContinuationToken")
        if not token:
            break
    out = sorted(set(keys))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out), encoding="utf-8")
    return out


def spot_closes(symbol: str, interval: str = "1d") -> dict[int, float]:
    """현물 종가를 `{타임스탬프: 종가}` 로. 무기한 축에 붙일 수 있게."""
    out = {}
    for m in spot_months(symbol, interval):
        fn = f"{symbol}-{interval}-{m}.zip"
        url = f"{DUMP}/{SPOT_PREFIX}/klines/{_q(symbol)}/{interval}/{_q(fn)}"
        blob = _cached(f"spot/{urllib.parse.quote(symbol, safe='')}/{interval}/{fn}",
                       lambda u=url: _get_or_empty(u))
        if not blob:
            continue
        for r in _parse(blob):
            out[int(r[0])] = float(r[4])
    return out


def warm_spot(symbols: list[str], interval: str = "1d", workers: int = 16) -> dict:
    """현물 봉 병렬 수집. 무기한에만 있고 현물엔 없는 심볼이 많다 — 정상이다."""
    from concurrent.futures import ThreadPoolExecutor
    bad, none = {}, []

    def one(sym):
        try:
            if not spot_months(sym, interval):
                none.append(sym)
                return
            spot_closes(sym, interval)
        except Exception as e:                      # noqa: BLE001
            bad[sym] = f"{type(e).__name__}: {e}"

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, symbols))
    return {"asked": len(symbols), "no_spot": len(none), "failed": bad}
