"""Points of interest and airports from OpenStreetMap via the free Overpass API.

Used for:
  * highlighting hospitals, petrol pumps and EV charging stations near a route
  * finding the nearest airport to a point (for the Airplane mode airport hops)

No API key. Overpass is rate-limited, so queries are kept small (the route is
sampled down to a handful of points) and a short in-memory cache is used.
"""
import time

import requests

import config
from algos import haversine

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": config.USER_AGENT})

# amenity tag -> (our kind, single-letter map label, display name)
POI_KINDS = {
    "hospital": ("hospital", "H", "Hospital"),
    "fuel": ("fuel", "F", "Petrol pump"),
    "charging_station": ("charging", "E", "EV charging"),
}

_airport_cache = {}


def _post(query, timeout=40):
    """Run an Overpass query, trying each mirror in turn."""
    last = None
    for url in config.OVERPASS_MIRRORS:
        try:
            r = SESSION.post(url, data={"data": query}, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last = e
    raise last


def _center(el):
    """(lat, lon) for a node, or the 'center' of a way/relation."""
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    c = el.get("center")
    if c:
        return c["lat"], c["lon"]
    return None


def _sample(coords, max_points=50):
    """Thin a route polyline down to at most max_points, evenly spaced."""
    n = len(coords)
    if n <= max_points:
        return list(coords)
    step = n / float(max_points)
    return [coords[int(i * step)] for i in range(max_points)]


def along_route(coords, radius_m=1500, kinds=("hospital", "fuel", "charging_station"), limit=120):
    """POIs of the given amenity kinds within radius_m of the route.

    Returns [{'kind','label','name','lat','lon'}, ...] sorted by amenity kind.
    """
    if not coords:
        return []
    pts = _sample(coords, 50)
    around = ",".join(f"{la:.5f},{lo:.5f}" for la, lo in pts)
    parts = []
    for tag in kinds:
        parts.append(f'nwr(around:{radius_m:.0f},{around})["amenity"="{tag}"];')
    query = f"[out:json][timeout:40];({''.join(parts)});out center tags;"
    try:
        js = _post(query)
    except Exception:
        return []
    out = []
    for el in js.get("elements", []):
        amenity = el.get("tags", {}).get("amenity")
        meta = POI_KINDS.get(amenity)
        if not meta:
            continue
        c = _center(el)
        if not c:
            continue
        kind, label, disp = meta
        name = el.get("tags", {}).get("name") or disp
        out.append({"kind": kind, "label": label, "name": name, "lat": c[0], "lon": c[1]})
        if len(out) >= limit:
            break
    order = {"hospital": 0, "fuel": 1, "charging": 2}
    out.sort(key=lambda p: order.get(p["kind"], 9))
    return out


def nearest_airport(lat, lon, radii_km=(60, 150, 400)):
    """Nearest usable airport to (lat, lon).

    Prefers aerodromes that look like they handle commercial flights (have an
    IATA code or are tagged international), falling back to the nearest aerodrome
    of any kind. Returns {'lat','lon','name','iata'} or None.
    """
    key = (round(lat, 2), round(lon, 2))
    hit = _airport_cache.get(key)
    if hit and time.time() - hit[0] < 3600:
        return hit[1]
    result = None
    for radius_km in radii_km:
        r = radius_km * 1000
        query = (f"[out:json][timeout:30];"
                 f'(nwr(around:{r},{lat:.5f},{lon:.5f})["aeroway"="aerodrome"];);'
                 f"out center tags;")
        try:
            js = _post(query, timeout=35)
        except Exception:
            continue
        cands = []
        for el in js.get("elements", []):
            c = _center(el)
            if not c:
                continue
            tags = el.get("tags", {})
            iata = tags.get("iata")
            atype = (tags.get("aerodrome:type") or tags.get("aerodrome") or "").lower()
            commercial = bool(iata) or "international" in atype or "public" in atype
            d = haversine((lat, lon), c)
            name = tags.get("name") or (iata and f"{iata} airport") or "Airport"
            cands.append((commercial, d, {"lat": c[0], "lon": c[1], "name": name, "iata": iata}))
        if cands:
            # prefer commercial airports; among equals, the nearest.
            cands.sort(key=lambda t: (not t[0], t[1]))
            result = cands[0][2]
            break
    _airport_cache[key] = (time.time(), result)
    return result
