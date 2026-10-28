"""Live traffic for the next N km of each route, from TomTom Traffic Flow (free key:
2,500 non-tile requests/day, no card).  We sample points along that stretch, read current vs
free-flow speed at each, and add the extra travel time to the route's base duration."""
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from algos import haversine
from tracker import nearest_index
import config

FLOW = config.TOMTOM_FLOW_API
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": config.USER_AGENT})
_cache = {}
TTL = 120                  # seconds a sample is reused (saves quota; alternatives share road)
CLOSURE_PENALTY_S = 6 * 3600
SAMPLES = 8


class TrafficError(Exception):
    pass


def _fetch_flow(key, lat, lon, timeout=8):
    """-> (result or None, requests_used). result = {'cur','free','closed'} in km/h."""
    k = (round(lat, 3), round(lon, 3))
    hit = _cache.get(k)
    if hit and time.time() - hit[0] < TTL:
        return hit[1], 0
    r = SESSION.get(FLOW, params={"key": key, "point": f"{lat:.5f},{lon:.5f}", "unit": "KMPH"}, timeout=timeout)
    if r.status_code in (401, 403):
        raise TrafficError("invalid key or daily free limit reached")
    if r.status_code == 429:
        raise TrafficError("too many requests, try again in a moment")
    res = None
    if r.status_code == 200:
        d = r.json().get("flowSegmentData", {})
        if "currentSpeed" in d and "freeFlowSpeed" in d:
            res = {"cur": d["currentSpeed"], "free": d["freeFlowSpeed"], "closed": bool(d.get("roadClosure"))}
    _cache[k] = (time.time(), res)
    return res, 1


def sample_window(coords, i0, radius_m, n=SAMPLES):
    """n points evenly spread over the next radius_m of route starting at index i0."""
    i, total = i0, 0.0
    while i + 1 < len(coords) and total < radius_m:
        total += haversine(coords[i], coords[i + 1])
        i += 1
    i1 = i
    if total < 200:
        return [], total
    pts, acc, k, step = [], 0.0, 0, total / n
    target = step / 2
    for j in range(i0, i1):
        seg = haversine(coords[j], coords[j + 1])
        while k < n and acc + seg >= target and seg > 0:
            t = (target - acc) / seg
            pts.append((coords[j][0] + (coords[j + 1][0] - coords[j][0]) * t,
                        coords[j][1] + (coords[j + 1][1] - coords[j][1]) * t))
            k += 1
            target += step
        acc += seg
    return pts, total


def level_of(ratio):
    return "Light" if ratio < 0.10 else "Moderate" if ratio < 0.30 else "Heavy"


def analyse_route(route, ref, key, radius_m, pool):
    i0, off = nearest_index(route["coords"], ref)
    pts, wlen = sample_window(route["coords"], i0, radius_m)
    info = {"level": None, "delay": 0.0, "ratio": 0.0, "closed": False,
            "ok": 0, "used": 0, "window_km": wlen / 1000.0, "off_m": off}
    if not pts:
        return info
    seg = wlen / len(pts)
    t_free = delay = 0.0
    for res, used in pool.map(lambda p: _fetch_flow(key, p[0], p[1]), pts):
        info["used"] += used
        if not res:
            continue
        info["ok"] += 1
        free, cur = max(res["free"], 5) / 3.6, max(res["cur"], 3) / 3.6
        t_free += seg / free
        delay += max(0.0, seg / cur - seg / free)
        info["closed"] = info["closed"] or res["closed"]
    if info["ok"]:
        scale = len(pts) / info["ok"]
        t_free, delay = t_free * scale, delay * scale
        info["delay"], info["ratio"] = delay, delay / t_free
        info["level"] = level_of(info["ratio"])
    return info


def apply_traffic(routes, ref, key, radius_m=50_000, budget=2400):
    """Adds live delay to each route (route['dur'] becomes the live ETA, 'dur_free' keeps the base).
    Returns number of API requests used. Raises TrafficError for bad key / quota."""
    if budget < SAMPLES:
        raise TrafficError("today's free traffic requests are used up")
    used = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for r in routes:
            r.setdefault("dur_free", r["dur"])
            info = analyse_route(r, ref, key, radius_m, pool)
            used += info["used"]
            r["traffic"] = info
            r["dur"] = r["dur_free"] + info["delay"] + (CLOSURE_PENALTY_S if info["closed"] else 0)
    return used
