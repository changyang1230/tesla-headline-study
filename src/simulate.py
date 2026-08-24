"""Generate a synthetic dataset matching the analysis schema.

Purpose: let `analysis.py` be written, run and debugged BEFORE any real data exist, so
that the analysis is genuinely pre-specified rather than shaped by what the real data
happen to look like. This is the mechanism that makes Protocol section 9.9 enforceable.

The generative model here is a guess. Nothing about it should be read as a prediction —
its only job is to exercise every code path in the analysis.

Usage:
    python -m src.simulate --out data/simulated.csv --seed 1 --tesla-or 4.0
"""

from __future__ import annotations

import argparse
import numpy as np
import pandas as pd

MAKE_POOL = {
    "Tesla": "tesla",
    "BYD": "other_bev", "Polestar": "other_bev",
    "BMW": "premium_ice", "Mercedes-Benz": "premium_ice", "Audi": "premium_ice",
    "Land Rover": "premium_ice",
    "Toyota": "mainstream_ice", "Mazda": "mainstream_ice", "Hyundai": "mainstream_ice",
    "Ford": "mainstream_ice", "Holden": "mainstream_ice", "Kia": "mainstream_ice",
    "Mitsubishi": "mainstream_ice", "Nissan": "mainstream_ice",
}
NON_TESLA = [m for m in MAKE_POOL if m != "Tesla"]
OUTLET_GROUPS = ["News Corp", "Nine", "Seven West", "ABC", "Guardian", "ACM", "SBS"]
REGISTERS = {"News Corp": "tabloid", "Nine": "broadsheet", "Seven West": "broadcast",
             "ABC": "public", "Guardian": "broadsheet", "ACM": "tabloid", "SBS": "public"}
TYPES = ["occupant_fatal_collision", "pedestrian_cyclist_struck",
         "single_vehicle_fire", "occupant_serious_collision"]


def simulate(n_tesla: int = 28, n_other: int = 130, seed: int = 1,
             *, tesla_log_or: float = np.log(4.0),
             bev_log_or: float = np.log(1.8), premium_log_or: float = np.log(2.2),
             incident_sd: float = 1.8, mean_articles: float = 8.0,
             p_multi_vehicle: float = 0.45) -> pd.DataFrame:
    """Two-level generative model mirroring the analysis structure.

    Incident-level random intercept produces the high ICC the power calculation assumes:
    whether the make is "the story" is mostly decided at the incident level and copied
    across outlets.
    """
    rng = np.random.default_rng(seed)
    rows = []

    makes = ["Tesla"] * n_tesla + list(rng.choice(NON_TESLA, size=n_other))
    for k, make in enumerate(makes):
        group = MAKE_POOL[make]
        inc = f"I{k:04d}"
        deaths = int(rng.choice([0, 1, 2], p=[0.25, 0.55, 0.20]))
        itype = str(rng.choice(TYPES, p=[0.45, 0.25, 0.10, 0.20]))
        child = int(rng.random() < 0.12)
        year = int(rng.integers(2021, 2026))
        age_band = str(rng.choice(["<=2y", "3-7y", ">=8y", "unknown"],
                                  p=[0.45, 0.25, 0.15, 0.15] if make == "Tesla"
                                  else [0.15, 0.30, 0.40, 0.15]))
        remoteness = str(rng.choice(["metro", "regional", "remote"],
                                    p=[0.75, 0.22, 0.03] if make == "Tesla"
                                    else [0.50, 0.40, 0.10]))
        multi = int(rng.random() < p_multi_vehicle)
        second = str(rng.choice(NON_TESLA)) if multi else ""
        fire = int(rng.random() < (0.20 if make == "Tesla" else 0.10))
        adas = int(rng.random() < (0.30 if make == "Tesla" else 0.02))
        tier = int(rng.choice([1, 2], p=[0.55, 0.45]))

        # incident-level propensity for the make to be "the story"
        eta = (-2.6
               + (tesla_log_or if group == "tesla" else 0.0)
               + (bev_log_or if group == "other_bev" else 0.0)
               + (premium_log_or if group == "premium_ice" else 0.0)
               + 0.35 * deaths + 0.5 * child
               + (0.45 if age_band == "<=2y" else 0.0)
               + (0.6 if fire else 0.0) + (0.9 if adas else 0.0)
               + rng.normal(0, incident_sd))

        n_art = max(3, int(rng.poisson(mean_articles)))
        groups = list(rng.choice(OUTLET_GROUPS, size=min(n_art, len(OUTLET_GROUPS)), replace=False))
        while len(groups) < n_art:
            groups.append(str(rng.choice(OUTLET_GROUPS)))
        wire_group = f"W{k:04d}" if rng.random() < 0.35 else ""

        for a, og in enumerate(groups):
            reg = REGISTERS[og]
            eta_a = eta + (0.35 if reg == "tabloid" else 0.0) + rng.normal(0, 0.4)
            p_head = 1 / (1 + np.exp(-eta_a))
            head = int(rng.random() < p_head)
            # body mentions the make far more often than the headline, and — the point of
            # the negative control — with a much weaker brand gradient
            p_body = 1 / (1 + np.exp(-(eta_a + 2.2 - 0.6 * (group == "tesla"))))
            body = int(head or rng.random() < p_body)
            rows.append(dict(
                article_id=f"{inc}A{a:02d}", incident_id=inc,
                outlet_group=og, outlet_register=reg,
                is_wire=int(bool(wire_group) and a < 2),
                syndication_group_id=wire_group if a < 2 else "",
                incident_date=f"{year}-0{rng.integers(1,10)}-1{rng.integers(0,9)}",
                year=year, deaths=deaths, victim_child=child, incident_type=itype,
                remoteness=remoteness, multi_vehicle=multi, fire_involved=fire,
                adas_alleged=adas, index_make=make, make_group=group,
                second_make=second, make_tier=tier, vehicle_age_band=age_band,
                tesla=int(make == "Tesla"),
                headline_names_make=head,
                headline_names_make_strict=int(head and rng.random() < 0.85),
                headline_names_second_make=int(
                    bool(second) and rng.random() < 1 / (1 + np.exp(-(eta_a - 1.4)))),
                body_names_make=body,
            ))
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="data/simulated.csv")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--n-tesla", type=int, default=28)
    ap.add_argument("--n-other", type=int, default=130)
    ap.add_argument("--tesla-or", type=float, default=4.0,
                    help="true Tesla odds ratio; set to 1.0 for a null dataset")
    args = ap.parse_args()

    df = simulate(args.n_tesla, args.n_other, args.seed, tesla_log_or=float(np.log(args.tesla_or)))
    df.to_csv(args.out, index=False)
    print(f"wrote {args.out}: {len(df)} articles across {df.incident_id.nunique()} incidents "
          f"({df.groupby('incident_id').tesla.first().sum()} Tesla)")
    print(df.groupby("make_group").headline_names_make.agg(["mean", "size"]).round(3))


if __name__ == "__main__":
    main()
