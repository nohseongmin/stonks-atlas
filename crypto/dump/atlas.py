"""전략 지도 — **통과자를 찾는 게 아니라 공간의 구조를 잰다.**

시행 119 건에 잡음바닥이 1.94 다. 벤치가 0.90 이니 통과하려면 여유 +1.04 가
필요한데, 외부 실증 최고가 1.04 였다. **후향 관문은 사실상 통과 불가 상태**다.

그 상태에서 팩터를 더 태우는 건 관문을 더 무의미하게 만들 뿐이다.
그래서 산출물을 바꾼다:

1. **모든 전략을 같은 축에 올려** 수익 계열을 저장한다
2. **전체 상관 구조**와 실효차원을 잰다 — 카탈로그 전체에 정보가 얼마나 있나
3. **정보원별 합성**을 만들어 정보원 사이 상관을 잰다

3 번이 핵심이다. `#2` 에서 무상관 두 다리를 섞어 Sharpe 가 올라갔다.
정보원이 서로 무상관이면 같은 일이 더 크게 일어날 수 있고,
상관이 높으면 **"네 종류를 다 썼다"는 말이 허구**였다는 뜻이다.

정보원별 합성은 **선택을 안 한다** — 그 정보원의 전 팩터 수익을 동일가중
평균한다. 최고를 고르면 그게 선택편향이다.
"""
from __future__ import annotations

import json
import math
import pickle
import statistics as st
from pathlib import Path

from .backtest import Bars, date_axis, run_cross_section
from .costs import BINANCE_USDM
from .experiment import BENCH, MIN_BARS, bench_curve
from .feed import CACHE, all_symbols, live_symbols, load_many
from .gate import GateConfig, cagr, max_drawdown, returns, sharpe
from .oi import load as load_oi
from .oizoo import build_oi, oi_rule
from .runoi import align, first_usable
from .runzoo import bench_window, effective_dims
from .strategies import MIN_NAMES
from .zoo import build, build2, build3, xs_rule

CFG = GateConfig()
SERIES = CACHE / "series.pkl"

#: 팩터 -> 정보원. **가격에서 나온 것과 아닌 것을 갈라야 지도가 의미를 갖는다.**
SOURCE = {
    "flow": {"taker_imb_7", "taker_imb_30", "taker_imb_chg"},
    "carry": {"funding_7", "funding_30", "funding_chg", "funding_adj_mom",
              "funding_z_90"},
}


def source_of(slug: str) -> str:
    if slug.startswith(("oi_", "lsr_", "taker_ls")):
        return "position"
    for name, members in SOURCE.items():
        if slug in members:
            return name
    return "price"


def build_all() -> dict:
    """전 전략을 **같은 축**에 올려 돌리고 수익 계열을 저장한다.

    포지션 자료가 2021-12 부터라 축을 거기 맞춘다. 가격 팩터의 Sharpe 는
    앞 배치와 달라지지만 **상관을 재려면 축이 같아야 한다.**
    """
    if SERIES.exists():
        return pickle.loads(SERIES.read_bytes())

    bars = load_many(all_symbols(), "1d", MIN_BARS)
    axis = date_axis(bars)
    ext_full = align(bars, axis)
    cut = axis[first_usable(ext_full, axis, MIN_NAMES)]

    sub = {}
    for s, b in bars.items():
        keep = [i for i, t in enumerate(b.ts) if t >= cut]
        if len(keep) < MIN_BARS:
            continue
        a, z = keep[0], keep[-1] + 1
        sub[s] = Bars(s, b.ts[a:z], b.open[a:z], b.high[a:z], b.low[a:z],
                      b.close[a:z], [f for f in b.funding if f[0] >= cut],
                      b.qvol[a:z], b.tbuy[a:z])
    saxis = date_axis(sub)
    sext = align(sub, saxis)
    at = bench_window(sub, saxis)
    bench = bench_curve(sub, saxis, 100.0)

    out = {"bench": returns(bench), "axis": len(saxis), "n": len(sub), "f": {}}
    price = build() + build2() + build3()
    print(f"같은 축({len(saxis)} 일, {len(sub)} 종목)에서 "
          f"{len(price) + len(build_oi())} 전략 실행", flush=True)
    for i, f in enumerate(price, 1):
        r = run_cross_section(sub, xs_rule(f, at), BINANCE_USDM, 100.0, 7)
        out["f"][f.slug] = returns(r.equity)
        if i % 10 == 0:
            print(f"  가격계 {i}/{len(price)}", flush=True)
    for i, f in enumerate(build_oi(), 1):
        r = run_cross_section(sub, oi_rule(f), BINANCE_USDM, 100.0, 7, extra=sext)
        out["f"][f.slug] = returns(r.equity)
    print(f"  포지션계 {len(build_oi())}/{len(build_oi())}", flush=True)

    SERIES.write_bytes(pickle.dumps(out, protocol=5))
    return out


def corr(a, b) -> float:
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    ma, mb = st.fmean(a[:n]), st.fmean(b[:n])
    sa, sb = st.pstdev(a[:n]), st.pstdev(b[:n])
    if not sa or not sb:
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a[:n], b[:n])) / n / (sa * sb)


def composite(series: list[list[float]]) -> list[float]:
    """동일가중 합성. **최고를 고르지 않는다** — 고르면 선택편향이다."""
    n = min(len(s) for s in series)
    return [st.fmean([s[i] for s in series]) for i in range(n)]


def main(argv: list[str] | None = None) -> int:
    d = build_all()
    bench = d["bench"]
    bsr = sharpe(bench, CFG.periods_per_year)
    slugs = sorted(d["f"])
    print(f"\n축 {d['axis']} 일 · 유니버스 {d['n']} · 전략 {len(slugs)}")
    print(f"같은 축 벤치 {BENCH} Sharpe {bsr:+.2f}\n")

    print("=" * 72)
    print("1) 카탈로그 전체 실효차원")
    dims = effective_dims([d["f"][s] for s in slugs])
    print(f"   {dims:.1f} / {len(slugs)} 전략 "
          f"(= {len(slugs)} 개를 태워 {dims:.1f} 개 베팅어치)")

    print("\n2) 정보원별")
    by = {}
    for s in slugs:
        by.setdefault(source_of(s), []).append(s)
    comps = {}
    for src in sorted(by):
        ss = by[src]
        c = composite([d["f"][x] for x in ss])
        comps[src] = c
        sd = effective_dims([d["f"][x] for x in ss]) if len(ss) > 1 else 1.0
        print(f"   {src:<10}{len(ss):>3} 전략 · 실효차원 {sd:4.1f} "
              f"(비율 {sd/len(ss):.2f}) · 합성 Sharpe "
              f"{sharpe(c, CFG.periods_per_year):+.2f}")

    print("\n3) 정보원 사이 상관 — **네 종류를 정말 다 썼나**")
    keys = sorted(comps)
    print("   " + " " * 10 + "".join(f"{k:>11}" for k in keys) + f"{'벤치':>11}")
    for a in keys:
        row = "".join(f"{corr(comps[a], comps[b]):>11.3f}" for b in keys)
        print(f"   {a:<10}{row}{corr(comps[a], bench):>11.3f}")

    print("\n4) 전 정보원 합성 (동일가중, 선택 없음)")
    allc = composite(list(comps.values()))
    print(f"   Sharpe {sharpe(allc, CFG.periods_per_year):+.2f} vs 벤치 {bsr:+.2f}")
    best = max(comps, key=lambda k: sharpe(comps[k], CFG.periods_per_year))
    print(f"   최고 단일 정보원: {best} "
          f"{sharpe(comps[best], CFG.periods_per_year):+.2f}")

    print("\n5) 같은 축에서 상위 10")
    rank = sorted(slugs, key=lambda s: -sharpe(d["f"][s], CFG.periods_per_year))
    for s in rank[:10]:
        print(f"   {s:<16}{sharpe(d['f'][s], CFG.periods_per_year):+.2f}  "
              f"[{source_of(s)}]")

    (CACHE / "atlas.json").write_text(json.dumps({
        "dims": dims, "n": len(slugs), "bench": bsr,
        "sources": {k: sharpe(v, CFG.periods_per_year) for k, v in comps.items()},
        "cross": {a: {b: corr(comps[a], comps[b]) for b in keys} for a in keys},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
