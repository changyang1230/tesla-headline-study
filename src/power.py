"""Sample size for the clustered two-proportion comparison (Protocol section 10).

Standard library only, so it runs anywhere, including before the analysis environment
exists.

The fragile assumption is the intracluster correlation. Whether the make is "the story"
is largely an incident-level property that outlets copy from one another, so rho is
expected to be high — and high rho is expensive. The grid below shows how expensive.
Phase 0 estimates rho from real data and the target is revised BEFORE any outcome
comparison is run.

Usage:
    python -m src.power
    python -m src.power --p0 0.10 --p1 0.35 --m 8 --rho 0.5
"""

from __future__ import annotations

import argparse
import math

#: Two-sided normal quantiles, hard-coded so the module needs no scipy.
_Z = {0.80: 0.8416212336, 0.90: 1.2815515655, 0.95: 1.6448536270, 0.975: 1.9599639845}


def z(p: float) -> float:
    if p in _Z:
        return _Z[p]
    # Acklam's inverse-normal approximation; accurate to ~1e-9 over (0,1).
    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00)
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > ph:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q, r = p - 0.5, (p - 0.5) ** 2
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def design_effect(m: float, rho: float) -> float:
    """DEFF = 1 + (m - 1) * rho for equal cluster sizes m."""
    return 1.0 + (m - 1.0) * rho


def n_per_arm_unclustered(p0: float, p1: float, alpha: float = 0.05, power: float = 0.80) -> float:
    """Articles per arm for a two-sided two-proportion z-test, ignoring clustering."""
    if p0 == p1:
        raise ValueError("p0 and p1 must differ")
    pbar = (p0 + p1) / 2
    za, zb = z(1 - alpha / 2), z(power)
    num = (za * math.sqrt(2 * pbar * (1 - pbar))
           + zb * math.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2
    return num / (p1 - p0) ** 2


def requirement(p0: float, p1: float, m: float, rho: float,
                alpha: float = 0.05, power: float = 0.80) -> dict[str, float]:
    n_plain = n_per_arm_unclustered(p0, p1, alpha, power)
    deff = design_effect(m, rho)
    n_articles = n_plain * deff
    n_clusters = math.ceil(n_articles / m)
    odds = lambda p: p / (1 - p)
    return {
        "p0": p0, "p1": p1, "m": m, "rho": rho, "alpha": alpha, "power": power,
        "or_target": odds(p1) / odds(p0),
        "articles_per_arm_unclustered": n_plain,
        "design_effect": deff,
        "articles_per_arm": n_articles,
        "incidents_per_arm": n_clusters,
        "total_incidents": 2 * n_clusters,
    }


def detectable_p1(p0: float, n_clusters: int, m: float, rho: float,
                  alpha: float = 0.05, power: float = 0.80, tol: float = 1e-5) -> float:
    """Smallest Tesla rate detectable with `n_clusters` incidents per arm.

    The question actually worth asking when the exposed arm is small and fixed by how
    many Tesla incidents Australia produced.
    """
    lo, hi = p0 + tol, 0.999
    for _ in range(200):
        mid = (lo + hi) / 2
        need = requirement(p0, mid, m, rho, alpha, power)["incidents_per_arm"]
        if need > n_clusters:
            lo = mid
        else:
            hi = mid
    return hi


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--p0", type=float, default=0.10, help="non-Tesla headline naming rate")
    ap.add_argument("--p1", type=float, default=0.35, help="Tesla headline naming rate")
    ap.add_argument("--m", type=float, default=8.0, help="mean articles per incident")
    ap.add_argument("--rho", type=float, default=0.5, help="intracluster correlation")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--power", type=float, default=0.80)
    args = ap.parse_args()

    r = requirement(args.p0, args.p1, args.m, args.rho, args.alpha, args.power)
    print("Primary sample size (Protocol section 10)")
    print("-" * 64)
    print(f"  non-Tesla rate p0            {r['p0']:.3f}")
    print(f"  Tesla rate p1                {r['p1']:.3f}   (OR {r['or_target']:.2f})")
    print(f"  mean articles per incident   {r['m']:.1f}")
    print(f"  ICC rho                      {r['rho']:.2f}")
    print(f"  alpha {r['alpha']:.2f} two-sided, power {r['power']:.0%}")
    print()
    print(f"  articles/arm ignoring clustering   {r['articles_per_arm_unclustered']:8.1f}")
    print(f"  design effect                      {r['design_effect']:8.2f}")
    print(f"  articles/arm after clustering      {r['articles_per_arm']:8.1f}")
    print(f"  INCIDENTS PER ARM                  {r['incidents_per_arm']:8.0f}")
    print()

    print("Sensitivity to the ICC (incidents needed in the Tesla arm)")
    print("-" * 64)
    print("  rho :   " + "".join(f"{x:>8.2f}" for x in (0.1, 0.2, 0.3, 0.5, 0.7, 0.9)))
    for m in (4, 6, 8, 12):
        cells = "".join(
            f"{requirement(args.p0, args.p1, m, rho, args.alpha, args.power)['incidents_per_arm']:>8.0f}"
            for rho in (0.1, 0.2, 0.3, 0.5, 0.7, 0.9))
        print(f"  m={m:<3}:  {cells}")
    print()

    print("What is detectable if the Tesla arm is capped by reality")
    print("-" * 64)
    print(f"  (p0={args.p0:.2f}, m={args.m:.0f}, rho={args.rho:.2f}, power {args.power:.0%})")
    for k in (10, 15, 20, 25, 30, 40, 60):
        p1 = detectable_p1(args.p0, k, args.m, args.rho, args.alpha, args.power)
        or_ = (p1 / (1 - p1)) / (args.p0 / (1 - args.p0))
        print(f"  {k:>3} Tesla incidents -> detectable rate {p1:6.1%}  (OR {or_:5.2f})")
    print()
    print("Read the last table before Phase 1. If Australia only produced 15 eligible")
    print("Tesla incidents in the window, the study can only detect a very large effect,")
    print("and that is the moment to invoke a Protocol section 10.4 fallback — not after")
    print("the analysis returns p = 0.31.")


if __name__ == "__main__":
    main()
