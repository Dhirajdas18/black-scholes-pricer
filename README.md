# Black-Scholes Pricer

[![CI](https://github.com/Dhirajdas18/black-scholes-pricer/actions/workflows/ci.yml/badge.svg)](https://github.com/Dhirajdas18/black-scholes-pricer/actions/workflows/ci.yml)
[![Dashboard](https://github.com/Dhirajdas18/black-scholes-pricer/actions/workflows/pages.yml/badge.svg)](https://dhirajdas18.github.io/black-scholes-pricer/)

European option pricing with the Black-Scholes model, tested against what NSE options actually did: what
NIFTY options cost against what they paid, how the Greeks behave, implied volatility on real option
prices, and delta hedging on real NIFTY paths.

**Live calculator and dashboard: [dhirajdas18.github.io/black-scholes-pricer](https://dhirajdas18.github.io/black-scholes-pricer/)**.
The pricer runs in the browser as you type; the charts are rebuilt weekly by GitHub Actions.

## Features

- [x] Black-Scholes prices with a dividend yield, put-call parity, Monte Carlo check (antithetic paths)
- [x] In-browser pricer, tested against the Python implementation through Node
- [x] Greeks: delta, gamma, vega, theta, rho (analytic, tested against finite differences; live in the calculator)
- [x] Implied volatility on real NIFTY option prices (NSE bhavcopy, 2015–2026); smile and skew
- [x] Delta hedging on real NIFTY paths, at real implied volatilities
- [x] Black-76 for options on futures (also in the calculator: enter a futures price)
- [x] Indian trading costs (STT, NSE charges, SEBI fee, stamp duty, GST, brokerage, spread) and what option selling, buying and hedging net
- [x] Model limits: Merton jump-diffusion fitted to every month's smile

## Findings

### 1. At India VIX, NIFTY puts cost more than they paid out, until one month

<table><tr>
<td><a href="docs/img/pricing_insurance.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/pricing_insurance.png"><img src="docs/img/pricing_insurance.gif" alt="Premium vs average payout of one-month at-the-money NIFTY puts and calls"></picture></a></td>
<td><a href="docs/img/pricing_seller.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/pricing_seller.png"><img src="docs/img/pricing_seller.gif" alt="Cumulative profit of selling a one-month at-the-money NIFTY put each month"></picture></a></td>
</tr></table>

<a href="docs/img/pricing_mc.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/pricing_mc.png"><img src="docs/img/pricing_mc.gif" alt="Monte Carlo estimate converging on the Black-Scholes price as paths increase" width="720"></picture></a>

Each month, a one-month at-the-money NIFTY option is priced with Black-Scholes at that day's India VIX
(a 6.5% risk-free rate, no dividends) and held to expiry. Months don't overlap; every figure is the median
across the 21 possible monthly start days (162 months each), so no start date is cherry-picked.

- **Puts cost about a third more than they paid out:** the premium averaged 1.66% of NIFTY and the payout
  1.26%. A put seller kept about 0.40% of the index a month before costs, positive for every start day
  (0.30% to 0.48%). Puts finished in the money in 40% of months.
- **One month erased years of that.** From 18 Feb 2020 the put paid out 27% of the index against a 1.4%
  premium, wiping out more than five years of the seller's gains in one month.
- **Calls were about fair:** 2.20% premium against 2.24% average payout. Black-Scholes uses one volatility
  for both, and India VIX ran above the volatility that followed
  ([returns-volatility study](https://github.com/Dhirajdas18/returns-volatility-dashboard)), but NIFTY's
  drift above the risk-free rate added to calls and took from puts.
- **These are model prices at India VIX, not traded premiums;** section 3 repeats the comparison with real
  NSE option prices, where out-of-the-money puts cost more than India VIX implies.
- **The formula checks out:** a one-million-path Monte Carlo (antithetic pairs) priced a test put at
  7.0986 ± 0.0054 against the formula's 7.1061, within 1.4 standard errors. The tests also pin Hull's
  textbook example (call 4.76, put 0.81) and put-call parity.

### 2. NIFTY beat its daily break-even move less often than Black-Scholes assumes, except in jumps

<table><tr>
<td><a href="docs/img/greeks_curves.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/greeks_curves.png"><img src="docs/img/greeks_curves.gif" alt="Call delta and gamma against NIFTY level for 30, 7 and 1 day to expiry"></picture></a></td>
<td><a href="docs/img/greeks_theta.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/greeks_theta.png"><img src="docs/img/greeks_theta.gif" alt="Value of an at-the-money call falling as expiry approaches"></picture></a></td>
</tr></table>

<a href="docs/img/greeks_breakeven.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/greeks_breakeven.png"><img src="docs/img/greeks_breakeven.gif" alt="Share of days NIFTY moved beyond 1, 2 and 3 times its VIX break-even move, vs a bell curve" width="720"></picture></a>

The Greeks measure how an option's price reacts to each input: **delta** to the price, **gamma** to how
fast delta changes, **vega** to volatility, **theta** to time, **rho** to interest rates. All five are
tested against finite differences and shown live in the [calculator](https://dhirajdas18.github.io/black-scholes-pricer/).
An at-the-money holder's gamma gains and theta losses cancel when NIFTY moves India VIX ÷ √252 in a day.

- **Near expiry, an at-the-money option turns into a switch.** With a day left, delta jumps from 0 to 1
  across a few hundred points of NIFTY and gamma is about five times its 30-day level (top left).
- **Time decay speeds up:** an at-the-money call loses half its value in the first 21.5 of its 30 days and
  the other half in the last 8.5 (top right).
- **The holder lost the daily race between gamma and theta 78% of the time.** Over 3,413 days NIFTY beat
  the break-even move on 21.9% of days, where a bell curve at the same volatility gives 31.7%.
- **But the biggest days were bigger than a bell curve allows:** moves beyond 3× the break-even came on
  0.35% of days against 0.27%. The top 1% of days earned back about half of the holder's daily losses;
  the holder still finished behind. This is the volatility risk premium seen one day at a time.
- **Delta and gamma predict a day's option price change well, until a jump:** for a 30-day at-the-money
  call, delta + gamma + theta missed a full Black-Scholes reprice (volatility held at the previous VIX)
  by a median 0.03% of the option's price, 0.37% on days NIFTY moved more than 3%, and 9.2% on
  20 Sep 2019 (the corporate-tax-cut day, NIFTY +5.2%).

### 3. Every month since 2015, NIFTY options charged extra for crash protection

<a href="docs/img/iv_smile.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/iv_smile.png"><img src="docs/img/iv_smile.gif" alt="Median implied volatility of NIFTY options across strikes, 2015 to 2026" width="720"></picture></a>

<table><tr>
<td><a href="docs/img/iv_premium.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/iv_premium.png"><img src="docs/img/iv_premium.gif" alt="Implied minus realised volatility for the 95% put, at-the-money option and 105% call"></picture></a></td>
<td><a href="docs/img/iv_skew.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/iv_skew.png"><img src="docs/img/iv_skew.gif" alt="Gap between 95% put and 105% call implied volatility each month since 2015"></picture></a></td>
</tr></table>

Black-Scholes assumes one volatility for every strike. Backing implied volatility out of real NIFTY
option closing prices (NSE's daily F&O bhavcopy, the first trading day of each month, the monthly expiry
about four weeks out; 143 months, 2015–2026) shows a lopsided smile instead, with crash protection
priced above what Black-Scholes allows.

- **The skew:** in the median month, a put 5% below the forward traded at 17.2% volatility, the
  at-the-money option at 14.1% and a call 5% above at 12.7%. Puts 10% below: 21.6%.
- **It never flipped.** The 95% put sat above the 105% call in all 143 months, by a median 4.4 points
  (2.7 to 6.4 in nine months out of ten). The widest gap was 10.1 points, on 1 Apr 2020, after the crash.
- **Crash protection was the most overpriced part:** against the volatility NIFTY actually showed until
  expiry (142 months whose expiry has passed), the 95% put's implied vol was a median 5.4 points too high
  (higher in 90% of months), the at-the-money option's 2.0 points (70%) and the 105% call's 1.2 points
  (59%).
- **Until it wasn't:** on 2 Mar 2020 the 95% put was priced at 28% volatility; NIFTY then moved at 88%.
- **The forward price comes from put-call parity at the at-the-money strike,** so no dividend guess is
  needed; it matched NIFTY futures to within 0.1% every month.
- **India VIX averages across strikes, including the expensive puts,** so the at-the-money implied vol
  ran a median 1.4 points below it. That is why finding 1, which priced at-the-money options at India
  VIX, slightly overstated their cost.

### 4. Delta hedging turned option selling into a volatility bet with a sixth of the risk

<a href="docs/img/hedge_cumulative.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/hedge_cumulative.png"><img src="docs/img/hedge_cumulative.gif" alt="Cumulative P&L of selling a monthly at-the-money NIFTY call, hedged daily vs unhedged" width="720"></picture></a>

<table><tr>
<td><a href="docs/img/hedge_gap.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/hedge_gap.png"><img src="docs/img/hedge_gap.gif" alt="Hedged seller's P&L against implied minus realised volatility, each month"></picture></a></td>
<td><a href="docs/img/hedge_frequency.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/hedge_frequency.png"><img src="docs/img/hedge_frequency.gif" alt="Simulated spread of hedged P&L by how often the hedge is rebalanced"></picture></a></td>
</tr></table>

Each month (142 months whose expiry has passed, 2015–2026), sell the at-the-money NIFTY call and,
separately, the 95% put at their real implied volatilities from finding 3, then hold delta units of
NIFTY, rebalanced at each day's close, until expiry. The dividend yield comes from the options' own
forward. Before trading costs (section 6 adds them).

- **Risk fell to a sixth:** the at-the-money call's monthly P&L swung by 2.44% of NIFTY unhedged and
  0.44% hedged daily (0.73% hedged weekly).
- **The sign flipped:** unhedged, selling the call lost 0.11% a month on average (−16% in total, mostly
  in the 2020–21 rally); hedged, it made 0.16% a month (+23% in total) and won 70% of months.
- **The 95% put:** hedged, it made 0.09% a month and won 84% of months; its worst month, March 2020,
  lost 2.9% of NIFTY hedged against 16.2% unhedged.
- **What a hedged seller earns is the volatility gap:** the monthly P&L tracked implied minus realised
  volatility (correlation 0.74 for the call, 0.76 for the put). Hedged, March 2020 still cost the call
  seller 1.3% even though the call expired worthless, because NIFTY moved at 88% volatility against 25%
  priced in. The worst hedged month was September 2019 (the corporate-tax-cut jump), −1.7%.
- **Hedging is never perfect:** on simulated paths where realised volatility exactly equals implied,
  the hedged P&L still spreads by 16% of the premium with daily rebalancing, 33% weekly and 66% when the
  hedge is set only once (right). Black-Scholes's risk-free hedge assumes continuous trading.

### 5. Priced off NIFTY futures (Black-76), calls and puts agree; off spot, they don't

<table><tr>
<td><a href="docs/img/b76_gap.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/b76_gap.png"><img src="docs/img/b76_gap.gif" alt="Call minus put implied volatility at the same strike, Black-76 vs Black-Scholes on spot"></picture></a></td>
<td><a href="docs/img/b76_carry.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/b76_carry.png"><img src="docs/img/b76_carry.gif" alt="Carry implied by NIFTY futures each month and the yearly median"></picture></a></td>
</tr></table>

Black-76 prices an option off the futures price instead of spot. The futures price already contains the
carry (interest minus dividends), so no dividend estimate is needed. Each month (143), the call and put
at the strike nearest NIFTY futures are run through both models.

- **Same strike, same expiry, so the two implied vols should match.** With Black-76 on the futures price
  they did, to a median 0.16 points. With Black-Scholes on spot and no dividends they were 1.66 points
  (about 1.7) apart (calls a median 1.44 points too low, worst 10.8): assuming a 6.5% carry with no
  dividends puts the forward too high.
- **The carry in futures:** ln(futures ÷ spot) ÷ time ran at a median 4.4% a year, so dividends and
  financing differences took about 2.1% off the 6.5% rate assumed elsewhere. It dipped to 1.1% in 2020
  (rate cuts and futures trading at a discount in the crash) and to 3.1% in the June–August dividend
  season, against 4.7% in other months. Monthly values are noisy: the spot close and the futures
  settlement price are not taken at exactly the same moment.
- **This is why section 3 took the forward from put-call parity** rather than from spot.

### 6. After Indian costs, the hedged option seller kept two-thirds of the edge

<table><tr>
<td><a href="docs/img/costs_waterfall.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/costs_waterfall.png"><img src="docs/img/costs_waterfall.gif" alt="Average monthly edge of the daily-hedged at-the-money call seller, from gross to net of each cost"></picture></a></td>
<td><a href="docs/img/costs_frequency.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/costs_frequency.png"><img src="docs/img/costs_frequency.gif" alt="Hedged seller's average monthly P&L before and after costs, by hedging frequency"></picture></a></td>
</tr></table>

Finding 4's trades, repriced with every Indian cost at the rates in force from April 2026 (STT 0.15% of
option premium on sales and of intrinsic value on exercise, 0.05% on futures sales; NSE charges, SEBI
fee, stamp duty, 18% GST; ₹20 brokerage per order on a 10-lot position, NIFTY lot 65). NSE's bhavcopy has
closing prices but no quotes, so the option's bid-ask spread is an assumption, tested at 0, 1 and 2
points each way.

- **The option's own costs are small:** selling the at-the-money call cost 0.003% of NIFTY in fees and
  taxes (₹65 a lot in the 10-lot book at a ₹500 premium; ₹86 for a single lot, as the calculator shows),
  0.011% with a 1-point half-spread.
- **The futures hedge, not the option, is the expensive part:** the daily hedge traded 1.6 times the
  position's value each month, and its costs came to 0.039% of NIFTY a month, 72% of that STT on futures
  sales. Together, costs took the hedged call seller from 0.159% to 0.109% a month (0.101% to 0.117%
  across the spread assumptions); the 95% put seller from 0.095% to 0.061%.
- **The April 2026 STT rise matters for hedgers:** at the previous rates the same hedge cost 0.022% a
  month instead of 0.039%.
- **Hedging less often cut costs but earned less before costs too.** Weekly hedging halved the hedge
  costs, but the at-the-money seller's gross edge fell from 0.159% to 0.022% a month (paired t = 3.1), so
  it netted −0.007%. The cause isn't established: NIFTY's weekly moves inside these months were only
  slightly larger than its daily moves implied (variance ratio 1.06, not significant), which explains
  only part of the gap.
- **Buying the 95% put as monthly protection** cost its holder 0.096% of NIFTY a month after costs
  (1-point spread), about 1.2% a year.

### 7. Crash jumps fit the smile, but the fitted crashes don't match history or stay put

<a href="docs/img/merton_smile.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/merton_smile.png"><img src="docs/img/merton_smile.gif" alt="Median NIFTY smile with the Merton jump-diffusion fit and Black-Scholes's single volatility" width="720"></picture></a>

<table><tr>
<td><a href="docs/img/merton_crashes.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/merton_crashes.png"><img src="docs/img/merton_crashes.gif" alt="Daily drops worse than 3, 4 and 5 percent a year: priced into options vs actual"></picture></a></td>
<td><a href="docs/img/merton_params.png"><picture><source media="(prefers-reduced-motion: reduce)" srcset="docs/img/merton_params.png"><img src="docs/img/merton_params.gif" alt="Fitted jump frequency and average jump size each month"></picture></a></td>
</tr></table>

Merton's jump-diffusion is Black-Scholes plus sudden jumps: on average λ a year, each moving NIFTY by
a random amount with mean μ and spread δ. Fitted to each month's smile from finding 3 (143 months), and
tested against Black-Scholes in the limit with no jumps, put-call parity and a Monte Carlo check.

- **It fits:** a typical month's smile missed by 4.1 vol points with one Black-Scholes volatility and by
  0.5 with Merton. The median month's fit: 10.7% everyday volatility plus 2.4 jumps a year of −3.2% on
  average (spread 6.4%).
- **Priced crashes vs real ones:** in the median month, option prices implied 0.96 days a year with a drop
  worse than −5%, where NIFTY had 0.60 (2015–2026); for −4%, 1.19 against 0.95. Moderate drops worse than
  −3% were priced at 1.38 a year against 1.81 actual. Options charge most for the biggest crashes, the
  same volatility risk premium as findings 1–4, now in crash terms.
- **The parameters don't stay put:** refitted monthly, the jump rate ranged from 1.1 to 4.7 a year
  between quartiles and hit the 20-a-year bound twice; the average jump ranged down to −26% (April 2020).
  The fit describes each month's smile rather than a fixed truth about NIFTY, and real crashes cluster
  (March 2020) where Merton's jumps are independent.

## Quick start

```bash
uv sync
uv run python scripts/fetch_data.py                                   # Yahoo Finance -> data/prices.parquet
uv run bsp price --spot 25000 --strike 25500 --days 30 --vol 0.15    # call and put
uv run python scripts/fetch_options.py                                # NSE archive -> data/options/ (local only)
uv run bsp report pricing                                             # also: greeks, iv, hedging, black76, costs, merton
uv run python scripts/build_site.py                                   # dashboard -> site/index.html
uv run pytest
```

## Design

- `src/bsp/bs.py`: Black-Scholes prices (vectorised) and a Monte Carlo check.
- `src/bsp/options.py`, `iv.py`: NSE F&O bhavcopy download and parsing; implied volatility (Brent's
  method), forward from put-call parity, and each month's smile. Raw NSE data is never committed; only
  the derived implied vols and carry (`docs/data/`) are, so the dashboard can rebuild without it.
- `src/bsp/costs.py`: NSE option and futures costs (rates in one table, sourced; the calculator mirrors it).
- `src/bsp/merton.py`: Merton jump-diffusion price (series), Monte Carlo check and smile fitting.
- `src/bsp/black76.py`: Black-76 price and implied vol for options on futures.
- `src/bsp/hedge.py`: delta-hedging simulator (any rebalancing interval, dividend yield, cash at r).
- `src/bsp/greeks.py`: analytic Greeks in reading units (per ₹1, per vol point, per day, per 1% rate).
- `src/bsp/pricer.js`: the same formula for the browser; a test compares it with Python through Node.
- `src/bsp/reports.py`: README findings, reproducible with `bsp report <topic>`.
- `src/bsp/site.py`, `calculator.html`, `page.html`: the dashboard, one static page; no server.

MIT licence.
