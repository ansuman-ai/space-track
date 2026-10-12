"""Unit tests for geometric road clipping in local spatial queries.

Verifies:
1. Geometric bounds: clipped length inside a 1.0 km circle must be < 2 * pi * 1.0 km and <= unclipped length.
2. Exact clipped lengths and passability metrics for Pasang Lhamu Highway near Syabrubesi (Q11).
3. Damage summary local road clipping consistency.
"""

from __future__ import annotations

import math
from pathlib import Path
import pytest

from src.copilot.facts import FactStore
from src.copilot.tools import CopilotTools, clip_linestring_to_circle


def test_linestring_clipping_geometry() -> None:
    """Test pure geometric LineString clipping against circle."""
    center_lon, center_lat = 85.3359, 28.1631
    radius_km = 1.0
    radius_m = radius_km * 1000.0

    # 1. Straight line passing directly through the center (approx 4 km long total)
    # 0.04 degrees latitude is ~4.4 km
    pts_through = [
        [center_lon, center_lat - 0.02],
        [center_lon, center_lat + 0.02],
    ]
    clip_m, unclip_m = clip_linestring_to_circle(pts_through, center_lon, center_lat, radius_km)
    assert clip_m > 0.0
    # Inside a 1 km circle, a diameter path is 2 * R = 2000 m
    assert 1950.0 <= clip_m <= 2050.0
    assert clip_m < 2 * math.pi * radius_m
    assert clip_m <= unclip_m

    # 2. Line entirely inside circle (500 m length)
    pts_inside = [
        [center_lon, center_lat - 0.002],
        [center_lon, center_lat + 0.002],
    ]
    clip_m, unclip_m = clip_linestring_to_circle(pts_inside, center_lon, center_lat, radius_km)
    assert clip_m > 0.0
    assert math.isclose(clip_m, unclip_m, rel_tol=1e-3)

    # 3. Line entirely outside circle (10 km away)
    pts_outside = [
        [center_lon + 0.1, center_lat + 0.1],
        [center_lon + 0.12, center_lat + 0.12],
    ]
    clip_m, unclip_m = clip_linestring_to_circle(pts_outside, center_lon, center_lat, radius_km)
    assert clip_m == 0.0


def test_road_clipping_geometric_bounds() -> None:
    """Verify Q11 road clipping satisfies geometric bounds and exact values.
    
    Clipped length inside a 1 km circle must be < 2 * pi * 1 km and <= unclipped length.
    """
    candidate_runs = [
        Path("/home/zeus/Downloads/project1/runs/test_A_cold_verify"),
        Path("/home/zeus/Downloads/project1/runs/test_A_cold_final2_run1"),
        Path("runs/test_A_cold_verify"),
    ]
    run_dir = next((p for p in candidate_runs if p.exists()), None)
    assert run_dir is not None, "Test run directory not found"

    store = FactStore(run_dir)
    tools = CopilotTools(store)

    res = tools.roads_status(name="Pasang Lhamu Highway", area="Syabrubesi", radius_km=1.0)

    assert res["status"] == "resolved"
    assert res["is_local_area"] is True
    assert res["radius_km"] == 1.0

    total_km = res["total_km"]
    unclipped_total_km = res["unclipped_total_km"]

    # Geometric constraints:
    # 1. Must be positive
    assert total_km > 0.0
    # 2. Inside a 1.0 km radius circle, total road length must be strictly less than circle circumference 2 * pi * R
    assert total_km < 2 * math.pi * 1.0
    # 3. Clipped total must be <= unclipped total of intersecting segments
    assert total_km <= unclipped_total_km

    # Exact expected numbers for Q11 Pasang Lhamu Highway near Syabrubesi (1.0 km radius)
    assert total_km == 2.29
    assert unclipped_total_km == 2.39
    assert res["destroyed_km"] == 1.46
    assert res["possibly_damaged_km"] == 0.64
    assert res["not_affected_km"] == 0.19
    assert res["cloud_unverified_km"] == 0.0
    assert res["passability"] == "CLOSED / BLOCKED / IMPASSABLE"
    assert res["is_open"] is False


def test_damage_summary_road_clipping() -> None:
    """Verify damage_summary clips road geometries in local queries."""
    candidate_runs = [
        Path("/home/zeus/Downloads/project1/runs/test_A_cold_verify"),
        Path("/home/zeus/Downloads/project1/runs/test_A_cold_final2_run1"),
        Path("runs/test_A_cold_verify"),
    ]
    run_dir = next((p for p in candidate_runs if p.exists()), None)
    assert run_dir is not None, "Test run directory not found"

    store = FactStore(run_dir)
    tools = CopilotTools(store)

    res = tools.damage_summary(area="Syabrubesi", radius_km=1.0)
    assert res["is_local_area"] is True
    assert "roads" in res

    roads = res["roads"]
    assert roads["total_km"] > 0.0
    assert roads["total_km"] <= roads["unclipped_total_km"]
    assert roads["total_km"] == 12.81
    assert roads["unclipped_total_km"] == 13.0
    assert roads["destroyed_km"] == 2.0
