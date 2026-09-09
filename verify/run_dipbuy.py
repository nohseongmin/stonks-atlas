"""딥바잉 배터리 실행 — PREREG_DIPBUY.md 검사 7 종."""
from __future__ import annotations

import statistics as st

from .dipbuy import (ASSETS, BASE, COST_BPS, GRID, LEVERAGED, fetch, hold, run,
                     stats)


def line(tag, s, b, extra=""):
    win = s["sharpe"] > b["sharpe"]
    print(f"  {tag:<16}SR {s['sharpe']:+.2f} vs 보유 {b['sharpe']:+.2f}"
          f" ({s['sharpe']-b['sharpe']:+.2f}) · 연복리 {s['cagr']*100:+6.1f}%"
          f" vs {b['cagr']*100:+6.1f}% · 낙폭 {s['mdd']*100:4.1f}%"
          f" vs {b['mdd']*100:4.1f}% · 노출 {s['exposure']*100:4.1f}%"
          f"   {'OK' if win else '**NG**'}{extra}")
    return win


def main(argv=None) -> int:
    w, dip = BASE
    data = {s: [c for _, c in fetch(s)] for s in ASSETS}
    data = {s: c for s, c in data.items() if len(c) > 400}
    print(f"딥바잉 배터리 — SMA({w}) 대비 −{dip:.0f}% 진입 / SMA 회복 청산")
    print(f"자산 {len(data)} · 왕복 비용 {COST_BPS:.0f}bp · 미보유 기간 무위험 연 4%\n")

    fails = []

    print("1·2) 노출조정 제거 + 자산 일반화 — **실제 포트폴리오가 보유를 넘는가**")
    wins = []
    for s in ASSETS:
        if s not in data:
            continue
        c = data[s]
        a, b = stats(run(c, w, dip)), stats(hold(c, w))
        wins.append(line(s, a, b, "  [레버리지]" if s in LEVERAGED else ""))
    rate = sum(wins) / len(wins)
    print(f"\n   매수보유를 넘은 자산 {sum(wins)}/{len(wins)} ({rate*100:.0f}%)")
    if rate <= 0.5:
        fails.append(f"1·2 노출조정 제거 — {sum(wins)}/{len(wins)} 만 보유를 넘음")

    print("\n3) 파라미터 고원 — SPY·QQQ 평균 여유폭")
    for gw, gd in GRID:
        m = []
        for s in ("SPY", "QQQ"):
            if s in data:
                c = data[s]
                m.append(stats(run(c, gw, gd))["sharpe"] - stats(hold(c, gw))["sharpe"])
        mark = "  <- 원 값" if (gw, gd) == BASE else ""
        print(f"  ({gw:>2}, {gd:.0f}%)      여유 {st.fmean(m):+.2f}{mark}")

    print("\n4) 하위표본 — SPY 전반/후반")
    c = data["SPY"]
    mid = len(c) // 2
    for tag, seg in (("전반", c[:mid]), ("후반", c[mid:])):
        a, b = stats(run(seg, w, dip)), stats(hold(seg, w))
        if not line(tag, a, b):
            fails.append(f"4 하위표본 — SPY {tag}에서 보유 미달")

    print("\n5) 비용 민감도 — SPY")
    for bps in (5, 10, 25, 50):
        a = stats(run(c, w, dip, cost_bps=bps))
        b = stats(hold(c, w))
        if not line(f"왕복 {bps}bp", a, b):
            fails.append(f"5 비용 — {bps}bp 에서 보유 미달")

    print("\n6) 레버리지 실제")
    lev = [s for s in LEVERAGED if s in data]
    lw = []
    for s in lev:
        cc = data[s]
        a, b = stats(run(cc, w, dip)), stats(hold(cc, w))
        lw.append(line(s, a, b))
    if lev and not any(lw):
        fails.append("6 레버리지 — 셋 다 보유 미달")

    print("\n7) 현금 수익 계상 — 무위험 0% 로 재계산 (SPY)")
    a0 = stats(run(c, w, dip, rf=0.0))
    a4 = stats(run(c, w, dip))
    b = stats(hold(c, w))
    print(f"  무위험 4%       SR {a4['sharpe']:+.2f} · 연복리 {a4['cagr']*100:+.1f}%")
    print(f"  무위험 0%       SR {a0['sharpe']:+.2f} · 연복리 {a0['cagr']*100:+.1f}%")
    print(f"  보유           SR {b['sharpe']:+.2f} · 연복리 {b['cagr']*100:+.1f}%")
    print(f"  → 결과가 현금 이자 가정에 {'**크게 의존**' if abs(a4['sharpe']-a0['sharpe'])>0.2 else '거의 무관'}"
          f" (차 {a4['sharpe']-a0['sharpe']:+.2f})")

    print(f"\n{'='*76}")
    if fails:
        print(f"**기각 — {len(fails)} 개 항목에서 무너졌다**")
        for f in fails:
            print(f"  · {f}")
    else:
        print("**7 종 전부 통과.** 이 프로젝트 첫 배터리 완주다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
