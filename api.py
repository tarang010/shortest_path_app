"""Thin HTTP client for the Tarang Nav backend.

All networking for accounts, combined trips and photos goes through here. The
app never touches MongoDB directly; it only talks to BACKEND_URL (config.py)
over HTTPS, sending the signed JWT in the Authorization header.
"""
import requests

import config

_session = requests.Session()
_session.headers.update({"User-Agent": config.USER_AGENT})
_token = None


class ApiError(Exception):
    pass


def set_token(token):
    global _token
    _token = token


def clear_token():
    global _token
    _token = None


def logged_in():
    return bool(_token)


def _headers(extra=None):
    h = dict(extra or {})
    if _token:
        h["Authorization"] = f"Bearer {_token}"
    return h


def _url(path):
    return config.BACKEND_URL.rstrip("/") + path


def _handle(r):
    if r.status_code // 100 == 2:
        try:
            return r.json()
        except Exception:
            return {}
    # Pull the FastAPI error detail if there is one.
    try:
        detail = r.json().get("detail")
    except Exception:
        detail = None
    raise ApiError(detail or f"Request failed ({r.status_code})")


def _request(method, path, *, json=None, data=None, files=None, timeout=25):
    try:
        r = _session.request(method, _url(path), json=json, data=data, files=files,
                             headers=_headers(), timeout=timeout)
    except requests.RequestException:
        raise ApiError("Can't reach the server. Check your connection.")
    return _handle(r)


# ---- auth ------------------------------------------------------------------
def signup(name, identifier, password):
    out = _request("POST", "/auth/signup",
                   json={"name": name, "identifier": identifier, "password": password})
    set_token(out["token"])
    return out


def login(identifier, password):
    out = _request("POST", "/auth/login", json={"identifier": identifier, "password": password})
    set_token(out["token"])
    return out


def me():
    return _request("GET", "/auth/me")


# ---- combined trips --------------------------------------------------------
def create_trip(name):
    return _request("POST", "/trips", json={"name": name})


def list_trips():
    return _request("GET", "/trips")


def get_trip(trip_id):
    return _request("GET", f"/trips/{trip_id}")


def invite(trip_id, identifier):
    return _request("POST", f"/trips/{trip_id}/invite", json={"identifier": identifier})


def join(trip_id):
    return _request("POST", "/trips/join", json={"trip_id": trip_id})


def update_location(trip_id, lat, lon):
    return _request("POST", f"/trips/{trip_id}/location", json={"lat": lat, "lon": lon}, timeout=15)


def get_locations(trip_id):
    return _request("GET", f"/trips/{trip_id}/locations", timeout=15)


def add_visited(trip_id, name, lat, lon, arrived=None, left=None):
    return _request("POST", f"/trips/{trip_id}/visited",
                    json={"name": name, "lat": lat, "lon": lon, "arrived": arrived, "left": left})


def archive(trip_id, summary=None):
    return _request("POST", f"/trips/{trip_id}/archive", json={"summary": summary})


def delete_trip(trip_id):
    return _request("DELETE", f"/trips/{trip_id}")


# ---- photos ----------------------------------------------------------------
def upload_photo(trip_id, file_path, caption=""):
    try:
        with open(file_path, "rb") as f:
            files = {"file": (file_path.split("/")[-1], f, "image/jpeg")}
            return _request("POST", f"/trips/{trip_id}/photos",
                            data={"caption": caption}, files=files, timeout=60)
    except ApiError:
        raise
    except Exception as e:
        raise ApiError(f"Could not read the photo: {e}")


def list_photos(trip_id):
    return _request("GET", f"/trips/{trip_id}/photos")


def download_photo(photo_id, dest_path):
    """Download a photo's bytes (with auth) to dest_path; returns the path."""
    try:
        r = _session.get(_url(f"/photos/{photo_id}"), headers=_headers(), timeout=30)
    except requests.RequestException:
        raise ApiError("Can't reach the server.")
    if r.status_code // 100 != 2:
        raise ApiError("Photo not found")
    with open(dest_path, "wb") as f:
        f.write(r.content)
    return dest_path
