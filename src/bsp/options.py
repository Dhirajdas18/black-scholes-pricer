"""NIFTY index options and futures from NSE's daily F&O bhavcopy (nsearchives.nseindia.com).

Each day's file lists every derivative contract. Only NIFTY index options (OPTIDX / IDO) and
futures (FUTIDX / IDF) are kept. Options use the closing price (the last trades); futures use the
settlement price. The data is downloaded to data/options/ and never committed.
"""

import io
import time
import urllib.request
import zipfile
from datetime import date

import pandas as pd

BASE = "https://nsearchives.nseindia.com"
UDIFF_START = date(2024, 7, 8)  # NSE switched bhavcopy formats on this date
UA = "black-scholes-pricer/0.1 (research)"


def url_fo(d: date) -> str:
    if d >= UDIFF_START:
        return f"{BASE}/content/fo/BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
    mon = d.strftime("%b").upper()
    return f"{BASE}/content/historical/DERIVATIVES/{d:%Y}/{mon}/fo{d:%d}{mon}{d:%Y}bhav.csv.zip"


def fetch(d: date, retries: int = 3, pause: float = 1.0) -> bytes | None:
    """The day's zipped bhavcopy, or None if NSE has no file (holiday) after a few tries."""
    req = urllib.request.Request(url_fo(d), headers={"User-Agent": UA})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
            return raw if raw.startswith(b"PK") else None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(pause * (attempt + 1))
    return None


def parse_fo(d: date, raw: bytes, symbol: str = "NIFTY") -> pd.DataFrame | None:
    """Index options and futures for `symbol`: date, expiry, strike, type, price, contracts, oi."""
    if not raw or not raw.startswith(b"PK"):
        return None
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        df = pd.read_csv(z.open(z.namelist()[0]), low_memory=False)
    df.columns = df.columns.str.strip()
    if "FinInstrmTp" in df.columns:
        kind = df["FinInstrmTp"].astype(str).str.strip()
        n = pd.DataFrame({
            "symbol": df["TckrSymb"], "kind": kind.map({"IDO": "opt", "IDF": "fut"}),
            "expiry": pd.to_datetime(df["XpryDt"], format="%Y-%m-%d"),
            "strike": df["StrkPric"], "opt": df["OptnTp"], "close": df["ClsPric"],
            "settle": df["SttlmPric"], "contracts": df["TtlTradgVol"], "oi": df["OpnIntrst"]})
    else:
        kind = df["INSTRUMENT"].astype(str).str.strip()
        n = pd.DataFrame({
            "symbol": df["SYMBOL"], "kind": kind.map({"OPTIDX": "opt", "FUTIDX": "fut"}),
            "expiry": pd.to_datetime(df["EXPIRY_DT"].astype(str).str.strip(), format="%d-%b-%Y"),
            "strike": df["STRIKE_PR"], "opt": df["OPTION_TYP"], "close": df["CLOSE"],
            "settle": df["SETTLE_PR"], "contracts": df["CONTRACTS"], "oi": df["OPEN_INT"]})
    n = n[n["kind"].notna() & (n["symbol"].astype(str).str.strip() == symbol)].copy()
    for c in ("strike", "close", "settle", "contracts", "oi"):
        n[c] = pd.to_numeric(n[c], errors="coerce")
    n["type"] = n["opt"].astype(str).str.strip().where(n["kind"] == "opt", "FUT")
    n["price"] = n["close"].where(n["kind"] == "opt", n["settle"])
    n["date"] = pd.Timestamp(d)
    cols = ["date", "expiry", "strike", "type", "price", "contracts", "oi"]
    return n[cols].reset_index(drop=True)
