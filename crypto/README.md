# dumpItAll

A research harness for testing whether leveraged cryptocurrency perpetual trading is viable with $100. It checks trading costs before evaluating strategies.

This work followed STONKS-03, which recorded 480 trials with no accepted strategy, and AI-STONKS v2, whose opening-range strategy returned -22.2 bp per trade after removing bias.

## Running

From this directory:

```bash
python -m dump.costs
pytest -q
```

## Cost model

With one-way fee `f`, spread `s`, leverage `L`, and equal profit or loss target `m`:

```text
Break-even price move = 2f + s
Round-trip cost / equity = L * (2f + s)
Required win rate = 0.5 + (2f + s) / (2m)
```

Leverage scales both gains and fees. It does not reduce the price move needed to cover a round trip.

The recorded model assumed an 11 bp round trip, ten round trips per day, and annual BTC long funding of 2.75% measured over 180 days.

| Leverage | Notional on $100 | Round-trip equity cost | Liquidation move | Annual funding cost | Time to lose 99% with zero edge |
|---:|---:|---:|---:|---:|---:|
| 1 | $100 | 0.11% | -99.5% | 2.7% | 418 days |
| 5 | $500 | 0.55% | -19.5% | 13.7% | 84 days |
| 10 | $1,000 | 1.10% | -9.5% | 27.5% | 42 days |
| 20 | $2,000 | 2.20% | -4.5% | 55.0% | 21 days |
| 50 | $5,000 | 5.50% | -1.5% | 137% | 8 days |

The model treats liquidation as a full loss. Its 1.25% notional liquidation fee exceeds the remaining margin under the modeled 0.40% maintenance requirement.

| Target move | Required win rate |
|---:|---:|
| 10 bp | 105%, infeasible |
| 20 bp | 77.5% |
| 50 bp | 61.0% |
| 100 bp | 55.5% |
| 500 bp | 51.1% |

The growth approximation carried over from STONKS-03 is `CAGR - rf = S*sigma - sigma²/2`. It peaks at `sigma = S`, giving `rf + S²/2`. The recorded example with Sharpe 1.0 gives a roughly 54% annual ceiling under its assumptions.

## Recorded reconnaissance

[RECON.md](RECON.md) contains the original measurements and sources. These are historical observations, not current exchange quotes or access guarantees.

### Funding carry

| Year | Annualized BTC funding |
|---|---:|
| 2021 | 30.69% |
| 2024 | 11.96% |
| 2025 | 5.14% |
| 2026 YTD at measurement | 2.65% |

The sample contained 7,646 observations. A spot/futures round trip cost 0.30%, and the recorded minimum BTC order was $77.58 because LOT_SIZE exceeded MIN_NOTIONAL.

Estimated net carry on a $100 neutral position was $0.06–0.16 per month. The calculation required $6,000–10,000 to target $10 monthly. Funding-sign prediction reached 87.6% with AR1 0.80, but timing returned -5.90% annually: collecting an extra 0.45% incurred 18% in fees.

### Historical universe

The dump scan recorded 1,018 symbols, 760 trading symbols, and accessible candles for 266 delisted symbols.

| Date | Universe | Subsequently delisted | Share |
|---|---:|---:|---:|
| 2021-06 | 123 | 45 | 36.6% |
| 2022-06 | 175 | 73 | 41.7% |
| 2023-06 | 240 | 103 | 42.9% |
| 2024-06 | 316 | 79 | 25.0% |
| 2025-06 | 525 | 127 | 24.2% |

Using only present-day exchangeInfo would omit 103 of the 240 symbols in the June 2023 universe. The harness instead builds a point-in-time universe.

The bookTicker dump ended on March 30, 2024. Spread reconstruction therefore uses aggTrades and bookDepth.

### Korean access and transfer research

The original research examined Korean-resident access, exchange registration, account-name checks, and transfer routes. Its observations and legal-source discussion are retained in [RECON.md](RECON.md).

The August 27, 2026 transfer review recorded support through Upbit, Bithumb, and Coinone under same-owner verification. It estimated 1.77% round-trip friction on KRW 150,000 for the lower-cost route and 3.12% for the TRON route, with initial 72-hour and subsequent 24-hour withdrawal delays. The then-planned risk-rating regime was expected around February 2027.

These findings remain provisional where `Venue.verified` is false. The README does not establish present legal status or availability.

| Venue | Recorded round-trip fee | Measurement note |
|---|---:|---|
| Hyperliquid | 9.0 bp | Spread unmeasured |
| Binance | 10.0 bp | Recorded BNB discount of 10% |
| Bybit | 11.0 bp | Spread unmeasured |

## Acceptance gates

All seven gates must pass:

| Gate | Requirement |
|---|---|
| Point-in-time data | Include delisted instruments. |
| Sample length | At least 365 periods. |
| Liquidation | Zero events. |
| Benchmark | Sharpe margin of at least +0.20 over BTC buy-and-hold. |
| Cost stress | Beat the benchmark at three times assumed costs. |
| Drawdown | At most 50%. |
| Noise floor | Exceed the expected best chance result for the recorded trial count. |

Power tests check that genuinely strong synthetic strategies can pass.

## Backtester safeguards

`PastView` raises IndexError for future indices. Liquidation uses intrabar highs and lows. `None` means keep a position, while zero means close it. The close-to-next-open gap is settled before execution. Decisions use the current close and execute at the following open.

## Files

```text
dump/costs.py     Cost arithmetic
dump/feed.py      Public dumps and historical universe
dump/backtest.py  Fees, spread, funding, and liquidation
dump/gate.py      Acceptance gates and trial ledger
tests/           Model and implementation checks
RECON.md         Measurements and sources
```

The original foundation checklist left spreads, fee tiers, Korean futures access, and public edge claims pending. Later experiments are recorded in the atlas rather than changing that historical checklist.

Secrets belong in ignored `.env` files. Live-trading keys are deferred until validation is complete. Public price, funding, and metrics data does not require a key in the recorded tests.
