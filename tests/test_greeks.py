import numpy as np
import pytest

from bsp.bs import bs_price
from bsp.greeks import greeks

S, K, T, R, V, Q = 25000.0, 25500.0, 30 / 365, 0.065, 0.15, 0.012


def _fd(kind, name, h):
    base = dict(s=S, k=K, t=T, r=R, sigma=V, q=Q)
    up, dn = dict(base), dict(base)
    up[name] += h
    dn[name] -= h
    p = lambda a: bs_price(a["s"], a["k"], a["t"], a["r"], a["sigma"], kind, a["q"])  # noqa: E731
    return (p(up) - p(dn)) / (2 * h), p(up), p(dn), p(base)


@pytest.mark.parametrize("kind", ["call", "put"])
def test_greeks_match_finite_differences(kind):
    g = greeks(S, K, T, R, V, kind, Q)
    assert g["delta"] == pytest.approx(_fd(kind, "s", 1.0)[0], rel=1e-5)
    _, up, dn, mid = _fd(kind, "s", 5.0)
    assert g["gamma"] == pytest.approx((up - 2 * mid + dn) / 25.0, rel=1e-3)
    assert g["vega"] == pytest.approx(_fd(kind, "sigma", 1e-4)[0] / 100, rel=1e-5)  # per vol point
    assert g["rho"] == pytest.approx(_fd(kind, "r", 1e-5)[0] / 100, rel=1e-4)  # per 1% rate
    assert g["theta"] == pytest.approx(-_fd(kind, "t", 1e-5)[0] / 365, rel=1e-4)  # per calendar day


def test_call_and_put_greeks_are_linked():
    c, p = greeks(S, K, T, R, V, "call", Q), greeks(S, K, T, R, V, "put", Q)
    assert c["delta"] - p["delta"] == pytest.approx(np.exp(-Q * T))
    assert c["gamma"] == pytest.approx(p["gamma"]) and c["vega"] == pytest.approx(p["vega"])


def test_at_the_money_gamma_explodes_near_expiry():
    g30 = greeks(S, S, 30 / 365, R, V, "call")["gamma"]
    g1 = greeks(S, S, 1 / 365, R, V, "call")["gamma"]
    assert g1 > 5 * g30
