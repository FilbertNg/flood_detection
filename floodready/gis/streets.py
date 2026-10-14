"""Named streets for a township from OpenStreetMap (build plan task G1).

Segments with the same name are merged into one street with a stable
`street_id` = <TOWNSHIP_ID>-<slug>. Data © OpenStreetMap contributors (ODbL).
"""
from __future__ import annotations

import math
import re

import geopandas as gpd
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge

OVERPASS_URLS = (  # public servers, tried in order (the main one often returns 504 when busy)
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
ROAD_CLASSES = ("motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
                "living_street", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link")
_RANK = {name: i for i, name in enumerate(ROAD_CLASSES)}
METRIC_CRS = 32647  # UTM 47N, covers the Klang Valley


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def overpass_query(lat: float, lon: float, radius_m: int) -> str:
    classes = "|".join(ROAD_CLASSES)
    return (f'[out:json][timeout:90];\n'
            f'way(around:{radius_m},{lat},{lon})["highway"~"^({classes})$"]["name"];\n'
            f'out geom;')


def tile_bboxes(lat: float, lon: float, radius_m: int, n: int) -> list[tuple[float, float, float, float]]:
    """Split the square around a centre into n x n (south, west, north, east) tiles.
    Small tiles keep each Overpass query light enough not to be refused."""
    dlat = radius_m / 111_320
    dlon = radius_m / (111_320 * math.cos(math.radians(lat)))
    south, west = lat - dlat, lon - dlon
    step_lat, step_lon = 2 * dlat / n, 2 * dlon / n
    return [(south + i * step_lat, west + j * step_lon, south + (i + 1) * step_lat, west + (j + 1) * step_lon)
            for i in range(n) for j in range(n)]


def overpass_bbox_query(bbox: tuple[float, float, float, float]) -> str:
    classes = "|".join(ROAD_CLASSES)
    s, w, n, e = bbox
    return (f'[out:json][timeout:60];\n'
            f'way({s:.5f},{w:.5f},{n:.5f},{e:.5f})["highway"~"^({classes})$"]["name"];\n'
            f'out geom;')


def merge_payloads(payloads: list[dict]) -> dict:
    """Combine tile responses; a road crossing a tile edge appears once."""
    seen, elements = set(), []
    for payload in payloads:
        for element in payload.get("elements", []):
            key = (element.get("type"), element.get("id"))
            if key not in seen:
                seen.add(key)
                elements.append(element)
    return {"elements": elements}


def streets_from_overpass(payload: dict, township_id: str) -> gpd.GeoDataFrame:
    """Merge named road segments into one row per street name."""
    by_name: dict[str, dict] = {}
    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        name, highway = tags.get("name"), tags.get("highway")
        if element.get("type") != "way" or not name or highway not in _RANK:
            continue
        line = LineString([(p["lon"], p["lat"]) for p in element["geometry"]])
        entry = by_name.setdefault(name.strip(), {"lines": [], "highway": highway})
        entry["lines"].append(line)
        if _RANK[highway] < _RANK[entry["highway"]]:
            entry["highway"] = highway

    gdf = gpd.GeoDataFrame(
        [{"township_id": township_id, "name": name, "highway": entry["highway"],
          "geometry": linemerge(MultiLineString(entry["lines"]))} for name, entry in by_name.items()],
        geometry="geometry", crs=4326)
    metric = gdf.to_crs(METRIC_CRS)
    gdf["length_m"] = metric.length.round(1)

    # When names slugify alike, the longest street keeps the clean ID (ties: by name).
    used, ids = set(), {}
    for i in gdf.sort_values(["length_m", "name"], ascending=[False, True]).index:
        slug = f"{township_id}-{slugify(gdf.at[i, 'name'])}"
        street_id, n = slug, 1
        while street_id in used:
            n += 1
            street_id = f"{slug}-{n}"
        used.add(street_id)
        ids[i] = street_id
    gdf.insert(0, "street_id", gdf.index.map(ids))
    centroids = metric.centroid.to_crs(4326)
    gdf["centroid_lat"] = centroids.y.round(6)
    gdf["centroid_lon"] = centroids.x.round(6)
    return gdf.sort_values("street_id").reset_index(drop=True)
