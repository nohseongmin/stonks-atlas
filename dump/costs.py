"""비용 산술 — **이 프로젝트의 첫 번째 관문.**

전략을 하나라도 짜기 전에 여기를 통과해야 한다. 이유는 앞선 프로젝트에서
같은 실수를 두 번 했기 때문이다:

- STONKS-03: 480 시행 중 인트라데이 전략 전멸. 원인은 신호가 아니라 **회전율**이었다.
- AI_STONKS: 틱 스캘핑 목표 0.1~0.2% 를 세웠다가, 개인 수수료에서
  필요 승률이 100% 를 넘는다는 걸 계산으로 알고 폐기했다.

두 번 다 **코드를 짜기 전에 산술로 끝났어야** 했다. 그래서 이번엔 산술이 먼저다.

## 핵심 항등식 세 개

**1. 왕복 손익분기 가격변동은 레버리지와 무관하다.**

    필요 변동 = 2f + s          (f = 편도 수수료율, s = 스프레드)

레버리지는 수익과 수수료를 **똑같이** 배로 만든다. $100 을 10 배로 굴리면
명목이 $1,000 이고 수수료도 10 배지만 수익도 10 배다. 그래서 "몇 % 움직여야
본전인가"는 레버리지가 바뀌어도 그대로다. **레버리지는 손익분기를 낮추지 않는다.**

**2. 레버리지가 바꾸는 것은 자본 대비 수수료 비중이다.**

    자본 대비 왕복 비용 = L x (2f + s)

L=10, f=5bp, s=1bp 면 왕복 한 번에 **자기 자본의 1.1%** 가 사라진다.
하루 10 번 왕복하면 하루 11%. 신호가 아무리 좋아도 이 지출이 먼저 나간다.

**3. 필요 승률은 목표 크기가 작을수록 폭발한다.**

    익절폭 = 손절폭 = m 일 때,   p = 0.5 + (2f + s) / (2m)

m 이 비용과 비슷해지면 p 가 1 로 발산한다. 스캘핑이 수학적으로 죽는 지점이 여기다.

## 수치는 전부 인자다

수수료·스프레드는 거래소·티어·심볼마다 다르고 시간이 지나면 바뀐다.
코드에 박지 않고 `Venue` 로 받는다. 기본값은 **검증 전 잠정치**이고
`verified` 플래그로 표시한다 — 검증 안 된 값으로 낸 결론은 결론이 아니다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

#: 무위험수익률. 목표 대비 상한 계산에 쓴다.
RF = 0.04
#: 1 년 = 크립토는 휴장이 없다.
DAYS_PER_YEAR = 365
#: 펀딩 정산 간격(시간). 거래소마다 다르면 Venue 로 옮긴다.
FUNDING_HOURS = 8


@dataclass(frozen=True)
class Venue:
    """거래소 비용 규격. **모든 숫자는 출처와 검증여부를 달고 다닌다.**"""

    name: str
    taker_bps: float          # 편도 테이커 수수료 (bp)
    maker_bps: float          # 편도 메이커 수수료 (bp)
    spread_bps: float         # 왕복에 한 번 지불하는 스프레드 (bp)
    min_notional_usd: float   # 최소 주문 명목
    max_leverage: float
    funding_bps_per_period: float   # 정산 1 회당 펀딩 (bp), 롱 기준 부호
    source: str = ""
    verified: bool = False

    def round_trip_bps(self, maker: bool = False) -> float:
        """왕복 총비용(bp). **명목 대비**이므로 레버리지와 무관하다."""
        fee = self.maker_bps if maker else self.taker_bps
        return 2 * fee + self.spread_bps

    def equity_cost_frac(self, leverage: float, maker: bool = False) -> float:
        """왕복 한 번이 **자기 자본**에서 갉는 비율."""
        return leverage * self.round_trip_bps(maker) / 1e4

    def funding_bps_per_day(self) -> float:
        return self.funding_bps_per_period * (24 / FUNDING_HOURS)


#: 잠정 규격. **검증 전이다.** 정찰 결과가 오면 교체하고 verified=True 로 올린다.
PROVISIONAL = Venue(
    name="binance-usdm(잠정)",
    taker_bps=5.0,
    maker_bps=2.0,
    spread_bps=1.0,
    min_notional_usd=100.0,
    max_leverage=125.0,
    funding_bps_per_period=1.0,
    source="미검증 — 정찰 대기",
    verified=False,
)


def required_win_rate(target_bps: float, venue: Venue, maker: bool = False) -> float:
    """익절=손절=`target_bps` 인 1:1 매매의 손익분기 승률.

    p*m - (1-p)*m = c  =>  p = 0.5 + c/(2m).
    1 을 넘으면 **어떤 승률로도 불가능**하다는 뜻이므로 그대로 돌려준다.
    """
    if target_bps <= 0:
        raise ValueError(f"익절폭은 양수여야 한다: {target_bps}")
    return 0.5 + venue.round_trip_bps(maker) / (2 * target_bps)


def required_edge_bps(monthly_target: float, trades_per_day: float,
                      venue: Venue, leverage: float, maker: bool = False) -> float:
    """월 목표 수익률을 내려면 **매 거래마다 명목 대비 몇 bp** 를 벌어야 하나.

    자본 대비 월 목표를 명목 대비로 환산(÷L)한 뒤 거래수로 나누고 비용을 더한다.
    """
    n = trades_per_day * DAYS_PER_YEAR / 12
    if n <= 0:
        raise ValueError(f"거래 횟수가 0 이다: {trades_per_day}")
    # 복리를 로그로 편다 — 거래당 필요 로그수익.
    per_trade_equity = math.log1p(monthly_target) / n
    return per_trade_equity / leverage * 1e4 + venue.round_trip_bps(maker)


def ruin_by_fees_days(trades_per_day: float, venue: Venue, leverage: float,
                      maker: bool = False) -> float:
    """**신호가 정확히 0 일 때** 수수료만으로 자본이 1% 로 줄기까지 걸리는 일수.

    각 왕복이 자본을 (1-c) 배로 만든다고 보면 log(0.01)/log(1-c) 번 걸린다.
    """
    c = venue.equity_cost_frac(leverage, maker)
    if c <= 0:
        return math.inf
    if c >= 1:
        return 0.0
    return math.log(0.01) / math.log(1 - c) / trades_per_day


def max_cagr(sharpe: float, rf: float = RF) -> float:
    """**어떤 레버리지로도 넘을 수 없는 상한** — STONKS-03 `goal.py` 에서 가져왔다.

    CAGR - rf = S*sigma - sigma^2/2 는 sigma = S 에서 최대이고 그 값이 S^2/2 다.
    레버리지는 Sharpe 를 못 바꾸므로 이 상한은 크립토에서도 그대로다.
    """
    return rf + sharpe * sharpe / 2


def liquidation_move(leverage: float, maintenance_margin: float = 0.005) -> float:
    """청산까지 필요한 역방향 가격 변동률.

    유지증거금률 mm 일 때 대략 1/L - mm 만큼 움직이면 청산된다.
    """
    if leverage <= 0:
        raise ValueError(f"레버리지는 양수여야 한다: {leverage}")
    return max(0.0, 1 / leverage - maintenance_margin)


def report(capital: float = 100.0, venue: Venue = PROVISIONAL,
           monthly_target: float = 0.05) -> None:
    """산술을 전부 펼쳐 보인다. 검증 안 된 규격이면 맨 위에 경고를 찍는다."""
    print(f"비용 산술 — 자본 ${capital:,.0f} · {venue.name}\n")
    if not venue.verified:
        print("**경고: 이 규격은 미검증이다. 아래 숫자로 결정을 내리지 마라.**")
        print(f"출처: {venue.source}\n")
    rt = venue.round_trip_bps()
    print(f"편도 테이커 {venue.taker_bps:.1f}bp · 스프레드 {venue.spread_bps:.1f}bp"
          f"  =>  왕복 {rt:.1f}bp")
    print(f"손익분기 가격변동 {rt/1e2:.3f}%  — **레버리지를 아무리 올려도 안 낮아진다**\n")

    print("레버리지별 (자본 $%.0f 기준)" % capital)
    print(f"{'L':>4}{'명목':>10}{'왕복비용':>10}{'자본대비':>9}"
          f"{'청산변동':>9}{'수수료만으로 -99%':>18}")
    for lev in (1, 3, 5, 10, 20, 50):
        notional = capital * lev
        cost_usd = notional * rt / 1e4
        frac = venue.equity_cost_frac(lev)
        liq = liquidation_move(lev)
        days = ruin_by_fees_days(10, venue, lev)
        flag = "" if notional >= venue.min_notional_usd else "  <최소명목미달"
        print(f"{lev:>4}{notional:>9,.0f}${cost_usd:>9.2f}${frac*100:>8.2f}%"
              f"{liq*100:>8.1f}%{days:>13.1f}일(10회/일){flag}")

    print(f"\n필요 승률 (익절=손절, 왕복 {rt:.1f}bp)")
    print(f"{'목표폭':>8}{'필요승률':>10}")
    for m in (10, 20, 50, 100, 200, 500):
        p = required_win_rate(m, venue)
        mark = "  **불가능**" if p >= 1 else ""
        print(f"{m:>6}bp{p*100:>9.1f}%{mark}")

    print(f"\n월 {monthly_target*100:.0f}% 를 내려면 거래당 명목 대비 몇 bp 를 벌어야 하나")
    print(f"{'거래/일':>8}{'L=3':>10}{'L=10':>10}{'L=20':>10}")
    for tpd in (0.2, 1, 5, 20):
        row = "".join(f"{required_edge_bps(monthly_target, tpd, venue, l):>10.1f}"
                      for l in (3, 10, 20))
        print(f"{tpd:>8.1f}{row}")
    print("\n(위 숫자에는 왕복비용이 이미 포함돼 있다. 순수 신호가 저만큼 있어야 한다는 뜻)")


if __name__ == "__main__":
    report()
