"""전략 동물원 — **점수 함수만 갈아끼운다.**

횡단면 전략은 전부 같은 뼈대다: 유동성으로 거르고, 점수로 정렬하고,
상위·하위 분위를 롱숏한다. 다른 건 **점수 하나**뿐이다.

그래서 전략마다 규칙 함수를 새로 쓰지 않는다. `Factor` 는 점수 계산과
방향(높은 쪽을 사느냐 낮은 쪽을 사느냐)만 담고 나머지는 공유한다.
**전략마다 자유 파라미터를 새로 만들 여지를 코드에서 없애는 것**이 목적이다.

## 주의 — 카탈로그를 늘리면 통과 기준이 같이 올라간다

잡음바닥은 `평균 + 표준편차 x a_n` 이고 `a_n` 은 시행 수와 함께 자란다.
30 개를 태우면 바닥이 올라가고 오늘의 최고 후보가 자동으로 기각될 수 있다.
**버그가 아니라 다중검정의 정의다.** `PREREG_ZOO.md` 에 미리 적어둔다.
"""
from __future__ import annotations

import math
import statistics as st
from dataclasses import dataclass

from .strategies import GROSS_LEVERAGE, MIN_NAMES, QUANTILE, _liquid

BENCH = "BTCUSDT"


def rets(close, n):
    """직전 n 일 일간수익. 자료가 모자라거나 0 가격이 섞이면 None."""
    if len(close) < n + 1:
        return None
    w = close[-n - 1:]
    out = []
    for a, b in zip(w, w[1:]):
        if a <= 0:
            return None
        out.append(b / a - 1)
    return out


def total(close, n):
    if len(close) < n + 1 or close[-n - 1] <= 0:
        return None
    return close[-1] / close[-n - 1] - 1


@dataclass(frozen=True)
class Factor:
    """점수 하나. direction=+1 이면 높은 점수를 롱, -1 이면 낮은 쪽을 롱."""

    slug: str
    family: str
    direction: int
    fn: object
    note: str = ""

    def score(self, p):
        if self.fn is None:
            return None
        try:
            return self.fn(p)
        except (ZeroDivisionError, st.StatisticsError, ValueError, TypeError):
            return None


def _sd(x):
    return st.pstdev(x) if x and len(x) > 1 else None


def _skew(x):
    if not x or len(x) < 3:
        return None
    m, s = st.fmean(x), st.pstdev(x)
    return None if s == 0 else sum((v - m) ** 3 for v in x) / (len(x) * s ** 3)


def _kurt(x):
    if not x or len(x) < 4:
        return None
    m, s = st.fmean(x), st.pstdev(x)
    return None if s == 0 else sum((v - m) ** 4 for v in x) / (len(x) * s ** 4)


def _downside(x):
    if not x:
        return None
    d = [v for v in x if v < 0]
    return None if len(d) < 2 else st.pstdev(d)


def _maxret(x):
    return max(x) if x else None


def _amihud(p, n):
    """비유동성 = 평균(절대수익 / 거래대금). 높을수록 비유동적."""
    r = rets(p["close"], n)
    q = p["qvol"]
    if r is None or len(q) < n:
        return None
    v = [abs(a) / b for a, b in zip(r, q[-n:]) if b > 0]
    return st.fmean(v) if len(v) >= n // 2 else None


def _dd(close, n):
    if len(close) < n:
        return None
    w = close[-n:]
    hi = max(w)
    return None if hi <= 0 else w[-1] / hi - 1


def _updays(close, n):
    r = rets(close, n)
    return None if r is None else sum(1 for v in r if v > 0) / len(r)


def _range(p, n):
    if len(p["high"]) < n:
        return None
    v = [(h - l) / c for h, l, c in
         zip(p["high"][-n:], p["low"][-n:], p["close"][-n:]) if c > 0]
    return st.fmean(v) if v else None


def _volshock(p):
    q = p["qvol"]
    if len(q) < 30:
        return None
    base = st.fmean(q[-30:])
    return None if base <= 0 else st.fmean(q[-7:]) / base


def _funding(p, days):
    """직전 days 일 펀딩 평균. **8 시간마다 정산이라 하루 3 건이다.**"""
    f = p.get("funding")
    if not f:
        return None
    k = days * 3
    return None if len(f) < k else st.fmean([r for _, r in f[-k:]])


def _beta(p, n, bench):
    r = rets(p["close"], n)
    if r is None or not bench or len(bench) != len(r):
        return None
    vb = st.pvariance(bench)
    if vb == 0:
        return None
    mb, mr = st.fmean(bench), st.fmean(r)
    return sum((a - mb) * (b - mr) for a, b in zip(bench, r)) / len(r) / vb


def _idio(p, n, bench):
    r = rets(p["close"], n)
    b = _beta(p, n, bench)
    if r is None or b is None:
        return None
    mb, mr = st.fmean(bench), st.fmean(r)
    return _sd([(y - mr) - b * (x - mb) for x, y in zip(bench, r)])


def build():
    """카탈로그. **파라미터는 문헌 표준값이고 결과를 보고 바꾸지 않는다.**"""
    F = Factor
    return [
        F("mom_7", "momentum", +1, lambda p: total(p["close"], 7), "LTW 1주"),
        F("mom_14", "momentum", +1, lambda p: total(p["close"], 14), "LTW 2주"),
        F("mom_21", "momentum", +1, lambda p: total(p["close"], 21)),
        F("mom_30", "momentum", +1, lambda p: total(p["close"], 30)),
        F("mom_90", "momentum", +1, lambda p: total(p["close"], 90)),
        F("mom_skip", "momentum", +1,
          lambda p: (None if len(p["close"]) < 38 or p["close"][-38] <= 0
                     else p["close"][-8] / p["close"][-38] - 1),
          "30일 모멘텀에서 최근 7일 건너뜀 — 단기반전 오염 제거"),
        F("rev_1", "reversal", -1, lambda p: total(p["close"], 1)),
        F("rev_3", "reversal", -1, lambda p: total(p["close"], 3)),
        F("rev_90", "reversal", -1, lambda p: total(p["close"], 90)),
        F("rev_180", "reversal", -1, lambda p: total(p["close"], 180)),
        F("lowvol_30", "risk", -1, lambda p: _sd(rets(p["close"], 30))),
        F("lowvol_90", "risk", -1, lambda p: _sd(rets(p["close"], 90))),
        F("downside_30", "risk", -1, lambda p: _downside(rets(p["close"], 30))),
        F("max_ret_30", "risk", -1, lambda p: _maxret(rets(p["close"], 30)),
          "Bali 복권효과 — 최대일수익 높은 종목을 피한다"),
        F("skew_30", "risk", -1, lambda p: _skew(rets(p["close"], 30))),
        F("kurt_30", "risk", -1, lambda p: _kurt(rets(p["close"], 30))),
        F("range_30", "risk", -1, lambda p: _range(p, 30)),
        F("drawdown_60", "risk", +1, lambda p: _dd(p["close"], 60),
          "60일 고점 대비 — 0 에 가까울수록 고점 근처"),
        F("high_252", "momentum", +1, lambda p: _dd(p["close"], 252),
          "52주 고점 근접도"),
        F("amihud_30", "liquidity", +1, lambda p: _amihud(p, 30),
          "비유동성 프리미엄 — 비유동적인 쪽을 롱"),
        F("dollar_vol", "liquidity", -1,
          lambda p: st.fmean(p["qvol"][-30:]) if len(p["qvol"]) >= 30 else None,
          "거래대금 자체 — 작은 쪽을 롱(규모효과 대용)"),
        F("vol_shock_7", "flow", +1, lambda p: _volshock(p)),
        F("updays_30", "momentum", +1, lambda p: _updays(p["close"], 30),
          "추세 일관성 — 상승일 비율"),
        F("price_level", "value", -1,
          lambda p: p["close"][-1] if len(p["close"]) else None,
          "명목가격 — 싼 종목 선호"),
        F("funding_7", "carry", -1, lambda p: _funding(p, 7),
          "펀딩 높은 쪽을 숏해 걷는다"),
        F("funding_30", "carry", -1, lambda p: _funding(p, 30)),
        F("funding_chg", "carry", -1,
          lambda p: (None if _funding(p, 7) is None or _funding(p, 30) is None
                     else _funding(p, 7) - _funding(p, 30))),
        F("beta_60", "risk", -1, None, "BAB — 저베타 롱 (벤치 주입 필요)"),
        F("idio_60", "risk", -1, None, "특이변동성 낮은 쪽 롱 (벤치 주입 필요)"),
    ]


def xs_rule(f, bench_rets=None, quantile=None, exclude=None):
    """Factor 를 횡단면 규칙으로. **분위·유동성 문턱은 #1 과 동일하다.**"""
    q = QUANTILE if quantile is None else quantile
    skip = exclude or set()

    def rule(t, past, live):
        pool = [s for s in _liquid(past, live) if s not in skip]
        if not pool:
            return {}
        b = bench_rets(t) if callable(bench_rets) else bench_rets
        score = {}
        for s in pool:
            p = past[s]
            if f.slug == "beta_60":
                v = _beta(p, 60, b)
            elif f.slug == "idio_60":
                v = _idio(p, 60, b)
            elif f.slug == "dbeta_60":
                v = _dbeta(p, 60, b)
            elif f.slug == "coskew_60":
                v = _coskew(p, 60, b)
            else:
                v = f.score(p)
            if v is not None and math.isfinite(v):
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


# ══════════════════════════════════════════════════════════════════════
# 2 차 배치 — 사냥 결과(90 후보)에서 **가격·거래량·펀딩만으로 되는 것**만.
# 오픈인터레스트·롱숏비율은 아직 안 받았다(약 60 만 파일 필요).
# 파라미터는 전부 출처의 표준값이고 결과를 보고 바꾸지 않는다.
# ══════════════════════════════════════════════════════════════════════


def _gk(p, n):
    """Garman-Klass 변동성 — OHLC 를 다 쓴다. 종가만 쓰는 것보다 효율적."""
    if len(p["high"]) < n:
        return None
    v = []
    for h, l, o, c in zip(p["high"][-n:], p["low"][-n:], p["open"][-n:], p["close"][-n:]):
        if h <= 0 or l <= 0 or o <= 0 or c <= 0:
            continue
        v.append(0.5 * math.log(h / l) ** 2 - (2 * math.log(2) - 1) * math.log(c / o) ** 2)
    return math.sqrt(max(0.0, st.fmean(v))) if v else None


def _osc(close, n):
    """RSI 계산용 상승·하락 평균."""
    r = rets(close, n)
    if r is None:
        return None
    up = st.fmean([max(0.0, v) for v in r])
    dn = st.fmean([max(0.0, -v) for v in r])
    return None if up + dn == 0 else 100 * up / (up + dn)


def _stoch(p, n):
    if len(p["high"]) < n:
        return None
    hi, lo = max(p["high"][-n:]), min(p["low"][-n:])
    return None if hi <= lo else (p["close"][-1] - lo) / (hi - lo)


def _cci(p, n):
    if len(p["high"]) < n:
        return None
    tp = [(h + l + c) / 3 for h, l, c in
          zip(p["high"][-n:], p["low"][-n:], p["close"][-n:])]
    m = st.fmean(tp)
    md = st.fmean([abs(v - m) for v in tp])
    return None if md == 0 else (tp[-1] - m) / (0.015 * md)


def _sma_dist(close, n):
    if len(close) < n:
        return None
    m = st.fmean(close[-n:])
    return None if m <= 0 else close[-1] / m - 1


def _ppo(close, fast=12, slow=26):
    if len(close) < slow:
        return None
    f, s = st.fmean(close[-fast:]), st.fmean(close[-slow:])
    return None if s <= 0 else (f - s) / s


def _ctrend(close):
    """이동평균 조합 예측 — 여러 창의 SMA 거리 평균. Han-Zhou-Zhu 단순화."""
    v = [_sma_dist(close, n) for n in (5, 10, 20, 50, 100)]
    v = [x for x in v if x is not None]
    return st.fmean(v) if len(v) >= 3 else None


def _taker(p, n):
    """테이커 매수 비율 — **주문흐름 불균형.** 0.5 가 중립."""
    q, t = p["qvol"], p["tbuy"]
    if len(q) < n or len(t) < n:
        return None
    qs = sum(q[-n:])
    return None if qs <= 0 else sum(t[-n:]) / qs


def _var(x, q=0.05):
    if not x or len(x) < 20:
        return None
    s = sorted(x)
    return s[max(0, int(len(s) * q) - 1)]


def _dbeta(p, n, bench):
    """하방 베타 — 시장이 내린 날만으로 잰다."""
    r = rets(p["close"], n)
    if r is None or not bench or len(bench) != len(r):
        return None
    pair = [(a, b) for a, b in zip(bench, r) if a < 0]
    if len(pair) < 10:
        return None
    xs, ys = [a for a, _ in pair], [b for _, b in pair]
    vb = st.pvariance(xs)
    if vb == 0:
        return None
    mx, my = st.fmean(xs), st.fmean(ys)
    return sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / len(xs) / vb


def _coskew(p, n, bench):
    r = rets(p["close"], n)
    if r is None or not bench or len(bench) != len(r):
        return None
    mb, mr = st.fmean(bench), st.fmean(r)
    sb, sr = st.pstdev(bench), st.pstdev(r)
    if sb == 0 or sr == 0:
        return None
    return sum((y - mr) * (x - mb) ** 2 for x, y in zip(bench, r)) / (len(r) * sr * sb ** 2)


BENCH_SLUGS = {"beta_60", "idio_60", "dbeta_60", "coskew_60"}


def build2():
    """사냥에서 온 2 차 배치. **가격·거래량·펀딩만.**"""
    F = Factor
    return [
        F("gk_vol_30", "risk", -1, lambda p: _gk(p, 30), "Garman-Klass 변동성"),
        F("rsi_14", "momentum", -1, lambda p: _osc(p["close"], 14), "과매수 회피"),
        F("stoch_14", "momentum", -1, lambda p: _stoch(p, 14)),
        F("cci_20", "momentum", -1, lambda p: _cci(p, 20)),
        F("sma_dist_20", "momentum", +1, lambda p: _sma_dist(p["close"], 20)),
        F("ppo_12_26", "momentum", +1, lambda p: _ppo(p["close"])),
        F("ctrend", "momentum", +1, lambda p: _ctrend(p["close"]),
          "여러 창 SMA 거리 평균 — Han-Zhou-Zhu 추세팩터 단순화"),
        F("donchian_55", "momentum", +1, lambda p: _stoch(p, 55),
          "55일 고저 범위 내 위치"),
        F("mom_skip_180_30", "momentum", +1,
          lambda p: (None if len(p["close"]) < 211 or p["close"][-211] <= 0
                     else p["close"][-31] / p["close"][-211] - 1),
          "180일 모멘텀에서 최근 30일 건너뜀"),
        F("maxd_prc", "value", -1,
          lambda p: max(p["high"][-30:]) if len(p["high"]) >= 30 else None,
          "LTW 최대가격 — 비싼 쪽 회피"),
        F("std_prcvol", "liquidity", -1,
          lambda p: _sd(p["qvol"][-30:]) if len(p["qvol"]) >= 30 else None,
          "거래대금 변동성 — LTW stdprcvol"),
        F("vol_ratio_50_200", "flow", +1,
          lambda p: (None if len(p["qvol"]) < 200 or st.fmean(p["qvol"][-200:]) <= 0
                     else st.fmean(p["qvol"][-50:]) / st.fmean(p["qvol"][-200:]))),
        F("abnormal_vol_30", "flow", +1,
          lambda p: (None if len(p["qvol"]) < 90 or _sd(p["qvol"][-90:]) in (None, 0)
                     else (st.fmean(p["qvol"][-30:]) - st.fmean(p["qvol"][-90:]))
                     / _sd(p["qvol"][-90:])),
          "거래량 이상치 z 점수"),
        F("downside_var_30", "risk", -1, lambda p: _var(rets(p["close"], 30)),
          "5% VaR — 꼬리손실 큰 쪽 회피"),
        F("taker_imb_7", "flow", +1, lambda p: _taker(p, 7),
          "테이커 매수 비율 — 주문흐름"),
        F("taker_imb_30", "flow", +1, lambda p: _taker(p, 30)),
        F("taker_imb_chg", "flow", +1,
          lambda p: (None if _taker(p, 7) is None or _taker(p, 30) is None
                     else _taker(p, 7) - _taker(p, 30))),
        F("funding_adj_mom", "carry", +1,
          lambda p: (None if total(p["close"], 30) is None or _funding(p, 30) is None
                     else total(p["close"], 30) - _funding(p, 30) * 90),
          "30일 모멘텀에서 그 기간 펀딩 비용을 뺀다"),
        F("dbeta_60", "risk", -1, None, "하방베타 — 낮은 쪽 롱 (벤치 주입)"),
        F("coskew_60", "risk", -1, None, "공왜도 — 낮은 쪽 롱 (벤치 주입)"),
    ]
