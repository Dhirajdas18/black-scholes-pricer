"""Command line: `bsp report <topic>` or `bsp price --spot 100 --strike 105 --days 30 --vol 0.2`."""

import argparse
from pathlib import Path

OUT = Path("out")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bsp", description="Black-Scholes pricing on NSE data")
    sub = parser.add_subparsers(dest="cmd", required=True)
    rep = sub.add_parser("report", help="build a topic's charts and print its numbers")
    rep.add_argument("topic")
    pr = sub.add_parser("price", help="price a European option")
    pr.add_argument("--spot", type=float, required=True)
    pr.add_argument("--strike", type=float, required=True)
    pr.add_argument("--days", type=float, required=True, help="calendar days to expiry")
    pr.add_argument("--vol", type=float, required=True, help="annual volatility, e.g. 0.18")
    pr.add_argument("--rate", type=float, default=0.065)
    pr.add_argument("--div", type=float, default=0.0, help="dividend yield")
    args = parser.parse_args(argv)

    if args.cmd == "report":
        from bsp import plots, reports

        if args.topic not in reports.REPORTS:
            parser.error(f"unknown topic {args.topic!r}; topics: {', '.join(reports.REPORTS)}")
        plots.style()
        for key, value in reports.REPORTS[args.topic](OUT).items():
            print(f"{key}: {value}")
        print(f"charts -> {OUT.resolve()}")
        return 0

    from bsp.bs import bs_price

    t = args.days / 365
    for kind in ("call", "put"):
        p = bs_price(args.spot, args.strike, t, args.rate, args.vol, kind, args.div)
        print(f"{kind}: {p:,.2f}")
    return 0
