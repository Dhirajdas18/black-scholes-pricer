"""Merton (1976) jump-diffusion: Black-Scholes plus sudden jumps.

Jumps arrive at rate `lam` a year; each multiplies the price by e^J with J ~ Normal(mu_j, delta^2).
The price is a Poisson-weighted sum of Black-Scholes prices, one for each number of jumps n:

    sum_n  e^(-lam' T) (lam' T)^n / n!  *  BS(S, K, T, r_n, sigma_n)
    lam' = lam (1 + k),  k = e^(mu_j + delta^2 / 2) - 1
    sigma_n^2 = sigma^2 + n delta^2 / T,   r_n = r - lam k + n ln(1 + k) / T
"""

from math import factorial

import numpy as np

from bsp.bs import bs_price


def merton_price(s, k, t, r, sigma, kind: str = "call", q: float = 0.0, lam: float = 0.0,
                 mu_j: float = 0.0, delta: float = 0.0, terms: int = 40):
    if lam == 0:
        return bs_price(s, k, t, r, sigma, kind, q)
    kbar = np.exp(mu_j + 0.5 * delta**2) - 1
    lam2 = lam * (1 + kbar)
    total = 0.0
    for n in range(terms):
        weight = np.exp(-lam2 * t) * (lam2 * t) ** n / factorial(n)
        if n > 5 and weight < 1e-14:
            break
        sig_n = np.sqrt(sigma**2 + n * delta**2 / t)
        r_n = r - lam * kbar + n * np.log1p(kbar) / t
        total = total + weight * bs_price(s, k, t, r_n, sig_n, kind, q)  # Hull's form
    return total


def merton_mc(s, k, t, r, sigma, kind: str = "call", q: float = 0.0, lam: float = 0.0,
              mu_j: float = 0.0, delta: float = 0.0, n_paths: int = 200_000, seed=None):
    """Monte Carlo price and standard error, simulating the jumps directly."""
    rng = np.random.default_rng(seed)
    kbar = np.exp(mu_j + 0.5 * delta**2) - 1
    n = rng.poisson(lam * t, n_paths)
    jumps = mu_j * n + delta * np.sqrt(n) * rng.standard_normal(n_paths)
    z = rng.standard_normal(n_paths)
    log_st = (np.log(s) + (r - q - lam * kbar - 0.5 * sigma**2) * t + sigma * np.sqrt(t) * z
              + jumps)
    st = np.exp(log_st)
    payoff = np.maximum(st - k, 0) if kind == "call" else np.maximum(k - st, 0)
    disc = np.exp(-r * t) * payoff
    return float(disc.mean()), float(disc.std(ddof=1) / np.sqrt(n_paths))


def fit_smile(moneyness, iv, t: float, r: float) -> dict:
    """Fit sigma, lam, mu_j, delta to one expiry's smile (implied vols at strikes given as a
    fraction of the forward). Works in forward terms (spot 1, dividend yield r) and minimises
    price errors divided by vega, which approximate vol errors. Two starting points; the better
    fit wins. Returns the parameters plus the root-mean-square vol error of the fit."""
    from scipy.optimize import least_squares

    from bsp.greeks import greeks
    from bsp.iv import implied_vol

    m, iv = np.asarray(moneyness, dtype=float), np.asarray(iv, dtype=float)
    kind = np.where(m < 1, "put", "call")
    market = np.array([bs_price(1.0, k, t, r, v, c, r)
                       for k, v, c in zip(m, iv, kind, strict=True)])
    vega = np.array([greeks(1.0, k, t, r, v, c, r)["vega"] * 100
                     for k, v, c in zip(m, iv, kind, strict=True)])

    def model(p):
        return np.array([merton_price(1.0, k, t, r, p[0], c, r, p[1], p[2], p[3])
                         for k, c in zip(m, kind, strict=True)])

    best = None
    for x0 in ([np.median(iv) * 0.8, 1.0, -0.05, 0.05], [np.median(iv) * 0.6, 0.3, -0.15, 0.08]):
        res = least_squares(lambda p: (model(p) - market) / vega, x0,
                            bounds=([0.02, 0.0, -0.6, 0.005], [1.0, 20.0, 0.3, 0.5]))
        if best is None or res.cost < best.cost:
            best = res
    sigma, lam, mu_j, delta = best.x
    fitted = np.array([implied_vol(p, 1.0, k, t, r, c, r)
                       for p, k, c in zip(model(best.x), m, kind, strict=True)])
    return {"sigma": sigma, "lam": lam, "mu_j": mu_j, "delta": delta,
            "rmse": float(np.sqrt(np.nanmean((fitted - iv) ** 2)))}
