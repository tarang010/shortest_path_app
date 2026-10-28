"""Backend configuration, read from environment variables on the host (Render).

NEVER hard-code the real secrets here. Set them in the Render dashboard
(Environment tab) or in a local .env file for development (see .env.example).
"""
import os

MONGODB_URI = os.environ.get("MONGODB_URI", "")
DB_NAME = os.environ.get("MONGODB_DB_NAME", "tarang")
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALG = "HS256"
JWT_TTL_DAYS = int(os.environ.get("JWT_TTL_DAYS", "30"))

# Comma-separated list of allowed origins for CORS. The mobile app sends no
# Origin header, so "*" is fine; tighten this if you add a web client.
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
