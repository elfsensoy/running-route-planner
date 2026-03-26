from pathlib import Path
import math
from typing import Dict, Tuple, Optional

import pandas as pd
import osmnx as ox
import networkx as nx


BASE_DIR = Path(__file__).resolve().parents[2]

GRAPH_PATH = BASE_DIR / "data" / "raw" / "fatih_walk.graphml"
POIS_PATH = BASE_DIR / "data" / "processed" / "fatih_pois_edge_mapped.csv"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "candidate_pois.csv"

CANDIDATE_DISTANCE_RATIO = 0.65
CANDIDATE_MULTIPLIER = 10


USER_INPUT = {
    "start_lat": 41.015,
    "start_lon": 28.960,
    "distance_range_km": {
        "min": 4,
        "max": 5
    },
    "poi_preferences": {
        "museum_historic": 2,
        "viewpoint_attraction": 1,
        "park_garden": 1,
        "food": 1
    },
    "elevation_preference": "low"
}


def build_edge_lookup(graph: nx.MultiDiGraph) -> Dict[Tuple[int, int, int], float]:
    """
    Build a lookup table from (u, v, key) to edge length in meters.
    """
    edge_lengths = {}

    for u, v, key, data in graph.edges(keys=True, data=True):
        length = data.get("length", math.inf)
        edge_lengths[(u, v, key)] = length

    return edge_lengths


def choose_poi_access_node(
    row: pd.Series,
    graph: nx.MultiDiGraph,
    edge_lengths: Dict[Tuple[int, int, int], float]
) -> Optional[int]:
    """
    Since each POI is mapped to an edge, choose one representative node
    of that edge to approximate network distance from the start node.

    For now, we use the edge's u node as the representative access node.
    This is a simple first approximation for candidate filtering.
    """
    u = row["nearest_edge_u"]
    v = row["nearest_edge_v"]

    if u in graph.nodes:
        return int(u)
    if v in graph.nodes:
        return int(v)

    return None


def main():
    start_lat = USER_INPUT["start_lat"]
    start_lon = USER_INPUT["start_lon"]
    max_distance_km = USER_INPUT["distance_range_km"]["max"]
    poi_preferences = USER_INPUT["poi_preferences"]

    max_candidate_distance_m = max_distance_km * 1000 * CANDIDATE_DISTANCE_RATIO

    selected_groups = {
        group: count for group, count in poi_preferences.items() if count > 0
    }

    if not selected_groups:
        raise ValueError("At least one POI group must have desired_count > 0.")

    print("Loading graph...")
    G = ox.load_graphml(GRAPH_PATH)

    print("Loading POIs...")
    pois_df = pd.read_csv(POIS_PATH)

    required_cols = {
        "poi_id",
        "name",
        "lat",
        "lon",
        "poi_group",
        "nearest_edge_u",
        "nearest_edge_v",
        "nearest_edge_key",
    }
    missing = required_cols - set(pois_df.columns)
    if missing:
        raise ValueError("Missing POI columns: {}".format(missing))

    print("Snapping start point to graph...")
    start_node = ox.distance.nearest_nodes(G, X=start_lon, Y=start_lat)

    print("Filtering by selected POI groups...")
    pois_df = pois_df[pois_df["poi_group"].isin(selected_groups.keys())].copy()

    pois_df = pois_df[
        pois_df["name"].notna() &
        (pois_df["name"].str.strip() != "") &
        (pois_df["name"].str.strip() != "Unnamed POI")
    ].copy()

    if pois_df.empty:
        raise ValueError("No POIs left after filtering by selected categories.")

    print("Preparing edge lookup...")
    edge_lengths = build_edge_lookup(G)

    print("Assigning representative access nodes for POIs...")
    pois_df["access_node"] = pois_df.apply(
        lambda row: choose_poi_access_node(row, G, edge_lengths),
        axis=1
    )

    pois_df = pois_df.dropna(subset=["access_node"]).copy()
    pois_df["access_node"] = pois_df["access_node"].astype(int)

    print("Computing network distance from start to each POI access node...")
    shortest_lengths = nx.single_source_dijkstra_path_length(
        G,
        start_node,
        weight="length"
    )

    pois_df["network_distance_from_start_m"] = pois_df["access_node"].map(shortest_lengths)
    pois_df = pois_df.dropna(subset=["network_distance_from_start_m"]).copy()

    print("Applying candidate distance threshold: {:.2f} m".format(max_candidate_distance_m))
    pois_df = pois_df[
        pois_df["network_distance_from_start_m"] <= max_candidate_distance_m
    ].copy()

    if pois_df.empty:
        raise ValueError("No POIs left after network distance filtering.")

    print("Selecting top candidates per group...")
    candidate_parts = []

    for group, desired_count in selected_groups.items():
        group_df = pois_df[pois_df["poi_group"] == group].copy()
        group_df = group_df.sort_values("network_distance_from_start_m", ascending=True)

        candidate_limit = desired_count * CANDIDATE_MULTIPLIER
        group_candidates = group_df.head(candidate_limit).copy()

        group_candidates["desired_count"] = desired_count
        group_candidates["candidate_limit"] = candidate_limit

        candidate_parts.append(group_candidates)

        print(
            "{}: desired={}, limit={}, selected={}".format(
                group, desired_count, candidate_limit, len(group_candidates)
            )
        )

    if not candidate_parts:
        raise ValueError("No candidate POIs could be generated.")

    candidate_df = pd.concat(candidate_parts, ignore_index=True)

    candidate_df = candidate_df[[
        "poi_id",
        "name",
        "poi_group",
        "lat",
        "lon",
        "nearest_edge_u",
        "nearest_edge_v",
        "nearest_edge_key",
        "access_node",
        "network_distance_from_start_m",
        "desired_count",
        "candidate_limit"
    ]].copy()

    candidate_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")

    print("\nSaved candidate POIs to: {}".format(OUTPUT_PATH))
    print("Total candidate POIs: {}".format(len(candidate_df)))
    print("\nCandidate counts by group:")
    print(candidate_df["poi_group"].value_counts())
    print("\nFirst 10 rows:")
    print(candidate_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()