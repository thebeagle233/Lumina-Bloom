from __future__ import annotations

import math
from typing import Any, Dict, List

import requests

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
TIMEOUT_SECONDS = 20


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius_m * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _display_name(tags: Dict[str, Any]) -> str:
    for key in ("name:en", "official_name:en", "short_name:en", "name", "official_name", "short_name"):
        if tags.get(key):
            return str(tags[key])
    return "Nearby outdoor spot"


def _place_type(tags: Dict[str, Any]) -> str:
    if tags.get("leisure") == "park":
        return "park"
    if tags.get("leisure") == "garden":
        return "garden"
    if tags.get("natural") == "beach":
        return "beach"
    if tags.get("natural") == "wood":
        return "woodland"
    return tags.get("leisure") or tags.get("natural") or tags.get("landuse") or "outdoor_spot"


def _fetch_overpass(query: str) -> Dict[str, Any]:
    last_error = None
    headers = {"User-Agent": "LuminaBloomDemo/1.2", "Accept": "application/json"}
    for url in OVERPASS_URLS:
        try:
            response = requests.post(url, data=query.encode("utf-8"), timeout=TIMEOUT_SECONDS, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"all Overpass endpoints failed: {last_error}")


def fetch_sunny_places(lat: float, lon: float, radius_m: int = 1500) -> Dict[str, Any]:
    query = f"""
    [out:json][timeout:20];
    (
      nwr(around:{radius_m},{lat},{lon})["leisure"~"park|garden|nature_reserve"];
      nwr(around:{radius_m},{lat},{lon})["natural"~"beach|wood|grassland"];
      nwr(around:{radius_m},{lat},{lon})["landuse"="recreation_ground"];
    );
    out center tags;
    """.strip()

    payload = _fetch_overpass(query)
    candidates: List[Dict[str, Any]] = []

    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        place_lat = element.get("lat") or element.get("center", {}).get("lat")
        place_lon = element.get("lon") or element.get("center", {}).get("lon")
        if place_lat is None or place_lon is None:
            continue

        distance_m = haversine_m(lat, lon, float(place_lat), float(place_lon))
        place_type = _place_type(tags)
        coarse_score = 1000 - distance_m
        if place_type == "park":
            coarse_score += 120
        elif place_type == "garden":
            coarse_score += 90
        elif place_type == "beach":
            coarse_score += 70

        candidates.append(
            {
                "id": f"osm-{element.get('type', 'item')}-{element.get('id', 'x')}",
                "name": _display_name(tags),
                "raw_name": str(tags.get("name", "")),
                "name_en": str(tags.get("name:en", "")),
                "type": place_type,
                "distance_m": round(distance_m),
                "walk_min": max(1, round(distance_m / 80)),
                "lat": float(place_lat),
                "lon": float(place_lon),
                "coarse_score": round(coarse_score, 2),
                "map_url": f"https://www.openstreetmap.org/?mlat={place_lat}&mlon={place_lon}#map=18/{place_lat}/{place_lon}",
            }
        )

    candidates.sort(key=lambda item: (-item["coarse_score"], item["distance_m"], item["name"]))
    return {
        "source": "openstreetmap-overpass",
        "count": len(candidates),
        "candidate_places": candidates[:10],
    }
