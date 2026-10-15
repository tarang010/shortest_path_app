"""Free map services only (no API keys, no Google):
  * OpenStreetMap Nominatim  -> place search
  * OSRM (FOSSGIS community servers for car/bicycle/foot, project-osrm demo as car fallback)

Realistic road tracing: the full-detail road geometry is downloaded (compact polyline) and
pre-simplified into several zoom levels so long inter-state routes stay smooth and fast."""
import math
import requests
from algos import haversine

UA = {"User-Agent": "TarangNav/2.0 (educational app)"}
NOMINATIM = "https://nominatim.openstreetmap.org/search"
SERVICES = {
    "car":  ["https://routing.openstreetmap.de/routed-car", "https://router.project-osrm.org"],
    "bike": ["https://routing.openstreetmap.de/routed-bike"],
    "foot": ["https://routing.openstreetmap.de/routed-foot"],
}
SESSION = requests.Session()
SESSION.headers.update(UA)
_geo_cache = {}
LOD_ZOOMS = (3, 5, 7, 9, 11, 13, 15)


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


def _radial(coords, tol):
    """O(n) simplification: drop points closer than `tol` degrees to the last kept point.
    Never creates a segment longer than the original point gaps, so corners stay on the road."""
    if len(coords) < 3:
        return coords
    out = [coords[0]]
    lx, ly = coords[0]
    t2 = tol * tol
    for p in coords[1:-1]:
        dx, dy = p[0] - lx, p[1] - ly
        if dx * dx + dy * dy >= t2:
            out.append(p)
            lx, ly = p
    out.append(coords[-1])
    return out


def make_lods(coords):
    """[(zoom, simplified_coords), ...] with ~1 px tolerance at that zoom, finest last."""
    lods = []
    for z in LOD_ZOOMS:
        tol = 1.0 * 360.0 / (256.0 * (2 ** z))
        lods.append((z, _radial(coords, tol)))
    return lods


def finish(route):
    route["lods"] = make_lods(route["coords"])
    return route


def _get(profile, path, params, timeout):
    last = None
    for base in SERVICES[profile]:
        try:
            r = SESSION.get(base + path, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:      # try next server
            last = e
    raise last


def road_matrix(points, profile="car"):
    """Distance matrix (metres) via OSRM /table. Falls back to straight-line."""
    try:
        coords = ";".join(f"{lo},{la}" for la, lo in points)
        js = _get(profile, f"/table/v1/driving/{coords}", {"annotations": "distance"}, 20)
        m = js["distances"]
        if all(x is not None for row in m for x in row):
            return m, "road (OSRM)"
    except Exception:
        pass
    return [[haversine(a, b) for b in points] for a in points], "straight-line (road service unavailable)"


def route_options(points, profile="car", alternatives=False, timeout=30):
    """Full-detail road geometry through `points` in order. List of route dicts."""
    try:
        coords = ";".join(f"{lo},{la}" for la, lo in points)
        params = {"overview": "full", "geometries": "polyline"}
        if alternatives and len(points) == 2:
            params["alternatives"] = "true"
        js = _get(profile, f"/route/v1/driving/{coords}", params, timeout)
        out = [finish({"dist": rt["distance"], "dur": rt["duration"],
                       "coords": decode_polyline(rt["geometry"]), "road": True, "est": False})
               for rt in js["routes"]]
        if out:
            return out
    except Exception:
        pass
    d = sum(haversine(points[i], points[i + 1]) for i in range(len(points) - 1))
    return [finish({"dist": d, "dur": None, "coords": list(points), "road": False, "est": False})]


def great_circle(a, b, n=64):
    """Points along the great-circle arc between a and b (lat, lon)."""
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    v1 = (math.cos(la1) * math.cos(lo1), math.cos(la1) * math.sin(lo1), math.sin(la1))
    v2 = (math.cos(la2) * math.cos(lo2), math.cos(la2) * math.sin(lo2), math.sin(la2))
    dot = max(-1.0, min(1.0, sum(x * y for x, y in zip(v1, v2))))
    w = math.acos(dot)
    if w < 1e-9:
        return [a, b]
    out = []
    for i in range(n + 1):
        t = i / n
        s1, s2 = math.sin((1 - t) * w) / math.sin(w), math.sin(t * w) / math.sin(w)
        x, y, z = (s1 * v1[k] + s2 * v2[k] for k in range(3))
        out.append((math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))))
    return out


def estimate_route(points, spec):
    """Train / airplane estimate through `points` in order (dashed arcs)."""
    coords, dist = [], 0.0
    for i in range(len(points) - 1):
        leg = great_circle(points[i], points[i + 1])
        coords += leg if not coords else leg[1:]
        dist += haversine(points[i], points[i + 1])
    dist *= spec["circuity"]
    dur = dist / (spec["speed_kmh"] / 3.6) + spec["overhead_s"]
    return finish({"dist": dist, "dur": dur, "coords": coords, "road": True, "est": True})
