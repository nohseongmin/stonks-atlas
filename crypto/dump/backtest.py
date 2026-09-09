"""체결 시뮬 — **비용을 먼저 빼고 나서 수익을 말한다.**

앞선 프로젝트에서 하네스 자책 버그가 14 개 나왔고 관문은 그중 하나도 못 잡았다.
가장 비쌌던 건 룩어헤드(#26)였다 — 규칙 함수에 원본 전체 배열을 넘겨서
`arr[-1]` 이 표본의 마지막 날이었다. 상관계수가 정확히 1.0000 이 나와서 우연히 걸렸다.

그래서 여기서는 규칙 함수가 **미래를 물리적으로 못 만지게** 한다.
`PastView` 는 `t` 이후 인덱스에 `IndexError` 를 던진다. 잊어버려서 새는 게 아니라
새려고 하면 터진다.

## 무기한선물이 주식과 다른 점

**펀딩.** 8 시간마다 롱↔숏 사이에 돈이 오간다. 포지션을 정산 시점에 들고 있으면
명목 대비로 낸다(또는 받는다). 스캘핑은 대개 정산을 안 넘기지만
**넘기는지 안 넘기는지는 시뮬이 판단할 일**이지 가정할 일이 아니다.

**청산.** 주식엔 없다. L 배면 역방향 1/L 만 움직여도 자본이 0 이 된다.
봉 안에서 일어나므로 종가만 보면 절대 안 잡힌다 — 고가/저가로 본다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .costs import Venue


class PastView:
    """`lst` 의 **인덱스 0..end 만** 보이는 읽기 전용 뷰. 복사하지 않는다.

    end 를 넘는 인덱스는 `IndexError` 다. 미래 참조가 조용히 성공하지 않는다.
    """

    __slots__ = ("_l", "_n")

    def __init__(self, lst, end: int):
        # **실제 길이로 자른다.** 안 자르면 빈 배열에 길이 60 을 주장하고,
        # 그걸 믿은 필터가 "자료가 충분하다"고 판단해 통과시킨다
        # (거래대금 없는 심볼이 유동성 필터를 통과할 뻔했다).
        self._l, self._n = lst, min(end + 1, len(lst))

    def __len__(self) -> int:
        return self._n

    def __getitem__(self, k):
        if isinstance(k, slice):
            start, stop, step = k.indices(self._n)
            return self._l[start:stop:step]
        i = k + self._n if k < 0 else k
        if not 0 <= i < self._n:
            raise IndexError(f"미래 참조 차단: {k} (가용 0..{self._n - 1})")
        return self._l[i]

    def __iter__(self):
        return iter(self._l[:self._n])


@dataclass
class Bars:
    """단일 심볼 OHLCV. `ts` 는 밀리초 epoch, 오름차순."""

    symbol: str
    ts: list[int]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    #: (정산시각ms, 요율) 오름차순. 롱이 내는 쪽이 양수.
    funding: list[tuple[int, float]] = field(default_factory=list)
    #: 봉별 거래대금(USDT). **유동성 필터에 쓴다** — 10~30bp 로 거래 가능한
    #: 종목만 남기려면 이게 있어야 한다. 없으면 빈 목록.
    qvol: list[float] = field(default_factory=list)
    #: 봉별 **테이커 매수** 거래대금. `tbuy/qvol` 이 주문흐름 불균형이다.
    #: klines CSV 10 번 열에 원래 있었는데 안 파싱하고 있었다 — 공짜 차원.
    tbuy: list[float] = field(default_factory=list)

    def __post_init__(self):
        n = len(self.ts)
        for extra in ("qvol", "tbuy"):
            v = getattr(self, extra)
            if v and len(v) != n:
                raise ValueError(f"{self.symbol}: {extra} 길이가 ts 와 다르다")
        for name in ("open", "high", "low", "close"):
            if len(getattr(self, name)) != n:
                raise ValueError(f"{self.symbol}: {name} 길이가 ts 와 다르다")
        if n and any(b <= a for a, b in zip(self.ts, self.ts[1:])):
            raise ValueError(f"{self.symbol}: ts 가 오름차순이 아니다")

    def __len__(self) -> int:
        return len(self.ts)


@dataclass
class Result:
    equity: list[float]
    target: list[float]          # 각 봉 진입 시점의 목표 레버리지(부호 있음)
    fees_paid: float
    funding_paid: float
    trades: int
    liquidated_at: int | None
    bars: int
    #: 심볼별 누적 손익 기여. **소수 종목이 만든 결과인지** 보는 데 쓴다.
    contrib: dict = field(default_factory=dict)

    @property
    def final(self) -> float:
        return self.equity[-1] if self.equity else 0.0

    @property
    def total_return(self) -> float:
        if not self.equity or self.equity[0] == 0:
            return 0.0
        return self.final / self.equity[0] - 1


#: 유지증거금률. 거래소·명목티어마다 다르다. 정찰 후 Venue 로 옮긴다.
# [검증] BTCUSDT·ETHUSDT 1구간(0~300,000 USDT) 0.40%, 최대 150배.
# ponytail: 1구간 값만 쓴다. $100 계좌는 이 구간을 벗어날 일이 없다.
MAINTENANCE_MARGIN = 0.004


def run(bars: Bars, rule, venue: Venue, capital: float = 100.0,
        maker: bool = False, maintenance: float = MAINTENANCE_MARGIN) -> Result:
    """`rule(t, past) -> 목표 레버리지` 를 매 봉마다 부른다.

    `past` 는 `PastView` 묶음이라 `t` 봉 종가까지만 보인다. 반환한 목표는
    **다음 봉 시가에 체결**된다 — 같은 봉 종가로 체결하면 그게 룩어헤드다.

    `None` 을 반환하면 직전 포지션 유지, `0` 은 청산이다. 둘은 다르다
    (앞 프로젝트에서 이 둘을 섞어놔서 위험 축소가 한 번도 작동 안 했다).
    """
    n = len(bars)
    if n < 2:
        raise ValueError(f"봉이 {n} 개다. 최소 2 개 필요")
    if capital <= 0:
        raise ValueError(f"자본은 양수여야 한다: {capital}")

    fee = (venue.maker_bps if maker else venue.taker_bps) / 1e4
    half_spread = venue.spread_bps / 2e4
    one_way = fee + half_spread

    eq = capital
    pos = 0.0                     # 현재 목표 레버리지 (부호 있음)
    equity, targets = [capital], []
    fees = funding_cost = 0.0
    trades = 0
    liquidated = None
    fidx = 0

    for t in range(n - 1):
        past = {k: PastView(getattr(bars, k), t)
                for k in ("ts", "open", "high", "low", "close")}
        want = rule(t, past)
        if want is None:
            want = pos
        want = float(want)
        if abs(want) > venue.max_leverage:
            raise ValueError(f"t={t}: 목표 {want} 가 최대 레버리지 "
                             f"{venue.max_leverage} 를 넘는다")

        o, hi, lo, c = (bars.open[t + 1], bars.high[t + 1],
                        bars.low[t + 1], bars.close[t + 1])
        if o <= 0:
            raise ValueError(f"t={t+1}: 시가가 {o} 다")

        # **갭 먼저.** 기존 포지션은 close[t] 에 마킹돼 있고 체결은 open[t+1] 이다.
        # 이 구간을 빼먹으면 봉 사이 수익이 통째로 사라진다(테스트가 잡았다).
        if pos != 0:
            gap = (o - bars.close[t]) / bars.close[t]
            eq *= 1 + pos * gap
            if eq <= 0:
                equity.append(0.0)
                liquidated = t + 1
                break

        # 시가에 체결. 거래 명목은 **레버리지 변화분 x 자본**.
        delta = abs(want - pos)
        if delta > 0:
            cost = eq * delta * one_way
            fees += cost
            eq -= cost
            trades += 1
        pos = want
        targets.append(pos)

        # **봉 안에서 청산되는지 먼저 본다.** 종가만 보면 절대 안 잡힌다.
        if pos != 0:
            adverse = (o - lo) / o if pos > 0 else (hi - o) / o
            if abs(pos) * adverse >= 1 - maintenance:
                eq = 0.0
                equity.append(0.0)
                liquidated = t + 1
                break

        eq *= 1 + pos * (c - o) / o

        # 펀딩 — 이 봉 구간에 걸친 정산 전부. 롱이 양수 요율을 낸다.
        while fidx < len(bars.funding) and bars.funding[fidx][0] <= bars.ts[t + 1]:
            ftime, rate = bars.funding[fidx]
            if ftime > bars.ts[t] and pos != 0:
                pay = eq * pos * rate
                funding_cost += pay
                eq -= pay
            fidx += 1

        if eq <= 0:
            eq = 0.0
            equity.append(0.0)
            liquidated = t + 1
            break
        equity.append(eq)

    return Result(equity, targets, fees, funding_cost, trades, liquidated, n)


def date_axis(bars: dict[str, Bars]) -> list[int]:
    """전 심볼 타임스탬프의 합집합. **상폐된 심볼의 날짜도 들어간다.**"""
    return sorted({t for b in bars.values() for t in b.ts})


def _index(bars: dict[str, Bars], axis: list[int]) -> dict[str, list[int | None]]:
    """축의 각 자리에 대응하는 심볼별 인덱스. 없으면 None."""
    out = {}
    for sym, b in bars.items():
        pos = {t: i for i, t in enumerate(b.ts)}
        out[sym] = [pos.get(t) for t in axis]
    return out


def _funding_index(bars: dict[str, Bars], axis: list[int]) -> dict[str, list[int]]:
    """축의 각 자리까지 **정산이 끝난** 펀딩 건수.

    펀딩은 봉이 아니라 8 시간 이벤트라 축에 1:1 로 안 붙는다. 규칙 함수가
    `t` 시점까지의 펀딩만 보게 하려면 이 개수로 잘라줘야 한다.
    """
    import bisect
    out = {}
    for sym, b in bars.items():
        ts = [f[0] for f in b.funding]
        out[sym] = [bisect.bisect_right(ts, t) for t in axis]
    return out


def run_cross_section(bars: dict[str, Bars], rule, venue: Venue,
                      capital: float = 100.0, rebalance: int = 7,
                      maker: bool = False, extra: dict | None = None) -> Result:
    """횡단면 전략. `rule(t, past, live) -> {심볼: 가중치}` 를 리밸런싱마다 부른다.

    `live` 는 **그 시점에 실제로 거래되던 심볼**이다. 상폐된 것도 살아 있던
    동안엔 들어 있고, 아직 상장 전인 것은 안 들어 있다. 이게 시점정합이다.

    가중치는 부호 있는 값이고 `sum(|w|)` 가 총 레버리지다.
    `None` 은 유지, `{}` 는 전량 청산 — **둘은 다르다.**

    ## 상폐 처리

    바이낸스는 상폐되는 무기한을 **마지막 마크가격으로 정산**한다. 그래서 마지막
    종가에 청산하는 것이 맞고, 임의의 상폐손실 계수를 넣지 않는다. 폭락은
    이미 봉에 찍혀 있다.

    ## 한계

    청산 판정을 **종가 기준**으로만 한다. 단일 심볼 경로는 봉 안 고가/저가를
    보지만 여기서는 여러 종목의 최악값이 동시에 오지 않으므로 그렇게 하면
    과도하게 보수적이다.
    """
    axis = date_axis(bars)
    n = len(axis)
    if n < 2:
        raise ValueError(f"축이 {n} 개다. 최소 2 개 필요")
    if rebalance < 1:
        raise ValueError(f"리밸런싱 간격은 1 이상이어야 한다: {rebalance}")

    idx = _index(bars, axis)
    fidx = _funding_index(bars, axis)
    #: 심볼 -> {이름: 축 정렬된 일별 배열}. 오픈인터레스트·현물 등.
    #: 값이 dict 가 아니면 예전 형태(oi 하나)로 보고 감싸준다.
    ext = {s: (v if isinstance(v, dict) else {"oi": v})
           for s, v in (extra or {}).items()}
    fee = (venue.maker_bps if maker else venue.taker_bps) / 1e4
    one_way = fee + venue.spread_bps / 2e4

    eq = capital
    held: dict[str, float] = {}
    equity, fees = [capital], 0.0
    funding_cost = 0.0
    trades = 0
    liquidated = None
    contrib: dict[str, float] = {}
    fpos = {s: 0 for s in bars}

    for t in range(n - 1):
        live = [s for s, ix in idx.items() if ix[t] is not None]

        if t % rebalance == 0:
            past = {}
            for s in live:
                d = {k: PastView(getattr(bars[s], k), idx[s][t])
                     for k in ("ts", "open", "high", "low", "close", "qvol", "tbuy")}
                d["funding"] = PastView(bars[s].funding, fidx[s][t] - 1)
                for name, arr in ext.get(s, {}).items():
                    d[name] = PastView(arr, t)
                past[s] = d
            want = rule(t, past, live)
            if want is not None:
                want = {s: float(w) for s, w in want.items() if w}
                gross = sum(abs(w) for w in want.values())
                if gross > venue.max_leverage:
                    raise ValueError(f"t={t}: 총 레버리지 {gross:.1f} 가 최대 "
                                     f"{venue.max_leverage} 를 넘는다")
                unknown = set(want) - set(live)
                if unknown:
                    raise ValueError(f"t={t}: 거래되지 않는 심볼에 가중치 — "
                                     f"{sorted(unknown)[:3]}")
                turn = sum(abs(want.get(s, 0.0) - held.get(s, 0.0))
                           for s in set(want) | set(held))
                if turn > 0:
                    cost = eq * turn * one_way
                    fees += cost
                    eq -= cost
                    trades += 1
                held = want

        # 이번 봉에 사라지는 종목은 마지막 종가에 정산한다(마크가격 정산).
        gone = [s for s in held if idx[s][t + 1] is None]
        if gone:
            turn = sum(abs(held[s]) for s in gone)
            cost = eq * turn * one_way
            fees += cost
            eq -= cost
            for s in gone:
                del held[s]

        pnl = 0.0
        for s, w in held.items():
            i0, i1 = idx[s][t], idx[s][t + 1]
            c0, c1 = bars[s].close[i0], bars[s].close[i1]
            if c0 > 0:
                part = w * (c1 / c0 - 1)
                pnl += part
                contrib[s] = contrib.get(s, 0.0) + part * eq
        eq *= 1 + pnl

        for s, w in held.items():
            fund = bars[s].funding
            while fpos[s] < len(fund) and fund[fpos[s]][0] <= axis[t + 1]:
                ftime, rate = fund[fpos[s]]
                if ftime > axis[t]:
                    pay = eq * w * rate
                    funding_cost += pay
                    eq -= pay
                fpos[s] += 1

        if eq <= 0:
            equity.append(0.0)
            liquidated = t + 1
            break
        equity.append(eq)

    return Result(equity, [], fees, funding_cost, trades, liquidated, n, contrib)
