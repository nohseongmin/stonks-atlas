"""포지션 팩터 실행 — PREREG_OI.md.

**축을 자른다.** OI 는 klines 보다 늦게 시작한다. 전 구간을 그대로 쓰면
전략이 초반 몇 년을 빈손으로 있고 Sharpe 가 희석된다 —
STONKS-03 의 #38(횡단면 가동률 54%)이 정확히 그 버그였다.
"""
from __future__ import annotations

import datetime as dt
import math
import statistics as st

from .backtest import date_axis, run_cross_section
from .costs import BINANCE_USDM
from .experiment import BENCH, MIN_BARS, bench_curve, stress
from .feed import all_symbols, live_symbols, load_many
from .gate import (GateConfig, cagr, evaluate, max_drawdown, record, returns,
                   sharpe, trials)
from .oi import load as load_oi
from .oizoo import build_oi, oi_rule
from .strategies import MIN_NAMES

DAY_MS = 86_400_000


def align(bars, axis):
    """심볼 -> 축 길이 리스트. 없는 날은 None. **채우지 않는다.**"""
    out, have = {}, 0
    for s in bars:
        rec = load_oi(s)
        if not rec:
            continue
        by = {}
        for d, v in rec.items():
            y, m, dd = (int(x) for x in d.split("-"))
            by[int(dt.datetime(y, m, dd, tzinfo=dt.timezone.utc).timestamp()) * 1000] = v
        row = [by.get(t) for t in axis]
        if any(x is not None for x in row):
            out[s] = row
            have += 1
    return out


def first_usable(ext, axis, need=MIN_NAMES):
    """`need` 개 이상 심볼에 OI 가 있는 **첫 날**의 축 인덱스."""
    for i in range(len(axis)):
        if sum(1 for r in ext.values() if r[i] is not None) >= need:
            return i
    return len(axis)


def main(argv: list[str] | None = None) -> int:
    cfg = GateConfig()
    bars = load_many(all_symbols(), "1d", MIN_BARS)
    axis = date_axis(bars)
    ext = align(bars, axis)
    i0 = first_usable(ext, axis)
    cut = axis[i0]
    print(f"OI 보유 심볼 {len(ext)} / {len(bars)}")
    print(f"축 절단: {i0} 번째 ({dt.datetime.fromtimestamp(cut/1000, dt.timezone.utc).date()})"
          f" — 그 전엔 {MIN_NAMES} 종목이 안 돼 횡단면이 성립하지 않는다")

    from .backtest import Bars
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
    pit = bool(set(sub) - set(live_symbols()))
    bench = bench_curve(sub, saxis, 100.0)
    bsr = sharpe(returns(bench), cfg.periods_per_year)
    print(f"절단 후 유니버스 {len(sub)} · 축 {len(saxis)} 일 · 시점정합 {pit}")
    print(f"**같은 축 위의 벤치** {BENCH} Sharpe {bsr:+.2f} · 통과선 "
          f"{bsr + cfg.min_margin_vs_bench:+.2f}\n")

    hard = stress(BINANCE_USDM, cfg.cost_stress_mult)
    factors = build_oi()
    rows = []
    for i, f in enumerate(factors, 1):
        r = run_cross_section(sub, oi_rule(f), BINANCE_USDM, 100.0, 7, extra=sext)
        sr = sharpe(returns(r.equity), cfg.periods_per_year)
        record(f"OI_{f.slug}", {"factor": f.slug, "dir": f.direction, "src": "oi"}, sr)
        rows.append({"f": f, "res": r, "sharpe": sr, "rets": returns(r.equity)})
        print(f"{i:>3}/{len(factors)} {f.slug:<15}Sharpe {sr:+.2f} · 연복리 "
              f"{cagr(r.equity, cfg.periods_per_year)*100:+7.1f}% · 낙폭 "
              f"{max_drawdown(r.equity)*100:5.1f}%"
              f"{'  <- 통과선 초과' if sr >= bsr + cfg.min_margin_vs_bench else ''}",
              flush=True)

    # 진단 — OI 증가가 모멘텀의 변장인지. 사전등록에 적어둔 것.
    from .zoo import build, xs_rule
    from .runzoo import bench_window, effective_dims
    at = bench_window(sub, saxis)
    mom = next(f for f in build() if f.slug == "mom_30")
    rm = run_cross_section(sub, xs_rule(mom, at), BINANCE_USDM, 100.0, 7)
    mr = returns(rm.equity)
    for tag in ("oi_growth_7", "oi_growth_30"):
        a = next(r["rets"] for r in rows if r["f"].slug == tag)
        m = min(len(a), len(mr))
        ma, mb = st.fmean(a[:m]), st.fmean(mr[:m])
        sa, sb = st.pstdev(a[:m]), st.pstdev(mr[:m])
        rho = (sum((x-ma)*(y-mb) for x, y in zip(a[:m], mr[:m]))/m/(sa*sb)
               if sa and sb else 0.0)
        print(f"\n진단: {tag} ↔ mom_30 상관 {rho:+.3f}"
              f"{'  ** 모멘텀의 변장 **' if abs(rho) > 0.8 else ''}")

    led = trials()
    spread = [t["sharpe"] for t in led]
    E = 0.5772156649015329
    floor = st.fmean(spread) + st.pstdev(spread) * (
        (1-E)*math.sqrt(2*math.log(len(led))) + E*math.sqrt(2*math.log(len(led)/math.e)))
    print(f"\n원장 {len(led)} 건 · **잡음바닥 {floor:+.2f}**")
    print(f"포지션 팩터 실효차원 "
          f"{effective_dims([r['rets'] for r in rows]):.1f} / {len(rows)}")

    rows.sort(key=lambda x: -x["sharpe"])
    good = [r for r in rows if r["sharpe"] >= bsr + cfg.min_margin_vs_bench]
    print(f"\n④ 를 넘은 것 {len(good)} 개")
    for r in good:
        s = run_cross_section(sub, oi_rule(r["f"]), hard, 100.0, 7, extra=sext)
        v = evaluate(r["res"], bench, s, len(led), spread, pit, cfg)
        print(f"\n── OI_{r['f'].slug} — {'**통과**' if v.passed else '기각'}")
        for c in v.checks:
            print(f"   {'OK' if c.ok else '**NG**':<7}{c.name:<12}{c.detail}")
    if not good:
        print("  없음 — 전부 ④ 에서 기각")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
