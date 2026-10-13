"""Free map services: OpenStreetMap Nominatim (geocoding) + OSRM public server (road routing).
No API key needed. Falls back to straight-line (haversine) if the network fails."""
import requests
from algos import haversine

UA = {"User-Agent": "ShortestPathKivyApp/1.0 (educational)"}
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OSRM = "https://router.project-osrm.org"


def geocode(text):
    r = requests.get(NOMINATIM, params={"q": text, "format": "json", "limit": 1}, headers=UA, timeout=15)
    r.raise_for_status()
    js = r.json()
    if not js:
        raise ValueError("Place not found: " + text)
    return float(js[0]["lat"]), float(js[0]["lon"]), js[0].get("display_name", text)


def road_matrix(points):
    """Distance matrix in metres via OSRM /table. Falls back to haversine."""
    try:
        coords = ";".join(f"{lo},{la}" for la, lo in points)
        r = requests.get(f"{OSRM}/table/v1/driving/{coords}", params={"annotations": "distance"},
                         headers=UA, timeout=20)
        r.raise_for_status()
        m = r.json()["distances"]
        if all(x is not None for row in m for x in row):
            return m, "road (OSRM)"
    except Exception:
        pass
    return [[haversine(a, b) for b in points] for a in points], "straight-line (offline fallback)"


def road_route(a, b):
    """Actual road distance (m) and duration (s) from A to B."""
    try:
        r = requests.get(f"{OSRM}/route/v1/driving/{a[1]},{a[0]};{b[1]},{b[0]}",
                         params={"overview": "false"}, headers=UA, timeout=20)
        r.raise_for_status()
        rt = r.json()["routes"][0]
        return rt["distance"], rt["duration"]
    except Exception:
        return None, None
