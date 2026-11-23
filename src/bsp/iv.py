"""Implied volatility: the volatility that makes Black-Scholes match an observed option price."""

import numpy as np
from scipy.optimize import brentq

from bsp.bs import bs_price


def implied_vol(price: float, s: float, k: float, t: float, r: float, kind: str = "call",
                q: float = 0.0, lo: float = 1e-4, hi: float = 5.0) -> float:
    """Solve bs_price(sigma) = price with Brent's method. NaN if no volatility can match it
    (a price below intrinsic value or above the no-arbitrage maximum)."""
    try:
        f = lambda v: bs_price(s, k, t, r, v, kind, q) - price  # noqa: E731
        if f(lo) > 0 or f(hi) < 0:
            return float("nan")
        return float(brentq(f, lo, hi, xtol=1e-10))
    except (ValueError, RuntimeError):
        return float("nan")


def implied_forward(call: float, put: float, k: float, t: float, r: float) -> float:
    """Forward price from put-call parity at one strike: F = K + e^(rT) (C - P).

    Needs no dividend estimate: the option market prices the forward itself.
    """
    return float(k + np.exp(r * t) * (call - put))


MONEYNESS = (0.90, 0.95, 1.00, 1.05, 1.10)


def snapshot_smile(chain, day, r: float = 0.065, target_days: int = 30,
                   min_days: int = 14, max_days: int = 60, min_price: float = 0.5,
                   min_strikes: int = 10):
    """Implied volatilities across strikes for the expiry closest to `target_days`.

    Only monthly expiries (those with a futures contract) with at least `min_strikes` traded
    strikes are considered. The forward comes from put-call parity at the strike nearest the
    futures price (no dividend guess). Only traded out-of-the-money options are used: puts below
    the forward, calls above.
    Returns (summary dict with iv at MONEYNESS levels, table of strikes), or None if the chain
    can't give a smile (no expiry in range, or no call-put pair).
    """
    import pandas as pd

    opts = chain[chain["type"].isin(["CE", "PE"]) & (chain["contracts"] > 0)
                 & (chain["price"] > min_price)].copy()
    opts["days"] = (opts["expiry"] - day).dt.days
    cand = opts[(opts["days"] >= min_days) & (opts["days"] <= max_days)]
    # Monthly expiries (the ones with a futures contract) are the liquid ones; since 2019 the
    # weekly nearest 30 days often has a single trade. Keep expiries with enough traded strikes.
    monthly = set(chain.loc[chain["type"] == "FUT", "expiry"])
    cand = cand[cand["expiry"].isin(monthly)]
    deep = cand.groupby("expiry")["strike"].nunique()
    cand = cand[cand["expiry"].isin(deep[deep >= min_strikes].index)]
    if cand.empty:
        return None
    expiry = cand.loc[(cand["days"] - target_days).abs().idxmin(), "expiry"]
    e = cand[cand["expiry"] == expiry]
    t = (expiry - day).days / 365
    pairs = e.pivot_table(index="strike", columns="type", values="price")
    if not {"CE", "PE"} <= set(pairs.columns):
        return None
    pairs = pairs.dropna()
    if pairs.empty:
        return None
    fut = chain[(chain["type"] == "FUT") & (chain["expiry"] == expiry)]["price"]
    ref = float(fut.iloc[0])
    k_atm = pairs.index[np.abs(pairs.index - ref).argmin()]
    fwd = implied_forward(pairs.loc[k_atm, "CE"], pairs.loc[k_atm, "PE"], k_atm, t, r)
    s_eff = fwd * np.exp(-r * t)
    otm = e[((e["type"] == "PE") & (e["strike"] < fwd))
            | ((e["type"] == "CE") & (e["strike"] >= fwd))].copy()
    otm["iv"] = [implied_vol(p, s_eff, k, t, r, "put" if typ == "PE" else "call")
                 for p, k, typ in zip(otm["price"], otm["strike"], otm["type"], strict=True)]
    otm["moneyness"] = otm["strike"] / fwd
    otm = otm.dropna(subset=["iv"]).sort_values("moneyness")
    if len(otm) < 5:
        return None
    m, iv = otm["moneyness"].to_numpy(), otm["iv"].to_numpy()
    summary = {"date": pd.Timestamp(day), "expiry": expiry, "days": int((expiry - day).days),
               "forward": fwd, "futures": ref}
    for level in MONEYNESS:
        key = f"iv{round(level * 100)}"
        summary[key] = float(np.interp(level, m, iv)) if m.min() <= level <= m.max() else np.nan
    otm["date"] = pd.Timestamp(day)
    return summary, otm[["date", "expiry", "strike", "type", "price", "moneyness", "iv"]]
