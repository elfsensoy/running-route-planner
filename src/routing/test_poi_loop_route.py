from pathlib import Path
from itertools import product
from typing import Dict, List, Tuple, Optional

import pandas as pd
import osmnx as ox
import networkx as nx


BASE_DIR = Path(__file__).resolve().parents[2]

GRAPH_PATH = BASE_DIR / "data" / "raw" / "fatih_walk.graphml"
CANDIDATES_PATH = BASE_DIR / "data" / "processed" / "candidate_pois.csv"
OUTPUT_SUMMARY_PATH = BASE_DIR / "data" / "processed" / "test_route_summary.csv"
OUTPUT_ROUTE_NODES_PATH = BASE_DIR / "data" / "processed" / "test_route_nodes.csv"


USER_INPUT = {
    "start_lat": 41.015,
    "start_lon": 28.960,
    "poi_preferences": {
        "museum_historic": 1,
        "park_garden": 1,
        "viewpoint_attraction": 1,
        "food": 1,
    },
}


def get_edge_length_sum(graph: nx.MultiDiGraph, route_nodes: List[int]) -> float:
    """
    Sum the lengths of consecutive edges along a node path.
    For MultiDiGraph, choose the shortest parallel edge between two nodes.
    """
    total = 0.0

    for u, v in zip(route_nodes[:-1], route_nodes[1:]):
        edge_data = graph.get_edge_data(u, v)
        if edge_data is None:
            raise ValueError(f"No edge found between consecutive route nodes: {u} -> {v}")

        min_length = min(
            data.get("length", float("inf"))
            for data in edge_data.values()
        )
        total += min_length

    return total


def build_segment(
    graph: nx.MultiDiGraph,
    source: int,
    target: int
) -> Tuple[List[int], float]:
    """
    Return shortest path nodes and its length between source and target.
    """
    path_nodes = nx.shortest_path(graph, source=source, target=target, weight="length")
    path_length = nx.shortest_path_length(graph, source=source, target=target, weight="length")
    return path_nodes, path_length


def merge_segments(segments: List[List[int]]) -> List[int]:
    """
    Merge path segments into one continuous node list.
    Avoid duplicating junction nodes.
    """
    if not segments:
        return []

    merged = segments[0][:]

    for segment in segments[1:]:
        if not segment:
            continue
        merged.extend(segment[1:])

    return merged


def select_top_k_per_group(
    df: pd.DataFrame,
    group_name: str,
    k: int = 3
) -> pd.DataFrame:
    """
    Take top-k nearest candidates from each requested group.
    """
    group_df = df[df["poi_group"] == group_name].copy()
    group_df = group_df.sort_values("network_distance_from_start_m", ascending=True)
    return group_df.head(k).copy()


def build_route_for_candidate_combination(
    graph: nx.MultiDiGraph,
    start_node: int,
    selected_rows: List[pd.Series]
) -> Dict:
    """
    Build a loop:
    start -> poi1 -> poi2 -> ... -> start
    """
    ordered_rows = sorted(
        selected_rows,
        key=lambda row: row["network_distance_from_start_m"]
    )

    visit_nodes = [int(row["access_node"]) for row in ordered_rows]

    all_segments = []
    segment_lengths = []

    current_node = start_node

    for poi_node in visit_nodes:
        seg_nodes, seg_len = build_segment(graph, current_node, poi_node)
        all_segments.append(seg_nodes)
        segment_lengths.append(seg_len)
        current_node = poi_node

    # close the loop
    seg_nodes, seg_len = build_segment(graph, current_node, start_node)
    all_segments.append(seg_nodes)
    segment_lengths.append(seg_len)

    merged_route_nodes = merge_segments(all_segments)
    total_length_m = sum(segment_lengths)

    selected_poi_ids = [row["poi_id"] for row in ordered_rows]
    selected_poi_names = [row["name"] for row in ordered_rows]
    selected_poi_groups = [row["poi_group"] for row in ordered_rows]

    return {
        "route_nodes": merged_route_nodes,
        "total_length_m": total_length_m,
        "selected_poi_ids": selected_poi_ids,
        "selected_poi_names": selected_poi_names,
        "selected_poi_groups": selected_poi_groups,
        "segment_lengths_m": segment_lengths,
    }


def main():
    print("Loading graph...")
    G = ox.load_graphml(GRAPH_PATH)

    print("Loading candidate POIs...")
    candidates_df = pd.read_csv(CANDIDATES_PATH)

    required_cols = {
        "poi_id",
        "name",
        "poi_group",
        "access_node",
        "network_distance_from_start_m",
    }
    missing = required_cols - set(candidates_df.columns)
    if missing:
        raise ValueError(f"Missing required columns in candidate CSV: {missing}")

    print("Snapping start point to graph...")
    start_node = ox.distance.nearest_nodes(
        G,
        X=USER_INPUT["start_lon"],
        Y=USER_INPUT["start_lat"]
    )

    requested_groups = {
        group: count
        for group, count in USER_INPUT["poi_preferences"].items()
        if count > 0
    }

    if not requested_groups:
        raise ValueError("At least one POI group must be requested.")

    print("Preparing top candidate subsets per group...")
    group_candidate_lists = {}

    # For this prototype, assume count=1 per group.
    # If later count>1 is needed, logic must be extended.
    for group, count in requested_groups.items():
        if count != 1:
            raise ValueError(
                f"This prototype currently supports only desired_count=1 per group. "
                f"Group '{group}' has desired_count={count}."
            )

        top_group_df = select_top_k_per_group(candidates_df, group, k=3)

        if top_group_df.empty:
            raise ValueError(f"No candidates found for group: {group}")

        group_candidate_lists[group] = [
            row for _, row in top_group_df.iterrows()
        ]

        print(f"{group}: using top {len(group_candidate_lists[group])} candidates for route testing")

    print("Generating route combinations...")
    ordered_group_names = list(group_candidate_lists.keys())
    ordered_candidate_lists = [group_candidate_lists[g] for g in ordered_group_names]

    best_result: Optional[Dict] = None
    all_results = []

    for combo in product(*ordered_candidate_lists):
        combo_poi_ids = [row["poi_id"] for row in combo]

        # avoid selecting same access node twice if categories overlap strangely
        combo_access_nodes = [int(row["access_node"]) for row in combo]
        if len(combo_access_nodes) != len(set(combo_access_nodes)):
            continue

        try:
            route_result = build_route_for_candidate_combination(G, start_node, list(combo))
        except nx.NetworkXNoPath:
            print(f"Skipping combination with no valid path: {combo_poi_ids}")
            continue

        result_row = {
            "selected_poi_ids": " | ".join(map(str, route_result["selected_poi_ids"])),
            "selected_poi_names": " | ".join(route_result["selected_poi_names"]),
            "selected_poi_groups": " | ".join(route_result["selected_poi_groups"]),
            "total_length_m": route_result["total_length_m"],
            "segment_lengths_m": " | ".join(f"{x:.2f}" for x in route_result["segment_lengths_m"]),
            "route_node_count": len(route_result["route_nodes"]),
        }
        all_results.append(result_row)

        if best_result is None or route_result["total_length_m"] < best_result["total_length_m"]:
            best_result = route_result

    if best_result is None:
        raise ValueError("No valid route combination could be generated.")

    print("\nBest route found:")
    print(f"Selected POIs: {best_result['selected_poi_names']}")
    print(f"Selected groups: {best_result['selected_poi_groups']}")
    print(f"Total route length: {best_result['total_length_m']:.2f} m")
    print(f"Route node count: {len(best_result['route_nodes'])}")

    # Save all tested route summaries
    summary_df = pd.DataFrame(all_results).sort_values("total_length_m", ascending=True)
    summary_df.to_csv(OUTPUT_SUMMARY_PATH, index=False, encoding="utf-8")

    # Save best route node sequence
    route_nodes_df = pd.DataFrame({
        "route_order": list(range(len(best_result["route_nodes"]))),
        "node_id": best_result["route_nodes"]
    })
    route_nodes_df.to_csv(OUTPUT_ROUTE_NODES_PATH, index=False, encoding="utf-8")

    print(f"\nSaved tested route summaries to: {OUTPUT_SUMMARY_PATH}")
    print(f"Saved best route node sequence to: {OUTPUT_ROUTE_NODES_PATH}")


if __name__ == "__main__":
    main()