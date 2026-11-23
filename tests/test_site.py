import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bsp.bs import bs_price
from bsp.site import build_html

JS = Path(__file__).resolve().parents[1] / "src" / "bsp" / "pricer.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_browser_pricer_matches_python():
    cases = [(42, 40, 0.5, 0.10, 0.20, "call", 0.0),
             (25000, 26000, 30 / 365, 0.065, 0.15, "put", 0.01),
             (100, 100, 2.0, 0.05, 0.6, "call", 0.03), (110, 100, 0.0, 0.05, 0.2, "put", 0.0)]
    script = (f"const {{bsPrice}} = require({json.dumps(str(JS))});"
              f"console.log(JSON.stringify({json.dumps(cases)}.map(c => bsPrice(...c))));")
    js = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True,
                                   check=True).stdout)
    py = [bs_price(*c[:5], c[5], c[6]) for c in cases]
    assert np.allclose(js, py, atol=1e-5)


def test_build_html_has_calculator_and_loads_plotly_once():
    idx = pd.bdate_range("2018-01-01", periods=400)
    s = pd.Series(100 * np.exp(np.cumsum(np.random.default_rng(0).normal(0, 0.01, 400))), index=idx)
    html = build_html(pd.DataFrame({"S": s, "vix": 0.15}))
    assert 'id="calc"' in html and "function bsPrice" in html
    assert html.count('src="https://cdn.plot.ly') == 1
