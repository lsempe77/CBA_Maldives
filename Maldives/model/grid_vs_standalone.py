"""
Grid Extension vs Standalone Analysis
======================================
For each island, compare:
  - Cost of submarine cable to nearest larger island
  - Cost of standalone solar+battery microgrid

Decision rule: connect via cable only if cable cost < standalone cost.
This is standard electrification planning methodology (OnSSET/GEP).

All parameters loaded from parameters.csv via config.py.
"""

import pandas as pd
import math
import os

try:
    from .config import get_config
except ImportError:
    from model.config import get_config


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _load_defaults_from_config():
    """Load analysis defaults from the config system (parameters.csv)."""
    cfg = get_config()
    return {
        "cable_cost_per_km": cfg.technology.inter_island_capex_per_km / 1e6,  # $M/km
        "standalone_cost_per_mw": (
            cfg.technology.solar_pv_capex / 1000  # $/kW -> $M/MW (solar component)
            + cfg.technology.battery_capex * 4 / 1000  # 4h battery per MW
        ),
        "demand_per_capita_kw": (
            cfg.demand.base_demand_gwh * 1e6  # GWh -> kWh
            / cfg.current_system.population_2026  # per capita kWh
            / 8760  # -> avg kW
            / cfg.demand.load_factor  # -> peak kW
        ),
        "routing_premium": cfg.technology.routing_premium,
        "backbone_cost_per_km": cfg.technology.cable_capex_per_km / 1e6,  # $M/km (deep-water)
    }


def analyse_grid_vs_standalone(
    csv_path: str,
    cable_cost_per_km: float = None,
    standalone_cost_per_mw: float = None,
    demand_per_capita_kw: float = None,
    routing_premium: float = None,
):
    """
    For each island, find the nearest larger island and compare
    cable-extension cost vs standalone solar+battery cost.
    
    All defaults loaded from parameters.csv via config.py.
    Returns DataFrame with decision for each island.
    """
    defaults = _load_defaults_from_config()
    cable_cost_per_km = cable_cost_per_km if cable_cost_per_km is not None else defaults["cable_cost_per_km"]
    standalone_cost_per_mw = standalone_cost_per_mw if standalone_cost_per_mw is not None else defaults["standalone_cost_per_mw"]
    demand_per_capita_kw = demand_per_capita_kw if demand_per_capita_kw is not None else defaults["demand_per_capita_kw"]
    routing_premium = routing_premium if routing_premium is not None else defaults["routing_premium"]

    df = pd.read_csv(csv_path)
    
    rows = []
    for i, row in df.iterrows():
        # Find nearest island with LARGER population
        min_dist = 9999.0
        nearest = ""
        for j, other in df.iterrows():
            if other["Pop"] > row["Pop"]:
                d = haversine_km(row["Y_deg"], row["X_deg"],
                                 other["Y_deg"], other["X_deg"]) * routing_premium
                if d < min_dist:
                    min_dist = d
                    nearest = other["Island_Name"]
        
        # Male is the largest -- it has no "larger" island, set dist=0
        if nearest == "":
            nearest = "(hub)"
            min_dist = 0.0
        
        # Economics
        peak_mw = row["Pop"] * demand_per_capita_kw / 1000.0
        cable_cost_M = min_dist * cable_cost_per_km
        standalone_cost_M = peak_mw * standalone_cost_per_mw
        
        cost_per_cap_cable = int(cable_cost_M * 1e6 / row["Pop"]) if row["Pop"] > 0 else 0
        cost_per_cap_standalone = int(standalone_cost_M * 1e6 / row["Pop"]) if row["Pop"] > 0 else 0
        ratio = cable_cost_M / standalone_cost_M if standalone_cost_M > 0 else 999.0
        
        # Decision: cable justified only if cheaper than standalone
        if ratio < 1.0:
            decision = "CABLE"
        elif ratio < 3.0:
            decision = "MAYBE"
        else:
            decision = "STANDALONE"
        
        rows.append({
            "Island": row["Island_Name"],
            "Atoll": row["Atoll"],
            "Pop": row["Pop"],
            "Nearest_Larger": nearest,
            "Dist_km": round(min_dist, 1),
            "Cable_Cost_M": round(cable_cost_M, 1),
            "Standalone_M": round(standalone_cost_M, 1),
            "Cable_per_cap": cost_per_cap_cable,
            "Stand_per_cap": cost_per_cap_standalone,
            "Ratio": round(ratio, 1),
            "Decision": decision,
        })
    
    return pd.DataFrame(rows).sort_values("Ratio")


def print_report(result: pd.DataFrame):
    """Pretty-print the analysis results."""
    cfg = get_config()
    cable_cost = cfg.technology.inter_island_capex_per_km / 1e6
    solar_capex = cfg.technology.solar_pv_capex

    print("=" * 130)
    print("  GRID EXTENSION vs STANDALONE SOLAR+BATTERY ANALYSIS")
    print(f"  Cable cost: ${cable_cost:.1f}M/km | Solar CAPEX: ${solar_capex:,.0f}/kW")
    print("  Decision: CABLE if cable < standalone | MAYBE if < 3x | STANDALONE if >= 3x")
    print("=" * 130)
    
    header = (f"{'Island':>18s} {'Atoll':>12s} {'Pop':>8s} {'Nearest':>16s} "
              f"{'Dist':>6s} {'Cable$M':>8s} {'Stand$M':>8s} "
              f"{'Cable/cap':>10s} {'Stand/cap':>10s} {'Ratio':>6s} {'Decision':>11s}")
    print(header)
    print("-" * 130)
    
    for _, r in result.iterrows():
        line = (f"{r['Island']:>18s} {r['Atoll']:>12s} {r['Pop']:>8,d} {r['Nearest_Larger']:>16s} "
                f"{r['Dist_km']:>6.1f} {r['Cable_Cost_M']:>8.1f} {r['Standalone_M']:>8.1f} "
                f"{r['Cable_per_cap']:>10,d} {r['Stand_per_cap']:>10,d} {r['Ratio']:>6.1f} {r['Decision']:>11s}")
        print(line)
    
    # Summary
    cable = result[result["Decision"] == "CABLE"]
    maybe = result[result["Decision"] == "MAYBE"]
    standalone = result[result["Decision"] == "STANDALONE"]
    
    print()
    print("=" * 130)
    print("  SUMMARY")
    print("=" * 130)
    print(f"  CABLE (justified):     {len(cable):>3d} islands, pop {cable['Pop'].sum():>8,d} "
          f"({cable['Pop'].sum() / result['Pop'].sum() * 100:.1f}%)")
    print(f"  MAYBE (borderline):    {len(maybe):>3d} islands, pop {maybe['Pop'].sum():>8,d} "
          f"({maybe['Pop'].sum() / result['Pop'].sum() * 100:.1f}%)")
    print(f"  STANDALONE (solar):    {len(standalone):>3d} islands, pop {standalone['Pop'].sum():>8,d} "
          f"({standalone['Pop'].sum() / result['Pop'].sum() * 100:.1f}%)")
    
    print()
    print("  CABLE-justified islands:")
    for _, r in cable.sort_values("Pop", ascending=False).iterrows():
        print(f"    {r['Island']:>18s} ({r['Atoll']}) - {r['Pop']:>7,d} pop, "
              f"{r['Dist_km']:.1f} km to {r['Nearest_Larger']}, "
              f"cable ${r['Cable_Cost_M']:.1f}M vs standalone ${r['Standalone_M']:.1f}M")
    
    print()
    print("  MAYBE islands (case-by-case):")
    for _, r in maybe.sort_values("Pop", ascending=False).iterrows():
        print(f"    {r['Island']:>18s} ({r['Atoll']}) - {r['Pop']:>7,d} pop, "
              f"{r['Dist_km']:.1f} km to {r['Nearest_Larger']}, "
              f"cable ${r['Cable_Cost_M']:.1f}M vs standalone ${r['Standalone_M']:.1f}M "
              f"(ratio {r['Ratio']:.1f}x)")
    
    print()
    total_cable_km = cable["Dist_km"].sum() + maybe["Dist_km"].sum()
    total_cable_cost = cable["Cable_Cost_M"].sum() + maybe["Cable_Cost_M"].sum()
    print(f"  If connecting CABLE + MAYBE islands: {total_cable_km:.0f} km, ${total_cable_cost:.0f}M")
    cable_only_km = cable["Dist_km"].sum()
    cable_only_cost = cable["Cable_Cost_M"].sum()
    print(f"  If connecting CABLE only:            {cable_only_km:.0f} km, ${cable_only_cost:.0f}M")


def analyse_atoll_backbone(csv_path: str,
                           backbone_cost_per_km: float = None,
                           standalone_cost_per_mw: float = None,
                           demand_per_capita_kw: float = None,
                           routing_premium: float = None):
    """
    Atoll-level analysis: is it worth connecting each atoll to the
    national backbone (deep-water cable to Male), or should the whole
    atoll run on standalone solar+battery?
    
    All defaults loaded from parameters.csv via config.py.
    """
    defaults = _load_defaults_from_config()
    backbone_cost_per_km = backbone_cost_per_km if backbone_cost_per_km is not None else defaults["backbone_cost_per_km"]
    standalone_cost_per_mw = standalone_cost_per_mw if standalone_cost_per_mw is not None else defaults["standalone_cost_per_mw"]
    demand_per_capita_kw = demand_per_capita_kw if demand_per_capita_kw is not None else defaults["demand_per_capita_kw"]
    routing_premium = routing_premium if routing_premium is not None else defaults["routing_premium"]

    df = pd.read_csv(csv_path)
    male = df[df["Island_Name"] == "Male"].iloc[0] if "Male" in df["Island_Name"].values else df[df["Island_Name"] == "Maale"].iloc[0]
    
    rows = []
    for atoll in sorted(df["Atoll"].unique()):
        sub = df[df["Atoll"] == atoll]
        pop = sub["Pop"].sum()
        peak_mw = pop * demand_per_capita_kw / 1000.0
        centroid_lat = sub["Y_deg"].mean()
        centroid_lon = sub["X_deg"].mean()
        dist = haversine_km(centroid_lat, centroid_lon,
                            male["Y_deg"], male["X_deg"]) * routing_premium
        
        cable_cost = dist * backbone_cost_per_km  # deep-water
        standalone_cost = peak_mw * standalone_cost_per_mw
        ratio = cable_cost / standalone_cost if standalone_cost > 0 else 999.0
        
        if atoll in ("Kaafu", "Male"):
            verdict = "HUB"  # Male is the hub
        elif ratio < 1.0:
            verdict = "BACKBONE"
        elif ratio < 5.0:
            verdict = "MAYBE"
        else:
            verdict = "STANDALONE"
        
        rows.append({
            "Atoll": atoll, "Pop": pop, "Islands": len(sub),
            "Peak_MW": round(peak_mw, 1),
            "Dist_Male_km": round(dist, 0),
            "Backbone_M": round(cable_cost, 0),
            "Standalone_M": round(standalone_cost, 0),
            "Ratio": round(ratio, 1),
            "Verdict": verdict,
        })
    
    adf = pd.DataFrame(rows).sort_values("Dist_Male_km")
    
    cfg = get_config()
    backbone_cost_display = cfg.technology.cable_capex_per_km / 1e6
    solar_capex_display = cfg.technology.solar_pv_capex

    print()
    print("=" * 110)
    print("  ATOLL-LEVEL BACKBONE ANALYSIS")
    print("  Question: Is it worth connecting each atoll to the national backbone via deep-water cable?")
    print(f"  Backbone cable: ${backbone_cost_display:.1f}M/km | Solar CAPEX: ${solar_capex_display:,.0f}/kW")
    print("=" * 110)
    
    header = (f"{'Atoll':>14s} {'Pop':>8s} {'Isl':>4s} {'MW':>5s} "
              f"{'Dist km':>8s} {'Backbone$M':>11s} {'Standalone$M':>13s} "
              f"{'Ratio':>6s} {'Verdict':>12s}")
    print(header)
    print("-" * 110)
    
    for _, r in adf.iterrows():
        line = (f"{r['Atoll']:>14s} {r['Pop']:>8,d} {r['Islands']:>4d} {r['Peak_MW']:>5.1f} "
                f"{r['Dist_Male_km']:>8.0f} {r['Backbone_M']:>11,.0f} {r['Standalone_M']:>13,.0f} "
                f"{r['Ratio']:>6.1f} {r['Verdict']:>12s}")
        print(line)
    
    print()
    hub = adf[adf["Verdict"] == "HUB"]
    backbone = adf[adf["Verdict"] == "BACKBONE"]
    maybe = adf[adf["Verdict"] == "MAYBE"]
    standalone = adf[adf["Verdict"] == "STANDALONE"]
    
    print(f"  HUB (Male):         {hub['Pop'].sum():>8,d} pop ({hub['Pop'].sum()/adf['Pop'].sum()*100:.0f}%)")
    print(f"  BACKBONE-worthy:    {backbone['Pop'].sum():>8,d} pop ({backbone['Pop'].sum()/adf['Pop'].sum()*100:.0f}%)")
    print(f"  MAYBE:              {maybe['Pop'].sum():>8,d} pop ({maybe['Pop'].sum()/adf['Pop'].sum()*100:.0f}%)")
    print(f"  STANDALONE (solar): {standalone['Pop'].sum():>8,d} pop ({standalone['Pop'].sum()/adf['Pop'].sum()*100:.0f}%)")
    
    print()
    print("  IMPLICATION: Most atolls outside the Greater Male area are better")
    print("  served by standalone solar+battery than by a deep-water backbone cable.")
    print("  The India submarine cable benefits primarily Kaafu (Male region).")
    
    return adf


if __name__ == "__main__":
    csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "islands_master.csv")
    
    # Part 1: Island-level grid extension analysis
    result = analyse_grid_vs_standalone(csv_path)
    print_report(result)
    
    # Part 2: Atoll-level backbone analysis
    atoll_result = analyse_atoll_backbone(csv_path)
