"""Free map services: OpenStreetMap Nominatim (geocoding) + OSRM public server (road routing).
No API key needed. Falls back to straight-line (haversine) if the network fails.

Speed notes: one shared HTTP session (keep-alive), compact polyline geometry instead of
GeoJSON, 'simplified' overview for long trips, geocode cache."""
import requests
from algos import haversine

UA = {"User-Agent": "ShortestPathKivyApp/1.0 (educational)"}
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OSRM = "https://router.project-osrm.org"
LONG_TRIP_M = 150_000      # beyond this, ask OSRM for a simplified (far smaller) geometry

SESSION = requests.Session()
SESSION.headers.update(UA)
_geo_cache = {}


def geocode(text):
    key = text.strip().lower()
    if key in _geo_cache:
        return _geo_cache[key]
    r = SESSION.get(NOMINATIM, params={"q": text, "format": "json", "limit": 1}, timeout=15)
    r.raise_for_status()
    js = r.json()
    if not js:
        raise ValueError("Place not found: " + text)
    res = (float(js[0]["lat"]), float(js[0]["lon"]), js[0].get("display_name", text))
    _geo_cache[key] = res
    return res


def decode_polyline(s, factor=1e5):
    """Google/OSRM encoded polyline -> [(lat, lon), ...] (pure python, no API involved)."""
    coords, i, lat, lon = [], 0, 0, 0
    while i < len(s):
        for which in (0, 1):
            shift = result = 0
            while True:
                b = ord(s[i]) - 63
                i += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            d = ~(result >> 1) if result & 1 else result >> 1
            if which == 0:
                lat += d
            else:
                lon += d
        coords.append((lat / factor, lon / factor))
    return coords


def _decimate(coords, limit=300):
    if len(coords) <= limit:
        return coords
    step = len(coords) / float(limit)
    out = [coords[int(i * step)] for i in range(limit)]
    out.append(coords[-1])
    return out


def road_matrix(points):
    """Distance matrix in metres via OSRM /table. Falls back to haversine."""
    try:
        coords = ";".join(f"{lo},{la}" for la, lo in points)
        r = SESSION.get(f"{OSRM}/table/v1/driving/{coords}", params={"annotations": "distance"}, timeout=20)
        r.raise_for_status()
        m = r.json()["distances"]
        if all(x is not None for row in m for x in row):
            return m, "road (OSRM)"
    except Exception:
        pass
    return [[haversine(a, b) for b in points] for a in points], "straight-line (road service unavailable)"


def route_options(points, alternatives=False, timeout=25):
    """Road geometry through `points` in the given order.
    Returns a list of {'dist','dur','coords'[(lat,lon)...],'road'(bool)}.
    alternatives=True asks OSRM for extra A->B routes (only works for 2 points)."""
    try:
        far = max(haversine(points[0], p) for p in points[1:]) > LONG_TRIP_M
        coords = ";".join(f"{lo},{la}" for la, lo in points)
        params = {"overview": "simplified" if far else "full", "geometries": "polyline"}
        if alternatives and len(points) == 2:
            params["alternatives"] = "true"
        r = SESSION.get(f"{OSRM}/route/v1/driving/{coords}", params=params, timeout=timeout)
        r.raise_for_status()
        out = []
        for rt in r.json()["routes"]:
            out.append({"dist": rt["distance"], "dur": rt["duration"],
                        "coords": _decimate(decode_polyline(rt["geometry"])), "road": True})
        if out:
            return out
    except Exception:
        pass
    d = sum(haversine(points[i], points[i + 1]) for i in range(len(points) - 1))
    return [{"dist": d, "dur": None, "coords": list(points), "road": False}]