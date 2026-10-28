"""Tarang Nav backend — FastAPI.

Run locally:
    cd server
    pip install -r requirements.txt
    set MONGODB_URI=...        (Windows)  /  export MONGODB_URI=...  (mac/linux)
    set JWT_SECRET=...
    uvicorn app:app --reload

Deployed on Render using render.yaml (gunicorn + uvicorn worker).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from db import init_indexes
import routes_auth
import routes_photos
import routes_trips

app = FastAPI(title="Tarang Nav API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_auth.router)
app.include_router(routes_trips.router)
app.include_router(routes_photos.router)


@app.on_event("startup")
def _startup():
    try:
        init_indexes()
    except Exception:
        pass


@app.get("/")
def health():
    return {"ok": True, "service": "tarang-nav", "db_configured": bool(config.MONGODB_URI)}
