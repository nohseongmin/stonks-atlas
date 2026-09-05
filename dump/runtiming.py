"""타이밍 실행 — PREREG_TIMING.md. BTCUSDT 단일 자산."""
from __future__ import annotations

import math
import statistics as st

from .backtest import run
from .costs import BINANCE_USDM
from .experiment import BENCH, MIN_BARS, stress
from .feed import all_symbols, load_many
from .gate import (GateConfig, cagr, evaluate, max_drawdown, record, returns,
                   sharpe, trials)
from .timing import build_timing


def main(argv: list[str] | None = None) -> int:
    cfg = GateConfig()
    bars = load_many([BENCH], "1d", MIN_BARS)[BENCH]
    hold = run(bars, lambda t, p: 1.0, BINANCE_USDM, 100.0)
    bsr = sharpe(returns(hold.equity), cfg.periods_per_year)
    print(f"{BENCH} {len(bars)} 봉 · 매수보유 Sharpe {bsr:+.2f} · 연복리 "
          f"{cagr(hold.equity, cfg.periods_per_year)*100:+.1f}% · 낙폭 "
          f"{max_drawdown(hold.equity)*100:.0f}%")
    print(f"통과선 {bsr + cfg.min_margin_vs_bench:+.2f}\n")

    hard = stress(BINANCE_USDM, cfg.cost_stress_mult)
    rows = []
    for i, (slug, rule) in enumerate(build_timing(), 1):
        r = run(bars, rule, BINANCE_USDM, 100.0)
        sr = sharpe(returns(r.equity), cfg.periods_per_year)
        record(f"TM_{slug}", {"factor": slug, "src": "timing"}, sr)
        rows.append({"slug": slug, "rule": rule, "res": r, "sharpe": sr})
        print(f"{i}/7 {slug:<15}Sharpe {sr:+.2f} · 연복리 "
              f"{cagr(r.equity, cfg.periods_per_year)*100:+7.1f}% · 낙폭 "
              f"{max_drawdown(r.equity)*100:5.1f}% · 거래 {r.trades:>4}"
              f"{'  <- 통과선 초과' if sr >= bsr + cfg.min_margin_vs_bench else ''}",
              flush=True)

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
        s = run(bars, r["rule"], hard, 100.0)
        v = evaluate(r["res"], hold.equity, s, len(led), spread, True, cfg)
        print(f"\n── TM_{r['slug']} — {'**통과**' if v.passed else '기각'}")
        for c in v.checks:
            print(f"   {'OK' if c.ok else '**NG**':<7}{c.name:<12}{c.detail}")
    if not good:
        print("  없음 — 전부 ④ 에서 기각")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
