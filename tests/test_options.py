import io
import zipfile
from datetime import date

import numpy as np
import pandas as pd
import pytest

from bsp.bs import bs_price
from bsp.iv import implied_forward, implied_vol
from bsp.options import parse_fo, url_fo


def _zip(csv: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("fo.csv", csv)
    return buf.getvalue()


def test_urls_switch_format_in_july_2024():
    assert url_fo(date(2020, 3, 2)).endswith("/DERIVATIVES/2020/MAR/fo02MAR2020bhav.csv.zip")
    assert url_fo(date(2025, 1, 2)).endswith("BhavCopy_NSE_FO_0_0_0_20250102_F_0000.csv.zip")


def test_parse_old_format_keeps_nifty_index_options_and_futures():
    csv = ("INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,OPEN,HIGH,LOW,CLOSE,SETTLE_PR,"
           "CONTRACTS,VAL_INLAKH,OPEN_INT,CHG_IN_OI,TIMESTAMP\n"
           "OPTIDX,NIFTY,26-Mar-2020,11000,PE,1,1,1,95.5,95.5,1200,0,5000,0,02-MAR-2020\n"
           "FUTIDX,NIFTY,26-Mar-2020,0,XX,1,1,1,11150,11150.4,9000,0,9000,0,02-MAR-2020\n"
           "OPTIDX,BANKNIFTY,26-Mar-2020,29000,CE,1,1,1,300,300,10,0,10,0,02-MAR-2020\n"
           "OPTSTK,INFY,26-Mar-2020,700,CE,1,1,1,30,30,10,0,10,0,02-MAR-2020\n")
    out = parse_fo(date(2020, 3, 2), _zip(csv))
    assert list(out["type"]) == ["PE", "FUT"]
    assert out.loc[out.type == "FUT", "price"].iloc[0] == pytest.approx(11150.4)  # futures: settle
    assert out.loc[out.type == "PE", "price"].iloc[0] == pytest.approx(95.5)  # options: close
    assert out["expiry"].iloc[0] == pd.Timestamp("2020-03-26")


def test_parse_new_format():
    csv = ("TradDt,FinInstrmTp,TckrSymb,XpryDt,StrkPric,OptnTp,ClsPric,SttlmPric,TtlTradgVol,"
           "OpnIntrst\n"
           "2025-01-02,IDO,NIFTY,2025-01-30,24000,CE,350.5,350.5,500,800\n"
           "2025-01-02,IDF,NIFTY,2025-01-30,,,23950,23960.2,100,100\n"
           "2025-01-02,STO,TCS,2025-01-30,4000,CE,50,50,10,10\n")
    out = parse_fo(date(2025, 1, 2), _zip(csv))
    assert sorted(out["type"]) == ["CE", "FUT"]
    assert out.loc[out.type == "CE", "strike"].iloc[0] == 24000


def test_implied_vol_recovers_the_input_volatility():
    for kind, k in (("call", 26000), ("put", 24000)):
        p = bs_price(25000, k, 30 / 365, 0.065, 0.18, kind)
        assert implied_vol(p, 25000, k, 30 / 365, 0.065, kind) == pytest.approx(0.18, abs=1e-6)


def test_implied_vol_is_nan_below_intrinsic_value():
    assert np.isnan(implied_vol(10.0, 25000, 24000, 30 / 365, 0.065, "call"))


def test_implied_forward_from_put_call_parity():
    f, r, t = 25100.0, 0.065, 30 / 365
    s = f * np.exp(-r * t)  # spot that makes the forward f with no dividends
    c = bs_price(s, 25000, t, r, 0.15, "call")
    p = bs_price(s, 25000, t, r, 0.15, "put")
    assert implied_forward(c, p, 25000, t, r) == pytest.approx(f)


def _chain(day, expiry, fwd, smile, r=0.065):
    t = (expiry - day).days / 365
    s = fwd * np.exp(-r * t)
    rows = [{"date": day, "expiry": expiry, "strike": np.nan, "type": "FUT", "price": fwd,
             "contracts": 100, "oi": 100}]
    for k in np.arange(fwd * 0.85, fwd * 1.15, fwd * 0.01):
        v = smile(k / fwd)
        for typ, kind in (("CE", "call"), ("PE", "put")):
            rows.append({"date": day, "expiry": expiry, "strike": round(k), "type": typ,
                         "price": bs_price(s, round(k), t, r, v, kind), "contracts": 10,
                         "oi": 10})
    return pd.DataFrame(rows)


def test_snapshot_smile_recovers_a_known_skew():
    from bsp.iv import snapshot_smile

    day, exp = pd.Timestamp("2021-03-01"), pd.Timestamp("2021-03-25")
    chain = _chain(day, exp, 15000.0, lambda m: 0.20 - 0.5 * (m - 1))  # steeper for low strikes
    summary, otm = snapshot_smile(chain, day)
    assert summary["forward"] == pytest.approx(15000.0, rel=1e-6)
    assert summary["iv95"] == pytest.approx(0.225, abs=1e-3)
    assert summary["iv105"] == pytest.approx(0.175, abs=1e-3)
    assert set(otm["type"]) == {"CE", "PE"}


def test_snapshot_smile_skips_a_chain_without_puts():
    from bsp.iv import snapshot_smile

    day, exp = pd.Timestamp("2021-03-01"), pd.Timestamp("2021-03-25")
    chain = _chain(day, exp, 15000.0, lambda m: 0.2)
    assert snapshot_smile(chain[chain.type != "PE"], day) is None


def test_snapshot_smile_prefers_the_liquid_monthly_over_a_thin_weekly():
    from bsp.iv import snapshot_smile

    day = pd.Timestamp("2022-08-01")
    monthly = _chain(day, pd.Timestamp("2022-08-25"), 17400.0, lambda m: 0.18)
    weekly = _chain(day, pd.Timestamp("2022-09-01"), 17450.0, lambda m: 0.30)
    weekly = weekly[weekly.type != "FUT"]  # weeklies have no futures contract
    weekly.loc[weekly.index[6:], "contracts"] = 0  # and only a few strikes trade
    summary, _ = snapshot_smile(pd.concat([monthly, weekly], ignore_index=True), day)
    assert summary["expiry"] == pd.Timestamp("2022-08-25")
    assert summary["iv100"] == pytest.approx(0.18, abs=1e-3)
