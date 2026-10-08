# STONKS Atlas: detailed results

Research records for Korean equities, US equities, and cryptocurrency. The consolidated project reports 620 trials, no accepted deployment candidate, and no completed robustness battery.

The crypto harness was imported into `crypto/` with its Git history so preregistration timestamps remain available. Earlier projects are retained in the linked legacy repositories.

## Market summary

| Market | Recorded access | Trials | Accepted | Main candidate | Outcome |
|---|---|---:|---:|---|---|
| Korean equities | Korean retail accounts, without leverage | 14 | 0 | Downside-deviation screen, SR 0.78 | Failed recent subsamples |
| US equities | Toss and Kiwoom | 467 | 0 | Mean-reversion dip buying | Failed the battery; 99% cash |
| Crypto | Binance perpetuals | 130 | 0 | taker_imb_30, SR 1.55 | Failed asset ablation |
| Live operation | Toss API | — | — | Eight-week paper trial | Stopped after day one |

Trial counts are the figures recorded in the source summaries; the ledger is the primary record for deduplicated trials.

## Live operation

See [markets/live.md](markets/live.md).

| Item | Recorded result |
|---|---|
| Toss token, quotes, account, and order API | Connection confirmed |
| Toss simulated environment | Unavailable in the original setup; local paper trading used |
| Real-order gates | Both --mode live and --i-understand-real-money required |
| Preregistered trial, July 2–August 27, 2026 | One journal day out of about forty trading days |
| Uptime target of at least 95% | Failed; observed uptime was 2.5% |
| Return deviation target of ±30% from backtest | Not reached |

The original paid advisory-channel proposal was rejected in the project's legal review. The self-trading track is separate. This record shows an operational failure regardless of whether a signal had passed research validation.

## Korean equities

See [markets/kr.md](markets/kr.md).

| Item | Recorded result |
|---|---|
| Twenty-five cross-sectional models | Best SR +0.798 versus chance expectation +0.826 |
| Large-cap downside-deviation screen | SR +0.78 versus 069500 +0.61; failed subsamples after the edge disappeared in 2015 |
| Effective dimension | 1.4 of 25; mean pair correlation +0.832 |
| Point-in-time universe | Unavailable; delisted candles failed in six of six Toss requests |
| Survivorship-bias proxy in crypto | Mean inflation of +0.102 Sharpe and +5.97 percentage points CAGR |
| Domestic crypto derivatives in the reviewed venues | None in the recorded review |
| Korean PEAD | Rejected: SR +0.525 versus 069500 +0.728; CAGR 7.95% versus 15.98%, with worse drawdown |
| PEAD sample | 183,107 filings; 9,717 net-income records; 238 stocks and 9,670 announcements, 2015–2026 |
| Preregistration deviation | Preliminary earnings averaged 1.2 per stock per year versus 48 required; regular filing receipt dates used instead |
| Revised financial data | fnlttMultiAcnt returns revised values; 14.3% had corrections; no free original-value route was available |

The data limitations favored the PEAD strategy in the recorded comparison, yet it still underperformed.

## US equities

See [markets/us.md](markets/us.md).

| Item | Recorded result |
|---|---|
| Tick scalping at 0.1–0.2% targets | Rejected by cost arithmetic; required win rate exceeded 100% |
| Stocks-in-play ORB | -22.2 bp per trade, t=-15.96, 15,217 trades after removing lookahead |
| Bias-removal sequence | +62.6 bp with a hand-selected universe; +14.0 bp with full-day volume; -22.2 bp with causal opening volume |
| S&P600 ORB | -47.6 / -77.6 / -117.6 bp under the tested costs |
| Seven intraday strategies | 79 stocks over two years; t statistics from -2 to -63; all rejected |
| Alpha101: 34 factors, 150 stocks, twenty years | Best net SR +0.48 at 21-day holding; maximum DSR 0.647 below 0.95; all 136 configurations rejected |
| Gross factor signals | IC +0.0162 and pre-cost SR +0.6–1.4; turnover consumed the advantage |
| Daily swing strategies | Apparent acceptance was explained by beta; index holding returned +49% and beat all tested strategies |
| Five-day, -5% dip buying | Reported exposure-adjusted alpha +3.5%; rejected in [RESULTS_DIPBUY.md](RESULTS_DIPBUY.md) |
| Actual dip-buying exposure | 1.0%; CAGR below buy-and-hold in twelve of thirteen assets |
| Source of Sharpe advantage | Cash interest; changing rf from 4% to 0% reduced SR from +0.74 to +0.19 |
| TQQQ, SOXL, TSLL dip buying | All lost; reported differences -0.14 / -0.23 / -0.25 |
| US catalog, 203 trials | Best +0.979 versus expected chance best +1.386; difference -0.406 |
| Effective dimension | 3.2 of 25; mean pair correlation +0.427 |

Dip buying produced CAGR +5.2% at rf=4% and +1.1% at rf=0%, compared with buy-and-hold +10.8% and SR +0.65. Exposure-adjusted alpha is not the return of the deployable portfolio.

## Cryptocurrency

See [markets/crypto.md](markets/crypto.md).

| Item | Recorded result |
|---|---|
| Point-in-time universe | Candles for 266 delisted symbols; 42.9% of the June 2023 universe had later delisted |
| BTC spread | 0.0129 bp, one tick; fees accounted for 99.9% of modeled cost |
| Maker round trip | 4 bp fees against 0.0129 bp spread, about -3.99 bp |
| Scalping at a 0.1% target | Required win rate 100.07% |
| Liquidation fee | 1.25% of notional, equivalent to twenty-five taker fills; full loss in the model |
| Funding carry | Annualized 30.69% in 2021 to 2.65% at the 2026 measurement; $0.06–0.16 monthly net on $100 |
| LTW weekly momentum, L=14 | SR +0.82 versus BTC buy-and-hold +0.90 |
| Neutral strategy plus beta | SR +1.06, correlation -0.065; theoretical optimized 1.26 not used |
| Forty-four price/volume factors | Effective dimension 6.2; best donchian_55 at 1.21 |
| Order flow, taker_buy/quote | Combined SR +1.35 |
| taker_imb_30 | SR 1.55; six of seven gates passed, but removing ten of 753 symbols reduced SR to 0.95, including LUNA |
| OI and long/short positions | lsr_chg +1.14; lsr_retail +0.96; top-trader following -1.27 |
| Spot basis | Best basis_resid 0.56; funding correlation -0.027 |
| Seven BTC timing rules | All rejected; best ema_cta 0.83 versus buy-and-hold 0.71 |
| Liquidation data | Historical prefix removed; forceOrder sends at most one record per second |
| Deribit options | BTC and ETH only, N=2; no usable cross section for this design |
| Korean transfer review | Supported routes were recorded, with 1.77% round-trip friction |

Exchange costs and access are historical measurements, not current availability guarantees.

## Findings across the experiments

High turnover consistently reduced net returns. Alpha101's best net SR changed from -0.37 at one-day holding to +0.48 at twenty-one days, but the longer holding period still did not pass multiple-testing correction.

The modeled growth ceiling is:

```text
CAGR - rf = S*sigma - sigma²/2
Maximum at sigma=S: rf + S²/2
```

| Observed Sharpe | Modeled monthly half-Kelly return | On KRW 30 million |
|---:|---:|---:|
| 1.06, crypto combination | 3.21% | KRW 960,000 |
| 0.90, BTC buy-and-hold | 2.49% | KRW 750,000 |
| 0.50, conservative case | 1.05% | KRW 320,000 |

The original 5% monthly target required Sharpe 1.42 under the half-Kelly model. The observed 1.55 candidate failed robustness testing.

### Multiple testing

| Crypto trials | 5 | 34 | 54 | 109 | 119 | 130 |
|---|---:|---:|---:|---:|---:|---:|
| Noise floor | 1.15 | 1.55 | 1.80 | 1.91 | 1.94 | 1.98 |
| Best observed SR | 1.06 | 1.06 | 1.55 | 1.55 | 1.55 | 1.55 |

### Effective dimensions

| Measurement | Dimension |
|---|---:|
| Korean catalog, 25 models | 1.4 |
| US catalog, 25 models | 3.2 |
| Crypto, 62 strategies | 8.2 |
| Crypto, five information sources | 2.81 |
| External: Correlation Without Factors | 1.85 |
| External: OctopusTakopi, 268-market CTA | 3.81 |

The measured strategies were highly correlated. Adding catalog entries did not add the same number of independent hypotheses.

### Direction differences in crypto

In the tested crypto samples, high volatility beat low volatility, lottery-like assets beat avoidance, persistence beat short-term reversal, following top traders returned negatively, basis momentum reversed, and volatility management reduced returns along with risk.

Signs were recorded as preregistered rather than flipped after seeing results. The best sign-flipped result, +1.27, also remained below the noise floor.

### External comparisons recorded by the project

| Source | Reported SR after the project's adjustments |
|---|---:|
| bryanvine/alpha-research | 0.39 |
| OctopusTakopi/funding-rate-alpha, excluding 2020–21 | 0.77 |
| OctopusTakopi/crypto-trend-following | 0.68–1.04 |

The project's review did not find independent validation of a publicly specified crypto strategy operating for more than three years after publication.

## Method

Rules, predictions, and rejection conditions were committed before results. The main overview records nine preregistrations; the earlier detailed summary recorded eight.

Seven gates check point-in-time data, sample length, liquidation, benchmark performance, tripled costs, drawdown, and the noise floor. Failed or unverified conditions reject a candidate. A fingerprinted ledger retains rejected trials without counting identical reruns twice.

The six-part robustness battery checks parameter plateaus, subsamples, cost, quantiles, asset ablation, and orthogonality. It may reject a candidate but cannot promote one by selecting a favorable variation. Power tests check the gates, and PastView blocks future indices.

## Implementation errors found

These were found through tests and runtime checks rather than strategy gates.

| Error | Evidence |
|---|---|
| ctx exposed complete future arrays | Suspicious SPY correlation of 1.0000 |
| US cross-section active only 54% of the time | An impossible 2,358-day sign run |
| Missing close-to-next-open gaps | Failed recovery of an injected signal |
| PastView reported length 60 for an empty array | Liquidity checks could accept zero-volume symbols |
| OI parser misaligned arrays after exceptions | 354 failed symbols |
| Unencoded Chinese-character symbols in URLs | Universe scan failure |

## Files and commands

```text
README.md       Overview
README.full.md  Detailed results
markets/        Market-specific accounts
evidence/       Preregistrations, results, and ledgers
crypto/         Imported crypto harness with history
verify/         US dip-buying verification
PREREG_*.md     Atlas preregistrations
RESULTS_*.md    Atlas results
```

```bash
python -m crypto.dump.costs
python -m crypto.dump.feed
python -m crypto.dump.runzoo
python -m crypto.dump.battery
cd crypto
python -m pytest -q
```

## Original repositories

| Repository | Scope |
|---|---|
| [legacy-dumpItAll](https://github.com/nohseongmin/legacy-dumpItAll) | Crypto harness, imported into crypto/ |
| [legacy-STONKS-03](https://github.com/nohseongmin/legacy-STONKS-03) | Three-market catalog, noise-floor tools, dimensions, DART collector |
| [legacy-ai-stonks-v2](https://github.com/nohseongmin/legacy-ai-stonks-v2) | ORB, Alpha101, daily swing, RiskGovernor |
| [legacy-AI-STONKS](https://github.com/nohseongmin/legacy-AI-STONKS) | Toss live-trading implementation and interrupted paper trial |
| [legacy-STONKS](https://github.com/nohseongmin/legacy-STONKS) | Initial forecasting notebooks |

The retrospective search is closed in this project. Restoring scheduled paper operation and establishing sustained uptime is the next unresolved step.
