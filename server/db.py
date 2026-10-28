"""MongoDB connection (pymongo) and GridFS handle for photo storage.

A single client is created at import and reused. Indexes are created once so
email / phone are unique and trip lookups are fast.
"""
import gridfs
from pymongo import ASCENDING, MongoClient

import config

_client = MongoClient(config.MONGODB_URI) if config.MONGODB_URI else None
db = _client[config.DB_NAME] if _client is not None else None
fs = gridfs.GridFS(db) if db is not None else None


def init_indexes():
    if db is None:
        return
    # Unique, but sparse so users may register with only an email OR only a phone.
    db.users.create_index([("email", ASCENDING)], unique=True, sparse=True)
    db.users.create_index([("phone", ASCENDING)], unique=True, sparse=True)
    db.trips.create_index([("members.user_id", ASCENDING)])
    db.trips.create_index([("invites", ASCENDING)])
