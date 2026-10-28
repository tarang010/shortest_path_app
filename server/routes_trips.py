"""Combined ("group") trips: create, invite, join, share live location, archive, history.

A trip document looks like:
{
  _id, name, owner, status: 'active'|'archived', created,
  members:   [{user_id, name}],
  invites:   ["someone@email", "+9199..."],        # pending, not yet joined
  locations: {user_id: {lat, lon, t}},             # each member's latest position
  visited:   [{name, lat, lon, arrived, left}],    # the memory diary
  photos:    [{id, caption, by, t}],               # GridFS ids (see routes_photos)
  summary:   {...}                                  # set when archived
}
"""
import datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from db import db
from models import ArchiveIn, InviteIn, JoinIn, LocationIn, TripCreateIn, VisitedIn
from security import current_user

router = APIRouter(prefix="/trips", tags=["trips"])


def _oid(s):
    try:
        return ObjectId(s)
    except Exception:
        raise HTTPException(400, "Bad id")


def _public(trip, me_id):
    return {
        "id": str(trip["_id"]),
        "name": trip.get("name"),
        "owner": trip.get("owner"),
        "is_owner": trip.get("owner") == me_id,
        "status": trip.get("status", "active"),
        "created": trip.get("created").timestamp() if trip.get("created") else None,
        "members": trip.get("members", []),
        "invites": trip.get("invites", []),
        "locations": trip.get("locations", {}),
        "visited": trip.get("visited", []),
        "photos": trip.get("photos", []),
        "summary": trip.get("summary"),
    }


def _get_trip(trip_id, user, require_member=True):
    trip = db.trips.find_one({"_id": _oid(trip_id)})
    if not trip:
        raise HTTPException(404, "Trip not found")
    me_id = str(user["_id"])
    is_member = any(m["user_id"] == me_id for m in trip.get("members", []))
    my_idents = [i for i in (user.get("email"), user.get("phone")) if i]
    is_invited = any(i in trip.get("invites", []) for i in my_idents)
    if require_member and not is_member and not is_invited:
        raise HTTPException(403, "Not a member of this trip")
    return trip, me_id, is_member


@router.post("")
def create_trip(body: TripCreateIn, user=Depends(current_user)):
    me_id = str(user["_id"])
    doc = {"name": body.name.strip() or "Trip", "owner": me_id, "status": "active",
           "created": datetime.datetime.utcnow(),
           "members": [{"user_id": me_id, "name": user.get("name", "User")}],
           "invites": [], "locations": {}, "visited": [], "photos": []}
    res = db.trips.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _public(doc, me_id)


@router.get("")
def list_trips(user=Depends(current_user)):
    me_id = str(user["_id"])
    my_idents = [i for i in (user.get("email"), user.get("phone")) if i]
    cur = db.trips.find({"$or": [{"members.user_id": me_id}, {"invites": {"$in": my_idents}}]})
    return [_public(t, me_id) for t in cur.sort("created", -1)]


@router.get("/{trip_id}")
def get_trip(trip_id: str, user=Depends(current_user)):
    trip, me_id, _ = _get_trip(trip_id, user)
    return _public(trip, me_id)


@router.post("/{trip_id}/invite")
def invite(trip_id: str, body: InviteIn, user=Depends(current_user)):
    trip, me_id, _ = _get_trip(trip_id, user)
    ident = body.identifier.strip().lower() if "@" in body.identifier else body.identifier.replace(" ", "")
    # If that person already has an account, add them straight away.
    existing = db.users.find_one({"$or": [{"email": ident}, {"phone": ident}]})
    if existing:
        eid = str(existing["_id"])
        if not any(m["user_id"] == eid for m in trip.get("members", [])):
            db.trips.update_one({"_id": trip["_id"]},
                                {"$push": {"members": {"user_id": eid, "name": existing.get("name", "User")}}})
    else:
        db.trips.update_one({"_id": trip["_id"]}, {"$addToSet": {"invites": ident}})
    return get_trip(trip_id, user)


@router.post("/join")
def join(body: JoinIn, user=Depends(current_user)):
    trip, me_id, is_member = _get_trip(body.trip_id, user)
    if not is_member:
        db.trips.update_one({"_id": trip["_id"]},
                            {"$push": {"members": {"user_id": me_id, "name": user.get("name", "User")}}})
    my_idents = [i for i in (user.get("email"), user.get("phone")) if i]
    db.trips.update_one({"_id": trip["_id"]}, {"$pull": {"invites": {"$in": my_idents}}})
    return get_trip(body.trip_id, user)


@router.post("/{trip_id}/location")
def update_location(trip_id: str, body: LocationIn, user=Depends(current_user)):
    trip, me_id, _ = _get_trip(trip_id, user)
    db.trips.update_one({"_id": trip["_id"]}, {"$set": {
        f"locations.{me_id}": {"lat": body.lat, "lon": body.lon,
                               "t": datetime.datetime.utcnow().timestamp()}}})
    return {"ok": True}


@router.get("/{trip_id}/locations")
def get_locations(trip_id: str, user=Depends(current_user)):
    trip, me_id, _ = _get_trip(trip_id, user)
    members = {m["user_id"]: m.get("name") for m in trip.get("members", [])}
    out = []
    for uid, loc in trip.get("locations", {}).items():
        out.append({"user_id": uid, "name": members.get(uid, "Member"),
                    "lat": loc["lat"], "lon": loc["lon"], "t": loc.get("t"),
                    "is_me": uid == me_id})
    return out


@router.post("/{trip_id}/visited")
def add_visited(trip_id: str, body: VisitedIn, user=Depends(current_user)):
    trip, me_id, _ = _get_trip(trip_id, user)
    db.trips.update_one({"_id": trip["_id"]}, {"$push": {"visited": body.dict()}})
    return {"ok": True}


@router.post("/{trip_id}/archive")
def archive(trip_id: str, body: ArchiveIn, user=Depends(current_user)):
    trip, me_id, _ = _get_trip(trip_id, user)
    upd = {"status": "archived", "archived_at": datetime.datetime.utcnow()}
    if body.summary:
        upd["summary"] = body.summary
    db.trips.update_one({"_id": trip["_id"]}, {"$set": upd})
    return get_trip(trip_id, user)


@router.delete("/{trip_id}")
def delete_trip(trip_id: str, user=Depends(current_user)):
    trip, me_id, _ = _get_trip(trip_id, user)
    if trip.get("owner") != me_id:
        raise HTTPException(403, "Only the trip owner can delete it")
    db.trips.delete_one({"_id": trip["_id"]})
    return {"ok": True}
