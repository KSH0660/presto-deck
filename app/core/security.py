from datetime import datetime, timedelta, UTC
from typing import Any, Dict, Optional

import bleach
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.domain.exceptions import UnauthorizedAccessException


class SecurityService:
    def __init__(self) -> None:
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def create_access_token(
        self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(UTC) + expires_delta
        else:
            expire = datetime.now(UTC) + timedelta(
                minutes=settings.jwt_expiration_minutes
            )

        to_encode.update({"exp": expire, "iat": datetime.now(UTC)})

        encoded_jwt = jwt.encode(
            to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        return encoded_jwt

    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(
                token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
            )
            return payload
        except JWTError as e:
            raise UnauthorizedAccessException("Invalid token", str(e))

    def hash_password(self, password: str) -> str:
        """Hash a password."""
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return self.pwd_context.verify(plain_password, hashed_password)

    def extract_user_id_from_token(self, token: str) -> str:
        """Extract user ID from JWT token."""
        payload = self.verify_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise UnauthorizedAccessException("Invalid token", "No user ID found")
        return user_id


class HTMLSanitizer:
    def __init__(self) -> None:
        self.allowed_tags = settings.html_sanitizer_tags
        self.allowed_attributes = settings.html_sanitizer_attributes

    def sanitize(self, html_content: str) -> str:
        """Sanitize HTML content to prevent XSS attacks."""
        cleaned_html = bleach.clean(
            html_content,
            tags=self.allowed_tags,
            attributes=self.allowed_attributes,
            strip=True,
            strip_comments=True,
        )
        return cleaned_html

    def sanitize_with_linkify(self, html_content: str) -> str:
        """Sanitize HTML and convert plain URLs to links."""
        cleaned_html = self.sanitize(html_content)
        return bleach.linkify(cleaned_html)


# Global instances
security_service = SecurityService()
html_sanitizer = HTMLSanitizer()


# FastAPI Dependency
async def get_current_user_id() -> str:
    # In a real app, this would come from a dependency that verifies a token
    # For now, we'll return a hardcoded user ID for testing purposes
    return "test-user-id"
