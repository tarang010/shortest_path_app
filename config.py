"""Central configuration for Tarang Nav.

Everything external (API endpoints, keys, the backend URL, the database string)
lives here so there is exactly one place to change it.

READ THIS BEFORE ADDING SECRETS
-------------------------------
This file is compiled into the APK. Anything in the APP-SIDE section below is
shipped to every user's phone and can be extracted from the APK in minutes.
  * APP-SIDE  : safe to ship (public endpoints, the free TomTom key, the URL of
                your own backend).
  * SERVER-SIDE: NEVER ship. The MongoDB Atlas connection string and JWT secret
                belong only on your backend server, not in the app. They are
                listed here only so you have one reference file; the real values
                must be read from environment variables on the server (see
                `server/` once the backend phase is built), not hard-coded.

Free services only. No paid third-party APIs.
"""
import os

# ============================================================================
# APP-SIDE  — safe to compile into the APK
# ============================================================================

# ---- Address search / geocoding (OpenStreetMap, free) ----------------------
PHOTON_API = "https://photon.komoot.io/api/"                 # search-as-you-type
NOMINATIM_API = "https://nominatim.openstreetmap.org/search"  # final lookup fallback

# ---- Routing (OSRM community servers, free) --------------------------------
OSRM_SERVICES = {
    "car":  ["https://routing.openstreetmap.de/routed-car", "https://router.project-osrm.org"],
    "bike": ["https://routing.openstreetmap.de/routed-bike"],
    "foot": ["https://routing.openstreetmap.de/routed-foot"],
}

# ---- Points of interest + airports (Overpass / OpenStreetMap, free) --------
OVERPASS_API = "https://overpass-api.de/api/interpreter"
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# ---- Live traffic (TomTom free tier: 2,500 non-tile requests/day, no card) -
TOMTOM_KEY = "euCZ3RC2alU0EHWXzXoVw0a5uf8g9fer"
TOMTOM_FLOW_API = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
DAILY_TRAFFIC_BUDGET = 2400

# ---- Elevation (free, no key; used to sanity-check barometer/GPS altitude) -
OPEN_ELEVATION_API = "https://api.open-elevation.com/api/v1/lookup"

# ---- HTTP identity sent to every free service ------------------------------
USER_AGENT = "TarangNav/4.0 (educational app)"

# ---- Your backend (holds the DB secret server-side; see SERVER-SIDE below) -
# Point this at your deployed backend. The app talks ONLY to this URL for
# login/signup, combined trips and photos. Override at runtime with the
# TARANG_BACKEND_URL environment variable if you like.
BACKEND_URL = os.environ.get("TARANG_BACKEND_URL", "https://your-backend.onrender.com")

# ============================================================================
# SERVER-SIDE  — NEVER ship these in the APK
# ----------------------------------------------------------------------------
# On the backend, read these from environment variables, NOT from this file.
# They are documented here only as a single reference of what the server needs.
# ============================================================================

# Example (set these as env vars on your host, e.g. Render/Railway/Fly.io):
#   MONGODB_URI = "mongodb+srv://<user>:<password>@<cluster>.mongodb.net/tarang?retryWrites=true&w=majority"
#   JWT_SECRET  = "<a long random string>"
MONGODB_URI = os.environ.get("MONGODB_URI", "")   # <-- set on the SERVER only
JWT_SECRET = os.environ.get("JWT_SECRET", "")      # <-- set on the SERVER only
MONGODB_DB_NAME = os.environ.get("MONGODB_DB_NAME", "tarang")
