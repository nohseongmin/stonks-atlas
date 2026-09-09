"""딥바잉 강건성 배터리 — PREREG_DIPBUY.md.

610 시행 중 유일하게 매수보유를 이긴 신호를 **처음으로 제대로 공격한다.**

    진입  close <= SMA(5) x 0.95
    청산  close >= SMA(5)

**노출조정 알파를 걷어내는 것**이 1 번 질문이다. 시장에 5% 만 있으면서
좋은 순간만 고르면 단위 노출당 알파는 좋아 보인다 — 실제 포트폴리오가
매수보유를 넘는지가 진짜 질문이다.

미보유 기간에는 **무위험수익 연 4%** 를 준다. 0 으로 치면 전략이 부당하게 불리하다.
"""
from __future__ import annotations

import math
import statistics as st
from pathlib import Path

TRADING_DAYS = 252
RF_ANNUAL = 0.04
COST_BPS = 10.0          # 왕복. 개인 미장 실비용 근사
CACHE = Path(__file__).resolve().parent.parent / "data" / "us"

#: PREREG_DIPBUY.md 에 고정. 결과를 보고 추가하거나 빼지 않는다.
ASSETS = ["SPY", "QQQ", "IWM", "DIA",
          "TQQQ", "SOXL", "TSLL",
          "XLK", "XLF", "XLE", "XLV",
          "EFA", "EEM"]
LEVERAGED = {"TQQQ", "SOXL", "TSLL"}
#: (창, 낙폭%) 격자. (5,5) 가 원 값이고 나머지는 이웃 확인용.
GRID = [(3, 3.0), (5, 3.0), (5, 5.0), (5, 7.0), (10, 3.0), (10, 5.0)]
BASE = (5, 5.0)


def fetch(sym: str) -> list[tuple[str, float]]:
    """일봉 종가. 디스크 캐시 — 같은 심볼을 두 번 받지 않는다."""
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{sym}.csv"
    if p.exists():
        return [(d, float(c)) for d, c in
                (l.split(",") for l in p.read_text().splitlines() if l)]
    import yfinance as yf
    df = yf.download(sym, period="max", interval="1d", auto_adjust=True,
                     progress=False)
    if df is None or df.empty:
        return []
    rows = [(str(i.date()), float(v)) for i, v in df["Close"].iloc[:, 0].items()
            if v == v and v > 0]
    p.write_text("\n".join(f"{d},{c}" for d, c in rows))
    return rows


def run(closes: list[float], window: int, dip: float, cost_bps: float = COST_BPS,
        rf: float = RF_ANNUAL) -> dict:
    """전략을 굴린다. **미보유 기간에 무위험수익을 준다.**

    체결은 신호 다음날 종가다 — 당일 종가로 판단하고 당일 종가에 사면 룩어헤드다.
    """
    daily_rf = (1 + rf) ** (1 / TRADING_DAYS) - 1
    half = cost_bps / 2e4
    eq, pos = 1.0, 0
    curve, days_in = [1.0], 0
    for i in range(window, len(closes) - 1):
        m = st.fmean(closes[i - window + 1:i + 1])
        px = closes[i]
        want = 1 if (pos == 0 and px <= m * (1 - dip / 100)) else \
               (0 if (pos > 0 and px >= m) else pos)
        if want != pos:
            eq *= 1 - half            # 편도 비용
            pos = want
        r = closes[i + 1] / closes[i] - 1 if closes[i] > 0 else 0.0
        eq *= (1 + r) if pos else (1 + daily_rf)
        days_in += pos
        curve.append(eq)
    n = len(curve) - 1
    return {"curve": curve, "n": n,
            "exposure": days_in / n if n else 0.0,
            "final": eq}


def hold(closes: list[float], window: int) -> dict:
    """같은 구간 매수보유. **전략과 같은 날짜에서 시작해야 공평하다.**"""
    eq, curve = 1.0, [1.0]
    for i in range(window, len(closes) - 1):
        eq *= closes[i + 1] / closes[i] if closes[i] > 0 else 1.0
        curve.append(eq)
    return {"curve": curve, "n": len(curve) - 1, "exposure": 1.0, "final": eq}


def stats(r: dict) -> dict:
    c = r["curve"]
    rets = [b / a - 1 for a, b in zip(c, c[1:]) if a > 0]
    sd = st.pstdev(rets) if len(rets) > 1 else 0.0
    sharpe = st.fmean(rets) / sd * math.sqrt(TRADING_DAYS) if sd else 0.0
    peak, mdd = c[0], 0.0
    for v in c:
        peak = max(peak, v)
        mdd = max(mdd, 1 - v / peak) if peak > 0 else mdd
    yrs = r["n"] / TRADING_DAYS
    cagr = (c[-1] ** (1 / yrs) - 1) if yrs > 0 and c[-1] > 0 else -1.0
    return {"sharpe": sharpe, "cagr": cagr, "mdd": mdd,
            "exposure": r["exposure"], "n": r["n"]}
