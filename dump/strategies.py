"""전략 규칙. **사전등록 문서에 적힌 그대로만 구현한다.**

여기에 파라미터를 추가하고 싶어지면 그건 코드 문제가 아니라 **새 사전등록이
필요한 일**이다. `PREREG_*.md` 에 없는 숫자가 이 파일에 있으면 안 된다.
"""
from __future__ import annotations

import statistics as st

#: PREREG_LTW.md 에 고정된 값들. 결과를 보고 바꾸지 않는다.
LIQUIDITY_TOP_FRAC = 0.50      # 거래대금 상위 절반
QUANTILE = 0.20                # 상하위 20%
LIQUIDITY_WINDOW = 30          # 거래대금 평균 창(일)
MIN_NAMES = 20                 # 이보다 적으면 횡단면이 성립 안 한다
GROSS_LEVERAGE = 1.0


def _liquid(past: dict, live: list[str]) -> list[str]:
    """직전 `LIQUIDITY_WINDOW` 일 평균 거래대금 **상위 절반**.

    거래대금이 없는 심볼은 **버린다.** 0 으로 치면 자동으로 하위에 몰려
    "유동성 없는 종목만 골라 담기"가 된다 — 부호가 정반대인 실수다.
    """
    vol = {}
    for s in live:
        q = past[s].get("qvol")
        if q is None or len(q) < LIQUIDITY_WINDOW:
            continue
        v = st.fmean(q[-LIQUIDITY_WINDOW:])
        if v > 0:
            vol[s] = v
    if len(vol) < MIN_NAMES:
        return []
    keep = max(MIN_NAMES, int(len(vol) * LIQUIDITY_TOP_FRAC))
    return sorted(vol, key=vol.get, reverse=True)[:keep]


def momentum(lookback: int, long_only: bool = False):
    """직전 `lookback` 일 수익으로 정렬해 상위 롱 / 하위 숏.

    `long_only=True` 면 숏 다리를 뺀다 — 상폐 직전 유동성이 결과를 만드는지
    가리기 위한 변형이고, 사전등록에 3 번째 시행으로 적혀 있다.
    """
    def rule(t, past, live):
        pool = _liquid(past, live)
        if not pool:
            return {}
        score = {}
        for s in pool:
            c = past[s]["close"]
            if len(c) > lookback and c[-lookback - 1] > 0:
                score[s] = c[-1] / c[-lookback - 1] - 1
        if len(score) < MIN_NAMES:
            return {}
        ranked = sorted(score, key=score.get, reverse=True)
        k = max(1, int(len(ranked) * QUANTILE))
        top, bot = ranked[:k], ranked[-k:]
        if long_only:
            return {s: GROSS_LEVERAGE / len(top) for s in top}
        side = GROSS_LEVERAGE / 2
        w = {s: side / len(top) for s in top}
        w.update({s: -side / len(bot) for s in bot})
        return w

    return rule
