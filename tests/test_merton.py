import numpy as np
import pytest

from bsp.bs import bs_price
from bsp.iv import implied_vol
from bsp.merton import merton_mc, merton_price

S, K, T, R, V, Q = 25000.0, 25500.0, 30 / 365, 0.065, 0.12, 0.01
JUMPS = dict(lam=0.5, mu_j=-0.08, delta=0.05)  # one jump every two years, -8% on average


def test_no_jumps_is_black_scholes():
    for kind in ("call", "put"):
        assert merton_price(S, K, T, R, V, kind, Q, lam=0.0, mu_j=-0.1, delta=0.05) == \
            pytest.approx(bs_price(S, K, T, R, V, kind, Q))


def test_parity_holds_with_jumps():
    c = merton_price(S, K, T, R, V, "call", Q, **JUMPS)
    p = merton_price(S, K, T, R, V, "put", Q, **JUMPS)
    assert c - p == pytest.approx(S * np.exp(-Q * T) - K * np.exp(-R * T))


def test_matches_monte_carlo():
    price = merton_price(S, 24000.0, T, R, V, "put", Q, **JUMPS)
    mc, se = merton_mc(S, 24000.0, T, R, V, "put", Q, **JUMPS, n_paths=400_000, seed=3)
    assert abs(mc - price) < 3 * se


def test_crash_jumps_make_downside_skew():
    iv = {m: implied_vol(merton_price(S, S * m, T, R, V, "put" if m < 1 else "call", Q, **JUMPS),
                         S, S * m, T, R, "put" if m < 1 else "call", Q) for m in (0.95, 1.05)}
    assert iv[0.95] > iv[1.05] + 0.01


def test_fit_smile_recovers_a_jump_smile():
    from bsp.merton import fit_smile

    t, true = 26 / 365, dict(lam=2.0, mu_j=-0.05, delta=0.06)
    m = np.arange(0.90, 1.101, 0.01)
    kind = np.where(m < 1, "put", "call")
    iv = np.array([implied_vol(merton_price(1.0, k, t, R, 0.10, c, R, **true), 1.0, k, t, R, c, R)
                   for k, c in zip(m, kind, strict=True)])
    fit = fit_smile(m, iv, t, R)
    assert fit["rmse"] < 0.001  # within 0.1 vol point
    assert fit["mu_j"] < 0 and 0.5 < fit["lam"] < 8


def test_many_expected_jumps_still_sum_correctly():
    price = merton_price(100.0, 100.0, 1.0, 0.05, 0.2, "call", lam=50, mu_j=0.0, delta=0.01)
    mc, se = merton_mc(100.0, 100.0, 1.0, 0.05, 0.2, "call", lam=50, mu_j=0.0, delta=0.01,
                       n_paths=200_000, seed=5)
    assert abs(price - mc) < 4 * se


def test_at_expiry_is_intrinsic():
    assert merton_price(110.0, 100.0, 0.0, 0.05, 0.2, "call", lam=1, mu_j=-0.1,
                        delta=0.05) == pytest.approx(10.0)
