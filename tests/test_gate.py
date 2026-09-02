"""관문 검정. **기각만 잘하는 관문은 쓸모없다** — 진짜도 통과시켜야 한다."""
import math

import pytest

from dump.backtest import Result
from dump.gate import (GateConfig, cagr, evaluate, expected_max_sharpe,
                       fingerprint, max_drawdown, record, returns, sharpe,
                       trials)


def curve(mean: float, n: int, sd: float = 0.01, seed: int = 1,
          start: float = 100.0) -> list[float]:
    """평균 `mean`, 표준편차 `sd` 인 합성 자본곡선.

    **분산이 0 이면 Sharpe 도 0 이다** — 일정 수익률 곡선으로는 관문을 못 만든다.
    난수는 LCG 로 직접 만든다. `hash()` 는 프로세스마다 소금이 달라
    같은 씨앗으로도 결과가 바뀐다(앞 프로젝트에서 테스트가 실제로 흔들렸다).
    """
    eq, x = [start], seed
    for _ in range(n):
        x = (x * 1103515245 + 12345) % 2147483648
        eq.append(eq[-1] * (1 + mean + sd * (x / 2147483648 - 0.5) * 3.464))
    return eq


def res(equity: list[float], liq: int | None = None) -> Result:
    return Result(equity, [], 0.0, 0.0, 0, liq, len(equity))


# ---------------------------------------------------------------- 지표

def test_returns_stop_after_wipeout():
    """청산 후엔 수익이 정의되지 않는다. 0 으로 채우면 통계가 거짓말한다."""
    assert returns([100, 110, 0, 0]) == pytest.approx([0.1, -1.0])
    assert returns([100.0]) == []


def test_sharpe_zero_when_no_variance():
    assert sharpe([0.01] * 50) == 0.0
    assert sharpe([]) == 0.0


def test_sharpe_annualizes_with_365_not_252():
    """크립토는 휴장이 없다. 252 를 쓰면 20% 과소평가된다."""
    r = [0.01, -0.01] * 100
    assert sharpe(r, 365) == pytest.approx(sharpe(r, 252) * math.sqrt(365 / 252))


def test_max_drawdown_and_cagr():
    assert max_drawdown([100, 120, 60, 90]) == pytest.approx(0.5)
    assert max_drawdown([100, 101, 102]) == 0.0
    assert cagr([100.0] * 366, 365) == pytest.approx(0.0, abs=1e-9)
    assert cagr([100, 0], 365) == -1.0


# ---------------------------------------------------------------- 잡음바닥

def test_expected_max_includes_the_mean():
    """**평균을 빼먹으면 결론의 방향이 뒤집힌다.** 앞 프로젝트에서 실제로 그랬다."""
    with_mean = expected_max_sharpe(100, 0.5, 0.3)
    without = expected_max_sharpe(100, 0.0, 0.3)
    assert with_mean == pytest.approx(without + 0.5)


def test_expected_max_grows_with_trials():
    a = expected_max_sharpe(10, 0.0, 1.0)
    b = expected_max_sharpe(1000, 0.0, 1.0)
    assert b > a > 0


def test_expected_max_undefined_below_three():
    """sqrt(2*log(2/e)) 가 음수라 n<3 은 정의되지 않는다."""
    for n in (0, 1, 2):
        with pytest.raises(ValueError):
            expected_max_sharpe(n, 0.0, 1.0)


# ---------------------------------------------------------------- 관문

GOOD = curve(0.0020, 500, sd=0.010, seed=1)    # Sharpe ~3.5
BENCH = curve(0.0006, 500, sd=0.020, seed=7)   # Sharpe ~0.5
NOISE = [0.1] * 30                             # 과거 시행들의 Sharpe 분포


def verdict(equity=None, stressed=None, pit=True, n=50, liq=None):
    e = equity or GOOD
    return evaluate(res(e, liq), BENCH, res(stressed or e, liq), n, NOISE, pit)


def test_gate_passes_a_genuinely_good_strategy():
    """**관문에 검정력이 있는지.** 전부 기각하는 관문은 정보가 없다."""
    v = verdict()
    assert v.passed, v.failures


def test_gate_is_fail_closed_on_pit():
    v = verdict(pit=False)
    assert not v.passed
    assert v.failures == ["① 시점정합"]


def test_gate_rejects_liquidation():
    v = verdict(liq=42)
    assert "③ 청산" in v.failures


def test_gate_rejects_when_cost_stress_kills_it():
    """가정 비용에선 되고 3 배에서 무너지면 기각이다."""
    v = verdict(stressed=curve(0.0004, 500, sd=0.010, seed=1))
    assert v.failures == ["⑤ 비용스트레스"]


def test_gate_rejects_thin_margin_over_bench():
    thin = curve(0.0007, 500, sd=0.020, seed=7)
    v = verdict(equity=thin, stressed=thin)
    assert "④ 벤치대비" in v.failures


def test_gate_rejects_short_sample():
    short = curve(0.0020, 100, sd=0.010, seed=1)
    v = evaluate(res(short), BENCH, res(short), 50, NOISE, True)
    assert "② 표본길이" in v.failures


def test_gate_rejects_deep_drawdown():
    eq = curve(0.0020, 500, sd=0.010, seed=1)
    eq[250] = eq[249] * 0.4        # 순간 -60%
    v = evaluate(res(eq), BENCH, res(eq), 50, NOISE, True)
    assert "⑥ 낙폭" in v.failures


def test_gate_cannot_judge_noise_floor_with_too_few_trials():
    v = evaluate(res(GOOD), BENCH, res(GOOD), 2, NOISE, True)
    assert "⑦ 잡음바닥" in v.failures


def test_noise_floor_rejects_a_lucky_winner():
    """시행을 많이 하고 **시행 간 산포가 크면** 높은 Sharpe 도 운으로 설명된다.

    바닥은 `평균 + 표준편차 x a_n` 이고 `a_n` 은 log 로만 자라므로
    시행 수보다 **산포가 더 크게 민다.**
    """
    spread = [-1.0, 2.0] * 10          # 평균 0.5, 표준편차 1.5
    v = evaluate(res(GOOD), BENCH, res(GOOD), 5000, spread, True)
    assert "⑦ 잡음바닥" in v.failures


def test_empty_verdict_is_not_a_pass():
    from dump.gate import Verdict
    assert not Verdict().passed


# ---------------------------------------------------------------- 원장

def test_fingerprint_is_stable_and_specific():
    assert fingerprint("a", {"w": 1}) == fingerprint("a", {"w": 1})
    assert fingerprint("a", {"w": 1}) != fingerprint("a", {"w": 2})
    assert fingerprint("a", {"w": 1}) != fingerprint("b", {"w": 1})


def test_ledger_dedupes_reruns(tmp_path):
    """같은 규칙을 다시 돌린 건 **새 시행이 아니다.** 세면 벌점이 부풀려진다."""
    p = tmp_path / "t.jsonl"
    record("m", {"w": 1}, 0.5, p)
    record("m", {"w": 1}, 0.5, p)
    record("m", {"w": 2}, 0.7, p)
    assert len(trials(p)) == 2


def test_ledger_empty_when_missing(tmp_path):
    assert trials(tmp_path / "none.jsonl") == []
