"""
Layer 4: Critical Infrastructure Exposure & EMS-Style Damage Grading.
Integrates pre-event OSM data with Layer 2 multi-class flood hazard footprints.
"""

from .coverage import compute_osm_coverage
from .grading import grade_buildings, grade_roads, grade_bridges
from .quicklook import render_l4_quicklook

__all__ = [
    "compute_osm_coverage",
    "grade_buildings",
    "grade_roads",
    "grade_bridges",
    "render_l4_quicklook",
]
