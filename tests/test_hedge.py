import numpy as np
import pytest

from bsp.bs import bs_price
from bsp.hedge import delta_hedge

S0, K, R, DAYS = 25000.0, 25000.0, 0.065, 21
T = 30 / 365  # 21 trading days spread over 30 calendar days


def _paths(sigma, n=1000, steps=DAYS, seed=0):
    rng = np.random.default_rng(seed)
    dt = T / steps
    z = rng.standard_normal((n, steps))
    logs = np.cumsum((R - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z, axis=1)
    return S0 * np.exp(np.hstack([np.zeros((n, 1)), logs]))


def _times(steps=DAYS):
    return np.linspace(T, 0.0, steps + 1)


def _pnls(paths, sigma, every=1, kind="call"):
    return np.array([delta_hedge(p, K, _times(), R, sigma, kind=kind, every=every)["pnl"]
                     for p in paths])


def test_hedged_seller_breaks_even_when_realised_equals_implied():
    pnl = _pnls(_paths(0.15), 0.15)
    premium = bs_price(S0, K, T, R, 0.15, "call")
    assert abs(pnl.mean()) < 0.03 * premium
    assert pnl.std() < 0.25 * premium  # hedging removes most of the risk of a naked short


def test_hedging_more_often_shrinks_the_error():
    paths = _paths(0.15)
    assert _pnls(paths, 0.15, every=1).std() < 0.7 * _pnls(paths, 0.15, every=5).std()


def test_seller_profit_follows_implied_minus_realised():
    assert _pnls(_paths(0.10), 0.15).mean() > 0  # realised below implied: seller gains
    assert _pnls(_paths(0.20), 0.15).mean() < 0  # realised above implied: seller loses


def test_hedged_call_and_put_give_the_same_pnl():
    p = _paths(0.12, n=20)
    np.testing.assert_allclose(_pnls(p, 0.15, kind="call"), _pnls(p, 0.15, kind="put"),
                               rtol=0, atol=1e-6 * S0)


def test_unhedged_result_is_premium_minus_payoff():
    p = _paths(0.15, n=1)[0]
    out = delta_hedge(p, K, _times(), R, 0.15, every=10**6)  # never rebalances after day 0
    assert out["unhedged"] == pytest.approx(
        bs_price(S0, K, T, R, 0.15, "call") * np.exp(R * T) - max(p[-1] - K, 0))
