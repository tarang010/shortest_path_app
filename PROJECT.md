# Tarang Nav — Project Documentation

A free, multi-mode navigation and trip-tracking app for Android, built with
Python + Kivy. It plans routes, tracks live trips (including in the background),
and supports accounts, shared "combined" trips and photo memories through a small
self-hosted backend. It uses **only free/open services** — no paid APIs.

---

## 1. What it does (features)

### Routing
- **Six transport modes:** Car, Bike (motorcycle), Bicycle, Walk, Bus, Airplane.
  Train and Truck are intentionally disabled.
- **Real road routes** from OSRM (car/bike/foot profiles) with full road geometry,
  simplified into multiple zoom levels so long routes stay fast and smooth.
- **Fastest vs Shortest** — both are computed and tagged; tap to switch.
- **Alternatives and multi-stop:** up to 8 stops. For multi-stop trips the app
  solves an order using classic algorithms (Dijkstra shortest-path tree, Prim MST,
  greedy nearest-neighbour and MST-walk TSP, improved by 2-opt) and shows several
  candidate orders.
- **Airplane mode = airport hops:** routes you by road to the nearest airport,
  draws the great-circle flight, then routes by road from the arrival airport to
  your destination. Airports come from OpenStreetMap (Overpass), preferring ones
  with an IATA code.
- **Live traffic** (optional) on car routes via the free TomTom Traffic tier:
  shows light/moderate/heavy traffic, delays and road closures, and can switch
  your selection to a less congested route.

### Live navigation & trip tracking
- **GPS tracking** with a live blue dot, accuracy halo and a green trail of where
  you have actually been.
- **Progress & ETA:** percentage done, distance remaining and estimated time.
- **Auto re-route:** if you drift off the route for a while, it recalculates from
  your current position to the destination.
- **Follow mode:** the map gently keeps you centred while navigating, without
  fighting manual panning.
- **Background operation:** an Android **foreground service** keeps recording when
  the screen is off or the app is minimized, until you stop the trip.

### Fitness metrics (Walk / Bicycle)
- A Strava-style activity page with **distance, time, pace, average/current speed,
  calories, and elevation gain/loss**.
- **Barometric elevation:** uses the phone's pressure sensor to detect real
  floor-level climbs and descents (GPS altitude is too noisy for this), falling
  back to GPS altitude when no barometer is present.
- **Calories** from a MET model based on pace and body weight, plus the work of
  climbing the elevation gained.

### Along the route
- **Nearby places:** one tap highlights **hospitals, petrol pumps and EV charging
  stations** within ~1.5 km of the selected route (OpenStreetMap / Overpass).
- **Fuel estimate:** enter your vehicle's mileage (km/L) in Settings and each
  Car/Bike/Bus route shows the fuel needed **there and round-trip** (and cost if
  you set a fuel price).

### Accounts & combined trips (backend)
- **Sign up / log in** with email or phone + password (passwords hashed server-side,
  JWT tokens on the device).
- **Combined trips:** create a named trip, **invite people by email or phone**, or
  let them join with a Trip ID.
- **Live location sharing:** members see each other on the map as coloured dots —
  useful if someone gets lost.
- **Memory diary:** log the places you visit with timestamps; **archive** a trip to
  keep it as a memory, or **delete** it (owner only).
- **Photo memories:** attach photos to a trip, stored on the backend and viewable
  later.

### Personal trip history
- Finished solo trips are saved on the phone (distance, time, average speed,
  calories, elevation) and listed under "Past trips".

---

## 2. Architecture

```
          Android app (Kivy)                         Your backend (Render)
  ┌─────────────────────────────┐             ┌──────────────────────────────┐
  │ main.py  UI + navigation     │   HTTPS     │ FastAPI (app.py)             │
  │ api.py   ───────────────────────────────▶ │  auth / trips / photos       │
  │ gps.py / service.py tracking │   JWT       │                              │
  │ geo/poi/traffic/fuel  logic  │             │ pymongo ──▶ MongoDB Atlas    │
  └─────────────────────────────┘             │ GridFS  ──▶ photo bytes      │
         │ free OSM services                   └──────────────────────────────┘
         ▼
  OSRM · Nominatim · Photon · Overpass · TomTom (free tier)
```

- The app talks to free OSM services directly for routing/search/POIs, and to the
  **backend only** for accounts, combined trips and photos.
- **The MongoDB connection string never ships in the APK.** It lives only on the
  server as an environment variable. The app holds a signed JWT and the backend
  URL (`config.py → BACKEND_URL`).

---

## 3. File-by-file

### App (device)
| File | Responsibility |
|------|----------------|
| `main.py` | App entry point, all UI (KV), map layer, navigation, trip tracking, accounts/trip popups |
| `config.py` | Single source of every API endpoint/key + `BACKEND_URL` |
| `modes.py` | Transport-mode definitions (+ disabled modes) |
| `geo.py` | Geocoding (Nominatim), OSRM routing, polyline decode, LOD simplification, plane routing |
| `places.py` | Address autocomplete (Photon) |
| `poi.py` | Overpass: nearby POIs + nearest airport |
| `traffic.py` | Live traffic sampling + delay model (TomTom) |
| `fuel.py` | Fuel/energy estimate |
| `tracker.py` | Trip maths: distance, moving time, speed, calories, elevation |
| `sensors.py` | Barometer (pressure → altitude) |
| `gps.py` | Foreground GPS via Android LocationManager (plyer fallback) |
| `service.py` | Background foreground-service tracker (separate process) |
| `background.py` | App-side control of the service + shared state file |
| `api.py` | HTTP client for the backend (JWT auth) |
| `algos.py` | Dijkstra, Prim MST, greedy/MST TSP, 2-opt |
| `buildozer.spec` | Android build configuration |

### Backend (`server/`)
| File | Responsibility |
|------|----------------|
| `app.py` | FastAPI app, CORS, router mounting, health check |
| `config.py` | Env vars: `MONGODB_URI`, `JWT_SECRET`, `DB_NAME` |
| `db.py` | MongoDB client + GridFS + indexes |
| `security.py` | bcrypt hashing, JWT create/verify, auth dependency |
| `models.py` | Pydantic request/response schemas |
| `routes_auth.py` | `/auth/signup`, `/auth/login`, `/auth/me` |
| `routes_trips.py` | Combined trips: create/invite/join/location/visited/archive/delete |
| `routes_photos.py` | Photo upload/list/fetch (GridFS) |
| `requirements.txt` · `render.yaml` · `.env.example` | Deploy config |

---

## 4. Tech stack
- **App:** Python 3.11, Kivy 2.3, kivy_garden.mapview, plyer, requests; packaged
  with Buildozer / python-for-android.
- **Backend:** FastAPI, Uvicorn/Gunicorn, pymongo, PyJWT, bcrypt, python-multipart.
- **Data:** MongoDB Atlas (free M0) + GridFS for photos.
- **Hosting:** Render free web service.
- **Maps/data:** OpenStreetMap ecosystem (OSRM, Nominatim, Photon, Overpass) +
  free TomTom traffic tier.

---

## 5. Backend data model (MongoDB)
- **users:** `{ name, email?, phone?, password_hash, created }` (unique sparse
  index on email and phone).
- **trips:** `{ name, owner, status: active|archived, created, members:[{user_id,
  name}], invites:[identifier], locations:{user_id:{lat,lon,t}}, visited:[{name,
  lat,lon,arrived,left}], photos:[{id,caption,by,t}], summary }`.
- **photos:** stored as GridFS objects; referenced by id from `trips.photos`.

## 6. Backend API
All routes except signup/login/health require `Authorization: Bearer <jwt>`.
- `POST /auth/signup` · `POST /auth/login` · `GET /auth/me`
- `POST /trips` · `GET /trips` · `GET /trips/{id}`
- `POST /trips/{id}/invite` · `POST /trips/join`
- `POST /trips/{id}/location` · `GET /trips/{id}/locations`
- `POST /trips/{id}/visited` · `POST /trips/{id}/archive` · `DELETE /trips/{id}`
- `POST /trips/{id}/photos` · `GET /trips/{id}/photos` · `GET /photos/{id}`

---

## 7. Configuration
Everything external is in `config.py`:
- App-side (safe to ship): Photon, Nominatim, OSRM, Overpass, TomTom key, Open
  Elevation, `USER_AGENT`, and `BACKEND_URL`.
- Server-side (never shipped): `MONGODB_URI`, `JWT_SECRET` — read from env vars on
  the server only.

## 8. Android permissions
`INTERNET`, `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`,
`ACCESS_BACKGROUND_LOCATION`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_LOCATION`,
`WAKE_LOCK`, `POST_NOTIFICATIONS`, `CAMERA`, `READ_MEDIA_IMAGES`.

---

## 9. Build & deploy (summary)
1. **Backend:** create a MongoDB Atlas M0 cluster; deploy `server/` to Render
   (Root Directory `server`, build `pip install -r requirements.txt`, start
   `gunicorn app:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT`); set
   `MONGODB_URI` and `JWT_SECRET`.
2. Put the Render URL into `config.py → BACKEND_URL`; commit and push.
3. **App:** GitHub → Actions → **Build Android** → `debug` for a test APK, or push
   a `v*` tag / choose `release` for a signed AAB (needs the keystore secrets —
   see `README.md`). Bump `android.numeric_version` before each Play upload.

See `README.md` (app build) and `server/README.md` (backend) for full steps.

---

## 10. Security notes
- No secrets in the APK; the DB string stays on the server.
- Passwords bcrypt-hashed; stateless JWT auth over HTTPS.
- Minimum necessary permissions; HTTPS-only networking.

## 11. Known limitations
- Bus and motorcycle reuse the car road network with a time factor (no free
  timetable/profile data).
- Airplane routing is an estimate (great-circle flight; no live flight schedules).
- Overpass/OSRM community servers are rate-limited and can be briefly slow; all
  network calls fail gracefully.
- Render's free tier sleeps when idle — the first request after a nap takes ~30 s.
- Background-service behaviour and the barometer depend on the device; verify on
  real hardware.

## 12. Possible future work
- Turn-by-turn voice guidance.
- Offline map tiles / cached routes.
- Push notifications for combined-trip events.
- Phone-number OTP verification (needs a paid SMS provider).
