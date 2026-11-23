"""Black-Scholes prices for European options, with a continuous dividend yield.

S spot, K strike, T years to expiry, r risk-free rate, sigma volatility, q dividend yield (all
annual, continuously compounded). Inputs broadcast like numpy arrays.
"""

import numpy as np
from scipy.stats import norm


def d1_d2(s, k, t, r, sigma, q=0.0):
    s, k, t, sigma = (np.asarray(x, dtype=float) for x in (s, k, t, sigma))
    vt = sigma * np.sqrt(t)
    d1 = (np.log(s / k) + (r - q + 0.5 * sigma**2) * t) / vt
    return d1, d1 - vt


def bs_price(s, k, t, r, sigma, kind: str = "call", q: float = 0.0):
    """Black-Scholes price. At expiry (t = 0) it returns the intrinsic value."""
    s, k, t = (np.asarray(x, dtype=float) for x in (s, k, t))
    sign = 1.0 if kind == "call" else -1.0
    with np.errstate(divide="ignore", invalid="ignore"):
        d1, d2 = d1_d2(s, k, np.maximum(t, 1e-300), r, sigma, q)
        price = sign * (s * np.exp(-q * t) * norm.cdf(sign * d1)
                        - k * np.exp(-r * t) * norm.cdf(sign * d2))
    intrinsic = np.maximum(sign * (s - k), 0.0)
    out = np.where(t <= 0, intrinsic, price)
    return out.item() if out.ndim == 0 else out


def mc_price(s, k, t, r, sigma, kind: str = "call", q: float = 0.0, n_paths: int = 100_000,
             seed: int | None = None) -> tuple[float, float]:
    """Monte Carlo price under the same assumptions (risk-neutral GBM, antithetic pairs).

    Returns (price, standard error). Used to check the formula, not to replace it.
    """
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(n_paths // 2)
    z = np.concatenate([z, -z])
    st = s * np.exp((r - q - 0.5 * sigma**2) * t + sigma * np.sqrt(t) * z)
    pay = np.maximum(st - k, 0) if kind == "call" else np.maximum(k - st, 0)
    disc = np.exp(-r * t) * pay
    pairs = 0.5 * (disc[: n_paths // 2] + disc[n_paths // 2:])  # antithetic pairs are independent
    return float(pairs.mean()), float(pairs.std(ddof=1) / np.sqrt(len(pairs)))
