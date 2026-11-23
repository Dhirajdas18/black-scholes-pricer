import numpy as np
import pandas as pd

from bsp.reports import hedge_table, realised_vol


def _iv_row(day, expiry):
    return pd.DataFrame({"expiry": [pd.Timestamp(expiry)], "forward": [25100.0], "iv100": [0.15],
                         "iv95": [0.18], "realised": [0.14]}, index=[pd.Timestamp(day)])


def _prices(end):
    days = pd.bdate_range("2026-11-02", end)
    return pd.Series(25000 * np.exp(np.linspace(0, 0.02, len(days))), index=days)


def test_month_is_skipped_until_prices_run_past_expiry():
    iv = _iv_row("2026-11-02", "2026-11-24")
    assert hedge_table(iv, _prices("2026-11-24")).empty  # expiry-day close may be intraday
    assert len(hedge_table(iv, _prices("2026-11-25"))) == 2  # both legs once final


def test_holiday_expiry_settles_on_the_last_trading_day():
    s = _prices("2026-11-30").drop(pd.Timestamp("2026-11-24"))  # expiry day is a holiday
    assert len(hedge_table(_iv_row("2026-11-02", "2026-11-24"), s)) == 2


def test_realised_vol_needs_the_whole_window():
    s = _prices("2026-11-20")
    assert np.isnan(realised_vol(s, pd.Timestamp("2026-11-02"), pd.Timestamp("2026-11-24")))
    assert np.isfinite(realised_vol(_prices("2026-11-25"), pd.Timestamp("2026-11-02"),
                                    pd.Timestamp("2026-11-24")))
