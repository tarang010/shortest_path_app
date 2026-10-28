# Tarang Nav

A free, multi-mode navigation and trip app for Android, built with Kivy. Uses
only free/open services (OpenStreetMap, OSRM, Photon, Overpass, a free TomTom
traffic key). Accounts, combined trips and photo memories are backed by your own
small FastAPI + MongoDB server.

## Features
- **Routing** for Car, Bike (motorcycle), Bicycle, Walk, Bus and **Airplane**
  (road to the nearest airport → flight → road to destination). Train and Truck
  are disabled.
- **Live traffic** on car routes (optional, free TomTom key).
- **Auto re-route** when you drift off the route, with a map that follows you.
- **Trip tracking** with distance, time, pace, calories and **barometric
  elevation** (real floor-level gain/loss), that **keeps running in the
  background** via a foreground service.
- **Nearby** hospitals, petrol pumps and EV charging stations along a route.
- **Fuel estimate** from your vehicle's mileage (one-way and round-trip).
- **Accounts** (email or phone + password) and **combined trips**: invite people,
  share live location, archive to a **memory diary** with visited places and
  **photos**.

## Repository layout
```
.
├── main.py            App entry point + all UI
├── config.py          Every API endpoint/key + your BACKEND_URL  (edit this)
├── modes.py           Transport modes
├── geo.py             Geocoding + OSRM routing + plane routing
├── places.py          Address autocomplete (Photon)
├── poi.py             Overpass: nearby POIs + nearest airport
├── fuel.py            Fuel/energy estimate
├── traffic.py         Live traffic (TomTom)
├── tracker.py         Trip maths (distance, calories, elevation)
├── sensors.py         Barometer (elevation)
├── gps.py             Foreground GPS (LocationManager)
├── service.py         Background tracking foreground service
├── background.py      App-side control of the service
├── api.py             HTTP client for the backend
├── algos.py           Dijkstra / MST / TSP
├── buildozer.spec     Android build config
├── server/            Backend (FastAPI + MongoDB) — deploy to Render
└── .github/workflows/ CI to build the APK/AAB
```

## 1. Configure
Open `config.py` and set `BACKEND_URL` to your deployed backend (see the server
`README`). The free TomTom key is already filled in; replace it with your own if
you like. The MongoDB connection string does **not** go in the app — it stays on
the server only.

## 2. Backend
See `server/README.md` for MongoDB Atlas setup and one-click Render deploy.
Put the resulting URL into `config.py`.

## 3. Run the app on desktop (for development)
```bash
pip install kivy kivy_garden.mapview plyer requests
python main.py
```
GPS, the barometer and the background service only work on a real Android device;
on desktop they are no-ops.

## 4. Build the Android app

### Easiest: GitHub Actions (no local setup)
1. Push this repo to GitHub.
2. **Actions → Build Android → Run workflow → debug** to get a test APK
   (download it from the run's Artifacts).

### Release build for the Play Store (signed AAB)
1. Create a signing keystore once:
   ```bash
   keytool -genkey -v -keystore release.keystore -alias tarang \
     -keyalg RSA -keysize 2048 -validity 10000
   ```
2. Add these **repository secrets** (Settings → Secrets and variables → Actions):
   - `KEYSTORE_BASE64` — the keystore file, base64-encoded
     (`base64 -w0 release.keystore` on Linux, or
     `[Convert]::ToBase64String([IO.File]::ReadAllBytes("release.keystore"))` in PowerShell)
   - `KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD`
3. Push a tag like `v4.0`, or run the workflow manually and pick **release**.
   The signed `.aab` appears in the run's Artifacts — upload that to the Play
   Console.
4. Bump `android.numeric_version` in `buildozer.spec` before every new upload
   (Play requires an increasing versionCode).

### Build locally instead (Linux/WSL)
```bash
pip install buildozer cython==0.29.36
buildozer android debug        # APK for testing
buildozer android release      # signed AAB (set the P4A_RELEASE_* env vars first)
```

## Security notes (Play Store)
- No secrets in the APK: the MongoDB string lives only on the server; the app
  authenticates with a JWT over HTTPS.
- Passwords are bcrypt-hashed server-side.
- The app talks to the backend over HTTPS only.
- Requests the minimum permissions it needs (location, background location,
  foreground service, camera/media for photos, notifications).
