"""Address suggestions while typing: Photon (OpenStreetMap data, built for search-as-you-type).
Nominatim's public server forbids autocomplete, so it is only used for the final lookup fallback."""
import requests
import config

PHOTON = config.PHOTON_API
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": config.USER_AGENT})


def suggest(q, bias=None, limit=5, timeout=6):
    """[{'label','lat','lon'}, ...]. bias=(lat, lon) ranks nearby places higher."""
    params = {"q": q, "limit": limit, "lang": "en"}
    if bias:
        params["lat"], params["lon"] = bias
    r = SESSION.get(PHOTON, params=params, timeout=timeout)
    r.raise_for_status()
    out, seen = [], set()
    for f in r.json().get("features", []):
        p, (lon, lat) = f.get("properties", {}), f["geometry"]["coordinates"][:2]
        parts, labels = [], set()
        for k in ("name", "street", "district", "locality", "city", "state", "country"):
            v = p.get(k)
            if v and v not in labels:
                labels.add(v)
                parts.append(v)
        label = ", ".join(parts[:4] if len(parts) > 4 else parts)
        if label and label not in seen:
            seen.add(label)
            out.append({"label": label, "lat": float(lat), "lon": float(lon)})
    return out
