import numpy as np
import pytest

from bsp.costs import RATES, futures_cost, option_cost
from bsp.hedge import delta_hedge


def test_option_sell_pays_stt_on_premium_buy_pays_stamp():
    sell = option_cost(400.0, "sell", lots=1, orders=0)
    buy = option_cost(400.0, "buy", lots=1, orders=0)
    fees = 400 * (RATES["txn_opt"] + RATES["sebi"]) * (1 + RATES["gst"])
    assert sell == pytest.approx(fees + 400 * RATES["stt_opt_sell"])
    assert buy == pytest.approx(fees + 400 * RATES["stamp_opt_buy"])


def test_exercise_stt_on_intrinsic_value_for_the_buyer():
    with_ex = option_cost(400.0, "buy", lots=1, orders=0, intrinsic=300.0)
    assert with_ex - option_cost(400.0, "buy", lots=1, orders=0) == pytest.approx(
        300 * RATES["stt_opt_exercise"])


def test_brokerage_is_per_order_spread_per_unit():
    base = option_cost(400.0, "sell", lots=10, orders=0)
    one_order = option_cost(400.0, "sell", lots=10, orders=1)
    assert one_order - base == pytest.approx(20 * (1 + RATES["gst"]) / (10 * RATES["lot"]))
    assert option_cost(400.0, "sell", lots=10, orders=0, half_spread=1.0) - base == \
        pytest.approx(1.0)


def test_futures_cost_stt_only_on_sales():
    sold = futures_cost(bought=0.0, sold=25000.0)
    bought = futures_cost(bought=25000.0, sold=0.0)
    assert sold - bought == pytest.approx(
        25000 * (RATES["stt_fut_sell"] - RATES["stamp_fut_buy"]))


def test_delta_hedge_reports_traded_notional():
    s = np.array([25000.0, 25200.0, 24900.0, 25100.0])
    t = np.array([3, 2, 1, 0]) / 365
    out = delta_hedge(s, 25000.0, t, 0.065, 0.15)
    assert out["bought"] > 0 and out["sold"] > 0
    once = delta_hedge(s, 25000.0, t, 0.065, 0.15, every=10**6)
    assert once["sold"] == 0  # only the opening purchase; expiry settles in cash
    assert once["bought"] == pytest.approx(out["delta0"] * s[0])
