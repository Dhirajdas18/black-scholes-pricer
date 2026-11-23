"""Costs of trading NSE index options and futures, per unit of the underlying, in index points.

Statutory and exchange rates as listed on Zerodha's charges page (zerodha.com/charges, checked
2026-11-23), with STT at the rates in force from 1 Apr 2026 (Finance Act 2026). Brokerage is a
discount broker's flat ₹20 per executed order. NIFTY lot size 65 (from Jan 2026 expiries).

The bid-ask spread is not in NSE's bhavcopy (closing prices only), so it is an explicit input:
`half_spread` index points paid per option trade.
"""

RATES = {
    "stt_opt_sell": 0.0015,  # of premium, seller pays
    "stt_opt_exercise": 0.0015,  # of intrinsic value, buyer of an option that expires in the money
    "stt_fut_sell": 0.0005,  # of traded value, sell side
    "txn_opt": 0.0003553,  # NSE transaction charge, of premium
    "txn_fut": 0.0000183,  # NSE transaction charge, of traded value
    "sebi": 10 / 1e7,  # ₹10 per crore
    "stamp_opt_buy": 0.00003,
    "stamp_fut_buy": 0.00002,
    "gst": 0.18,  # on brokerage + SEBI fee + transaction charge
    "brokerage": 20.0,  # ₹ per executed order
    "lot": 65,
}


def option_cost(premium: float, side: str, lots: int = 1, orders: int = 1,
                intrinsic: float = 0.0, half_spread: float = 0.0, rates: dict = RATES) -> float:
    """Cost per unit of opening one option position of `lots` lots with `orders` orders.

    `intrinsic` > 0 adds the exercise STT a buyer pays when the option expires in the money
    (NSE index options settle in cash; there is no closing trade).
    """
    fees = premium * (rates["txn_opt"] + rates["sebi"])
    brokerage = rates["brokerage"] * orders / (lots * rates["lot"])
    cost = fees + brokerage + rates["gst"] * (fees + brokerage) + half_spread
    if side == "sell":
        cost += premium * rates["stt_opt_sell"]
    else:
        cost += premium * rates["stamp_opt_buy"] + intrinsic * rates["stt_opt_exercise"]
    return float(cost)


def futures_cost(bought: float, sold: float, orders: int = 0, units: float = 1.0,
                 rates: dict = RATES) -> float:
    """Cost of hedge trades with `bought` / `sold` traded value per unit; brokerage of `orders`
    orders spread over `units` units of the position."""
    fees = (bought + sold) * (rates["txn_fut"] + rates["sebi"])
    brokerage = rates["brokerage"] * orders / units
    return float(fees + brokerage + rates["gst"] * (fees + brokerage)
                 + sold * rates["stt_fut_sell"] + bought * rates["stamp_fut_buy"])


# STT before the Finance Act 2026 change (1 Oct 2024 - 31 Mar 2026), for comparison only.
RATES_PRE_2026 = {**RATES, "stt_opt_sell": 0.001, "stt_opt_exercise": 0.00125,
                  "stt_fut_sell": 0.0002}
