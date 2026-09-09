"""강건성 배터리 — PREREG_TAKER.md. **죽일 수만 있고 승격시킬 수 없다.**

최고 변형을 고르지 않는다. 전부 통과해야 유지되고 하나라도 무너지면 기각이다.
그래서 새 가설이 아니라 기존 1 건의 진단이고 **원장에 기록하지 않는다.**
"""
from __future__ import annotations

import statistics as st

from .backtest import Bars, date_axis, run_cross_section
from .costs import BINANCE_USDM
from .experiment import BENCH, MIN_BARS, bench_curve, stress
from .feed import all_symbols, live_symbols, load_many
from .gate import GateConfig, cagr, max_drawdown, returns, sharpe
from .runzoo import bench_window
from .zoo import Factor, _taker, xs_rule

CFG = GateConfig()
TARGET = "taker_imb_30"


def taker_factor(n: int) -> Factor:
    return Factor(f"taker_imb_{n}", "flow", +1, lambda p, k=n: _taker(p, k))


def slice_bars(bars: dict[str, Bars], lo: int, hi: int) -> dict[str, Bars]:
    """타임스탬프 [lo, hi) 로 자른다. **잘린 뒤에도 최소 봉 수를 지킨다.**"""
    out = {}
    for s, b in bars.items():
        keep = [i for i, t in enumerate(b.ts) if lo <= t < hi]
        if len(keep) < MIN_BARS:
            continue
        a, z = keep[0], keep[-1] + 1
        out[s] = Bars(s, b.ts[a:z], b.open[a:z], b.high[a:z], b.low[a:z],
                      b.close[a:z],
                      [f for f in b.funding if lo <= f[0] < hi],
                      b.qvol[a:z], b.tbuy[a:z])
    return out


def score(bars, rule, venue, tag):
    r = run_cross_section(bars, rule, venue, 100.0, 7)
    axis = date_axis(bars)
    bench = bench_curve(bars, axis, 100.0)
    bsr = sharpe(returns(bench), CFG.periods_per_year)
    sr = sharpe(returns(r.equity), CFG.periods_per_year)
    ok = sr - bsr >= CFG.min_margin_vs_bench
    print(f"  {tag:<28}Sharpe {sr:+.2f} · 벤치 {bsr:+.2f} · 여유 {sr-bsr:+.2f}"
          f" · 연복리 {cagr(r.equity, CFG.periods_per_year)*100:+6.1f}%"
          f" · 낙폭 {max_drawdown(r.equity)*100:5.1f}%   {'OK' if ok else '**NG**'}")
    return sr, bsr, ok, r


def main(argv: list[str] | None = None) -> int:
    bars = load_many(all_symbols(), "1d", MIN_BARS)
    axis = date_axis(bars)
    at = bench_window(bars, axis)
    f30 = taker_factor(30)
    fails = []

    print(f"강건성 배터리 — {TARGET}")
    print(f"유니버스 {len(bars)} · 축 {len(axis)} 일 · 시점정합 "
          f"{bool(set(bars) - set(live_symbols()))}\n")

    print("1) 창 길이 고원 — 30 만 되고 이웃이 무너지면 과최적화")
    plateau = {}
    for n in (7, 14, 30, 60, 90):
        sr, bsr, ok, _ = score(bars, xs_rule(taker_factor(n), at), BINANCE_USDM,
                               f"창 {n}일")
        plateau[n] = sr
    neigh = [plateau[n] - 0.90 >= CFG.min_margin_vs_bench for n in (14, 60)]
    if not all(neigh):
        fails.append("1 고원 — 30 의 이웃(14·60)이 통과선을 못 넘었다")

    print("\n2) 하위표본 — 한쪽에서만 되면 표본 특수성")
    mid = axis[len(axis) // 2]
    for tag, lo, hi in (("전반", axis[0], mid), ("후반", mid, axis[-1] + 1)):
        sub = slice_bars(bars, lo, hi)
        sat = bench_window(sub, date_axis(sub))
        sr, bsr, ok, _ = score(sub, xs_rule(f30, sat), BINANCE_USDM,
                               f"{tag} ({len(sub)} 종목)")
        if not ok:
            fails.append(f"2 하위표본 — {tag}에서 통과선 미달")

    print("\n3) 비용 민감도 — 10 배에서도 벤치를 넘어야")
    for m in (3, 5, 10):
        sr, bsr, ok, _ = score(bars, xs_rule(f30, at), stress(BINANCE_USDM, m),
                               f"비용 {m}배")
        if not ok:
            fails.append(f"3 비용 — {m}배에서 통과선 미달")

    print("\n4) 분위 민감도 — 20% 에서만 되면 과최적화")
    for q in (0.10, 0.20, 0.30):
        sr, bsr, ok, _ = score(bars, xs_rule(f30, at, quantile=q), BINANCE_USDM,
                               f"분위 {q*100:.0f}%")
        if not ok:
            fails.append(f"4 분위 — {q*100:.0f}% 에서 통과선 미달")

    print("\n5) 자산 절제 — 기여 상위 10 종목 제외")
    _, _, _, base = score(bars, xs_rule(f30, at), BINANCE_USDM, "기준(전 종목)")
    top10 = sorted(base.contrib, key=lambda s: -abs(base.contrib[s]))[:10]
    print(f"     기여 상위: {', '.join(top10[:6])}...")
    sr, bsr, ok, _ = score(bars, xs_rule(f30, at, exclude=set(top10)),
                           BINANCE_USDM, "상위 10 제외")
    if not ok:
        fails.append("5 자산 절제 — 소수 종목이 결과를 만들었다")

    print("\n6) 모멘텀 직교성 — 상관 0.8 넘으면 모멘텀의 변장")
    from .zoo import build
    mom30 = next(f for f in build() if f.slug == "mom_30")
    rm = run_cross_section(bars, xs_rule(mom30, at), BINANCE_USDM, 100.0, 7)
    a, b = returns(base.equity), returns(rm.equity)
    m = min(len(a), len(b))
    ma, mb = st.fmean(a[:m]), st.fmean(b[:m])
    sa, sb = st.pstdev(a[:m]), st.pstdev(b[:m])
    rho = (sum((x - ma) * (y - mb) for x, y in zip(a[:m], b[:m])) / m / (sa * sb)
           if sa and sb else 0.0)
    print(f"  {'mom_30 과의 상관':<28}{rho:+.3f}   "
          f"{'**NG**' if abs(rho) > 0.8 else 'OK'}")
    if abs(rho) > 0.8:
        fails.append("6 직교성 — 모멘텀과 사실상 같은 것")

    print(f"\n{'='*70}")
    if fails:
        print(f"**기각 — {len(fails)} 개 항목에서 무너졌다**")
        for f in fails:
            print(f"  · {f}")
    else:
        print("**6 종 전부 통과.** 그래도 배포하지 않는다 — ⑦ 이 열려 있고")
        print("그건 과거 데이터로 못 푼다. 전진검증에 단일 시도로 올린다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
