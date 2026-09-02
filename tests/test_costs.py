"""비용 산술 검정. 여기가 틀리면 이 프로젝트 전체가 틀린다."""
import math

import pytest

from dump.costs import (Venue, annual_to_bps_per_period, liquidation_move, max_cagr, required_edge_bps,
                        required_win_rate, ruin_by_fees_days)

V = Venue("test", taker_bps=5.0, maker_bps=2.0, spread_bps=1.0,
          min_notional_usd=100.0, max_leverage=125.0,
          funding_bps_per_period=1.0, source="합성", verified=True)


def test_round_trip_is_leverage_free():
    """**핵심 주장**: 손익분기 가격변동은 레버리지에 안 변한다."""
    assert V.round_trip_bps() == pytest.approx(11.0)
    assert V.round_trip_bps(maker=True) == pytest.approx(5.0)


def test_equity_cost_scales_with_leverage():
    """자본 대비 비용은 정확히 레버리지에 비례한다."""
    assert V.equity_cost_frac(1) == pytest.approx(0.0011)
    assert V.equity_cost_frac(10) == pytest.approx(0.011)
    assert V.equity_cost_frac(20) == pytest.approx(2 * V.equity_cost_frac(10))


def test_required_win_rate_diverges_at_small_targets():
    """익절폭이 왕복비용과 같아지면 필요 승률 100% — 스캘핑이 죽는 지점."""
    assert required_win_rate(1000, V) == pytest.approx(0.5055, abs=1e-4)
    cost = V.round_trip_bps()
    assert required_win_rate(cost, V) == pytest.approx(1.0)
    assert required_win_rate(cost / 2, V) > 1.0


def test_required_win_rate_rejects_nonpositive():
    with pytest.raises(ValueError):
        required_win_rate(0, V)


def test_required_edge_covers_cost_at_minimum():
    """어떤 목표에서도 필요 엣지는 왕복비용보다 크다."""
    for tpd in (0.2, 1, 5, 20):
        assert required_edge_bps(0.05, tpd, V, 10) > V.round_trip_bps()


def test_required_edge_falls_with_leverage_and_rises_with_frequency():
    a = required_edge_bps(0.05, 1, V, 3)
    b = required_edge_bps(0.05, 1, V, 10)
    assert b < a                       # 레버리지가 높으면 거래당 필요 폭은 작아진다
    assert required_edge_bps(0.05, 20, V, 10) < required_edge_bps(0.05, 1, V, 10)


def test_ruin_by_fees_matches_closed_form():
    """신호 0 일 때 수수료만으로 -99% 까지 걸리는 시간."""
    c = V.equity_cost_frac(10)
    expected = math.log(0.01) / math.log(1 - c) / 10
    assert ruin_by_fees_days(10, V, 10) == pytest.approx(expected)
    assert ruin_by_fees_days(10, V, 20) < ruin_by_fees_days(10, V, 10)


def test_ruin_infinite_when_free():
    free = Venue("free", 0, 0, 0, 0, 1, 0)
    assert ruin_by_fees_days(10, free, 10) == math.inf


def test_max_cagr_ceiling():
    """레버리지 상한 — STONKS-03 에서 넘어온 항등식."""
    assert max_cagr(0.0) == pytest.approx(0.04)
    assert max_cagr(1.0) == pytest.approx(0.54)
    assert max_cagr(2.0) == pytest.approx(2.04)


def test_liquidation_move_shrinks_with_leverage():
    assert liquidation_move(10, 0.004) == pytest.approx(0.096)
    assert liquidation_move(100, 0.004) == pytest.approx(0.006)
    assert liquidation_move(500, 0.004) == 0.0
    with pytest.raises(ValueError):
        liquidation_move(0)


def test_annual_funding_converts_to_period():
    """연 2.75% -> 8h 당 bp. 정산이 하루 3 번, 1 년 365 일."""
    assert annual_to_bps_per_period(0.0275) == pytest.approx(0.0275 / 1095 * 1e4)
    assert annual_to_bps_per_period(0.0) == 0.0


def test_binance_venue_is_verified_others_are_not():
    """검증 플래그가 실제 상태를 말해야 한다. 안 잰 건 안 잰 거다."""
    from dump.costs import BINANCE_USDM, BYBIT, HYPERLIQUID
    assert BINANCE_USDM.verified            # 수수료·스프레드·펀딩 전부 실측
    assert not HYPERLIQUID.verified and not BYBIT.verified   # 스프레드 미측정
    assert BINANCE_USDM.taker_bps == 5.0
    assert BINANCE_USDM.min_notional_usd == pytest.approx(77.58)
    assert BINANCE_USDM.round_trip_bps() == pytest.approx(10.0129)


def test_maker_only_loses_to_fees_on_btc():
    """**"지정가만 쓰면 된다"는 탈출구가 닫혀 있는지.**

    BTC 무기한 스프레드 전체가 0.0129bp 인데 메이커 왕복은 4bp 다.
    스프레드를 양쪽 다 완벽히 먹어도 왕복마다 진다.
    """
    from dump.costs import BINANCE_USDM, SPREAD_BPS
    captured = SPREAD_BPS["BTCUSDT"]
    maker_cost = 2 * BINANCE_USDM.maker_bps
    assert captured - maker_cost == pytest.approx(-3.9871)


def test_liquidation_fee_dwarfs_trading_fees():
    """**청산 한 번 = 테이커 체결 25 회분.** 비용 모델의 진짜 주인공.

    그리고 청산은 언제나 전액 손실이다 — L=10 에서 수수료만 자본의 12.5% 인데
    그 시점에 남은 증거금은 자본의 4%(명목의 0.40%) 뿐이다.
    """
    from dump.costs import BINANCE_USDM as V
    assert V.liquidation_fee_bps / V.taker_bps == pytest.approx(25.0)
    assert V.liquidation_cost_frac(10) == pytest.approx(0.125)
    assert V.liquidation_cost_frac(10) > V.maintenance_margin * 10


def test_bnb_discount_is_ten_percent_on_futures():
    """선물은 10%, 현물은 25%. 섞으면 비용을 낙관하게 된다."""
    from dump.costs import BINANCE_USDM, BINANCE_USDM_BNB
    assert BINANCE_USDM_BNB.taker_bps == pytest.approx(BINANCE_USDM.taker_bps * 0.9)
    assert BINANCE_USDM_BNB.liquidation_fee_bps == BINANCE_USDM.liquidation_fee_bps


def test_hyperliquid_is_cheaper_than_binance():
    from dump.costs import BINANCE_USDM, BYBIT, HYPERLIQUID
    assert HYPERLIQUID.round_trip_bps() < BINANCE_USDM.round_trip_bps() < BYBIT.round_trip_bps()
    assert not HYPERLIQUID.verified          # 스프레드를 안 쟀다
