# STONKS Atlas

A research archive testing trading strategies across Korean equities, US equities, and cryptocurrency. The consolidated records report 620 trials and no strategy accepted for deployment.

[View the results site](https://nohseongmin.github.io/stonks-atlas/).

## Results

| Market | Recorded trials | Main candidate | Rejection reason |
|---|---:|---|---|
| Korean equities | 14 | Downside-deviation screen, Sharpe 0.78 | The advantage disappeared in recent subsamples. |
| US equities | 467 | Mean-reversion dip buying | Most of the apparent Sharpe advantage came from cash interest. |
| Crypto | 130 | taker_imb_30, Sharpe 1.55 | Removing ten of 753 assets reduced Sharpe to 0.95. |
| Live operation | — | Eight-week paper trial | Operation stopped after the first day. |

These are the source summaries' recorded counts. The deduplicated ledgers retain the individual trials and their outcomes.

Most candidates failed the benchmark comparison. Some then failed at tripled costs; the remaining results did not clear the multiple-testing noise floor. No candidate completed the robustness battery.

## Main observations

The strongest crypto candidate depended on a small set of assets, including LUNA. The US dip-buying portfolio held cash about 99% of the time: setting the risk-free rate to zero reduced Sharpe from 0.74 to 0.19.

Repeated strategy searches raised the crypto noise floor from 1.15 after five trials to 1.98 after 130. The best observed Sharpe remained 1.55.

Many catalog entries measured similar exposures:

| Sample | Effective dimension |
|---|---:|
| Twenty-five Korean models | 1.4 |
| Twenty-five US models | 3.2 |
| Sixty-two crypto strategies | 8.2 |
| Five crypto information sources | 2.81 |

These findings describe the tested data and assumptions. They do not establish that other signals cannot exist.

The live paper trial recorded one operating day out of about forty, or 2.5% uptime against a 95% requirement. Sustained operation remained unresolved independently of the research results.

## Method

- Commit rules, predictions, and rejection conditions before examining results.
- Require seven gates: point-in-time data, sample length, liquidation, benchmark performance, tripled costs, drawdown, and the noise floor.
- Retain rejected trials in a fingerprinted ledger.
- Run robustness checks for parameter plateaus, subsamples, costs, quantiles, asset ablation, and orthogonality.
- Check gate power with synthetic signals.
- Block future indices through PastView.

Tests and runtime checks also found implementation defects that the strategy gates did not catch, including future data exposed through ctx, incomplete date coverage, missing overnight gaps, and parser alignment errors.

## Detailed records

- [Korean equities](markets/kr.md)
- [US equities](markets/us.md)
- [Cryptocurrency](markets/crypto.md)
- [Live operation](markets/live.md)
- [Full tables and measurements](README.full.md)
- [Preregistrations, results, and ledgers](evidence/)

## Running the crypto harness

```bash
python -m crypto.dump.costs
python -m crypto.dump.feed
python -m crypto.dump.runzoo
python -m crypto.dump.battery
cd crypto
python -m pytest -q
```

## Repository layout

```text
README.md       Overview
README.full.md  Detailed tables
markets/        Market-specific records
evidence/       Original preregistrations, results, and ledgers
crypto/         Crypto harness imported with its Git history
verify/         US dip-buying verifier
```

Earlier repositories remain available as [legacy-dumpItAll](https://github.com/nohseongmin/legacy-dumpItAll), [legacy-STONKS-03](https://github.com/nohseongmin/legacy-STONKS-03), [legacy-ai-stonks-v2](https://github.com/nohseongmin/legacy-ai-stonks-v2), [legacy-AI-STONKS](https://github.com/nohseongmin/legacy-AI-STONKS), and [legacy-STONKS](https://github.com/nohseongmin/legacy-STONKS).

The next unresolved task is sustained paper operation. The retrospective strategy search is closed.
