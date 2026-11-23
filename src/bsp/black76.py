"""Black-76: European options priced from the futures (or forward) price instead of spot.

price = e^(-rT) [F N(d1) - K N(d2)],  d1 = (ln(F/K) + sigma^2 T / 2) / (sigma sqrt(T)).

The futures price already contains the carry (interest minus dividends), so no dividend estimate
is needed. It equals Black-Scholes with spot F and dividend yield r, which is how it's computed.
"""

from bsp.bs import bs_price
from bsp.iv import implied_vol


def black76_price(f, k, t, r, sigma, kind: str = "call"):
    return bs_price(f, k, t, r, sigma, kind, q=r)


def implied_vol_76(price: float, f: float, k: float, t: float, r: float,
                   kind: str = "call") -> float:
    return implied_vol(price, f, k, t, r, kind, q=r)
