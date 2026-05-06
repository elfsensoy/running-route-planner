from functools import lru_cache
from itertools import combinations, permutations, product
import math
from pathlib import Path
from typing import Dict, List, Optional

import networkx as nx
import osmnx as ox
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
GRAPH_PATH = BASE_DIR / "data" / "raw" / "fatih_walk.graphml"
POIS_PATH = BASE_DIR / "data" / "processed" / "fatih_pois_edge_mapped.csv"

CANDIDATE_DISTANCE_RATIO = 0.75
CANDIDATE_MULTIPLIER = 10
TOP_K_PER_GROUP = 4
MAX_POIS_PER_GROUP = 10
MAX_TOTAL_POIS = 10
EXACT_ORDER_LIMIT = 4
OVERLAP_RATIO_TOLERANCE = 0.03


class RouteGenerationError(ValueError):
    pass


@lru_cache(maxsize=1)
def load_graph() -> nx.MultiDiGraph:
    return ox.load_graphml(GRAPH_PATH)


@lru_cache(maxsize=1)
def load_pois() -> pd.DataFrame:
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
        raise RouteGenerationError(f"Missing POI columns: {sorted(missing)}")
    return pois_df


def available_poi_groups() -> List[str]:
    return sorted(load_pois()["poi_group"].dropna().unique().tolist())


def node_coordinates(graph: nx.MultiDiGraph, node_id: int) -> Dict[str, float]:
    node = graph.nodes[node_id]
    return {
        "lat": float(node["y"]),
        "lon": float(node["x"]),
    }


def path_length(graph: nx.MultiDiGraph, path_nodes: List[int]) -> float:
    total = 0.0
    for u, v in zip(path_nodes[:-1], path_nodes[1:]):
        edge_data = graph.get_edge_data(u, v)
        if edge_data is None:
            raise RouteGenerationError(f"No edge found between route nodes {u} and {v}.")
        total += min(float(data.get("length", float("inf"))) for data in edge_data.values())
    return total


def heuristic_distance(graph: nx.MultiDiGraph, node1: int, node2: int) -> float:
    x1 = float(graph.nodes[node1]["x"])
    y1 = float(graph.nodes[node1]["y"])
    x2 = float(graph.nodes[node2]["x"])
    y2 = float(graph.nodes[node2]["y"])
    return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5


def build_segment(
    graph: nx.MultiDiGraph,
    source: int,
    target: int,
    routing_algorithm: str,
) -> Dict:
    if routing_algorithm == "dijkstra":
        nodes = nx.shortest_path(graph, source=source, target=target, weight="length")
    elif routing_algorithm == "astar":
        nodes = nx.astar_path(
            graph,
            source,
            target,
            heuristic=lambda u, v: heuristic_distance(graph, u, v),
            weight="length",
        )
    else:
        raise RouteGenerationError(f"Unsupported routing algorithm: {routing_algorithm}")

    return {
        "nodes": nodes,
        "length_m": path_length(graph, nodes),
    }


def merge_segments(segments: List[List[int]]) -> List[int]:
    if not segments:
        return []

    merged = segments[0][:]
    for segment in segments[1:]:
        if segment:
            merged.extend(segment[1:])
    return merged


def choose_poi_access_node(row: pd.Series, graph: nx.MultiDiGraph) -> Optional[int]:
    u = int(row["nearest_edge_u"])
    v = int(row["nearest_edge_v"])

    if u in graph.nodes:
        return u
    if v in graph.nodes:
        return v
    return None


def build_candidate_pois(
    graph: nx.MultiDiGraph,
    pois_df: pd.DataFrame,
    start_node: int,
    max_distance_km: float,
    poi_preferences: Dict[str, int],
    candidate_distance_ratio: float = CANDIDATE_DISTANCE_RATIO,
) -> pd.DataFrame:
    selected_groups = {
        group: int(count)
        for group, count in poi_preferences.items()
        if int(count) > 0
    }
    if not selected_groups:
        raise RouteGenerationError("At least one POI group must be requested.")

    candidate_df = pois_df[pois_df["poi_group"].isin(selected_groups.keys())].copy()
    candidate_df = candidate_df[
        candidate_df["name"].notna()
        & (candidate_df["name"].astype(str).str.strip() != "")
        & (candidate_df["name"].astype(str).str.strip() != "Unnamed POI")
    ].copy()

    if candidate_df.empty:
        raise RouteGenerationError("No POIs found for the selected categories.")

    candidate_df["access_node"] = candidate_df.apply(
        lambda row: choose_poi_access_node(row, graph),
        axis=1,
    )
    candidate_df = candidate_df.dropna(subset=["access_node"]).copy()
    candidate_df["access_node"] = candidate_df["access_node"].astype(int)

    shortest_lengths = nx.single_source_dijkstra_path_length(
        graph,
        start_node,
        weight="length",
    )
    candidate_df["network_distance_from_start_m"] = candidate_df["access_node"].map(
        shortest_lengths
    )
    candidate_df = candidate_df.dropna(subset=["network_distance_from_start_m"]).copy()

    max_candidate_distance_m = max_distance_km * 1000 * candidate_distance_ratio
    candidate_df = candidate_df[
        candidate_df["network_distance_from_start_m"] <= max_candidate_distance_m
    ].copy()

    if candidate_df.empty:
        raise RouteGenerationError("No POIs are close enough for this distance range.")

    candidate_parts = []
    for group, desired_count in selected_groups.items():
        group_df = candidate_df[candidate_df["poi_group"] == group].copy()
        group_df = group_df.sort_values("network_distance_from_start_m", ascending=True)
        group_candidates = group_df.head(desired_count * CANDIDATE_MULTIPLIER).copy()
        if group_candidates.empty:
            raise RouteGenerationError(f"No candidate POIs found for group: {group}")
        candidate_parts.append(group_candidates)

    return pd.concat(candidate_parts, ignore_index=True)


def select_top_k_per_group(df: pd.DataFrame, group_name: str, k: int) -> pd.DataFrame:
    group_df = df[df["poi_group"] == group_name].copy()
    group_df = group_df.sort_values("network_distance_from_start_m", ascending=True)
    return group_df.head(k).copy()


def build_loop_for_order(
    graph: nx.MultiDiGraph,
    start_node: int,
    ordered_rows: List[pd.Series],
    routing_algorithm: str,
    segment_cache: Dict,
    final_node: Optional[int],
) -> Dict:
    all_segments = []
    segment_lengths = []
    current_node = start_node

    for row in ordered_rows:
        target_node = int(row["access_node"])
        segment = get_cached_segment(
            segment_cache=segment_cache,
            graph=graph,
            source=current_node,
            target=target_node,
            routing_algorithm=routing_algorithm,
        )
        all_segments.append(segment["nodes"])
        segment_lengths.append(segment["length_m"])
        current_node = target_node

    if final_node is not None:
        segment = get_cached_segment(
            segment_cache=segment_cache,
            graph=graph,
            source=current_node,
            target=final_node,
            routing_algorithm=routing_algorithm,
        )
        all_segments.append(segment["nodes"])
        segment_lengths.append(segment["length_m"])

    route_nodes = merge_segments(all_segments)
    overlap = route_overlap_metrics(graph, route_nodes)

    return {
        "route_nodes": route_nodes,
        "total_length_m": sum(segment_lengths),
        "segment_lengths_m": segment_lengths,
        **overlap,
        "selected_pois": [
            {
                "poi_id": str(row["poi_id"]),
                "name": str(row["name"]),
                "poi_group": str(row["poi_group"]),
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "access_node": int(row["access_node"]),
            }
            for row in ordered_rows
        ],
    }


def get_cached_segment(
    segment_cache: Dict,
    graph: nx.MultiDiGraph,
    source: int,
    target: int,
    routing_algorithm: str,
) -> Dict:
    cache_key = (int(source), int(target))
    if cache_key not in segment_cache:
        segment_cache[cache_key] = build_segment(
            graph=graph,
            source=int(source),
            target=int(target),
            routing_algorithm=routing_algorithm,
        )
    return segment_cache[cache_key]


def route_overlap_metrics(graph: nx.MultiDiGraph, route_nodes: List[int]) -> Dict:
    seen_edges = set()
    repeated_edge_distance_m = 0.0

    for u, v in zip(route_nodes[:-1], route_nodes[1:]):
        edge_key = tuple(sorted((int(u), int(v))))
        edge_data = graph.get_edge_data(u, v)
        edge_length = 0.0
        if edge_data is not None:
            edge_length = min(float(data.get("length", 0.0)) for data in edge_data.values())

        if edge_key in seen_edges:
            repeated_edge_distance_m += edge_length
        else:
            seen_edges.add(edge_key)

    total_length_m = path_length(graph, route_nodes) if len(route_nodes) > 1 else 0.0
    overlap_ratio = repeated_edge_distance_m / total_length_m if total_length_m else 0.0

    return {
        "repeated_edge_distance_m": repeated_edge_distance_m,
        "overlap_ratio": overlap_ratio,
    }


def is_better(candidate: Dict, current_best: Optional[Dict]) -> bool:
    if current_best is None:
        return True
    if candidate["within_target_range"] and not current_best["within_target_range"]:
        return True
    if current_best["within_target_range"] and not candidate["within_target_range"]:
        return False

    overlap_delta = candidate["overlap_ratio"] - current_best["overlap_ratio"]
    if abs(overlap_delta) > OVERLAP_RATIO_TOLERANCE:
        return overlap_delta < 0

    if candidate["distance_error_m"] != current_best["distance_error_m"]:
        return candidate["distance_error_m"] < current_best["distance_error_m"]
    return candidate["total_length_m"] < current_best["total_length_m"]


def nearest_neighbor_order(
    rows: List[pd.Series],
    start_node: int,
    graph: nx.MultiDiGraph,
) -> List[pd.Series]:
    remaining = rows[:]
    ordered = []
    current = start_node

    while remaining:
        current_x = float(graph.nodes[current]["x"])
        current_y = float(graph.nodes[current]["y"])
        next_index, next_row = min(
            enumerate(remaining),
            key=lambda item: (
                (
                    float(graph.nodes[int(item[1]["access_node"])]["x"]) - current_x
                ) ** 2
                + (
                    float(graph.nodes[int(item[1]["access_node"])]["y"]) - current_y
                ) ** 2
            ),
        )
        ordered.append(next_row)
        remaining.pop(next_index)
        current = int(next_row["access_node"])

    return ordered


def angular_order(
    rows: List[pd.Series],
    start_node: int,
    graph: nx.MultiDiGraph,
    reverse: bool = False,
) -> List[pd.Series]:
    start_x = float(graph.nodes[start_node]["x"])
    start_y = float(graph.nodes[start_node]["y"])

    return sorted(
        rows,
        key=lambda row: math.atan2(
            float(graph.nodes[int(row["access_node"])]["y"]) - start_y,
            float(graph.nodes[int(row["access_node"])]["x"]) - start_x,
        ),
        reverse=reverse,
    )


def route_order_variants(
    rows: List[pd.Series],
    start_node: int,
    graph: nx.MultiDiGraph,
) -> List[List[pd.Series]]:
    if len(rows) <= EXACT_ORDER_LIMIT:
        return [list(order) for order in permutations(rows)]

    variants = [
        nearest_neighbor_order(rows, start_node, graph),
        angular_order(rows, start_node, graph),
        angular_order(rows, start_node, graph, reverse=True),
    ]

    unique_variants = []
    seen = set()
    for variant in variants:
        key = tuple(str(row["poi_id"]) for row in variant)
        if key not in seen:
            unique_variants.append(variant)
            seen.add(key)
    return unique_variants


def generate_route(
    start_lat: float,
    start_lon: float,
    min_distance_km: float,
    max_distance_km: float,
    poi_preferences: Dict[str, int],
    routing_algorithm: str = "astar",
    loop_route: bool = True,
    end_lat: Optional[float] = None,
    end_lon: Optional[float] = None,
) -> Dict:
    if min_distance_km <= 0 or max_distance_km <= 0:
        raise RouteGenerationError("Distance values must be positive.")
    if min_distance_km > max_distance_km:
        raise RouteGenerationError("Minimum distance cannot be greater than maximum distance.")

    requested_groups = {
        group: int(count)
        for group, count in poi_preferences.items()
        if int(count) > 0
    }
    total_requested_pois = sum(requested_groups.values())
    if total_requested_pois > MAX_TOTAL_POIS:
        raise RouteGenerationError(
            f"Select at most {MAX_TOTAL_POIS} POIs in total for a fast interactive route."
        )
    for group, count in requested_groups.items():
        if count > MAX_POIS_PER_GROUP:
            raise RouteGenerationError(
                f"This prototype supports up to {MAX_POIS_PER_GROUP} POIs per group. "
                f"'{group}' requested {count}."
            )

    routing_algorithm = routing_algorithm.lower()
    graph = load_graph()
    pois_df = load_pois()

    start_node = ox.distance.nearest_nodes(graph, X=start_lon, Y=start_lat)
    try:
        candidates_df = build_candidate_pois(
            graph=graph,
            pois_df=pois_df,
            start_node=start_node,
            max_distance_km=max_distance_km,
            poi_preferences=requested_groups,
        )
    except RouteGenerationError:
        candidates_df = build_candidate_pois(
            graph=graph,
            pois_df=pois_df,
            start_node=start_node,
            max_distance_km=max_distance_km,
            poi_preferences=requested_groups,
            candidate_distance_ratio=1.5,
        )

    if loop_route:
        final_node = int(start_node)
    elif end_lat is not None and end_lon is not None:
        final_node = int(ox.distance.nearest_nodes(graph, X=end_lon, Y=end_lat))
    else:
        final_node = None

    group_candidate_lists = {}
    for group, desired_count in requested_groups.items():
        top_k = max(desired_count, min(desired_count + 2, TOP_K_PER_GROUP))
        top_group_df = select_top_k_per_group(candidates_df, group, top_k)
        if top_group_df.empty:
            raise RouteGenerationError(f"No candidates found for group: {group}")
        if len(top_group_df) < desired_count:
            raise RouteGenerationError(
                f"Only {len(top_group_df)} candidates found for group '{group}', "
                f"but {desired_count} were requested."
            )
        group_candidate_lists[group] = [row for _, row in top_group_df.iterrows()]

    min_distance_m = min_distance_km * 1000
    max_distance_m = max_distance_km * 1000
    target_distance_m = (min_distance_m + max_distance_m) / 2

    combinations_evaluated = 0
    permutations_evaluated = 0
    feasible_routes_found = 0
    best_result = None
    segment_cache = {}

    group_selection_lists = [
        list(combinations(group_candidate_lists[group], requested_groups[group]))
        for group in group_candidate_lists
    ]

    for grouped_combo in product(*group_selection_lists):
        combinations_evaluated += 1
        combo = [row for group_rows in grouped_combo for row in group_rows]
        access_nodes = [int(row["access_node"]) for row in combo]
        if len(access_nodes) != len(set(access_nodes)):
            continue

        for ordered_combo in route_order_variants(combo, start_node, graph):
            permutations_evaluated += 1
            try:
                route_result = build_loop_for_order(
                    graph=graph,
                    start_node=start_node,
                    ordered_rows=list(ordered_combo),
                    routing_algorithm=routing_algorithm,
                    segment_cache=segment_cache,
                    final_node=final_node,
                )
            except nx.NetworkXNoPath:
                continue

            total_length_m = route_result["total_length_m"]
            route_result["within_target_range"] = min_distance_m <= total_length_m <= max_distance_m
            route_result["distance_error_m"] = abs(total_length_m - target_distance_m)
            feasible_routes_found += 1

            if is_better(route_result, best_result):
                best_result = route_result

    if best_result is None:
        raise RouteGenerationError("No valid route could be generated.")

    route_nodes = [int(node_id) for node_id in best_result["route_nodes"]]
    route_coordinates = [node_coordinates(graph, node_id) for node_id in route_nodes]

    return {
        "start": {
            "input_lat": start_lat,
            "input_lon": start_lon,
            "snapped_node": int(start_node),
            **node_coordinates(graph, int(start_node)),
        },
        "end": (
            {
                "input_lat": end_lat,
                "input_lon": end_lon,
                "snapped_node": int(final_node),
                **node_coordinates(graph, int(final_node)),
            }
            if final_node is not None and not loop_route
            else None
        ),
        "route": {
            "nodes": route_nodes,
            "coordinates": route_coordinates,
            "total_length_m": round(best_result["total_length_m"], 2),
            "total_length_km": round(best_result["total_length_m"] / 1000, 3),
            "within_target_range": best_result["within_target_range"],
            "is_suggestion": not best_result["within_target_range"],
            "distance_error_m": round(best_result["distance_error_m"], 2),
            "overlap_ratio": round(best_result["overlap_ratio"], 4),
            "repeated_edge_distance_m": round(best_result["repeated_edge_distance_m"], 2),
            "segment_lengths_m": [round(length, 2) for length in best_result["segment_lengths_m"]],
        },
        "selected_pois": best_result["selected_pois"],
        "metrics": {
            "routing_algorithm": routing_algorithm,
            "distance_min_m": min_distance_m,
            "distance_max_m": max_distance_m,
            "target_distance_m": target_distance_m,
            "candidate_count": int(len(candidates_df)),
            "cached_segments": len(segment_cache),
            "combinations_evaluated": combinations_evaluated,
            "route_orders_evaluated": permutations_evaluated,
            "permutations_evaluated": permutations_evaluated,
            "feasible_routes_found": feasible_routes_found,
            "loop_route": loop_route,
        },
    }
