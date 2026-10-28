"""Request/response schemas (Pydantic)."""
from typing import Optional

from pydantic import BaseModel


class SignupIn(BaseModel):
    name: str
    identifier: str          # email address or phone number
    password: str


class LoginIn(BaseModel):
    identifier: str
    password: str


class TokenOut(BaseModel):
    token: str
    user_id: str
    name: str


class TripCreateIn(BaseModel):
    name: str


class InviteIn(BaseModel):
    identifier: str          # email or phone of the person to invite


class JoinIn(BaseModel):
    trip_id: str


class LocationIn(BaseModel):
    lat: float
    lon: float


class VisitedIn(BaseModel):
    name: str
    lat: float
    lon: float
    arrived: Optional[float] = None
    left: Optional[float] = None


class ArchiveIn(BaseModel):
    summary: Optional[dict] = None
