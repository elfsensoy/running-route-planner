from pathlib import Path
from itertools import product, permutations
from typing import Dict, List, Tuple, Optional
import time
import json

import pandas as pd
import osmnx as ox
import networkx as nx


BASE_DIR = Path(__file__).resolve().parents[2]

GRAPH_PATH = BASE_DIR / "data" / "raw" / "fatih_walk.graphml"
CANDIDATES_PATH = BASE_DIR / "data" / "processed" / "candidate_pois.csv"

OUTPUT_SUMMARY_PATH = BASE_DIR / "data" / "processed" / "project_route_summary.csv"
OUTPUT_ROUTE_NODES_PATH = BASE_DIR / "data" / "processed" / "project_best_route_nodes.csv"
OUTPUT_SELECTED_POIS_PATH = BASE_DIR / "data" / "processed" / "project_selected_pois.csv"
OUTPUT_EXPERIMENT_DIR = BASE_DIR / "data" / "processed" / "experiment_results"


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
    "routing_algorithm": "astar",   # "dijkstra" or "astar"
    "elevation_preference": "low",     # placeholder for future use
}


TOP_K_PER_GROUP = 4


def heuristic_distance(graph: nx.MultiDiGraph, node1: int, node2: int) -> float:
    """
    Euclidean heuristic for A* using node coordinates.
    """
    x1 = graph.nodes[node1]["x"]
    y1 = graph.nodes[node1]["y"]
    x2 = graph.nodes[node2]["x"]
    y2 = graph.nodes[node2]["y"]
    return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5


def build_segment(
    graph: nx.MultiDiGraph,
    source: int,
    target: int,
    routing_algorithm: str = "dijkstra"
) -> Tuple[List[int], float]:
    """
    Build one segment between two nodes using the selected routing algorithm.
    """
    if routing_algorithm == "dijkstra":
        path_nodes = nx.shortest_path(graph, source=source, target=target, weight="length")
        path_length = nx.shortest_path_length(graph, source=source, target=target, weight="length")

    elif routing_algorithm == "astar":
        path_nodes = nx.astar_path(
            graph,
            source,
            target,
            heuristic=lambda u, v: heuristic_distance(graph, u, v),
            weight="length"
        )
        path_length = nx.path_weight(graph, path_nodes, weight="length")

    else:
        raise ValueError(f"Unsupported routing algorithm: {routing_algorithm}")

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
    k: int
) -> pd.DataFrame:
    group_df = df[df["poi_group"] == group_name].copy()
    group_df = group_df.sort_values("network_distance_from_start_m", ascending=True)
    return group_df.head(k).copy()


def build_loop_for_order(
    graph: nx.MultiDiGraph,
    start_node: int,
    ordered_rows: List[pd.Series],
    routing_algorithm: str
) -> Dict:
    visit_nodes = [int(row["access_node"]) for row in ordered_rows]

    all_segments = []
    segment_lengths = []
    current_node = start_node

    for poi_node in visit_nodes:
        seg_nodes, seg_len = build_segment(
            graph=graph,
            source=current_node,
            target=poi_node,
            routing_algorithm=routing_algorithm
        )
        all_segments.append(seg_nodes)
        segment_lengths.append(seg_len)
        current_node = poi_node

    # close loop
    seg_nodes, seg_len = build_segment(
        graph=graph,
        source=current_node,
        target=start_node,
        routing_algorithm=routing_algorithm
    )
    all_segments.append(seg_nodes)
    segment_lengths.append(seg_len)

    merged_route_nodes = merge_segments(all_segments)
    total_length_m = sum(segment_lengths)

    return {
        "route_nodes": merged_route_nodes,
        "total_length_m": total_length_m,
        "segment_lengths_m": segment_lengths,
        "selected_poi_ids": [row["poi_id"] for row in ordered_rows],
        "selected_poi_names": [row["name"] for row in ordered_rows],
        "selected_poi_groups": [row["poi_group"] for row in ordered_rows],
        "selected_access_nodes": visit_nodes,
    }


def evaluate_route(
    route_result: Dict,
    min_distance_m: float,
    max_distance_m: float,
    target_distance_m: float
) -> Dict:
    total_length_m = route_result["total_length_m"]
    within_target_range = min_distance_m <= total_length_m <= max_distance_m
    distance_error_m = abs(total_length_m - target_distance_m)

    return {
        **route_result,
        "within_target_range": within_target_range,
        "distance_error_m": distance_error_m,
    }


def is_better(candidate: Dict, current_best: Optional[Dict]) -> bool:
    if current_best is None:
        return True

    # 1) Prefer routes within target range
    if candidate["within_target_range"] and not current_best["within_target_range"]:
        return True
    if current_best["within_target_range"] and not candidate["within_target_range"]:
        return False

    # 2) Prefer smaller distance error
    if candidate["distance_error_m"] < current_best["distance_error_m"]:
        return True
    if candidate["distance_error_m"] > current_best["distance_error_m"]:
        return False

    # 3) If tied, prefer shorter route
    if candidate["total_length_m"] < current_best["total_length_m"]:
        return True

    return False


def print_experiment_summary(metrics: Dict) -> None:
    print("\n" + "=" * 60)
    print("EXPERIMENT SUMMARY")
    print("=" * 60)
    print(f"Routing algorithm       : {metrics['routing_algorithm']}")
    print(f"Start node              : {metrics['start_node']}")
    print(f"Distance min (m)        : {metrics['distance_min_m']}")
    print(f"Distance max (m)        : {metrics['distance_max_m']}")
    print(f"Target distance (m)     : {metrics['target_distance_m']}")
    print(f"Total candidate count   : {metrics['total_candidate_count']}")
    print(f"Combinations evaluated  : {metrics['combinations_evaluated']}")
    print(f"Permutations evaluated  : {metrics['permutations_evaluated']}")
    print(f"Feasible routes found   : {metrics['feasible_routes_found']}")
    print(f"Best route length (m)   : {metrics['best_route_length_m']}")
    print(f"Distance error (m)      : {metrics['best_distance_error_m']}")
    print(f"Execution time (sec)    : {metrics['execution_time_sec']}")
    print("Categories:")
    for category, info in metrics["categories"].items():
        print(f"  - {category}: {info['candidate_count']} candidates")
    print(f"Selected POIs           : {metrics['selected_pois']}")
    print("=" * 60)


def save_experiment_summary(metrics: Dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    json_file = output_dir / f"experiment_summary_{timestamp}.json"

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=4, ensure_ascii=False)

    return json_file


def main():
    start_time = time.perf_counter()

    routing_algorithm = USER_INPUT.get("routing_algorithm", "dijkstra").lower()

    metrics = {
        "routing_algorithm": routing_algorithm,
        "start_node": None,
        "distance_min_m": None,
        "distance_max_m": None,
        "target_distance_m": None,
        "categories": {},
        "total_candidate_count": 0,
        "combinations_evaluated": 0,
        "permutations_evaluated": 0,
        "feasible_routes_found": 0,
        "best_route_length_m": None,
        "best_distance_error_m": None,
        "selected_pois": [],
        "execution_time_sec": None,
    }

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
    metrics["start_node"] = int(start_node)

    requested_groups = {
        group: count
        for group, count in USER_INPUT["poi_preferences"].items()
        if count > 0
    }

    if not requested_groups:
        raise ValueError("At least one POI group must be requested.")

    for group, count in requested_groups.items():
        if count != 1:
            raise ValueError(
                f"This version supports only desired_count=1 per group. "
                f"Group '{group}' has desired_count={count}."
            )

    min_distance_m = USER_INPUT["distance_range_km"]["min"] * 1000
    max_distance_m = USER_INPUT["distance_range_km"]["max"] * 1000
    target_distance_m = (min_distance_m + max_distance_m) / 2

    metrics["distance_min_m"] = min_distance_m
    metrics["distance_max_m"] = max_distance_m
    metrics["target_distance_m"] = target_distance_m

    print(f"Target route range: {min_distance_m:.0f} m - {max_distance_m:.0f} m")
    print(f"Target route center: {target_distance_m:.0f} m")
    print(f"Routing algorithm: {routing_algorithm}")

    print("Preparing top candidate subsets per group...")
    group_candidate_lists = {}

    for group in requested_groups.keys():
        top_group_df = select_top_k_per_group(candidates_df, group, TOP_K_PER_GROUP)

        if top_group_df.empty:
            raise ValueError(f"No candidates found for group: {group}")

        rows = [row for _, row in top_group_df.iterrows()]
        group_candidate_lists[group] = rows
        metrics["categories"][group] = {"candidate_count": len(rows)}

        print(f"{group}: using top {len(rows)} candidates")

    metrics["total_candidate_count"] = sum(
        info["candidate_count"] for info in metrics["categories"].values()
    )

    ordered_group_names = list(group_candidate_lists.keys())
    ordered_candidate_lists = [group_candidate_lists[g] for g in ordered_group_names]

    print("Generating candidate combinations and route orders...")
    all_results = []
    best_result = None

    tested_combo_count = 0
    tested_order_count = 0

    for combo in product(*ordered_candidate_lists):
        tested_combo_count += 1
        metrics["combinations_evaluated"] += 1

        combo_access_nodes = [int(row["access_node"]) for row in combo]
        if len(combo_access_nodes) != len(set(combo_access_nodes)):
            continue

        for ordered_combo in permutations(combo):
            tested_order_count += 1
            metrics["permutations_evaluated"] += 1

            try:
                route_result = build_loop_for_order(
                    graph=G,
                    start_node=start_node,
                    ordered_rows=list(ordered_combo),
                    routing_algorithm=routing_algorithm
                )
            except nx.NetworkXNoPath:
                continue

            evaluated = evaluate_route(
                route_result=route_result,
                min_distance_m=min_distance_m,
                max_distance_m=max_distance_m,
                target_distance_m=target_distance_m
            )

            metrics["feasible_routes_found"] += 1

            result_row = {
                "routing_algorithm": routing_algorithm,
                "selected_poi_ids": " | ".join(map(str, evaluated["selected_poi_ids"])),
                "selected_poi_names": " | ".join(evaluated["selected_poi_names"]),
                "selected_poi_groups": " | ".join(evaluated["selected_poi_groups"]),
                "total_length_m": evaluated["total_length_m"],
                "distance_error_m": evaluated["distance_error_m"],
                "within_target_range": evaluated["within_target_range"],
                "segment_lengths_m": " | ".join(f"{x:.2f}" for x in evaluated["segment_lengths_m"]),
                "route_node_count": len(evaluated["route_nodes"]),
            }
            all_results.append(result_row)

            if is_better(evaluated, best_result):
                best_result = evaluated

    if best_result is None:
        raise ValueError("No valid route could be generated.")

    metrics["best_route_length_m"] = round(best_result["total_length_m"], 2)
    metrics["best_distance_error_m"] = round(best_result["distance_error_m"], 2)
    metrics["selected_pois"] = best_result["selected_poi_names"]

    end_time = time.perf_counter()
    metrics["execution_time_sec"] = round(end_time - start_time, 4)

    print("\nRoute search completed.")
    print(f"Tested candidate combinations: {tested_combo_count}")
    print(f"Tested route orders: {tested_order_count}")

    print("\nBest route found:")
    print(f"Selected POIs: {best_result['selected_poi_names']}")
    print(f"Selected groups: {best_result['selected_poi_groups']}")
    print(f"Total route length: {best_result['total_length_m']:.2f} m")
    print(f"Distance error from target center: {best_result['distance_error_m']:.2f} m")
    print(f"Within target range: {best_result['within_target_range']}")
    print(f"Route node count: {len(best_result['route_nodes'])}")

    print_experiment_summary(metrics)

    summary_df = pd.DataFrame(all_results).sort_values(
        by=["within_target_range", "distance_error_m", "total_length_m"],
        ascending=[False, True, True]
    )
    summary_df.to_csv(OUTPUT_SUMMARY_PATH, index=False, encoding="utf-8")

    route_nodes_df = pd.DataFrame({
        "route_order": list(range(len(best_result["route_nodes"]))),
        "node_id": best_result["route_nodes"]
    })
    route_nodes_df.to_csv(OUTPUT_ROUTE_NODES_PATH, index=False, encoding="utf-8")

    selected_pois_df = pd.DataFrame({
        "poi_id": best_result["selected_poi_ids"],
        "name": best_result["selected_poi_names"],
        "poi_group": best_result["selected_poi_groups"],
        "access_node": best_result["selected_access_nodes"],
    })
    selected_pois_df.to_csv(OUTPUT_SELECTED_POIS_PATH, index=False, encoding="utf-8")

    experiment_json_path = save_experiment_summary(metrics, OUTPUT_EXPERIMENT_DIR)

    print(f"\nSaved route summary to: {OUTPUT_SUMMARY_PATH}")
    print(f"Saved best route nodes to: {OUTPUT_ROUTE_NODES_PATH}")
    print(f"Saved selected POIs to: {OUTPUT_SELECTED_POIS_PATH}")
    print(f"Saved experiment summary to: {experiment_json_path}")


if __name__ == "__main__":
    main()