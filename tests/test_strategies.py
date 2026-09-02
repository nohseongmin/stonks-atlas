"""전략 규칙 검정. **사전등록에 없는 숫자가 코드에 있으면 안 된다.**"""
import pytest

from dump.backtest import Bars, PastView, run_cross_section
from dump.costs import Venue
from dump.strategies import (GROSS_LEVERAGE, LIQUIDITY_WINDOW, MIN_NAMES,
                             _liquid, momentum)

FREE = Venue("free", 0, 0, 0, 0, 5, 0)
DAY = 86_400_000
N = 60


def past_of(closes: list[float], qvol: list[float] | None = None) -> dict:
    n = len(closes)
    return {"close": PastView(closes, n - 1),
            "qvol": PastView(qvol if qvol is not None else [1e6] * n, n - 1)}


def book(rets: dict[str, float], vols: dict[str, float] | None = None) -> dict:
    """심볼마다 일정 일간수익률 `rets[s]` 로 자라는 봉."""
    out = {}
    for s, r in rets.items():
        px = [100.0]
        for _ in range(N - 1):
            px.append(px[-1] * (1 + r))
        v = (vols or {}).get(s, 1e6)
        out[s] = Bars(s, [i * DAY for i in range(N)], px, px, px, px, [], [v] * N)
    return out


# ---------------------------------------------------------------- 유동성 필터

def test_liquid_drops_symbols_without_volume():
    """**거래대금이 없으면 버린다.** 0 으로 치면 하위에 몰려 부호가 뒤집힌다."""
    live = [f"S{i}" for i in range(30)]
    past = {s: past_of([100.0] * N, [1e6] * N) for s in live}
    past["S0"] = past_of([100.0] * N, [])           # 거래대금 없음
    past["S1"] = past_of([100.0] * N, [0.0] * N)    # 전부 0
    out = _liquid(past, live)
    assert "S0" not in out and "S1" not in out


def test_liquid_keeps_the_top_half():
    live = [f"S{i:02d}" for i in range(40)]
    past = {s: past_of([100.0] * N, [float(i + 1) * 1e5] * N)
            for i, s in enumerate(live)}
    out = _liquid(past, live)
    assert len(out) == 20
    assert "S39" in out and "S00" not in out


def test_liquid_needs_full_window():
    live = [f"S{i}" for i in range(30)]
    past = {s: past_of([100.0] * N, [1e6] * (LIQUIDITY_WINDOW - 1)) for s in live}
    assert _liquid(past, live) == []


def test_liquid_refuses_thin_cross_section():
    live = [f"S{i}" for i in range(MIN_NAMES - 1)]
    past = {s: past_of([100.0] * N) for s in live}
    assert _liquid(past, live) == []


# ---------------------------------------------------------------- 모멘텀

def _past(rets, vols):
    return {s: past_of(p.close) | {"qvol": PastView(p.qvol, N - 1)}
            for s, p in book(rets, vols).items()}


#: 홀수 심볼에만 큰 거래대금 — 유동성 필터가 홀수 20 개를 남긴다.
#: 전부 같은 값을 주면 동점 정렬이 알파벳 앞 절반(= 패자들)만 남긴다.
RETS = {f"S{i:02d}": (i - 20) * 0.001 for i in range(40)}
VOLS = {f"S{i:02d}": 1e6 * (1 + i % 2) for i in range(40)}


def test_momentum_longs_winners_and_shorts_losers():
    r = momentum(7)(0, _past(RETS, VOLS), sorted(RETS))
    assert r["S39"] > 0 and r["S01"] < 0
    assert "S38" not in r          # 거래대금 하위 절반은 아예 후보가 아니다
    assert sum(abs(w) for w in r.values()) == pytest.approx(GROSS_LEVERAGE)
    assert sum(r.values()) == pytest.approx(0.0, abs=1e-12)   # 시장중립


def test_long_only_variant_has_no_shorts():
    r = momentum(7, long_only=True)(0, _past(RETS, VOLS), sorted(RETS))
    assert all(w > 0 for w in r.values())
    assert sum(r.values()) == pytest.approx(GROSS_LEVERAGE)


def test_momentum_returns_empty_when_history_is_short():
    live = [f"S{i}" for i in range(30)]
    past = {s: past_of([100.0] * 5, [1e6] * 5) for s in live}
    assert momentum(7)(0, past, live) == {}


def test_momentum_runs_end_to_end_through_the_harness():
    """실행기에 물려 실제로 돌아가는지. 승자가 계속 이기면 돈을 벌어야 한다."""
    rets = {f"S{i:02d}": (i - 20) * 0.002 for i in range(40)}
    res = run_cross_section(book(rets), momentum(7), FREE, rebalance=7)
    assert res.liquidated_at is None
    assert res.final > 100.0
