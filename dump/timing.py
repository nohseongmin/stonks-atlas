"""타이밍 전략 — PREREG_TIMING.md. **단일 자산 진입·청산.**

123 시행이 전부 횡단면이었다. 이건 처음으로 "언제 들어가나"를 묻는다.
"""
from __future__ import annotations

import math
import statistics as st

from .zoo import _ema, _sd, rets, total

VOL_TARGET = 0.20
MAX_LEVERAGE = 3.0
DD_LIMIT = -0.20


def _rv(close, n=60):
    """연율화 실현변동성. 크립토는 365 일."""
    r = rets(close, n)
    sd = _sd(r) if r else None
    return None if not sd else sd * math.sqrt(365)


def tsmom(n):
    def rule(t, past):
        v = total(past["close"], n)
        return None if v is None else (1.0 if v > 0 else 0.0)
    return rule


def sma_cross(fast=50, slow=200):
    def rule(t, past):
        c = past["close"]
        if len(c) < slow:
            return None
        return 1.0 if st.fmean(c[-fast:]) > st.fmean(c[-slow:]) else 0.0
    return rule


def donchian(n=55):
    """고점 갱신이면 롱, 저점이면 현금. 그 사이는 **유지**한다."""
    def rule(t, past):
        h, l, c = past["high"], past["low"], past["close"]
        if len(c) < n + 1:
            return None
        if c[-1] >= max(h[-n - 1:-1]):
            return 1.0
        if c[-1] <= min(l[-n - 1:-1]):
            return 0.0
        return None
    return rule


def ema_cta():
    """다속도 EMA 차를 변동성 정규화해 tanh 평균. 음수는 현금(숏 안 씀)."""
    def rule(t, past):
        c = past["close"]
        if len(c) < 200:
            return None
        v = _rv(c)
        if not v or c[-1] <= 0:
            return None
        w = list(c[-200:])
        sig = st.fmean([math.tanh((_ema(w, f) - _ema(w, s)) / (c[-1] * v / math.sqrt(365)))
                        for f, s in ((16, 48), (32, 96), (64, 192))])
        return max(0.0, min(1.0, sig))
    return rule


def vol_target(target=VOL_TARGET, cap=MAX_LEVERAGE):
    """항상 롱, 노출 = 목표변동성 / 실현변동성. **수익은 안 건드리고 변동성만 맞춘다.**"""
    def rule(t, past):
        v = _rv(past["close"])
        return None if not v else min(cap, target / v)
    return rule


def dd_derisk(n=60, limit=DD_LIMIT):
    def rule(t, past):
        c = past["close"]
        if len(c) < n:
            return None
        hi = max(c[-n:])
        return 0.0 if hi > 0 and c[-1] / hi - 1 < limit else 1.0
    return rule


def build_timing():
    return [
        ("tsmom_90", tsmom(90)),
        ("tsmom_180", tsmom(180)),
        ("sma_50_200", sma_cross()),
        ("donchian_55t", donchian()),
        ("ema_cta", ema_cta()),
        ("vol_target_20", vol_target()),
        ("dd_derisk", dd_derisk()),
    ]
