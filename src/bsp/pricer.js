// Black-Scholes in the browser. Mirrors bsp/bs.py; tests compare the two through Node.
function normCdf(x) {
  // Abramowitz & Stegun 7.1.26 erf approximation (max error about 1.5e-7)
  const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741, a4 = -1.453152027, a5 = 1.061405429;
  const p = 0.3275911, sign = x < 0 ? -1 : 1, z = Math.abs(x) / Math.SQRT2;
  const t = 1 / (1 + p * z);
  const erf = 1 - ((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * Math.exp(-z * z);
  return 0.5 * (1 + sign * erf);
}

function bsPrice(s, k, t, r, sigma, kind, q = 0) {
  const sign = kind === "call" ? 1 : -1;
  if (!(t > 0) || !(sigma > 0)) {
    const fwd = s * Math.exp(-q * Math.max(t, 0)) - k * Math.exp(-r * Math.max(t, 0));
    return Math.max(sign * fwd, 0);
  }
  const vt = sigma * Math.sqrt(t);
  const d1 = (Math.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / vt;
  const d2 = d1 - vt;
  return sign * (s * Math.exp(-q * t) * normCdf(sign * d1) - k * Math.exp(-r * t) * normCdf(sign * d2));
}

if (typeof module !== "undefined") module.exports = { normCdf, bsPrice };
