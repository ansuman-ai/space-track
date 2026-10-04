"""
Destination Extraction for Layer 5 Routing.
Extracts health facilities / hospitals in the buffered region as target destinations.
Falls back to place=town/city if no health facilities exist.
"""

import logging
from typing import List, Dict, Any, Optional
import geopandas as gpd
from shapely.geometry import Point

logger = logging.getLogger("l5_destinations")


def extract_destinations(
    hospitals_path: str = "data/raw/osm_buffered/osm_hospitals.geojson",
    places_path: str = "data/raw/osm_buffered/osm_places.geojson",
    utm_crs: str = "EPSG:32645"
) -> gpd.GeoDataFrame:
    """
    Extracts target destinations in the buffered area.
    Prefers OSM hospitals / health facilities; if none found, falls back to place=town/city.
    """
    h_gdf = gpd.read_file(hospitals_path)
    records = []

    if len(h_gdf) > 0:
        h_utm = h_gdf.to_crs(utm_crs)
        for idx, row in h_utm.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            pt = geom.centroid
            oid = row.get("@osmId", f"hosp_{idx}")
            name = row.get("name")
            if name is None or str(name) == "nan":
                name = f"Health Facility ({oid})"
            facility_type = row.get("amenity", row.get("healthcare", "hospital"))

            records.append({
                "destination_id": str(oid),
                "name": str(name),
                "category": "health_facility",
                "facility_type": str(facility_type),
                "geometry": Point(pt.x, pt.y)
            })
    else:
        logger.warning("No health facilities found in buffered area; falling back to place=town/city...")
        p_gdf = gpd.read_file(places_path)
        p_towns = p_gdf[p_gdf["place"].isin(["city", "town"])].to_crs(utm_crs)
        for idx, row in p_towns.iterrows():
            pt = row.geometry.centroid
            oid = row.get("@osmId", f"place_{idx}")
            name = row.get("name", f"Town ({oid})")
            records.append({
                "destination_id": str(oid),
                "name": str(name),
                "category": "town_fallback",
                "facility_type": str(row.get("place", "town")),
                "geometry": Point(pt.x, pt.y)
            })

    dest_gdf = gpd.GeoDataFrame(records, crs=utm_crs)

    print("\n--- DESTINATIONS USED IN ROUTING ANALYSIS ---")
    print(f"Total destinations: {len(dest_gdf)}")
    for idx, r in dest_gdf.iterrows():
        did = r["destination_id"]
        nm = r["name"]
        ft = r["facility_type"]
        pt = r.geometry
        print(f"  {did:20s} | {nm:42s} | type: {ft:12s} | UTM: ({pt.x:.1f}, {pt.y:.1f})")

    return dest_gdf
