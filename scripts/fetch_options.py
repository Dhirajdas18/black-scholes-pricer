"""Download NIFTY option snapshots (first trading day of each month) into data/options/.

NSE's archive has one F&O bhavcopy per trading day; only the NIFTY rows are kept. Re-running skips
months already downloaded.
"""

import sys
import time
from pathlib import Path

import pandas as pd

from bsp.data import INDEX, load
from bsp.options import fetch, parse_fo

OUT = Path("data/options/nifty_options.parquet")


def main(start: str = "2015-01-01") -> None:
    days = load("adj_close", [INDEX]).index
    days = days[days >= start]
    firsts = pd.Series(days, index=days).groupby([days.year, days.month]).first()
    have = pd.read_parquet(OUT) if OUT.exists() else pd.DataFrame(columns=["date"])
    done = set(pd.to_datetime(have["date"]).dt.normalize())
    frames = [have] if len(have) else []
    for i, d in enumerate(firsts):
        if d in done:
            continue
        raw = fetch(d.date())
        rows = parse_fo(d.date(), raw) if raw else None
        status = "no file" if rows is None else f"{len(rows)} rows"
        print(f"[{i + 1}/{len(firsts)}] {d:%Y-%m-%d}: {status}", flush=True)
        if rows is not None and len(rows):
            frames.append(rows)
        time.sleep(1.0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(frames, ignore_index=True).to_parquet(OUT)
    print(f"-> {OUT}")


if __name__ == "__main__":
    main(*sys.argv[1:])
