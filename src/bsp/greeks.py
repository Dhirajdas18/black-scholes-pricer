"""Black-Scholes Greeks: how an option's price reacts to each input.

Units chosen for reading: delta per ₹1 move in spot, gamma per ₹1 (change in delta),
vega per 1 volatility point, theta per calendar day, rho per 1 percentage point of interest rate.
"""

import numpy as np
from scipy.stats import norm

from bsp.bs import d1_d2


def greeks(s, k, t, r, sigma, kind: str = "call", q: float = 0.0) -> dict:
    d1, d2 = d1_d2(s, k, t, r, sigma, q)
    s, k, t = (np.asarray(x, dtype=float) for x in (s, k, t))
    dq, dr, pdf = np.exp(-q * t), np.exp(-r * t), norm.pdf(d1)
    sqt = np.sqrt(t)
    gamma = dq * pdf / (s * sigma * sqt)
    vega = s * dq * pdf * sqt / 100
    decay = -s * dq * pdf * sigma / (2 * sqt)
    if kind == "call":
        delta = dq * norm.cdf(d1)
        theta = decay - r * k * dr * norm.cdf(d2) + q * s * dq * norm.cdf(d1)
        rho = k * t * dr * norm.cdf(d2) / 100
    else:
        delta = dq * (norm.cdf(d1) - 1)
        theta = decay + r * k * dr * norm.cdf(-d2) - q * s * dq * norm.cdf(-d1)
        rho = -k * t * dr * norm.cdf(-d2) / 100
    out = {"delta": delta, "gamma": gamma, "vega": vega, "theta": theta / 365, "rho": rho}
    return {name: (v.item() if np.ndim(v) == 0 else v) for name, v in out.items()}
