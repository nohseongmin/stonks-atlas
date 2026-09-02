"""관문 — **이 파일이 헌법이다. 결과를 보고 문턱을 고치지 않는다.**

앞선 프로젝트에서 480 시행을 태워 통과 0 건이었다. 그게 실패가 아니라
관문이 일한 증거다. 문턱을 목표에 맞춰 낮췄으면 가짜 엣지 다섯 겹이
그대로 배포됐을 것이다.

기준을 바꿔야 하면 **결과를 보기 전에** 바꾸고 커밋에 남긴다.

## 크립토라서 다른 것

| | 주식 | 크립토 |
|---|---|---|
| 연간 기간 수 | 252 | **365** (휴장 없음) |
| 시점정합 유니버스 | 불가능했다 | **가능하다** — 그래서 선택이 아니라 필수 |
| 청산 | 없음 | **한 번이면 끝**. 낙폭과 다른 종류의 사건이다 |
| 벤치마크 | SPY | **BTC 매수보유** |

시점정합을 강제하는 이유: 2023-06 무기한 유니버스 240 개 중 **103 개(42.9%)가
오늘 죽어 있다.** 오늘 목록으로 그때 횡단면을 만들면 그 103 개가 조용히 빠지고,
빠진 건 전부 망한 쪽이다.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics as st
from dataclasses import dataclass, field
from pathlib import Path

from .backtest import Result

PERIODS_PER_YEAR = 365
LEDGER = Path(__file__).resolve().parent.parent / "data" / "trials.jsonl"


def returns(equity: list[float]) -> list[float]:
    """자본곡선 -> 기간수익. 0 이 된 뒤는 버린다(청산 후엔 수익이 정의 안 된다)."""
    out = []
    for a, b in zip(equity, equity[1:]):
        if a <= 0:
            break
        out.append(b / a - 1)
    return out


def sharpe(rets: list[float], periods: int = PERIODS_PER_YEAR) -> float:
    if len(rets) < 2:
        return 0.0
    sd = st.pstdev(rets)
    return 0.0 if sd == 0 else st.fmean(rets) / sd * math.sqrt(periods)


def max_drawdown(equity: list[float]) -> float:
    peak, worst = equity[0], 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            worst = max(worst, 1 - v / peak)
    return worst


def cagr(equity: list[float], periods: int = PERIODS_PER_YEAR) -> float:
    n = len(equity) - 1
    if n <= 0 or equity[0] <= 0:
        return 0.0
    if equity[-1] <= 0:
        return -1.0
    return (equity[-1] / equity[0]) ** (periods / n) - 1


def expected_max_sharpe(n_trials: int, mean: float, sd: float) -> float:
    """**시행 `n` 번이면 순전히 운으로 이만큼 나온다.** Bailey-Lopez de Prado.

    평균을 빼먹으면 결론의 방향이 뒤집힌다 — 앞 프로젝트에서 실제로 그랬다.
    """
    if n_trials < 3:
        raise ValueError(f"기대 최댓값은 n>=3 에서만 정의된다: {n_trials}")
    e = 0.5772156649015329          # 오일러-마스케로니
    a = ((1 - e) * math.sqrt(2 * math.log(n_trials))
         + e * math.sqrt(2 * math.log(n_trials / math.e)))
    return mean + sd * a


@dataclass(frozen=True)
class GateConfig:
    """통과 문턱. 숫자마다 근거를 남긴다 — 임의로 정한 값을 배제하려고."""

    #: 크립토는 휴장이 없다. 252 를 쓰면 Sharpe 가 20% 과소평가된다.
    periods_per_year: int = PERIODS_PER_YEAR
    #: 1 년 미만 표본으로는 어떤 통계도 의미가 없다.
    min_observations: int = 365
    #: **가정 비용의 3 배에서도 벤치를 넘어야 한다.** 스트레스 때 스프레드가
    #: 1,321 배로 벌어진 실측이 있다(2025-10-10). 3 배는 관대한 쪽이다.
    cost_stress_mult: float = 3.0
    #: 벤치(BTC 매수보유) 대비 Sharpe 여유. 0 이면 '겨우 같음'이라 통과가 아니다.
    min_margin_vs_bench: float = 0.20
    #: 청산은 낙폭과 다르다. 자본이 0 이 되면 복구가 없다.
    max_liquidations: int = 0
    #: 반토막까지는 감내한다. 그 아래는 '고위험'이 아니라 재기 불가.
    max_drawdown_allowed: float = 0.50
    #: 시점정합 유니버스를 **쓸 수 있으므로 쓴다.** 안 쓸 이유가 없다.
    require_pit: bool = True


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class Verdict:
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)

    @property
    def failures(self) -> list[str]:
        return [c.name for c in self.checks if not c.ok]


def evaluate(result: Result, bench_equity: list[float], stressed: Result,
             n_trials: int, trial_sharpes: list[float],
             pit: bool, cfg: GateConfig = GateConfig()) -> Verdict:
    """**전부 통과해야 통과.** 하나라도 실패하면 기각(fail-closed)."""
    v = Verdict()
    rets = returns(result.equity)
    sr = sharpe(rets, cfg.periods_per_year)
    bench_sr = sharpe(returns(bench_equity), cfg.periods_per_year)
    mdd = max_drawdown(result.equity)

    v.checks.append(Check(
        "① 시점정합", pit or not cfg.require_pit,
        "상폐 종목 포함 유니버스" if pit else
        "**오늘 살아있는 종목으로 과거를 만들었다.** 2023-06 기준 42.9% 가 빠진다"))

    v.checks.append(Check(
        "② 표본길이", len(rets) >= cfg.min_observations,
        f"{len(rets)} 기간 (최소 {cfg.min_observations})"))

    v.checks.append(Check(
        "③ 청산", (result.liquidated_at is None) and
        (stressed.liquidated_at is None),
        "없음" if result.liquidated_at is None
        else f"**{result.liquidated_at} 번째 봉에서 청산.** 자본 0"))

    margin = sr - bench_sr
    v.checks.append(Check(
        "④ 벤치대비", margin >= cfg.min_margin_vs_bench,
        f"Sharpe {sr:+.2f} vs 벤치 {bench_sr:+.2f} · 여유 {margin:+.2f} "
        f"(필요 {cfg.min_margin_vs_bench:+.2f})"))

    stress_sr = sharpe(returns(stressed.equity), cfg.periods_per_year)
    v.checks.append(Check(
        "⑤ 비용스트레스", stress_sr - bench_sr >= cfg.min_margin_vs_bench,
        f"비용 {cfg.cost_stress_mult:.0f}배에서 Sharpe {stress_sr:+.2f} "
        f"· 여유 {stress_sr - bench_sr:+.2f}"))

    v.checks.append(Check(
        "⑥ 낙폭", mdd <= cfg.max_drawdown_allowed,
        f"{mdd*100:.1f}% (허용 {cfg.max_drawdown_allowed*100:.0f}%)"))

    if n_trials >= 3 and len(trial_sharpes) >= 2:
        floor = expected_max_sharpe(n_trials, st.fmean(trial_sharpes),
                                    st.pstdev(trial_sharpes))
        v.checks.append(Check(
            "⑦ 잡음바닥", sr > floor,
            f"시행 {n_trials} 건이면 운으로 {floor:+.2f} 까지 나온다 "
            f"· 관측 {sr:+.2f}"))
    else:
        v.checks.append(Check("⑦ 잡음바닥", False,
                              f"시행이 {n_trials} 건이라 판정 불가 (최소 3)"))
    return v


def fingerprint(name: str, spec: dict) -> str:
    """같은 규칙을 두 번 세지 않기 위한 지문."""
    blob = json.dumps({"name": name, **spec}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def record(name: str, spec: dict, sharpe_value: float,
           path: Path = LEDGER) -> None:
    """원장에 시행을 남긴다. **기각도 남긴다** — 안 남기면 다중검정 벌점이 거짓말이 된다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"fp": fingerprint(name, spec), "name": name,
           "spec": spec, "sharpe": sharpe_value}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def trials(path: Path = LEDGER) -> list[dict]:
    """지문으로 중복을 제거해 읽는다. 같은 규칙 재실행은 새 시행이 아니다."""
    if not path.exists():
        return []
    seen = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            seen[r["fp"]] = r
    return list(seen.values())
