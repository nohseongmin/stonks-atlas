"""포지션 팩터 — PREREG_OI.md 그대로. **점수만 다르고 나머지는 #1~#5 와 동일.**

OI 자료는 봉이 아니라 **날짜 키 dict** 로 들어온다. 그래서 축 정렬을 따로 한다.
`past` 에 `oi` 키로 **t 시점까지의 일별 요약 리스트**를 넣어준다.

    각 원소 = [OI(USD), 상위트레이더 롱숏비, 전체계정 롱숏비, 테이커 롱숏비]
"""
from __future__ import annotations

import statistics as st

from .strategies import GROSS_LEVERAGE, MIN_NAMES, QUANTILE, _liquid
from .zoo import Factor, _sd

OI, TOP, ACCT, TAKER = 0, 1, 2, 3


def _col(p, i, n):
    """창 안의 **실제 관측만** 뽑는다. 빠진 날은 None 이고 채우지 않는다.

    앞으로 채우면(forward-fill) 없는 자료를 만들어내는 것이고, 0 으로 채우면
    순위가 뒤집힌다. 관측이 창의 절반도 없으면 그 종목은 그날 제외한다.
    """
    o = p.get("oi")
    if not o or len(o) < n:
        return None
    v = [row[i] for row in o[-n:] if row is not None]
    return v if len(v) >= n // 2 else None


def _growth(p, n):
    """창 양 끝의 실제 관측으로 증가율. 끝이 비어 있으면 계산하지 않는다."""
    o = p.get("oi")
    if not o or len(o) < n + 1:
        return None
    w = o[-n - 1:]
    first = next((r for r in w if r is not None), None)
    last = next((r for r in reversed(w) if r is not None), None)
    if first is None or last is None or first is last or first[OI] <= 0:
        return None
    return last[OI] / first[OI] - 1


def _mean(p, i, n):
    v = _col(p, i, n)
    return st.fmean(v) if v else None


def _price_ret(p, n):
    c = p["close"]
    if len(c) < n + 1 or c[-n - 1] <= 0:
        return None
    return c[-1] / c[-n - 1] - 1


def build_oi():
    """PREREG_OI.md 표 그대로. 방향은 출처 주장대로 고정한다."""
    F = Factor
    return [
        F("oi_growth_7", "position", +1, lambda p: _growth(p, 7)),
        F("oi_growth_30", "position", +1, lambda p: _growth(p, 30)),
        F("oi_price_div", "position", +1,
          lambda p: (None if _growth(p, 30) is None or _price_ret(p, 30) is None
                     else _growth(p, 30) - _price_ret(p, 30)),
          "OI 는 느는데 가격이 안 오른 쪽"),
        F("oi_to_vol", "position", -1,
          lambda p: (None if _mean(p, OI, 1) is None or len(p["qvol"]) < 30
                     or st.fmean(p["qvol"][-30:]) <= 0
                     else _mean(p, OI, 1) / st.fmean(p["qvol"][-30:])),
          "회전 안 되는 포지션 회피"),
        F("lsr_retail", "position", -1, lambda p: _mean(p, ACCT, 30),
          "**개인이 몰린 쪽 반대**"),
        F("lsr_top", "position", +1, lambda p: _mean(p, TOP, 30),
          "상위 트레이더를 따라간다"),
        F("lsr_spread", "position", +1,
          lambda p: (None if _mean(p, TOP, 30) is None or _mean(p, ACCT, 30) is None
                     else _mean(p, TOP, 30) - _mean(p, ACCT, 30)),
          "스마트-덤 스프레드"),
        F("lsr_chg", "position", -1,
          lambda p: (None if _mean(p, ACCT, 7) is None or _mean(p, ACCT, 30) is None
                     else _mean(p, ACCT, 7) - _mean(p, ACCT, 30)),
          "개인 쏠림의 변화"),
        F("taker_ls_30", "position", +1, lambda p: _mean(p, TAKER, 30),
          "metrics 판 주문흐름"),
        F("oi_shock_7", "position", +1,
          lambda p: (None if _mean(p, OI, 7) is None or _mean(p, OI, 30) in (None, 0)
                     else _mean(p, OI, 7) / _mean(p, OI, 30))),
    ]


def oi_rule(f, quantile=None):
    """`#1`~`#5` 와 같은 뼈대. 점수만 포지션 자료에서 온다."""
    q = QUANTILE if quantile is None else quantile

    def rule(t, past, live):
        pool = _liquid(past, live)
        if not pool:
            return {}
        score = {}
        for s in pool:
            v = f.score(past[s])
            if v is not None and v == v and abs(v) != float("inf"):
                score[s] = v * f.direction
        if len(score) < MIN_NAMES:
            return {}
        ranked = sorted(score, key=score.get, reverse=True)
        k = max(1, int(len(ranked) * q))
        top, bot = ranked[:k], ranked[-k:]
        side = GROSS_LEVERAGE / 2
        w = {s: side / len(top) for s in top}
        w.update({s: -side / len(bot) for s in bot})
        return w
    return rule
