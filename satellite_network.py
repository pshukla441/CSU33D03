from __future__ import annotations

"""A small deterministic satellite-network simulator.

Features
--------
- Fake satellite catalog with predictable, time-varying positions.
- Helpers to query the closest satellite to a latitude, longitude, or point.
- Route planning across satellites from one ground point to another.

The same timestamp always produces the same positions.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import heapq
import math
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

EARTH_RADIUS_KM = 6371.0
DEFAULT_GROUND_TO_SAT_MAX_KM = 7000.0
DEFAULT_INTER_SAT_MAX_KM = 12000.0
DEFAULT_ROUTE_SATELLITE_LIMIT = 12
DEFAULT_EPOCH = datetime(2025, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class Satellite:
    """Defines a fake satellite and its deterministic trajectory parameters."""

    sat_id: str
    name: str
    altitude_km: float
    base_lat_deg: float
    amplitude_deg: float
    period_seconds: float
    lon0_deg: float
    lon_rate_deg_per_sec: float
    phase_deg: float


# A fake constellation spread across several orbital planes.
SATELLITES: List[Satellite] = [
    Satellite("SAT-001", "Aster-1", 550,   0, 25,  95 * 60,  -170,  0.055,   0),
    Satellite("SAT-002", "Aster-2", 550,   5, 22,  97 * 60,  -130,  0.057,  35),
    Satellite("SAT-003", "Aster-3", 575, -10, 30, 100 * 60,   -85,  0.053,  80),
    Satellite("SAT-004", "Aster-4", 575,  12, 27, 102 * 60,   -40,  0.052, 110),
    Satellite("SAT-005", "Aster-5", 600, -15, 35, 105 * 60,    10,  0.050, 145),
    Satellite("SAT-006", "Aster-6", 600,   8, 28,  98 * 60,    50,  0.058, 190),
    Satellite("SAT-007", "Aster-7", 625, -20, 32, 110 * 60,    95,  0.047, 220),
    Satellite("SAT-008", "Aster-8", 625,  18, 24, 108 * 60,   135,  0.049, 255),
    Satellite("SAT-009", "Aster-9", 650,  -5, 26, 112 * 60,   175,  0.046, 285),
    Satellite("SAT-010", "Aster-10", 650, 10, 31, 115 * 60,  -145,  0.045, 315),
    Satellite("SAT-011", "Aster-11", 675, -12, 29, 118 * 60, -100,  0.044, 340),
    Satellite("SAT-012", "Aster-12", 675, 16, 23, 120 * 60,   -55,  0.043,  20),
]


@dataclass(frozen=True)
class SatellitePosition:
    satellite: Satellite
    latitude_deg: float
    longitude_deg: float
    altitude_km: float
    timestamp: datetime


@dataclass(frozen=True)
class RouteResult:
    timestamp: datetime
    source: Tuple[float, float]
    destination: Tuple[float, float]
    node_path: List[str]
    total_distance_km: float
    edge_breakdown_km: List[float]


# ----------------------------- Time + motion helpers -----------------------------


def _ensure_utc(dt: Optional[datetime]) -> datetime:
    """Normalize a datetime to timezone-aware UTC.

    If dt is None, uses current UTC time.
    If dt is naive, interprets it as UTC.
    """
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)



def _seconds_since_epoch(dt: datetime, epoch: datetime = DEFAULT_EPOCH) -> float:
    return (_ensure_utc(dt) - epoch).total_seconds()



def _wrap_longitude(lon_deg: float) -> float:
    wrapped = (lon_deg + 180.0) % 360.0 - 180.0
    # Keep +180 instead of -180 if it lands exactly there.
    if wrapped == -180.0 and lon_deg > 0:
        return 180.0
    return wrapped



def satellite_position(
    satellite: Satellite,
    at_time: Optional[datetime] = None,
    *,
    epoch: datetime = DEFAULT_EPOCH,
) -> SatellitePosition:
    """Return the deterministic position of one satellite at a given time.

    Latitude oscillates sinusoidally, while longitude advances at a constant rate.
    The parameters are chosen to create plausible-looking motion, not orbital fidelity.
    """
    t = _ensure_utc(at_time)
    elapsed = _seconds_since_epoch(t, epoch=epoch)
    phase_rad = math.radians(satellite.phase_deg)
    lat = satellite.base_lat_deg + satellite.amplitude_deg * math.sin(
        (2.0 * math.pi * elapsed / satellite.period_seconds) + phase_rad
    )
    lat = max(-90.0, min(90.0, lat))

    # Add a slight wobble to longitude so paths do not look perfectly linear.
    lon = (
        satellite.lon0_deg
        + satellite.lon_rate_deg_per_sec * elapsed
        + 4.0 * math.sin((2.0 * math.pi * elapsed / (satellite.period_seconds * 1.7)) + phase_rad / 2.0)
    )
    lon = _wrap_longitude(lon)

    return SatellitePosition(
        satellite=satellite,
        latitude_deg=lat,
        longitude_deg=lon,
        altitude_km=satellite.altitude_km,
        timestamp=t,
    )



def all_satellite_positions(
    at_time: Optional[datetime] = None,
    satellites: Sequence[Satellite] = SATELLITES,
) -> List[SatellitePosition]:
    """Return positions for all satellites at a given time."""
    t = _ensure_utc(at_time)
    return [satellite_position(s, t) for s in satellites]


# ----------------------------- Distance calculations -----------------------------


def great_circle_distance_km(
    lat1_deg: float,
    lon1_deg: float,
    lat2_deg: float,
    lon2_deg: float,
    radius_km: float = EARTH_RADIUS_KM,
) -> float:
    """Haversine distance over the Earth's surface."""
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1_deg, lon1_deg, lat2_deg, lon2_deg))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    c = 2.0 * math.asin(min(1.0, math.sqrt(a)))
    return radius_km * c



def _ecef_from_lat_lon_alt(lat_deg: float, lon_deg: float, alt_km: float) -> Tuple[float, float, float]:
    """Convert geodetic lat/lon with spherical Earth approximation to ECEF XYZ."""
    lat_rad = math.radians(lat_deg)
    lon_rad = math.radians(lon_deg)
    r = EARTH_RADIUS_KM + alt_km
    x = r * math.cos(lat_rad) * math.cos(lon_rad)
    y = r * math.cos(lat_rad) * math.sin(lon_rad)
    z = r * math.sin(lat_rad)
    return x, y, z



def straight_line_distance_km(
    lat1_deg: float,
    lon1_deg: float,
    alt1_km: float,
    lat2_deg: float,
    lon2_deg: float,
    alt2_km: float,
) -> float:
    """3D straight-line distance using a spherical Earth approximation."""
    x1, y1, z1 = _ecef_from_lat_lon_alt(lat1_deg, lon1_deg, alt1_km)
    x2, y2, z2 = _ecef_from_lat_lon_alt(lat2_deg, lon2_deg, alt2_km)
    return math.dist((x1, y1, z1), (x2, y2, z2))


# ----------------------------- Query helpers -----------------------------


def closest_satellite_to_latitude(
    latitude_deg: float,
    at_time: Optional[datetime] = None,
    satellites: Sequence[Satellite] = SATELLITES,
) -> SatellitePosition:
    """Return the satellite whose current latitude is closest to latitude_deg."""
    positions = all_satellite_positions(at_time, satellites)
    return min(positions, key=lambda p: abs(p.latitude_deg - latitude_deg))



def closest_satellite_to_longitude(
    longitude_deg: float,
    at_time: Optional[datetime] = None,
    satellites: Sequence[Satellite] = SATELLITES,
) -> SatellitePosition:
    """Return the satellite whose current longitude is closest to longitude_deg."""
    positions = all_satellite_positions(at_time, satellites)

    def lon_delta(a: float, b: float) -> float:
        return abs((a - b + 180.0) % 360.0 - 180.0)

    return min(positions, key=lambda p: lon_delta(p.longitude_deg, longitude_deg))



def closest_satellite_to_point(
    latitude_deg: float,
    longitude_deg: float,
    at_time: Optional[datetime] = None,
    satellites: Sequence[Satellite] = SATELLITES,
) -> SatellitePosition:
    """Return the satellite closest to a ground point by 3D straight-line distance."""
    positions = all_satellite_positions(at_time, satellites)
    return min(
        positions,
        key=lambda p: straight_line_distance_km(
            latitude_deg,
            longitude_deg,
            0.0,
            p.latitude_deg,
            p.longitude_deg,
            p.altitude_km,
        ),
    )


# ----------------------------- Routing -----------------------------


def _build_network_edges(
    positions: Sequence[SatellitePosition],
    source: Tuple[float, float],
    destination: Tuple[float, float],
    *,
    max_ground_to_sat_km: float,
    max_inter_sat_km: float,
    max_satellites_in_route: int,
) -> Dict[str, List[Tuple[str, float]]]:
    """Build a sparse graph connecting ground endpoints and reachable satellites.

    Nodes:
        SRC, DST, and one node per satellite (using sat_id)
    Weights:
        3D straight-line distance.
    Constraints:
        - Ground connects only to satellites within max_ground_to_sat_km.
        - Satellites connect to each other within max_inter_sat_km.
        - Optionally, only the N satellites nearest to either endpoint are considered.
    """
    src_lat, src_lon = source
    dst_lat, dst_lon = destination

    scored_positions = []
    for p in positions:
        src_d = straight_line_distance_km(src_lat, src_lon, 0.0, p.latitude_deg, p.longitude_deg, p.altitude_km)
        dst_d = straight_line_distance_km(dst_lat, dst_lon, 0.0, p.latitude_deg, p.longitude_deg, p.altitude_km)
        scored_positions.append((min(src_d, dst_d), p, src_d, dst_d))

    scored_positions.sort(key=lambda item: item[0])
    chosen = scored_positions[: max(2, min(max_satellites_in_route, len(scored_positions)))]

    chosen_positions = [item[1] for item in chosen]
    src_distances = {item[1].satellite.sat_id: item[2] for item in chosen}
    dst_distances = {item[1].satellite.sat_id: item[3] for item in chosen}

    graph: Dict[str, List[Tuple[str, float]]] = {"SRC": [], "DST": []}
    for p in chosen_positions:
        graph[p.satellite.sat_id] = []

    # Ground to satellites.
    for p in chosen_positions:
        sid = p.satellite.sat_id
        src_d = src_distances[sid]
        dst_d = dst_distances[sid]
        if src_d <= max_ground_to_sat_km:
            graph["SRC"].append((sid, src_d))
            graph[sid].append(("SRC", src_d))
        if dst_d <= max_ground_to_sat_km:
            graph[sid].append(("DST", dst_d))
            graph["DST"].append((sid, dst_d))

    # Inter-satellite links.
    for i, a in enumerate(chosen_positions):
        for b in chosen_positions[i + 1 :]:
            d = straight_line_distance_km(
                a.latitude_deg,
                a.longitude_deg,
                a.altitude_km,
                b.latitude_deg,
                b.longitude_deg,
                b.altitude_km,
            )
            if d <= max_inter_sat_km:
                a_id = a.satellite.sat_id
                b_id = b.satellite.sat_id
                graph[a_id].append((b_id, d))
                graph[b_id].append((a_id, d))

    return graph



def _dijkstra(graph: Dict[str, List[Tuple[str, float]]], start: str, goal: str) -> Tuple[List[str], float, List[float]]:
    heap: List[Tuple[float, str]] = [(0.0, start)]
    dist: Dict[str, float] = {start: 0.0}
    prev: Dict[str, Tuple[str, float]] = {}

    while heap:
        current_dist, node = heapq.heappop(heap)
        if current_dist > dist.get(node, math.inf):
            continue
        if node == goal:
            break
        for neighbor, weight in graph.get(node, []):
            cand = current_dist + weight
            if cand < dist.get(neighbor, math.inf):
                dist[neighbor] = cand
                prev[neighbor] = (node, weight)
                heapq.heappush(heap, (cand, neighbor))

    if goal not in dist:
        raise ValueError("No route found with the current network thresholds.")

    # Reconstruct path.
    node_path = [goal]
    edge_weights: List[float] = []
    cursor = goal
    while cursor != start:
        parent, weight = prev[cursor]
        node_path.append(parent)
        edge_weights.append(weight)
        cursor = parent
    node_path.reverse()
    edge_weights.reverse()
    return node_path, dist[goal], edge_weights



def optimal_satellite_route(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
    at_time: Optional[datetime] = None,
    satellites: Sequence[Satellite] = SATELLITES,
    *,
    max_ground_to_sat_km: float = DEFAULT_GROUND_TO_SAT_MAX_KM,
    max_inter_sat_km: float = DEFAULT_INTER_SAT_MAX_KM,
    max_satellites_in_route: int = DEFAULT_ROUTE_SATELLITE_LIMIT,
) -> RouteResult:
    """Find the minimum-distance route from ground point A to ground point B.

    The route can travel:
        source ground point -> satellite(s) -> destination ground point

    The function uses Dijkstra over a graph built from the satellites' positions
    at the requested time.
    """
    t = _ensure_utc(at_time)
    positions = all_satellite_positions(t, satellites)
    graph = _build_network_edges(
        positions,
        source=(latitude_a, longitude_a),
        destination=(latitude_b, longitude_b),
        max_ground_to_sat_km=max_ground_to_sat_km,
        max_inter_sat_km=max_inter_sat_km,
        max_satellites_in_route=max_satellites_in_route,
    )
    node_path, total_km, edge_breakdown = _dijkstra(graph, "SRC", "DST")
    return RouteResult(
        timestamp=t,
        source=(latitude_a, longitude_a),
        destination=(latitude_b, longitude_b),
        node_path=node_path,
        total_distance_km=total_km,
        edge_breakdown_km=edge_breakdown,
    )


# ----------------------------- Pretty-print helpers -----------------------------


def describe_position(position: SatellitePosition) -> str:
    return (
        f"{position.satellite.name} ({position.satellite.sat_id}) at "
        f"lat={position.latitude_deg:.2f}, lon={position.longitude_deg:.2f}, "
        f"alt={position.altitude_km:.0f} km @ {position.timestamp.isoformat()}"
    )



def describe_route(route: RouteResult) -> str:
    segments = " + ".join(f"{d:.1f} km" for d in route.edge_breakdown_km)
    path = " -> ".join(route.node_path)
    return (
        f"Route @ {route.timestamp.isoformat()}\n"
        f"Path: {path}\n"
        f"Total distance: {route.total_distance_km:.1f} km\n"
        f"Segments: {segments}"
    )


# ----------------------------- Example usage -----------------------------


if __name__ == "__main__":
    demo_time = datetime(2026, 3, 25, 12, 0, tzinfo=timezone.utc)

    print("All satellite positions at demo time:")
    for pos in all_satellite_positions(demo_time):
        print("  ", describe_position(pos))

    print("\nClosest to latitude 40:")
    print("  ", describe_position(closest_satellite_to_latitude(40.0, demo_time)))

    print("\nClosest to longitude -75:")
    print("  ", describe_position(closest_satellite_to_longitude(-75.0, demo_time)))

    print("\nClosest to point (37.7749, -122.4194):")
    print("  ", describe_position(closest_satellite_to_point(37.7749, -122.4194, demo_time)))

    print("\nRoute from San Francisco to Tokyo:")
    route = optimal_satellite_route(
        37.7749,
        -122.4194,
        35.6762,
        139.6503,
        demo_time,
        max_ground_to_sat_km=7000.0,
        max_inter_sat_km=12000.0,
        max_satellites_in_route=12,
    )
    print(describe_route(route))
