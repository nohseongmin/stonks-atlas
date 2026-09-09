"""횡단면 실행 검정. **시점정합이 실제로 지켜지는지가 핵심이다.**"""
import pytest

from dump.backtest import Bars, date_axis, run_cross_section
from dump.costs import Venue

V = Venue("t", taker_bps=5.0, maker_bps=2.0, spread_bps=1.0,
          min_notional_usd=10.0, max_leverage=5.0,
          funding_bps_per_period=0.0, verified=True)
FREE = Venue("free", 0, 0, 0, 0, 5, 0)
DAY = 86_400_000


def flat(days: list[int], px: float = 100.0, name: str = "X", funding=None) -> Bars:
    n = len(days)
    return Bars(name, [d * DAY for d in days], [px] * n, [px] * n,
                [px] * n, [px] * n, funding or [])


#: A 는 0~9 내내, B 는 0~4 만(상폐), C 는 5~9 만(나중 상장).
def book():
    return {"A": flat(list(range(10)), name="A"),
            "B": flat(list(range(5)), name="B"),
            "C": flat(list(range(5, 10)), name="C")}


def seen(bars, rebalance=1, venue=FREE):
    """리밸런싱마다 `live` 로 넘어온 심볼을 기록한다."""
    log = []

    def rule(t, past, live):
        log.append((t, tuple(sorted(live))))
        return {}

    run_cross_section(bars, rule, venue, rebalance=rebalance)
    return dict(log)


# ---------------------------------------------------------------- 시점정합

def test_axis_includes_delisted_symbol_dates():
    assert len(date_axis(book())) == 10


def test_live_excludes_unlisted_and_includes_delisted():
    """**이게 시점정합의 전부다.** 상장 전은 빠지고, 상폐 전까진 들어온다."""
    log = seen(book())
    assert log[0] == ("A", "B")          # C 는 아직 상장 전
    assert log[4] == ("A", "B")          # B 의 마지막 날
    assert log[5] == ("A", "C")          # B 상폐, C 상장
    assert log[9 - 1] == ("A", "C")


def test_rule_cannot_see_future_prices():
    def cheat(t, past, live):
        return {live[0]: past[live[0]]["close"][t + 1]}

    with pytest.raises(IndexError, match="미래 참조 차단"):
        run_cross_section(book(), cheat, FREE, rebalance=1)


def test_weight_on_dead_symbol_is_rejected():
    """상폐된 종목에 가중치를 주면 조용히 무시하지 않고 터진다."""
    def stale(t, past, live):
        return {"B": 1.0}

    with pytest.raises(ValueError, match="거래되지 않는 심볼"):
        run_cross_section(book(), stale, FREE, rebalance=1)


# ---------------------------------------------------------------- 상폐 정산

def test_delisting_closes_the_position_and_charges_cost():
    """상폐는 마지막 종가 정산이다. 청산 비용은 든다."""
    r = run_cross_section(book(), lambda t, p, l: {"B": 1.0} if t == 0 else None,
                          V, rebalance=1)
    assert r.fees_paid > 0
    assert r.liquidated_at is None


def test_delisting_without_position_costs_nothing():
    r = run_cross_section(book(), lambda t, p, l: {"A": 1.0} if t == 0 else None,
                          V, rebalance=1)
    one_way = (V.taker_bps + V.spread_bps / 2) / 1e4
    assert r.fees_paid == pytest.approx(100.0 * one_way)      # 진입 한 번뿐


# ---------------------------------------------------------------- 비용·규칙

def test_zero_signal_bleeds_only_fees():
    lev = 2.0
    r = run_cross_section(book(),
                          lambda t, p, l: {"A": lev} if t % 2 == 0 else {},
                          V, rebalance=1)
    assert r.final < 100.0
    assert r.funding_paid == 0.0


def test_none_holds_and_empty_dict_exits():
    """`None`(유지) 과 `{}`(청산) 은 다르다."""
    hold = run_cross_section(book(), lambda t, p, l: {"A": 1.0} if t == 0 else None,
                             V, rebalance=1)
    exit_ = run_cross_section(book(),
                              lambda t, p, l: {"A": 1.0} if t == 0 else {},
                              V, rebalance=1)
    assert exit_.trades > hold.trades


def test_gross_leverage_cap_enforced():
    with pytest.raises(ValueError, match="총 레버리지"):
        run_cross_section(book(), lambda t, p, l: {"A": 4.0, "C": 4.0},
                          V, rebalance=1)


def test_rebalance_interval_respected():
    log = seen(book(), rebalance=3)
    assert sorted(log) == [0, 3, 6]


def test_rebalance_must_be_positive():
    with pytest.raises(ValueError, match="1 이상"):
        run_cross_section(book(), lambda t, p, l: {}, V, rebalance=0)


# ---------------------------------------------------------------- 수익·펀딩

def test_long_captures_the_move():
    px = [100.0 * 1.01 ** i for i in range(10)]
    b = {"A": Bars("A", [i * DAY for i in range(10)], px, px, px, px)}
    r = run_cross_section(b, lambda t, p, l: {"A": 1.0}, FREE, rebalance=1)
    assert r.final == pytest.approx(100.0 * 1.01 ** 9, rel=1e-9)


def test_short_earns_when_price_falls():
    px = [100.0 * 0.99 ** i for i in range(10)]
    b = {"A": Bars("A", [i * DAY for i in range(10)], px, px, px, px)}
    r = run_cross_section(b, lambda t, p, l: {"A": -1.0}, FREE, rebalance=1)
    assert r.final > 100.0


def test_long_pays_funding_short_receives():
    f = [(int(1.5 * DAY), 0.01)]
    b = {"A": flat(list(range(5)), name="A", funding=f)}
    lon = run_cross_section(b, lambda t, p, l: {"A": 1.0}, FREE, rebalance=1)
    sho = run_cross_section(b, lambda t, p, l: {"A": -1.0}, FREE, rebalance=1)
    assert lon.funding_paid == pytest.approx(1.0)
    assert sho.funding_paid == pytest.approx(-1.0)
    assert lon.final == pytest.approx(99.0)


def test_wipeout_stops_the_run():
    px = [100.0, 100.0, 1.0, 1.0]
    b = {"A": Bars("A", [i * DAY for i in range(4)], px, px, px, px)}
    r = run_cross_section(b, lambda t, p, l: {"A": 2.0}, FREE, rebalance=1)
    assert r.liquidated_at == 2
    assert r.final == 0.0
