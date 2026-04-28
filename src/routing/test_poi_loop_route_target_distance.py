from pathlib import Path
from itertools import product
from typing import Dict, List, Tuple, Optional

import pandas as pd
import osmnx as ox
import networkx as nx


BASE_DIR = Path(__file__).resolve().parents[2]

GRAPH_PATH = BASE_DIR / "data" / "raw" / "fatih_walk.graphml"
CANDIDATES_PATH = BASE_DIR / "data" / "processed" / "candidate_pois.csv"
OUTPUT_SUMMARY_PATH = BASE_DIR / "data" / "processed" / "test_route_summary_target_distance.csv"
OUTPUT_ROUTE_NODES_PATH = BASE_DIR / "data" / "processed" / "test_route_nodes_target_distance.csv"


USER_INPUT = {
    "start_lat": 41.015,
    "start_lon": 28.960,
    "distance_range_km": {
        "min": 4,
        "max": 5,
    },
    "poi_preferences": {
        "museum_historic": 1,
        "park_garden": 1,
        "viewpoint_attraction": 1,
        "food": 1,
    },
}


def build_segment(
    graph: nx.MultiDiGraph,
    source: int,
    target: int
) -> Tuple[List[int], float]:
    path_nodes = nx.shortest_path(graph, source=source, target=target, weight="length")
    path_length = nx.shortest_path_length(graph, source=source, target=target, weight="length")
    return path_nodes, path_length


def merge_segments(segments: List[List[int]]) -> List[int]:
    if not segments:
        return []

    merged = segments[0][:]
    for segment in segments[1:]:
        if segment:
            merged.extend(segment[1:])
    return merged


def select_top_k_per_group(
    df: pd.DataFrame,
    group_name: str,
    k: int = 3
) -> pd.DataFrame:
    group_df = df[df["poi_group"] == group_name].copy()
    group_df = group_df.sort_values("network_distance_from_start_m", ascending=True)
    return group_df.head(k).copy()


def build_route_for_candidate_combination(
    graph: nx.MultiDiGraph,
    start_node: int,
    selected_rows: List[pd.Series]
) -> Dict:
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

    min_distance_m = USER_INPUT["distance_range_km"]["min"] * 1000
    max_distance_m = USER_INPUT["distance_range_km"]["max"] * 1000
    target_distance_m = (min_distance_m + max_distance_m) / 2

    print(f"Target route range: {min_distance_m:.0f} m - {max_distance_m:.0f} m")
    print(f"Target route center: {target_distance_m:.0f} m")

    print("Preparing top candidate subsets per group...")
    group_candidate_lists = {}

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
        combo_access_nodes = [int(row["access_node"]) for row in combo]

        if len(combo_access_nodes) != len(set(combo_access_nodes)):
            continue

        try:
            route_result = build_route_for_candidate_combination(G, start_node, list(combo))
        except nx.NetworkXNoPath:
            print(f"Skipping combination with no valid path: {combo_poi_ids}")
            continue

        total_length_m = route_result["total_length_m"]
        distance_error_m = abs(total_length_m - target_distance_m)
        within_target_range = min_distance_m <= total_length_m <= max_distance_m

        result_row = {
            "selected_poi_ids": " | ".join(map(str, route_result["selected_poi_ids"])),
            "selected_poi_names": " | ".join(route_result["selected_poi_names"]),
            "selected_poi_groups": " | ".join(route_result["selected_poi_groups"]),
            "total_length_m": total_length_m,
            "distance_error_m": distance_error_m,
            "within_target_range": within_target_range,
            "segment_lengths_m": " | ".join(f"{x:.2f}" for x in route_result["segment_lengths_m"]),
            "route_node_count": len(route_result["route_nodes"]),
        }
        all_results.append(result_row)

        candidate_result = {
            **route_result,
            "distance_error_m": distance_error_m,
            "within_target_range": within_target_range,
        }

        if best_result is None:
            best_result = candidate_result
        else:
            current_best_in_range = best_result["within_target_range"]
            candidate_in_range = within_target_range

            if candidate_in_range and not current_best_in_range:
                best_result = candidate_result
            elif candidate_in_range == current_best_in_range:
                if distance_error_m < best_result["distance_error_m"]:
                    best_result = candidate_result

    if best_result is None:
        raise ValueError("No valid route combination could be generated.")

    print("\nBest route found:")
    print(f"Selected POIs: {best_result['selected_poi_names']}")
    print(f"Selected groups: {best_result['selected_poi_groups']}")
    print(f"Total route length: {best_result['total_length_m']:.2f} m")
    print(f"Distance error from target center: {best_result['distance_error_m']:.2f} m")
    print(f"Within target range: {best_result['within_target_range']}")
    print(f"Route node count: {len(best_result['route_nodes'])}")

    summary_df = pd.DataFrame(all_results).sort_values(
        by=["within_target_range", "distance_error_m"],
        ascending=[False, True]
    )
    summary_df.to_csv(OUTPUT_SUMMARY_PATH, index=False, encoding="utf-8")

    route_nodes_df = pd.DataFrame({
        "route_order": list(range(len(best_result["route_nodes"]))),
        "node_id": best_result["route_nodes"]
    })
    route_nodes_df.to_csv(OUTPUT_ROUTE_NODES_PATH, index=False, encoding="utf-8")

    print(f"\nSaved tested route summaries to: {OUTPUT_SUMMARY_PATH}")
    print(f"Saved best route node sequence to: {OUTPUT_ROUTE_NODES_PATH}")


if __name__ == "__main__":
    main()