import numpy as np
import pytest

from bsp.black76 import black76_price, implied_vol_76
from bsp.bs import bs_price

F, K, T, R, V = 25100.0, 25000.0, 30 / 365, 0.065, 0.15


def test_parity_on_futures():
    c, p = black76_price(F, K, T, R, V, "call"), black76_price(F, K, T, R, V, "put")
    assert c - p == pytest.approx(np.exp(-R * T) * (F - K))


def test_same_as_black_scholes_on_the_discounted_futures_price():
    s = F * np.exp(-R * T)  # the spot that makes F the forward with no dividends
    for kind in ("call", "put"):
        assert black76_price(F, K, T, R, V, kind) == pytest.approx(bs_price(s, K, T, R, V, kind))


def test_hull_futures_option_example():
    # Hull, Options, Futures and Other Derivatives: European put on futures, F = K = 20,
    # r = 9%, sigma = 25%, T = 4 months -> 1.12
    assert black76_price(20, 20, 4 / 12, 0.09, 0.25, "put") == pytest.approx(1.12, abs=0.005)


def test_implied_vol_76_round_trip():
    for kind, k in (("call", 26000.0), ("put", 24000.0)):
        assert implied_vol_76(black76_price(F, k, T, R, 0.21, kind), F, k, T, R, kind) == \
            pytest.approx(0.21, abs=1e-6)
