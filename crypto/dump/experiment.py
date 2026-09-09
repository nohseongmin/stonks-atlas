"""검정 실행기 — **사전등록된 시행을 전부 돌리고 전부 기록한다.**

좋은 쪽만 보고하면 그게 다중검정이다. 여기서는 기각도 원장에 남긴다.
"""
from __future__ import annotations

import math
import statistics as st

from .backtest import Bars, date_axis, run_cross_section
from .costs import BINANCE_USDM, Venue
from .feed import all_symbols, live_symbols, load_many
from .gate import (GateConfig, cagr, evaluate, max_drawdown, record, returns,
                   sharpe, trials)
from .strategies import momentum

BENCH = "BTCUSDT"
MIN_BARS = 60          # 거래대금 30 일 창 + 룩백을 채우려면 이만큼은 필요


def bench_curve(bars: dict[str, Bars], axis: list[int],
                capital: float = 100.0) -> list[float]:
    """벤치 매수보유를 **횡단면과 같은 축 위에** 올린다.

    벤치가 없는 날은 직전 값을 유지한다 — 비교 대상의 길이가 다르면
    Sharpe 를 나란히 놓을 수 없다.
    """
    b = bars[BENCH]
    pos = {t: i for i, t in enumerate(b.ts)}
    out, last = [], None
    for t in axis:
        i = pos.get(t)
        if i is not None:
            last = b.close[i]
        out.append(last)
    first = next(v for v in out if v is not None)
    return [capital * (v if v is not None else first) / first for v in out]


def stress(venue: Venue, mult: float) -> Venue:
    from dataclasses import replace
    return replace(venue, name=f"{venue.name}x{mult:g}",
                   taker_bps=venue.taker_bps * mult,
                   maker_bps=venue.maker_bps * mult,
                   spread_bps=venue.spread_bps * mult)


def run(specs: list[tuple[str, dict, object]], venue: Venue = BINANCE_USDM,
        cfg: GateConfig = GateConfig(), rebalance: int = 7,
        capital: float = 100.0) -> list[dict]:
    """`(이름, 사양, 규칙)` 목록을 돌린다. 사양은 원장 지문에 들어간다."""
    syms = all_symbols()
    print(f"심볼 {len(syms)} 개 적재 중...", flush=True)
    bars = load_many(syms, "1d", MIN_BARS)
    axis = date_axis(bars)
    print(f"적재 {len(bars)} 개 (봉 {MIN_BARS} 개 미만 {len(syms)-len(bars)} 개 제외)"
          f" · 축 {len(axis)} 일 · {min(axis)//86400000} ~ {max(axis)//86400000}\n")

    # **시점정합을 주장하지 말고 확인한다.** 상폐 종목이 실제로 들어있는지 센다.
    dead = sorted(set(bars) - set(live_symbols()))
    pit = bool(dead)
    print(f"시점정합: 유니버스에 상폐 종목 {len(dead)} 개 포함 "
          f"({', '.join(dead[:4])}...)" if pit else
          "**시점정합 아님 — 살아있는 종목만 들어있다**")

    bench = bench_curve(bars, axis, capital)
    bsr = sharpe(returns(bench), cfg.periods_per_year)
    print(f"벤치 {BENCH} 매수보유 — Sharpe {bsr:+.2f} · "
          f"연복리 {cagr(bench, cfg.periods_per_year)*100:+.1f}% · "
          f"낙폭 {max_drawdown(bench)*100:.0f}%\n")

    hard = stress(venue, cfg.cost_stress_mult)
    out = []
    for name, spec, rule in specs:
        r = run_cross_section(bars, rule, venue, capital, rebalance)
        s = run_cross_section(bars, rule, hard, capital, rebalance)
        sr = sharpe(returns(r.equity), cfg.periods_per_year)
        record(name, spec, sr)
        out.append({"name": name, "spec": spec, "res": r, "stressed": s,
                    "sharpe": sr})
        print(f"{name:<22} Sharpe {sr:+.2f} · 연복리 "
              f"{cagr(r.equity, cfg.periods_per_year)*100:+7.1f}% · 낙폭 "
              f"{max_drawdown(r.equity)*100:5.1f}% · 수수료 ${r.fees_paid:,.0f} · "
              f"펀딩 ${r.funding_paid:,.0f} · 거래 {r.trades}", flush=True)

    led = trials()
    spread = [t["sharpe"] for t in led]
    print(f"\n원장 누적 시행 {len(led)} 건\n")
    for o in out:
        v = evaluate(o["res"], bench, o["stressed"], len(led), spread, pit, cfg)
        print(f"── {o['name']} — {'**통과**' if v.passed else '기각'}")
        for c in v.checks:
            print(f"   {'OK' if c.ok else '**NG**':<7}{c.name:<12}{c.detail}")
        print()
        o["verdict"] = v
    return out


VOL_WINDOW = 90        # PREREG_COMBO.md 에 고정. 결과를 보고 바꾸지 않는다.


def combine(ltw_rule, weights):
    """LTW 다리와 벤치 다리를 합친다. `weights(t) -> (LTW 그로스, 벤치 그로스)`.

    LTW 가 신호를 못 내면(횡단면이 얇으면) **벤치 다리만** 그 비중으로 든다.
    비중을 키워 메우지 않는다 — 그건 사전등록에 없는 재량이다.
    """
    def rule(t, past, live):
        g1, g2 = weights(t)
        w = ltw_rule(t, past, live) or {}
        gross = sum(abs(x) for x in w.values())
        out = {s: x * g1 / gross for s, x in w.items()} if gross else {}
        if BENCH in live:
            out[BENCH] = out.get(BENCH, 0.0) + g2
        return out
    return rule


def inverse_vol(a: list[float], b: list[float], window: int = VOL_WINDOW):
    """직전 `window` 일 실현변동성의 역수 비중. **t 시점까지만 본다.**"""
    def w(t):
        if t < window:
            return 0.5, 0.5
        sa, sb = st.pstdev(a[t - window:t]), st.pstdev(b[t - window:t])
        if sa <= 0 or sb <= 0:
            return 0.5, 0.5
        ia, ib = 1 / sa, 1 / sb
        return ia / (ia + ib), ib / (ia + ib)
    return w


def correlation(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    ma, mb = st.fmean(a[:n]), st.fmean(b[:n])
    num = sum((x - ma) * (y - mb) for x, y in zip(a[:n], b[:n]))
    da = math.sqrt(sum((x - ma) ** 2 for x in a[:n]))
    db = math.sqrt(sum((y - mb) ** 2 for y in b[:n]))
    return 0.0 if da == 0 or db == 0 else num / (da * db)


def combo_main(argv: list[str] | None = None) -> int:
    """PREREG_COMBO.md — 비중 규칙 2 개. **상관이 얼마든 둘 다 돌린다.**"""
    cfg = GateConfig()
    syms = all_symbols()
    bars = load_many(syms, "1d", MIN_BARS)
    axis = date_axis(bars)
    dead = sorted(set(bars) - set(live_symbols()))
    bench = bench_curve(bars, axis, 100.0)
    brets = returns(bench)
    print(f"적재 {len(bars)} · 축 {len(axis)} 일 · 상폐 포함 {len(dead)} 개")
    print(f"벤치 {BENCH} Sharpe {sharpe(brets, cfg.periods_per_year):+.2f}")
    print()

    solo = run_cross_section(bars, momentum(14), BINANCE_USDM, 100.0, 7)
    lrets = returns(solo.equity)
    rho = correlation(lrets, brets)
    print(f"── 진단: LTW L=14 ↔ {BENCH} 상관 **{rho:+.3f}**")
    n = min(len(lrets), len(brets))
    s1 = sharpe(brets[:n], cfg.periods_per_year)
    s2 = sharpe(lrets[:n], cfg.periods_per_year)
    if abs(rho) < 1:
        theo = math.sqrt(max(0.0, (s1*s1 + s2*s2 - 2*rho*s1*s2) / (1 - rho*rho)))
        print(f"   이론 조합 Sharpe {theo:.2f} (S1={s1:.2f} S2={s2:.2f})")
    print("   **이 이론값은 표본내 적합이다. 배포 근거가 아니다.**")
    print()

    specs = [
        ("조합_고정50", {"rule": "fixed", "ltw": 0.5, "bench": 0.5},
         combine(momentum(14), lambda t: (0.5, 0.5))),
        ("조합_역변동성", {"rule": "inverse_vol", "window": VOL_WINDOW},
         combine(momentum(14), inverse_vol(lrets, brets))),
    ]
    run(specs, cfg=cfg)
    return 0


def main(argv: list[str] | None = None) -> int:
    """PREREG_LTW.md 에 선언한 **3 건 전부.** 좋은 쪽만 고르지 않는다."""
    specs = [
        ("LTW_모멘텀_L7", {"lookback": 7, "long_only": False}, momentum(7)),
        ("LTW_모멘텀_L14", {"lookback": 14, "long_only": False}, momentum(14)),
        ("LTW_모멘텀_L7_롱온리", {"lookback": 7, "long_only": True},
         momentum(7, long_only=True)),
    ]
    run(specs)
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(combo_main() if "--combo" in sys.argv else main())
