"""Delta hedging: sell an option, hold delta units of the underlying, rebalance, settle."""

import numpy as np

from bsp.bs import bs_price
from bsp.greeks import greeks


def delta_hedge(s, k: float, t, r: float, sigma: float, kind: str = "call", q: float = 0.0,
                every: int = 1) -> dict:
    """P&L at expiry of selling one option at volatility `sigma` and delta-hedging it.

    s: underlying price at each step, from the sale to expiry. t: years to expiry at each step
    (last 0). The hedge is rebalanced every `every` steps using Black-Scholes delta at `sigma`;
    cash earns `r`. No trading costs. Returns pnl (hedged), unhedged (premium grown at r minus
    payoff) and premium, all in index points per unit.
    """
    s, t = np.asarray(s, dtype=float), np.asarray(t, dtype=float)
    premium = float(bs_price(s[0], k, t[0], r, sigma, kind, q))
    payoff = max(s[-1] - k, 0.0) if kind == "call" else max(k - s[-1], 0.0)
    shares = float(greeks(s[0], k, t[0], r, sigma, kind, q)["delta"])
    cash = premium - shares * s[0]
    for i in range(1, len(s)):
        dt = t[i - 1] - t[i]
        cash = cash * np.exp(r * dt) + shares * s[i - 1] * (np.exp(q * dt) - 1)  # dividends
        if i < len(s) - 1 and i % every == 0:
            new = float(greeks(s[i], k, t[i], r, sigma, kind, q)["delta"])
            cash -= (new - shares) * s[i]
            shares = new
    pnl = cash + shares * s[-1] - payoff
    unhedged = premium * np.exp(r * (t[0] - t[-1])) - payoff
    return {"pnl": float(pnl), "unhedged": float(unhedged), "premium": premium}
