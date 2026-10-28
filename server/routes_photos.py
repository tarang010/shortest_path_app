"""Trip photos ("memory diary" images), stored in MongoDB GridFS."""
import datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from db import db, fs
from security import current_user
from routes_trips import _get_trip, _oid

router = APIRouter(tags=["photos"])


@router.post("/trips/{trip_id}/photos")
def upload_photo(trip_id: str, file: UploadFile = File(...),
                 caption: str = Form(""), user=Depends(current_user)):
    trip, me_id, _ = _get_trip(trip_id, user)
    if fs is None:
        raise HTTPException(503, "Storage not configured")
    data = file.file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "Photo too large (max 8 MB)")
    pid = fs.put(data, filename=file.filename or "photo.jpg",
                 content_type=file.content_type or "image/jpeg")
    meta = {"id": str(pid), "caption": caption, "by": me_id,
            "t": datetime.datetime.utcnow().timestamp()}
    db.trips.update_one({"_id": trip["_id"]}, {"$push": {"photos": meta}})
    return meta


@router.get("/trips/{trip_id}/photos")
def list_photos(trip_id: str, user=Depends(current_user)):
    trip, me_id, _ = _get_trip(trip_id, user)
    return trip.get("photos", [])


@router.get("/photos/{photo_id}")
def get_photo(photo_id: str, user=Depends(current_user)):
    if fs is None:
        raise HTTPException(503, "Storage not configured")
    try:
        gf = fs.get(ObjectId(photo_id))
        data = gf.read()
        return Response(content=data, media_type=gf.content_type or "image/jpeg")
    except Exception:
        raise HTTPException(404, "Photo not found")
