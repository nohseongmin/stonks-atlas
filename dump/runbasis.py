"""베이시스 실행 — PREREG_BASIS.md.

현물이 있는 심볼만 남으므로 유니버스가 줄고, 그건 **그 자체로 편향**이다
(현물 미상장 코인은 대체로 더 작고 투기적이다). 사전등록에 적어뒀다.
"""
from __future__ import annotations

import math
import statistics as st

from .backtest import Bars, date_axis, run_cross_section
from .basis import build_basis, resid_rule
from .costs import BINANCE_USDM
from .experiment import BENCH, MIN_BARS, bench_curve, stress
from .feed import all_symbols, live_symbols, load_many, spot_closes
from .gate import (GateConfig, cagr, evaluate, max_drawdown, record, returns,
                   sharpe, trials)
from .oizoo import oi_rule
from .zoo import build, xs_rule


def spot_map(bars, axis):
    """심볼 -> {"spot": 축 정렬 현물 종가}. 현물이 없으면 그 심볼은 빠진다."""
    out = 0
    ext = {}
    for s in bars:
        cl = spot_closes(s, "1d")
        if not cl:
            continue
        row = [cl.get(t) for t in axis]
        if sum(1 for x in row if x is not None) >= MIN_BARS:
            ext[s] = {"spot": row}
            out += 1
    return ext, out


def main(argv: list[str] | None = None) -> int:
    cfg = GateConfig()
    every = load_many(all_symbols(), "1d", MIN_BARS)
    axis0 = date_axis(every)
    ext0, n = spot_map(every, axis0)
    print(f"현물 보유 {n} / {len(every)} — 나머지는 무기한 전용")

    bars = {s: b for s, b in every.items() if s in ext0}
    axis = date_axis(bars)
    ext = {s: {"spot": [ext0[s]["spot"][axis0.index(t)] for t in axis]}
           for s in bars}
    pit = bool(set(bars) - set(live_symbols()))
    bench = bench_curve(bars, axis, 100.0)
    bsr = sharpe(returns(bench), cfg.periods_per_year)
    print(f"유니버스 {len(bars)} · 축 {len(axis)} 일 · 시점정합 {pit}")
    print(f"같은 축 벤치 {BENCH} Sharpe {bsr:+.2f} · 통과선 "
          f"{bsr + cfg.min_margin_vs_bench:+.2f}\n")

    hard = stress(BINANCE_USDM, cfg.cost_stress_mult)
    specs = [(f.slug, oi_rule(f), f) for f in build_basis()]
    specs.append(("basis_resid", resid_rule(), None))

    rows = []
    for i, (slug, rule, f) in enumerate(specs, 1):
        r = run_cross_section(bars, rule, BINANCE_USDM, 100.0, 7, extra=ext)
        sr = sharpe(returns(r.equity), cfg.periods_per_year)
        record(f"BS_{slug}", {"factor": slug, "src": "basis"}, sr)
        rows.append({"slug": slug, "res": r, "sharpe": sr,
                     "rets": returns(r.equity)})
        print(f"{i}/{len(specs)} {slug:<14}Sharpe {sr:+.2f} · 연복리 "
              f"{cagr(r.equity, cfg.periods_per_year)*100:+7.1f}% · 낙폭 "
              f"{max_drawdown(r.equity)*100:5.1f}%"
              f"{'  <- 통과선 초과' if sr >= bsr + cfg.min_margin_vs_bench else ''}",
              flush=True)

    # 진단 — 베이시스가 펀딩의 변장인가. 사전등록의 반증 조건.
    from .runzoo import bench_window
    at = bench_window(bars, axis)
    fund = next(f for f in build() if f.slug == "funding_30")
    rf = run_cross_section(bars, xs_rule(fund, at), BINANCE_USDM, 100.0, 7)
    fr = returns(rf.equity)
    a = next(r["rets"] for r in rows if r["slug"] == "basis_7")
    m = min(len(a), len(fr))
    ma, mb = st.fmean(a[:m]), st.fmean(fr[:m])
    sa, sb = st.pstdev(a[:m]), st.pstdev(fr[:m])
    rho = (sum((x-ma)*(y-mb) for x, y in zip(a[:m], fr[:m]))/m/(sa*sb)
           if sa and sb else 0.0)
    print(f"\n진단: basis_7 ↔ funding_30 상관 **{rho:+.3f}**")
    print("   0.8 초과면 베이시스는 펀딩의 변장이고 새 정보원이 아니다 — "
          f"{'**변장이다**' if abs(rho) > 0.8 else '변장은 아니다'}")

    led = trials()
    spread = [t["sharpe"] for t in led]
    E = 0.5772156649015329
    floor = st.fmean(spread) + st.pstdev(spread) * (
        (1-E)*math.sqrt(2*math.log(len(led))) + E*math.sqrt(2*math.log(len(led)/math.e)))
    print(f"\n원장 {len(led)} 건 · **잡음바닥 {floor:+.2f}**")

    rows.sort(key=lambda x: -x["sharpe"])
    good = [r for r in rows if r["sharpe"] >= bsr + cfg.min_margin_vs_bench]
    print(f"\n④ 를 넘은 것 {len(good)} 개")
    for r in good:
        rule = dict((s, ru) for s, ru, _ in specs)[r["slug"]]
        srr = run_cross_section(bars, rule, hard, 100.0, 7, extra=ext)
        v = evaluate(r["res"], bench, srr, len(led), spread, pit, cfg)
        print(f"\n── BS_{r['slug']} — {'**통과**' if v.passed else '기각'}")
        for c in v.checks:
            print(f"   {'OK' if c.ok else '**NG**':<7}{c.name:<12}{c.detail}")
    if not good:
        print("  없음 — 전부 ④ 에서 기각")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
