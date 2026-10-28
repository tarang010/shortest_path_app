# Tarang Nav backend

FastAPI + MongoDB Atlas. Holds accounts, combined trips and trip photos. The
MongoDB connection string lives here as an environment variable only — it is
never shipped in the Android app.

## 1. MongoDB Atlas (free)
1. Create a free account at mongodb.com/atlas and a free **M0** cluster.
2. **Database Access** -> add a user with a password.
3. **Network Access** -> allow `0.0.0.0/0` (or restrict to Render's IPs).
4. **Connect -> Drivers** -> copy the `mongodb+srv://...` string.

## 2. Run locally
```bash
cd server
python -m venv .venv && . .venv/Scripts/activate   # Windows
pip install -r requirements.txt
set MONGODB_URI=mongodb+srv://...      # your Atlas string
set JWT_SECRET=some-long-random-string
uvicorn app:app --reload
```
Open http://127.0.0.1:8000/ — you should see `{"ok": true, ...}` and interactive
docs at http://127.0.0.1:8000/docs.

## 3. Deploy to Render (free)
1. Push this repo to GitHub.
2. Render dashboard -> **New + -> Blueprint** -> pick the repo. Render reads
   `server/render.yaml`.
3. Set the secret env vars when prompted: `MONGODB_URI`, `JWT_SECRET`.
4. Deploy. You get a URL like `https://tarang-nav-api.onrender.com`.
5. Put that URL into the app's `config.py` as `BACKEND_URL`.

> Render's free web service sleeps after inactivity; the first request after a
> nap takes ~30 s to wake. Fine for this app.

## Endpoints
- `POST /auth/signup` `{name, identifier, password}` -> `{token, user_id, name}`
- `POST /auth/login` `{identifier, password}` -> `{token, ...}`
- `GET  /auth/me`
- `POST /trips` `{name}` — create a combined trip
- `GET  /trips` — my trips (active + archived + pending invites)
- `POST /trips/{id}/invite` `{identifier}` — invite by email/phone
- `POST /trips/join` `{trip_id}`
- `POST /trips/{id}/location` `{lat, lon}` — share my live position
- `GET  /trips/{id}/locations` — every member's latest position
- `POST /trips/{id}/visited` `{name, lat, lon, arrived, left}` — memory diary entry
- `POST /trips/{id}/archive` / `DELETE /trips/{id}`
- `POST /trips/{id}/photos` (multipart `file`, `caption`) / `GET /trips/{id}/photos`
- `GET  /photos/{photo_id}`

All routes except signup/login/health require `Authorization: Bearer <token>`.
