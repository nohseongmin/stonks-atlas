"""딥바잉 체결 시점 검정. 네트워크 없이 합성 종가만 쓴다."""
import unittest

from .dipbuy import TRADING_DAYS, run


class DipbuyExecutionTests(unittest.TestCase):
    def test_entry_does_not_earn_return_before_next_close(self):
        r = run([100.0, 100.0, 80.0, 120.0], 2, 5.0, cost_bps=0.0, rf=0.0)
        self.assertEqual(r["curve"], [1.0, 1.0])
        self.assertEqual(r["exposure"], 0.0)

    def test_exit_keeps_return_until_next_close(self):
        r = run([100.0, 100.0, 80.0, 120.0, 60.0], 2, 5.0,
                cost_bps=0.0, rf=0.0)
        self.assertEqual(r["curve"], [1.0, 1.0, 0.5])
        self.assertEqual(r["exposure"], 0.5)

    def test_cash_interest_and_costs_follow_execution(self):
        rf, cost_bps = 0.04, 10.0
        daily_rf = (1 + rf) ** (1 / TRADING_DAYS) - 1
        half = cost_bps / 2e4
        r = run([100.0, 100.0, 80.0, 120.0, 60.0, 90.0], 2, 5.0,
                cost_bps=cost_bps, rf=rf)
        entry = (1 + daily_rf) * (1 - half)
        exit = entry * 0.5 * (1 - half)
        final = exit * (1 + daily_rf) * (1 - half)
        for actual, expected in zip(r["curve"], [1.0, entry, exit, final]):
            self.assertAlmostEqual(actual, expected)
        self.assertAlmostEqual(r["final"], final)
        self.assertEqual(r["n"], 3)
        self.assertEqual(r["exposure"], 1 / 3)


if __name__ == "__main__":
    unittest.main()
