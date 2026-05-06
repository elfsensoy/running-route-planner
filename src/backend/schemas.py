from typing import Dict, List, Literal

from pydantic import BaseModel, Field, field_validator


class RouteRequest(BaseModel):
    start_lat: float = Field(..., ge=-90, le=90)
    start_lon: float = Field(..., ge=-180, le=180)
    min_distance_km: float = Field(..., gt=0)
    max_distance_km: float = Field(..., gt=0)
    poi_preferences: Dict[str, int] = Field(default_factory=dict)
    routing_algorithm: Literal["astar", "dijkstra"] = "astar"
    elevation_preference: Literal["low", "medium", "high", "none"] = "none"

    @field_validator("max_distance_km")
    @classmethod
    def validate_distance_range(cls, max_distance_km, info):
        min_distance_km = info.data.get("min_distance_km")
        if min_distance_km is not None and max_distance_km < min_distance_km:
            raise ValueError("max_distance_km must be greater than or equal to min_distance_km")
        return max_distance_km

    @field_validator("poi_preferences")
    @classmethod
    def validate_poi_preferences(cls, poi_preferences):
        selected = {group: count for group, count in poi_preferences.items() if count > 0}
        if not selected:
            raise ValueError("Select at least one POI category")
        for group, count in selected.items():
            if count != 1:
                raise ValueError(
                    f"This prototype supports one POI per selected group. '{group}' requested {count}."
                )
        return poi_preferences


class Coordinate(BaseModel):
    lat: float
    lon: float


class SelectedPoi(Coordinate):
    poi_id: str
    name: str
    poi_group: str
    access_node: int


class RouteInfo(BaseModel):
    nodes: List[int]
    coordinates: List[Coordinate]
    total_length_m: float
    total_length_km: float
    within_target_range: bool
    distance_error_m: float
    segment_lengths_m: List[float]


class RouteResponse(BaseModel):
    start: dict
    route: RouteInfo
    selected_pois: List[SelectedPoi]
    metrics: dict
