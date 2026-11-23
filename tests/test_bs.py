import numpy as np
import pytest

from bsp.bs import bs_price, mc_price


def test_hull_textbook_example():
    # Hull, Options, Futures and Other Derivatives: S=42, K=40, r=10%, sigma=20%, T=0.5
    assert bs_price(42, 40, 0.5, 0.10, 0.20, "call") == pytest.approx(4.76, abs=0.005)
    assert bs_price(42, 40, 0.5, 0.10, 0.20, "put") == pytest.approx(0.81, abs=0.005)


def test_put_call_parity_with_dividend_yield():
    s, k, t, r, q, v = 100.0, 95.0, 0.75, 0.065, 0.012, 0.25
    c, p = bs_price(s, k, t, r, v, "call", q), bs_price(s, k, t, r, v, "put", q)
    assert c - p == pytest.approx(s * np.exp(-q * t) - k * np.exp(-r * t))


def test_limits_expiry_and_zero_volatility():
    assert bs_price(110, 100, 0.0, 0.05, 0.2, "call") == pytest.approx(10.0)
    assert bs_price(90, 100, 0.0, 0.05, 0.2, "put") == pytest.approx(10.0)
    # no volatility: worth the discounted forward intrinsic value
    fwd_call = max(100 * np.exp(0.05) - 95, 0) * np.exp(-0.05)
    assert bs_price(100, 95, 1.0, 0.05, 1e-9, "call") == pytest.approx(fwd_call, rel=1e-6)


def test_vectorised_over_strikes():
    out = bs_price(100.0, np.array([90.0, 100.0, 110.0]), 0.5, 0.05, 0.2, "call")
    assert out.shape == (3,) and np.all(np.diff(out) < 0)  # higher strike, cheaper call


def test_monte_carlo_agrees_within_three_standard_errors():
    est, se = mc_price(100, 105, 0.5, 0.065, 0.22, "put", q=0.01, n_paths=200_000, seed=1)
    exact = bs_price(100, 105, 0.5, 0.065, 0.22, "put", 0.01)
    assert abs(est - exact) < 3 * se and se < 0.02
