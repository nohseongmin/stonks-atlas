# STONKS-03

An archived research harness for Korean equities, US equities, and cryptocurrency. The final overview records 43 investigations, 224 catalog configurations, and 480 unique attempts, with no deployable edge.

Earlier tables below retain the counts from their respective stages. Fourteen implementation defects were found through harness checks and code review, fixed, and followed by reruns. The deployment account under consideration was Toss in Korea.

## Noise-floor comparison

The search used OHLCV, SEC financial statements, FRED rates, and Form 4 insider data. An early phase contained 27 detailed investigations, followed by 114 catalog tests.

At the 429-attempt comparison stage:

| Market | Attempts | Best observed SR | Expected best under chance | Difference |
|---|---:|---:|---:|---:|
| US equities | 203 | +0.979 | +1.386 | -0.406 |
| Korean equities | 13 | +0.798 | +0.826 | -0.029 |
| Crypto | 213 | +0.817 | +1.009 | -0.192 |

Reproduce this with `python -m stonks.noisefloor`.

The expected maximum uses the mean and standard deviation of trial results, multiplied by the trial-count factor. Correlated trials reduce the effective independent count:

| Market | Mean pair correlation | Effective dimension | Compression | Compression needed to change conclusion |
|---|---:|---:|---:|---:|
| US | +0.427 | 3.2 / 25 | 7.8x | 28x |
| Korea | +0.832 | 1.4 / 25 | 17.7x | 8x |

The Korean result was therefore less decisive under correlation adjustment.

## Last candidate: downside deviation

The Korean large-cap screen selected the lowest-downside-deviation 20%. It recorded SR +0.78 versus 069500 +0.61, a Sharpe margin of +0.173, CAGR margin of +2.00 percentage points, and drawdown of 40% versus 41%.

The catalog's effective dimension of 1.4 means its downside-deviation and maximum-drawdown results are closely related tests. The effective Korean trial count was estimated at five-to-six, close to the decision boundary of five.

Korean data contained only survivors. Six delisted-stock candle requests failed even though metadata was available. To estimate the bias, the same twenty-five crypto models were run on 400 symbols including delistings and 270 survivors. Survivorship raised mean Sharpe by +0.102 and CAGR by +5.97 percentage points. The effect varied: five-year reversal gained +0.48 Sharpe, while downside deviation changed by approximately zero.

After code-review fixes:

| Market | Downside-deviation SR | Benchmark SR | Result |
|---|---:|---:|---|
| US | +0.38 | +0.74 | Below |
| Korea | +0.79 | +0.61 | Above |
| Crypto | +0.65 | +0.64 | Above |

The Korean result still faced incomplete historical data and uncertain multiple-testing correction. The crypto result depended on the assumed delisting loss:

| Delisting loss | Benchmark margin |
|---:|---:|
| 0% | +0.057 |
| 50%, preregistered default | +0.013 |
| 75% | -0.009 |
| 100% | -0.032 |

For 130 delisted coins, median returns before the last candle were -61.2% over ninety days and -76.9% over 252 days; the lower quartile was -89.8%. Post-delisting prices were unavailable, so the 50% loss assumption could not be validated. The crypto candidate was rejected on sensitivity.

### Korean robustness battery, investigation 42

The battery was preregistered to reject candidates, without promoting them by choosing a favorable variation.

| Check | Recorded result | Outcome |
|---|---|---|
| Parameter plateau, 63/126/252/504 | SR 0.69 / 0.79 / 0.78 / 0.81 | Passed |
| Quantiles, 10/20/30% | SR 0.86 / 0.78 / 0.71 | Passed |
| Costs, 35/50/80/120 bp | SR 0.78 / 0.77 / 0.74 / 0.70 | Passed |
| Twelve random 20% controls | SR 0.473 ± 0.013; candidate 23.8 standard deviations higher | Passed |
| Subsamples | First half 1.03; second half 0.62 versus benchmark 0.72 | Failed |

The six-part battery recorded four passes. The advantage was concentrated in the earliest period:

| Period | Strategy SR | Benchmark SR | Difference |
|---|---:|---:|---:|
| 2010-01 to 2015-07 | +1.45 | +0.35 | +1.10 |
| 2015-07 to 2021-01 | +0.34 | +0.76 | -0.42 |
| 2021-01 to 2026-08 | +0.51 | +0.74 | -0.23 |

The preregistered concern that random equal-weight portfolios would explain the result was not supported. The signal appeared in the early sample, but did not persist after 2015.

## Cross-market styles

After fixes, rank correlations were US–Korea -0.530, t=-2.93; US–crypto -0.507, t=-2.76; and Korea–crypto +0.643, t=+3.93.

| Market | Top-five model types |
|---|---|
| US | Three-year reversal, 12–1 momentum, trend quality, five-year reversal, six-month relative strength |
| Korea | Downside deviation, maximum drawdown, skewness, maximum daily return, low volatility |
| Crypto | Downside deviation, skewness, low volatility, maximum drawdown, idiosyncratic volatility |

Four of Korea's and crypto's top five overlapped. The US sample favored return-based styles; Korea and crypto favored risk-based styles.

The top eight US allocation results shared gold exposure. Removing gold eliminated the excess performance. Gate power tests accepted injected true Sharpe 3.0 signals 100% of the time; the measured detection floor was about 1.5.

## Failure modes observed

The numbers here identify failure types, not the gate execution order.

| Type | Recorded evidence |
|---|---|
| Survivorship bias | Excluding delistings removed 50.6% of the 2010 universe. |
| Lookahead | Removing unavailable entry-time information changed +14 bp to -22 bp. |
| Costs | Turnover of 50–80% consumed factor returns; tested intraday approaches failed. |
| Beta mistaken for alpha | A pure-beta strategy passed with t=+76.98 and annual alpha +0.00%. |
| Multiple testing | 619 independent tests at p<0.05 would produce roughly 31 chance passes. |
| Weak benchmark | Apparent alpha +33.7% annually used a benchmark returning -38% annually. |
| Optimization beyond parameters | Nine of nine parameter plateaus passed, but only three of twelve cross-asset replications did. |
| Replication pool bias | Ten of fifteen subsets included the return-driving gold asset. |
| Rebalancing phase | Changing the weekday moved crisis performance by 33.5 percentage points. |
| Data availability bias | Gold was the only uncorrelated asset with measurable total returns in the setup. |
| Asset selection | Permanent-portfolio SR 0.73 fell to 0.47–0.59 without gold. |
| Cross-market style reversal | Earlier rank comparisons showed US–Korea -0.67 and Korea–crypto +0.52. |
| Revised data | NFCI revises its full history, so present values are not necessarily those available at the time. |
| Inactive universe | US individual-stock data began in June 2015 but used a 1993-onward SPY date axis; 54% coverage shrank SR by about 27%. |
| Zero-filled persistence | Inactive periods produced sign-persistence z=+3.18; after fixing coverage, z=-0.06. |

The last two were implementation defects. A 2,358-day sign run exposed the problem.

## Checking the harness

Strategy gates do not test the harness itself. Investigation 40 added `stonks/canary.py` for future-data blocking, false positives on noise, and recovery of injected signals. Investigation 41 found nine factor or data-contract defects, four affecting results.

Runtime checks caught coverage failures that source review missed; code review found factor defects outside the canary's scope. The signal-recovery check is needed because an implementation can destroy a real signal while every strategy gate simply rejects it.

## GateConfig

The numbered gate checks use a different sequence from the failure types above.

| Check | Requirement |
|---|---|
| 1: survivorship | Point-in-time universe including delistings |
| 2: lookahead | Machine check passed; required positional argument to evaluate() |
| 3: costs | Net Sharpe above zero |
| 4: absolute return | CAGR at least min_cagr |
| 4b: drawdown | At most max_drawdown_allowed |
| 5: multiple testing | DSR at least 0.95 and sample length at least MinBTL; trials read from the ledger |
| 7: replication | More than 50% across other assets or subsets; unverified means rejected |

Historical deployment goals were CAGR at least 25%, drawdown at most 80%, and outperformance of leveraged passive exposure. Changing a target requires changing and recording criteria before viewing results; it does not justify weakening data-integrity checks.

## Trial ledger

Every evaluation records acceptance or rejection. A SHA256 fingerprint of name and parameters prevents identical reruns from inflating counts while retaining parameter searches.

Three ledger issues were found:

1. Modules bypassed evaluate(), leaving one trial instead of fifteen. Backfilling changed DSR from 1.000 to 0.000.
2. Reruns after a window-alignment fix kept the same fingerprints and did not increase trial counts.
3. evaluate(ledger=None) selected the default ledger and inserted 200 synthetic power-test runs, changing 117 entries to 317. It now raises for None instead.

A recorded US ledger snapshot had 138 lines across nineteen families, median Sharpe +0.49, and maximum +0.98.

## Investigation record

See [EXTERNAL_MODELS.md](EXTERNAL_MODELS.md) for details.

| No. | Subject | Outcome |
|---:|---|---|
| 1 | NostalgiaForInfinity | No testable claim; 12,193 degrees of freedom implied SR noise floor 1.40. |
| 2 | RSRS timing | Rejected 2/5; signal present, parameter plateau 0/9. |
| 3 | Forty-seven fundamental factor families | Rejected 2/5; six controls failed, but SPY was not exceeded. |
| 4 | Multiasset allocation | Rejected 4/5. |
| 5 | Faber TAA | Initial 6/8 withdrawn after failed replication traced to gold. |
| 6 | Gold independence | Tail correlation -0.021; return advantage came from direction. |
| 7 | GEM dual momentum | Rejected 4/5; monthly decisions lagged the five-week decline. |
| 8 | PAA defensive allocation | Rejected 4/6; crisis checks passed 2/2, returns did not. |
| 9 | Three leveraged timing designs | Rejected; crisis losses. |
| 10 | Twenty-seven decision frequencies | Rejected; rebalancing-phase sensitivity identified. |
| 11 | Tranche rebalancing | Acceptance withdrawn after gold ablation; replication-pool bias identified. |
| 12 | Uncorrelated assets | Gold was not unique; data-availability bias identified. |
| 13 | Synthetic bonds | Rejected 5/8; best SR 0.98, return-stripped margin -1.0 percentage point. |
| 14 | Twenty-eight rotation families | Rejected 2/5; rising-asset exposure explained results. |
| 15 | Four seasonal rules | Rejected; anomalies weakened in later data. |
| 16 | Mean reversion | One of six claims testable; rejected 2/7. |
| 17 | Seven learned-weight families | Lost to equal weighting. |
| 18 | Form 4, 1.52 million records | Rejected; the control won. |
| 19 | Gate power | True SR 3.0 accepted 100%; detection floor 1.5. |
| 20 | Forward paper test | Began a two-year observation period. |
| 21 | Execution constraints | No accepted edge remained after constraints. |
| 22 | Korean replication | Delisted candles unavailable; kr_date() lookahead found. |
| 23 | Bulk intake harness | Timing, cross-section, rotation, and long/short execution types. |
| 24 | Korean replication of six US candidates | Zero of three usable replications succeeded without retuning. |
| 25 | Twelve allocation models | Six TAA models ranked lowest; two benchmark exceedances came from gold. |
| 26 | Twelve sector and cross-asset models | Preregistered prediction confirmed; ctx lookahead invalidated ten runs, which were rerun. |
| 27 | Twenty-five neutral long/short models | Tested residual performance after removing beta. |
| 28 | Twenty-five Korean models | Two benchmark exceedances; US–Korea rank correlation -0.53. |
| 29 | Ranking reversal | Persisted with aligned windows at -0.65; within-US correlation +0.93. |
| 30 | Effective dimension | Korea 1.4 and US 3.2 out of twenty-five models. |
| 31 | Four ensembles and five macro rules | Ensembles below the best individual; NFCI threshold explained 96% of the margin. |
| 32 | Crypto market | Delisted candles enabled a point-in-time universe. |
| 33 | Twenty-five point-in-time crypto models | None beat BTC under the tested assumptions. |
| 34 | Survivorship measurement | Mean +0.102 SR and +5.97 points CAGR; downside deviation approximately zero. |
| 35 | Three-market comparison | Return/risk styles reversed across markets; Korea and crypto shared four top-five entries. |
| 36 | Style prediction | z=-0.06, indistinguishable from chance. |
| 37 | Goal feasibility | Highest observed SR left a 28-point annual shortfall at any modeled leverage. |
| 38 | Universe coverage | US coverage 54%; SR understated by 27%. |
| 39 | Correct-window rerun | Conclusion unchanged; benchmark SR rose from 0.55 to 0.74 too. |
| 40 | Canary tests | Leakage, noise, and signal recovery; recorded two-second CI run. |
| 41 | Nine review findings | Four affected results; one crypto exceedance rejected on sensitivity. |
| 42 | Final robustness battery | Four passes; subsamples showed the edge disappeared after 2015. |
| 43 | gs-quant and bullstory.io | Tools or content without a testable model claim. |

### Catalog batches

| Batch | Family | Tests | Benchmark exceedances |
|---:|---|---:|---:|
| 1 | Classical technical and academic factors | 10 | 1 |
| 2 | Seven technical and six academic factors | 13 | 0 |
| 3 | Overnight, long-horizon, and combinations | 10 | 2 |
| 4 | Residuals, group risk, and paths | 8 | 0 |
| 5 | Execution and exit rules | 7 | 3 |
| 6 | Continuous exposure and relative strength | 9 | 0 |
| 7 | TAA allocation | 12 | 2 |
| 8 | Sector and cross-asset rotation | 12 | 1 |
| 9 | Neutral long/short | 25 | — |
| — | Korean replication | 8 | 0 |

No batch produced a candidate that passed all gates.

## Repeated findings

Signals often had the intended direction but did not outperform after costs and style exposure. Timing reduced drawdown from 56% to 19–40%, with lower returns. Diversification advantages were usually explained by a rising component asset. Leverage increased returns and crisis losses.

Five exposure comparisons showed:

| Comparison | Result |
|---|---|
| Higher threshold on the same signal | SR 0.58 to 0.26 |
| Binary to continuous exposure | No improvement; two of three pairs worsened |
| Defensive TAA versus fixed allocation | All six TAA models below fixed allocation |
| Remove only the defense rule | SR 0.36 to 0.63 |
| Switch to Treasuries instead of reducing exposure | Margin penalty 0.27 to 0.00 |

| Portfolio | CAGR | Maximum drawdown | Risk-normalized return |
|---|---:|---:|---:|
| SPY holding | +9.1% | 56% | +9.1% |
| SPY trend/Treasury switch | +7.0% | 27% | +9.2% |
| SSO trend/Treasury switch | +12.7% | 45% | +10.6% |
| SSO holding | +14.4% | 85% | +9.1% |

Drawdown reduction was meaningful, but did not produce a comparable increase in normalized return.

The aligned US–Korea style correlation was -0.649, while within-US stability was +0.929. Conditional style prediction matched signs 48.5% of the time versus chance 49.0%, z=-0.06.

Rank ensembles returned SR 0.46 for all models, 0.48 for return-based models, and 0.33 for risk-based models, below the roughly 0.60 best individual. The point-in-time crypto catalog had no BTC exceedances under 50% delisting losses; seventeen of twenty-five CAGRs were negative.

## Data and pending work at the archive date

OHLCV, 3.97 million SEC financial records, sixty-four years of synthetic bonds from FRED, and 1.52 million Form 4 records had produced no accepted candidate.

Korean PEAD remained pending in this archived version. `stonks/dart.py` and `stonks/catalog14.py` were written but awaited DART credentials. Later atlas results are separate from this record.

Set DART_API_KEY in an ignored .env file using a key obtained from [OpenDART](https://opendart.fss.or.kr), then run:

```bash
python -m stonks.dart
```

The original collection plan expected hundreds of calls against a 20,000-call daily limit.

## Files and checks

The archive recorded forty-seven standard-library modules, thirty-three preregistrations, eighteen test files with 214 tests, and about 1.3 GB of regenerable ignored data.

Core modules include types, stats, ledger, gate, and lookahead. Data adapters cover Toss, SEC, fundamentals, insiders, FRED, Korean markets, crypto, and DART. Intake implements four execution types, and catalog through catalog13 hold the public-model corpus.

```bash
python -m pytest -q
python -m stonks.canary
python -m stonks.noisefloor
python -m stonks.goal
python -m stonks.forward
```

## Lessons for reusing the harness

Count degrees of freedom before testing. Include the mean when calculating the noise floor, and measure effective dimensions rather than relying only on nominal model counts.

Require a meaningful benchmark margin, remove return-driving assets during replication, test rebalancing phases, and keep ctx and other side channels restricted to the past.

Declare the universe explicitly. Adding forty-four ETFs to an implicit sorted cache changed a historical margin by 3.4x. Check date coverage before evaluating returns; load_market rejects coverage below 80%.

Use canaries that recover real signals as well as rejecting leakage. Check impossible diagnostics. Include recent subsamples and preregister robustness rules that can only reject, rather than selecting the best variant afterward.

## Original return target

The project aimed for 5% monthly, approximately 80% annually. Under `CAGR - rf = S*sigma - sigma²/2`, the maximum modeled growth is `rf + S²/2`.

| Measure | Recorded value |
|---|---:|
| Required SR for 80% annually, full Kelly | 1.23 |
| Required SR, half Kelly | 1.42 |
| Best SR in the 486-trial comparison | 0.98 |
| Measured gate detection floor | 1.50 |
| Modeled annual ceiling at SR 0.98 | 52% |
| Modeled ceiling at SPY SR 0.55 | 19% |

The target exceeded the observed model ceiling by 28 percentage points. Full-Kelly assumptions also implied a 50% chance of losing half the capital and a 10% chance of losing 90%.

The required Sharpe was below the gate's measured detection floor, limiting what the available sample could establish.

[The forward test](https://github.com/nohseongmin/legacy-STONKS-03/blob/main/PREREG_FORWARD.md) fixed five strategies, including a coin-flip control, with judgment deferred until two years of observations.
