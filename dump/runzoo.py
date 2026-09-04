"""동물원 실행 — PREREG_ZOO.md 그대로. **전부 돌리고 전부 기록한다.**

상위 몇 개만 보고하지 않는다. 전체 분포가 이 검정의 산출물이다.
"""
from __future__ import annotations

import math
import statistics as st

from .backtest import date_axis, run_cross_section
from .costs import BINANCE_USDM
from .experiment import BENCH, MIN_BARS, bench_curve, stress
from .feed import all_symbols, live_symbols, load_many
from .gate import (GateConfig, cagr, evaluate, max_drawdown, record, returns,
                   sharpe, trials)
from .zoo import build, build2, xs_rule

BETA_WINDOW = 60


def bench_window(bars, axis):
    """t 시점까지의 벤치 일간수익 마지막 `BETA_WINDOW` 개. 베타·특이변동성용."""
    b = bars[BENCH]
    pos = {t: i for i, t in enumerate(b.ts)}
    px, last = [], None
    for t in axis:
        i = pos.get(t)
        if i is not None:
            last = b.close[i]
        px.append(last)
    first = next(v for v in px if v is not None)
    px = [v if v is not None else first for v in px]

    def at(t):
        if t < BETA_WINDOW + 1:
            return None
        w = px[t - BETA_WINDOW:t + 1]
        return [b_ / a - 1 for a, b_ in zip(w, w[1:]) if a > 0]
    return at


def effective_dims(series: list[list[float]]) -> float:
    """상관행렬의 참여비 `n^2 / SUM c_ij^2`.

    상관행렬은 대각합이 n 이므로 고윳값 합이 n 이고, 제곱합은 프로베니우스
    노름과 같다. **고유분해 없이** 실효 차원이 나온다.
    """
    n = len(series)
    if n < 2:
        return float(n)
    m = min(len(s) for s in series)
    cols = [s[:m] for s in series]
    mu = [st.fmean(c) for c in cols]
    sd = [st.pstdev(c) for c in cols]
    tot = 0.0
    for i in range(n):
        for j in range(n):
            if sd[i] == 0 or sd[j] == 0:
                tot += 1.0 if i == j else 0.0
                continue
            c = sum((a - mu[i]) * (b - mu[j]) for a, b in zip(cols[i], cols[j]))
            tot += (c / (m * sd[i] * sd[j])) ** 2
    return n * n / tot if tot else float(n)


def main(argv: list[str] | None = None) -> int:
    cfg = GateConfig()
    bars = load_many(all_symbols(), "1d", MIN_BARS)
    axis = date_axis(bars)
    pit = bool(set(bars) - set(live_symbols()))
    bench = bench_curve(bars, axis, 100.0)
    brets = returns(bench)
    bsr = sharpe(brets, cfg.periods_per_year)
    at = bench_window(bars, axis)
    hard = stress(BINANCE_USDM, cfg.cost_stress_mult)

    factors = build() + build2()
    print(f"적재 {len(bars)} · 축 {len(axis)} 일 · 시점정합 {pit}")
    print(f"벤치 {BENCH} Sharpe {bsr:+.2f} · 통과선 {bsr + cfg.min_margin_vs_bench:+.2f}")
    print(f"팩터 {len(factors)} 개 실행\n")

    rows = []
    for i, f in enumerate(factors, 1):
        r = run_cross_section(bars, xs_rule(f, at), BINANCE_USDM, 100.0, 7)
        sr = sharpe(returns(r.equity), cfg.periods_per_year)
        record(f"ZOO_{f.slug}", {"factor": f.slug, "dir": f.direction}, sr)
        rows.append({"f": f, "res": r, "sharpe": sr,
                     "rets": returns(r.equity)})
        print(f"{i:>3}/{len(factors)} {f.slug:<14}{f.family:<11}"
              f"Sharpe {sr:+.2f} · 연복리 {cagr(r.equity, cfg.periods_per_year)*100:+7.1f}%"
              f" · 낙폭 {max_drawdown(r.equity)*100:5.1f}%"
              f"{'  <- 벤치 초과' if sr > bsr else ''}", flush=True)

    rows.sort(key=lambda x: -x["sharpe"])
    led = trials()
    spread = [t["sharpe"] for t in led]
    floor = (st.fmean(spread) + st.pstdev(spread) *
             ((1 - 0.5772156649015329) * math.sqrt(2 * math.log(len(led))) +
              0.5772156649015329 * math.sqrt(2 * math.log(len(led) / math.e))))
    print(f"\n원장 누적 {len(led)} 건 · 평균 {st.fmean(spread):+.2f} "
          f"· 표준편차 {st.pstdev(spread):.2f} · **잡음바닥 {floor:+.2f}**")

    dims = effective_dims([r["rets"] for r in rows])
    print(f"실효 차원 **{dims:.1f}** / {len(rows)} 개 "
          f"(= {len(rows)} 개를 태워 {dims:.1f} 개 베팅어치)")

    print("\n계열별 최고")
    fam = {}
    for r in rows:
        fam.setdefault(r["f"].family, r)
    for k, r in sorted(fam.items(), key=lambda kv: -kv[1]["sharpe"]):
        print(f"  {k:<12}{r['f'].slug:<14}{r['sharpe']:+.2f}")

    # **④ 에서 이미 기각된 것에는 스트레스를 돌리지 않는다.**
    # 판정은 안 바뀐다 — ④ 하나만 실패해도 기각(fail-closed)이기 때문이다.
    live_ones = [r for r in rows if r["sharpe"] >= bsr + cfg.min_margin_vs_bench]
    print(f"\n④ 벤치대비를 넘은 팩터 {len(live_ones)} 개")
    for r in live_ones:
        s = run_cross_section(bars, xs_rule(r["f"], at), hard, 100.0, 7)
        v = evaluate(r["res"], bench, s, len(led), spread, pit, cfg)
        print(f"\n── {r['f'].slug} — {'**통과**' if v.passed else '기각'}")
        for c in v.checks:
            print(f"   {'OK' if c.ok else '**NG**':<7}{c.name:<12}{c.detail}")
    if not live_ones:
        print("  없음 — 전부 ④ 에서 기각")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
