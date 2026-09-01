"""체결 시뮬 검정. **봉인이 뚫리는지가 제일 중요하다.**"""
import pytest

from dump.backtest import Bars, PastView, run
from dump.costs import Venue

V = Venue("test", taker_bps=5.0, maker_bps=2.0, spread_bps=1.0,
          min_notional_usd=100.0, max_leverage=125.0,
          funding_bps_per_period=1.0, source="합성", verified=True)

HOUR = 3_600_000


def flat(n: int, price: float = 100.0, funding=None) -> Bars:
    """가격이 전혀 안 움직이는 봉. 남는 건 비용뿐이다."""
    return Bars("T", [i * HOUR for i in range(n)], [price] * n, [price] * n,
                [price] * n, [price] * n, funding or [])


# ---------------------------------------------------------------- 봉인

def test_pastview_blocks_future():
    v = PastView([0, 1, 2, 3, 4], 2)
    assert len(v) == 3
    assert v[2] == 2 and v[-1] == 2
    for bad in (3, 4, 99):
        with pytest.raises(IndexError):
            v[bad]


def test_pastview_slice_cannot_escape():
    v = PastView(list(range(10)), 3)
    assert v[:] == [0, 1, 2, 3]
    assert v[2:99] == [2, 3]


def test_rule_reading_future_raises():
    """**규칙이 미래를 만지면 조용히 새지 않고 터진다.**"""
    def cheat(t, past):
        return past["close"][t + 1]

    with pytest.raises(IndexError, match="미래 참조 차단"):
        run(flat(20), cheat, V)


# ---------------------------------------------------------------- 비용

def test_zero_signal_bleeds_exactly_fees():
    """신호 0, 가격 무변동. 남는 손실은 정확히 수수료여야 한다."""
    lev = 10.0
    r = run(flat(5), lambda t, p: lev if t % 2 == 0 else 0.0, V, capital=100.0)
    one_way = (V.taker_bps + V.spread_bps / 2) / 1e4
    expected = 100.0
    for _ in range(4):                      # 4 번의 레버리지 변화
        expected *= 1 - lev * one_way
    assert r.final == pytest.approx(expected)
    assert r.trades == 4
    assert r.funding_paid == 0.0


def test_backtest_agrees_with_cost_arithmetic():
    """시뮬의 왕복 비용이 `costs.py` 의 1 차 근사와 일치해야 한다.

    시뮬은 곱셈, 산술은 덧셈이라 2 차항만큼 다르다. 그 차이가 작아야 한다.
    """
    lev = 10.0
    r = run(flat(3), lambda t, p: lev if t == 0 else 0.0, V, capital=100.0)
    sim_frac = 1 - r.final / 100.0
    assert sim_frac == pytest.approx(V.equity_cost_frac(lev), rel=0.02)


def test_none_holds_and_zero_exits():
    """`None` 은 유지, `0` 은 청산. **다른 뜻이다.**"""
    held = run(flat(6), lambda t, p: 5.0 if t == 0 else None, V)
    assert held.trades == 1
    exited = run(flat(6), lambda t, p: 5.0 if t == 0 else 0.0, V)
    assert exited.trades == 2


# ---------------------------------------------------------------- 청산

def test_liquidation_uses_intrabar_low_not_close():
    """봉 안에서 찍고 회복해도 청산이다. 종가만 보면 못 잡는다."""
    b = flat(3)
    b.low[1] = 89.0                       # -11%, 10 배면 자본 초과
    r = run(b, lambda t, p: 10.0, V)
    assert r.liquidated_at == 1
    assert r.final == 0.0


def test_short_liquidates_on_high():
    b = flat(3)
    b.high[1] = 111.0
    r = run(b, lambda t, p: -10.0, V)
    assert r.liquidated_at == 1


def test_no_liquidation_when_move_is_survivable():
    b = flat(3)
    b.low[1] = 95.0                       # -5%, 10 배면 -50% 손실이지만 생존
    r = run(b, lambda t, p: 10.0, V)
    assert r.liquidated_at is None
    assert 0 < r.final < 100.0


def test_leverage_over_max_rejected():
    with pytest.raises(ValueError, match="최대 레버리지"):
        run(flat(5), lambda t, p: 999.0, V)


# ---------------------------------------------------------------- 펀딩

FREE = Venue("free", 0, 0, 0, 0, 125, 0)


def test_long_pays_positive_funding():
    """수수료 0 인 거래소로 재서 펀딩만 남긴다."""
    b = flat(4, funding=[(int(1.5 * HOUR), 0.01)])
    r = run(b, lambda t, p: 1.0, FREE, capital=100.0)
    assert r.funding_paid == pytest.approx(1.0)
    assert r.final == pytest.approx(99.0)


def test_short_receives_positive_funding():
    b = flat(4, funding=[(int(1.5 * HOUR), 0.01)])
    r = run(b, lambda t, p: -1.0, V)
    assert r.funding_paid < 0             # 받는다


def test_flat_position_pays_no_funding():
    b = flat(4, funding=[(int(1.5 * HOUR), 0.01)])
    r = run(b, lambda t, p: 0.0, V)
    assert r.funding_paid == 0.0


def test_each_funding_charged_once():
    b = flat(6, funding=[(int(1.5 * HOUR), 0.01), (int(2.5 * HOUR), 0.01)])
    r = run(b, lambda t, p: 1.0, V)
    two = run(flat(6, funding=[(int(1.5 * HOUR), 0.01)]), lambda t, p: 1.0, V)
    assert r.funding_paid > two.funding_paid


# ---------------------------------------------------------------- 신호 복원

def test_planted_edge_is_recovered():
    """**심어둔 참 신호를 하네스가 파괴하지 않는지.**

    #38 에서 하네스가 참 신호를 27% 죽이고 있었고 관문은 아무 말도 안 했다.
    관문은 '너무 좋으면' 기각하지 '너무 나쁘면' 침묵한다.
    """
    n, up = 40, 0.01
    px = [100.0]
    for i in range(n - 1):
        px.append(px[-1] * (1 + up))
    b = Bars("T", [i * HOUR for i in range(n)], px, px, px, px)
    r = run(b, lambda t, p: 1.0, FREE)
    # **(n-2) 승이다.** 규칙은 t 봉 종가를 보고 t+1 시가에 체결하므로
    # 첫 봉 상승은 구조적으로 못 먹는다. 이 한 칸이 실행 지연의 값이다.
    assert r.final == pytest.approx(100.0 * (1 + up) ** (n - 2), rel=1e-9)


def test_too_few_bars_rejected():
    with pytest.raises(ValueError, match="최소 2"):
        run(flat(1), lambda t, p: 0.0, V)


def test_bars_reject_unsorted_timestamps():
    with pytest.raises(ValueError, match="오름차순"):
        Bars("T", [2 * HOUR, HOUR], [1, 1], [1, 1], [1, 1], [1, 1])
