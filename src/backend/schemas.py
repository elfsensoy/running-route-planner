from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class RouteRequest(BaseModel):
    start_lat: float = Field(..., ge=-90, le=90)
    start_lon: float = Field(..., ge=-180, le=180)
    min_distance_km: float = Field(..., gt=0)
    max_distance_km: float = Field(..., gt=0)
    poi_preferences: Dict[str, int] = Field(default_factory=dict)
    selected_poi_ids: List[str] = Field(default_factory=list)
    elevation_preference: Literal["low", "medium", "high"] = "medium"
    loop_route: bool = True
    end_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    end_lon: Optional[float] = Field(default=None, ge=-180, le=180)

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
            if count > 10:
                raise ValueError(f"Select at most 10 POIs for '{group}'")
        if sum(selected.values()) > 10:
            raise ValueError("Select at most 10 POIs in total")
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
    is_suggestion: bool
    distance_error_m: float
    overlap_ratio: float
    repeated_edge_distance_m: float
    segment_lengths_m: List[float]
    elevation: dict


class RouteResponse(BaseModel):
    start: dict
    end: Optional[dict] = None
    route: RouteInfo
    route_options: List[dict] = Field(default_factory=list)
    selected_pois: List[SelectedPoi]
    metrics: dict
