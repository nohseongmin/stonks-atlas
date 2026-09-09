"""베이시스 팩터 — PREREG_BASIS.md. **아무도 안 해본 유일한 축.**

`past[s]["spot"]` 에 축 정렬된 현물 종가가 들어온다(없는 날은 None).
무기한 OHLC4 와 현물 OHLC4 의 비율이 베이시스다.

    b = 무기한 OHLC4 / 현물 OHLC4 − 1

OHLC4 를 쓰는 이유: 종가 하나는 스냅샷 잡음이 크다. 두 시장의 종가가
같은 순간이 아닐 수 있고, 그 차이가 그대로 가짜 베이시스가 된다.
"""
from __future__ import annotations

import statistics as st

from .strategies import GROSS_LEVERAGE, MIN_NAMES, QUANTILE, _liquid
from .zoo import Factor, _funding, _sd

RESID_WINDOW = 5
Z_WINDOW = 60
#: 자기 베이시스 변동이 이보다 작으면 z 점수가 반올림 잡음으로 폭발한다.
MIN_BASIS_SD = 5e-4


def _ohlc4(p, i):
    return (p["open"][i] + p["high"][i] + p["low"][i] + p["close"][i]) / 4


def series(p, n):
    """직전 `n` 일 베이시스. 현물이 없는 날은 **건너뛴다**(채우지 않는다)."""
    sp = p.get("spot")
    if sp is None or len(sp) < n or len(p["close"]) < n:
        return None
    out = []
    for k in range(-n, 0):
        s = sp[k]
        if s is None or s <= 0:
            continue
        perp = _ohlc4(p, k)
        if perp > 0:
            out.append(perp / s - 1)
    return out if len(out) >= max(2, n // 2) else None


def _level(p, n):
    v = series(p, n)
    return st.fmean(v) if v else None


def _z(p, n=Z_WINDOW):
    v = series(p, n)
    if not v:
        return None
    sd = _sd(v)
    return None if not sd or sd < MIN_BASIS_SD else (v[-1] - st.fmean(v)) / sd


def _chg(p):
    a, b = series(p, 3), series(p, 10)
    if not a or not b or len(b) < 4:
        return None
    return st.fmean(a) - st.fmean(b[:-3])


def build_basis():
    F = Factor
    return [
        F("basis_7", "basis", -1, lambda p: _level(p, 7),
          "베이시스 높은 쪽 숏 — 레버리지 롱이 몰린 것"),
        F("basis_z_60", "basis", -1, lambda p: _z(p),
          "자기 과거 대비 괴리 — 되돌아온다"),
        F("basis_chg", "basis", +1, lambda p: _chg(p),
          "레버리지 수요 충격 — 짧은 구간에선 이어진다"),
    ]


def resid_rule(quantile=None):
    """**펀딩이 설명 못 하는 베이시스**로 정렬한다. 이 배치의 핵심.

    매 리밸런싱마다 횡단면 회귀 `b_i = a + c·f_i + e_i` 를 풀고 잔차로 정렬한다.
    종목 하나만 봐서는 못 만드는 점수라 `Factor` 가 아니라 규칙으로 짠다.
    """
    q = QUANTILE if quantile is None else quantile

    def rule(t, past, live):
        pool = _liquid(past, live)
        if not pool:
            return {}
        pairs = {}
        for s in pool:
            b = _level(past[s], RESID_WINDOW)
            f = _funding(past[s], RESID_WINDOW)
            if b is not None and f is not None:
                pairs[s] = (b, f)
        if len(pairs) < MIN_NAMES:
            return {}
        bs = [v[0] for v in pairs.values()]
        fs = [v[1] for v in pairs.values()]
        vf = st.pvariance(fs)
        mb, mf = st.fmean(bs), st.fmean(fs)
        # 펀딩이 전부 같으면 회귀가 성립 안 한다 — 그땐 잔차 = 편차다.
        c = (0.0 if vf == 0 else
             sum((f - mf) * (b - mb) for b, f in pairs.values()) / len(pairs) / vf)
        # **부호 −1**: 펀딩이 설명하는 것보다 비싼 무기한을 숏한다.
        score = {s: -((b - mb) - c * (f - mf)) for s, (b, f) in pairs.items()}
        ranked = sorted(score, key=score.get, reverse=True)
        k = max(1, int(len(ranked) * q))
        top, bot = ranked[:k], ranked[-k:]
        side = GROSS_LEVERAGE / 2
        w = {s: side / len(top) for s in top}
        w.update({s: -side / len(bot) for s in bot})
        return w

    return rule
