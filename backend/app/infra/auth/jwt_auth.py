"""
JWT Authentication implementation for Presto Deck.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import HTTPException, status
from pydantic import BaseModel

from app.infra.config.settings import get_settings


class JWTPayload(BaseModel):
    """JWT token payload structure."""

    user_id: str
    exp: int
    iat: int


class JWTAuth:
    """JWT Authentication handler."""

    def __init__(self):
        self.settings = get_settings()

    def create_access_token(self, user_id: UUID) -> str:
        """Create JWT access token for user."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=self.settings.jwt_expires_minutes)

        payload = {
            "user_id": str(user_id),
            "exp": int(expires_at.timestamp()),
            "iat": int(now.timestamp()),
        }

        return jwt.encode(
            payload, self.settings.jwt_secret_key, algorithm=self.settings.jwt_algorithm
        )

    def verify_token(self, token: str) -> JWTPayload:
        """Verify JWT token and return payload."""
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm],
            )
            return JWTPayload(**payload)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def extract_user_id_from_token(self, token: str) -> UUID:
        """Extract user ID from JWT token."""
        payload = self.verify_token(token)
        return UUID(payload.user_id)


def get_jwt_auth() -> JWTAuth:
    """Get JWT authentication instance."""
    return JWTAuth()
