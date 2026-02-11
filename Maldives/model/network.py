"""
Inter-Island Network Module
============================

Computes inter-island distance matrix, Minimum Spanning Trees (MST),
and cable infrastructure costs for the Maldives energy CBA model.

Architecture:
    1. Load island master data (coordinates, atoll, population, area)
       Source: islands_master.csv (176 inhabited islands from GDB + Census P5 2022)
    2. Compute haversine distance matrix (all pairs)
    3. Apply routing premium (1.15× for reef avoidance)
    4. Build MST per atoll (intra-atoll mini-grid cables)
    5. Build MST across atoll centroids (national grid backbone)
    6. Estimate cable CAPEX from distances × cost per km

Usage:
    # As module
    from model.network import IslandNetwork
    net = IslandNetwork.from_csv("data/islands_master.csv")
    print(net.summary())

    # Standalone
    python -m model.network
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EARTH_RADIUS_KM = 6371.0


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance between two points on Earth in kilometres.
    Inputs in decimal degrees.
    """
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def compute_distance_matrix(
    lats: np.ndarray,
    lons: np.ndarray,
    routing_premium: float = 1.0,
) -> np.ndarray:
    """
    Compute pairwise haversine distance matrix (km) with routing premium.

    Parameters
    ----------
    lats : array of latitudes (decimal degrees)
    lons : array of longitudes (decimal degrees)
    routing_premium : multiplicative factor for reef/bathymetry routing
                      (1.15 = 15% longer than straight-line)

    Returns
    -------
    dist_matrix : (n, n) symmetric numpy array of routed distances in km
    """
    n = len(lats)
    dist = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d = haversine_km(lats[i], lons[i], lats[j], lons[j])
            dist[i, j] = d
            dist[j, i] = d
    return dist * routing_premium


def prim_mst(dist_matrix: np.ndarray, indices: list[int]) -> list[tuple[int, int, float]]:
    """
    Compute Minimum Spanning Tree using Prim's algorithm.

    LW-08: Naive O(V³) implementation. For 183 islands this runs in <1s,
    acceptable for one-shot analysis. If performance becomes a concern,
    replace with scipy.sparse.csgraph.minimum_spanning_tree (O(E log V)).

    Parameters
    ----------
    dist_matrix : full (n, n) distance matrix
    indices : subset of node indices to include in MST

    Returns
    -------
    edges : list of (i, j, distance_km) tuples forming the MST
    """
    if len(indices) <= 1:
        return []

    # Work with subset
    in_tree = {indices[0]}
    edges = []

    while len(in_tree) < len(indices):
        best_edge = None
        best_dist = float("inf")

        for u in in_tree:
            for v in indices:
                if v not in in_tree and dist_matrix[u, v] < best_dist:
                    best_dist = dist_matrix[u, v]
                    best_edge = (u, v, best_dist)

        if best_edge is None:
            break  # disconnected (shouldn't happen for complete graph)

        edges.append(best_edge)
        in_tree.add(best_edge[1])

    return edges


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MSTResult:
    """Result of a Minimum Spanning Tree computation."""
    name: str
    edges: list[tuple[str, str, float]]  # (island_a, island_b, distance_km)
    total_length_km: float
    n_nodes: int
    n_edges: int

    def __str__(self) -> str:
        lines = [f"MST: {self.name} ({self.n_nodes} nodes, {self.total_length_km:.1f} km total)"]
        for a, b, d in sorted(self.edges, key=lambda x: x[2]):
            lines.append(f"  {a:>20s} -- {b:<20s}  {d:6.1f} km")
        return "\n".join(lines)


@dataclass
class NetworkSummary:
    """Summary of all network computations."""
    n_islands: int
    n_atolls: int
    total_population: int
    atoll_msts: list[MSTResult]
    backbone_mst: MSTResult
    total_intra_atoll_km: float
    total_backbone_km: float
    total_network_km: float
    routing_premium: float

    # Cable cost estimates
    intra_atoll_capex_musd: float = 0.0
    backbone_capex_musd: float = 0.0
    total_capex_musd: float = 0.0

    def __str__(self) -> str:
        lines = [
            "=" * 70,
            "  MALDIVES INTER-ISLAND NETWORK ANALYSIS",
            "=" * 70,
            f"  Islands: {self.n_islands}  |  Atolls: {self.n_atolls}  |  "
            f"Population: {self.total_population:,}",
            f"  Routing premium: {self.routing_premium:.0%} (reef/bathymetry avoidance)",
            "",
            "-" * 70,
            "  INTRA-ATOLL CABLE NETWORKS (MST per atoll)",
            "-" * 70,
        ]
        for mst in sorted(self.atoll_msts, key=lambda m: m.total_length_km, reverse=True):
            lines.append(f"  {mst.name:<20s}  {mst.n_nodes:>2d} islands  "
                         f"{mst.total_length_km:>7.1f} km")

        lines.extend([
            f"  {'TOTAL INTRA-ATOLL':<20s}  {sum(m.n_nodes for m in self.atoll_msts):>2d} islands  "
            f"{self.total_intra_atoll_km:>7.1f} km",
            "",
            "-" * 70,
            "  INTER-ATOLL BACKBONE (MST across atoll centroids)",
            "-" * 70,
        ])
        for a, b, d in sorted(self.backbone_mst.edges, key=lambda x: x[2]):
            lines.append(f"  {a:>20s} -- {b:<20s}  {d:6.1f} km")
        lines.append(f"  {'TOTAL BACKBONE':<20s}  {self.backbone_mst.n_nodes:>2d} atolls  "
                     f"{self.total_backbone_km:>7.1f} km")

        lines.extend([
            "",
            "-" * 70,
            "  TOTAL NETWORK",
            "-" * 70,
            f"  Intra-atoll:       {self.total_intra_atoll_km:>8.1f} km",
            f"  Inter-atoll:       {self.total_backbone_km:>8.1f} km",
            f"  TOTAL:             {self.total_network_km:>8.1f} km",
        ])

        if self.total_capex_musd > 0:
            lines.extend([
                "",
                "-" * 70,
                "  ESTIMATED CABLE CAPEX",
                "-" * 70,
                f"  Intra-atoll (shallow): ${self.intra_atoll_capex_musd:>8.1f}M",
                f"  Inter-atoll (deep):    ${self.backbone_capex_musd:>8.1f}M",
                f"  TOTAL:                 ${self.total_capex_musd:>8.1f}M",
            ])

        lines.append("=" * 70)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class IslandNetwork:
    """
    Manages the inter-island network model for the Maldives.

    Loads island data, computes distances, builds MSTs,
    and estimates cable infrastructure costs.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        routing_premium: float = None,
        intra_atoll_capex_per_km_usd: float = None,
        inter_atoll_capex_per_km_usd: float = None,
    ):
        """
        Parameters
        ----------
        df : DataFrame with columns: Island_Name, Atoll, Pop, X_deg, Y_deg
        routing_premium : multiplier on straight-line distance for cable routing
            If None, loaded from get_config().technology.routing_premium
        intra_atoll_capex_per_km_usd : cable cost for shallow intra-atoll links
            If None, loaded from get_config().technology.inter_island_capex_per_km
        inter_atoll_capex_per_km_usd : cable cost for deeper inter-atoll links
            If None, loaded from get_config().technology.cable_capex_per_km
        """
        # S-14 fix: load from config if not explicitly provided (no hardcoded defaults)
        if routing_premium is None or intra_atoll_capex_per_km_usd is None or inter_atoll_capex_per_km_usd is None:
            try:
                from .config import get_config
            except ImportError:
                from model.config import get_config
            cfg = get_config()
            if routing_premium is None:
                routing_premium = cfg.technology.routing_premium
            if intra_atoll_capex_per_km_usd is None:
                intra_atoll_capex_per_km_usd = cfg.technology.inter_island_capex_per_km
            if inter_atoll_capex_per_km_usd is None:
                inter_atoll_capex_per_km_usd = cfg.technology.cable_capex_per_km

        self.df = df.copy()
        self.routing_premium = routing_premium
        self.intra_atoll_capex_per_km = intra_atoll_capex_per_km_usd
        self.inter_atoll_capex_per_km = inter_atoll_capex_per_km_usd

        # Validate required columns
        required = {"Island_Name", "Atoll", "Pop", "X_deg", "Y_deg"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns in GIS data: {missing}")

        # Compute distance matrix
        self.lats = self.df["Y_deg"].values
        self.lons = self.df["X_deg"].values
        self.names = self.df["Island_Name"].values
        self.atolls = self.df["Atoll"].values
        self.pops = self.df["Pop"].values

        self.dist_matrix = compute_distance_matrix(
            self.lats, self.lons, routing_premium=self.routing_premium
        )

        # Atoll groupings
        self.atoll_groups: dict[str, list[int]] = {}
        for i, atoll in enumerate(self.atolls):
            self.atoll_groups.setdefault(atoll, []).append(i)

        # Computed results (lazy)
        self._atoll_msts: Optional[dict[str, MSTResult]] = None
        self._backbone_mst: Optional[MSTResult] = None

    @classmethod
    def from_csv(
        cls,
        csv_path: str | Path,
        routing_premium: float = None,
        intra_atoll_capex_per_km_usd: float = None,
        inter_atoll_capex_per_km_usd: float = None,
    ) -> "IslandNetwork":
        """Load from GIS CSV file."""
        df = pd.read_csv(csv_path)
        return cls(
            df,
            routing_premium=routing_premium,
            intra_atoll_capex_per_km_usd=intra_atoll_capex_per_km_usd,
            inter_atoll_capex_per_km_usd=inter_atoll_capex_per_km_usd,
        )

    @classmethod
    def from_config(cls, config=None) -> "IslandNetwork":
        """
        Load from a Config object (or get_config() if None).
        Uses network parameters from config.
        """
        from pathlib import Path

        if config is None:
            try:
                from .config import get_config
            except ImportError:
                from model.config import get_config
            config = get_config()

        # Resolve CSV path relative to model directory
        model_dir = Path(__file__).parent
        csv_path = model_dir.parent / "data" / "islands_master.csv"

        routing_premium = config.technology.routing_premium
        intra_capex = config.technology.inter_island_capex_per_km
        inter_capex = config.technology.cable_capex_per_km

        return cls(
            pd.read_csv(csv_path),
            routing_premium=routing_premium,
            intra_atoll_capex_per_km_usd=intra_capex,
            inter_atoll_capex_per_km_usd=inter_capex,
        )

    # --- Distance lookups ---

    def distance_between(self, island_a: str, island_b: str) -> float:
        """Get routed distance (km) between two islands by name."""
        idx_a = self._island_index(island_a)
        idx_b = self._island_index(island_b)
        return self.dist_matrix[idx_a, idx_b]

    def nearest_neighbours(self, island: str, n: int = 5) -> list[tuple[str, float]]:
        """Get the n nearest islands to the given island."""
        idx = self._island_index(island)
        dists = self.dist_matrix[idx]
        # Exclude self (distance 0)
        sorted_idx = np.argsort(dists)
        result = []
        for j in sorted_idx:
            if j != idx:
                result.append((self.names[j], dists[j]))
                if len(result) >= n:
                    break
        return result

    # --- MST computations ---

    def compute_atoll_msts(self) -> dict[str, MSTResult]:
        """Compute MST for each atoll (intra-atoll cable network)."""
        if self._atoll_msts is not None:
            return self._atoll_msts

        self._atoll_msts = {}
        for atoll, indices in self.atoll_groups.items():
            edges_raw = prim_mst(self.dist_matrix, indices)
            edges_named = [
                (self.names[i], self.names[j], d)
                for i, j, d in edges_raw
            ]
            total = sum(d for _, _, d in edges_named)
            self._atoll_msts[atoll] = MSTResult(
                name=atoll,
                edges=edges_named,
                total_length_km=total,
                n_nodes=len(indices),
                n_edges=len(edges_named),
            )
        return self._atoll_msts

    def compute_backbone_mst(self) -> MSTResult:
        """
        Compute MST across atoll centroids (inter-atoll backbone).

        Uses population-weighted centroid for each atoll.
        """
        if self._backbone_mst is not None:
            return self._backbone_mst

        atoll_names = sorted(self.atoll_groups.keys())
        n_atolls = len(atoll_names)

        # Compute population-weighted centroids
        centroids_lat = np.zeros(n_atolls)
        centroids_lon = np.zeros(n_atolls)

        for k, atoll in enumerate(atoll_names):
            indices = self.atoll_groups[atoll]
            pops = self.pops[indices].astype(float)
            total_pop = pops.sum()
            if total_pop > 0:
                centroids_lat[k] = np.average(self.lats[indices], weights=pops)
                centroids_lon[k] = np.average(self.lons[indices], weights=pops)
            else:
                centroids_lat[k] = np.mean(self.lats[indices])
                centroids_lon[k] = np.mean(self.lons[indices])

        # Distance matrix between atoll centroids (with routing premium)
        centroid_dist = compute_distance_matrix(
            centroids_lat, centroids_lon, routing_premium=self.routing_premium
        )

        # MST on centroid graph
        edges_raw = prim_mst(centroid_dist, list(range(n_atolls)))
        edges_named = [
            (atoll_names[i], atoll_names[j], d)
            for i, j, d in edges_raw
        ]
        total = sum(d for _, _, d in edges_named)

        self._backbone_mst = MSTResult(
            name="National Backbone",
            edges=edges_named,
            total_length_km=total,
            n_nodes=n_atolls,
            n_edges=len(edges_named),
        )
        return self._backbone_mst

    # --- Summary ---

    def summary(self) -> NetworkSummary:
        """Compute full network summary with cable costs."""
        atoll_msts = self.compute_atoll_msts()
        backbone_mst = self.compute_backbone_mst()

        total_intra = sum(m.total_length_km for m in atoll_msts.values())
        total_backbone = backbone_mst.total_length_km
        total_network = total_intra + total_backbone

        intra_capex = total_intra * self.intra_atoll_capex_per_km / 1e6
        backbone_capex = total_backbone * self.inter_atoll_capex_per_km / 1e6
        total_capex = intra_capex + backbone_capex

        return NetworkSummary(
            n_islands=len(self.df),
            n_atolls=len(self.atoll_groups),
            total_population=int(self.pops.sum()),
            atoll_msts=list(atoll_msts.values()),
            backbone_mst=backbone_mst,
            total_intra_atoll_km=total_intra,
            total_backbone_km=total_backbone,
            total_network_km=total_network,
            routing_premium=self.routing_premium,
            intra_atoll_capex_musd=intra_capex,
            backbone_capex_musd=backbone_capex,
            total_capex_musd=total_capex,
        )

    # --- Scenario-specific queries ---

    def greater_male_network(self) -> MSTResult:
        """
        Cable network for Greater Malé hub scenario.
        Connects all Kaafu atoll islands + Male atoll (Maale, Hulhumaale, Vilin'gili).
        """
        # In COD-AB GDB, Male city islands are under "Male" atoll,
        # while outer Kaafu islands are under "Kaafu".
        kaafu_indices = self.atoll_groups.get("Kaafu", [])
        male_indices = self.atoll_groups.get("Male", [])
        combined = kaafu_indices + male_indices
        edges_raw = prim_mst(self.dist_matrix, combined)
        edges_named = [
            (self.names[i], self.names[j], d)
            for i, j, d in edges_raw
        ]
        total = sum(d for _, _, d in edges_named)
        return MSTResult(
            name="Greater Malé (Kaafu + Male)",
            edges=edges_named,
            total_length_km=total,
            n_nodes=len(combined),
            n_edges=len(edges_named),
        )

    def get_distance_dataframe(self) -> pd.DataFrame:
        """Return the full distance matrix as a labelled DataFrame."""
        return pd.DataFrame(
            self.dist_matrix,
            index=self.names,
            columns=self.names,
        )

    def get_atoll_summary_df(self) -> pd.DataFrame:
        """Summary table: per-atoll stats."""
        atoll_msts = self.compute_atoll_msts()
        rows = []
        for atoll in sorted(self.atoll_groups.keys()):
            indices = self.atoll_groups[atoll]
            mst = atoll_msts[atoll]
            rows.append({
                "Atoll": atoll,
                "Islands": len(indices),
                "Population": int(self.pops[indices].sum()),
                "MST Length (km)": round(mst.total_length_km, 1),
                "MST Edges": mst.n_edges,
                "Avg Edge (km)": round(mst.total_length_km / max(mst.n_edges, 1), 1),
            })
        return pd.DataFrame(rows)

    # --- Internal helpers ---

    def _island_index(self, name: str) -> int:
        """Get array index for an island name."""
        matches = np.where(self.names == name)[0]
        if len(matches) == 0:
            raise ValueError(f"Island not found: '{name}'. Available: {list(self.names)}")
        return matches[0]


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------

def main():
    """Run network analysis and print summary."""
    import sys

    # Resolve data path
    model_dir = Path(__file__).parent
    csv_path = model_dir.parent / "data" / "islands_master.csv"

    if not csv_path.exists():
        print(f"Error: GIS data not found at {csv_path}")
        sys.exit(1)

    # Load parameters from config system (parameters.csv)
    try:
        from .config import get_config
    except ImportError:
        from model.config import get_config

    cfg = get_config()
    routing_premium = cfg.technology.routing_premium
    intra_capex = cfg.technology.inter_island_capex_per_km
    inter_capex = cfg.technology.cable_capex_per_km

    net = IslandNetwork.from_csv(
        csv_path,
        routing_premium=routing_premium,
        intra_atoll_capex_per_km_usd=intra_capex,
        inter_atoll_capex_per_km_usd=inter_capex,
    )

    # Print full summary
    s = net.summary()
    print(s)

    # Print Greater Male hub specifically
    print()
    gm = net.greater_male_network()
    print(gm)

    # Print atoll summary table
    print()
    print("-" * 70)
    print("  ATOLL SUMMARY TABLE")
    print("-" * 70)
    print(net.get_atoll_summary_df().to_string(index=False))

    # Print some spot-check distances
    print()
    print("-" * 70)
    print("  SPOT-CHECK DISTANCES")
    print("-" * 70)
    checks = [
        ("Maale", "Hulhumaale"),        # 7.5 km within Male atoll
        ("Maale", "Hithadhoo"),          # Male to southernmost city (Seenu)
        ("Kulhudhuffushi", "Maale"),     # Second city to capital
        ("Fuvahmulah", "Hithadhoo"),     # Two southern cities
        ("Naifaru", "Kulhudhuffushi"),   # Lhaviyani hub to HDh
    ]
    for a, b in checks:
        try:
            d = net.distance_between(a, b)
            print(f"  {a:>20s} -- {b:<20s}  {d:6.1f} km")
        except ValueError as e:
            print(f"  Warning: {e}")


if __name__ == "__main__":
    main()
