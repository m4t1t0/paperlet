"""JWT authentication service."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4

import jwt
from passlib.hash import bcrypt

from backend.src.shared.config import get_settings
from backend.src.identity.domain.model import User, UserRole


class TokenPair:
    """Access and refresh token pair."""

    def __init__(self, access_token: str, refresh_token: str, expires_in: int) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_in = expires_in
        self.token_type = "Bearer"


class JwtService:
    """JWT token management service."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def create_access_token(self, user_id: UUID, session_id: UUID) -> str:
        """Create a short-lived access token."""
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=self._settings.jwt_access_token_expire_minutes)
        payload = {
            "sub": str(user_id),
            "sid": str(session_id),
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "type": "access",
        }
        return jwt.encode(payload, self._settings.secret_key, algorithm=self._settings.jwt_algorithm)

    def create_refresh_token(self, user_id: UUID, session_id: UUID) -> str:
        """Create a long-lived refresh token."""
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=self._settings.jwt_refresh_token_expire_days)
        payload = {
            "sub": str(user_id),
            "sid": str(session_id),
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "type": "refresh",
        }
        return jwt.encode(payload, self._settings.secret_key, algorithm=self._settings.jwt_algorithm)

    def decode_token(self, token: str) -> dict:
        """Decode and validate a token."""
        try:
            return jwt.decode(
                token,
                self._settings.secret_key,
                algorithms=[self._settings.jwt_algorithm],
            )
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")

    def verify_access_token(self, token: str) -> tuple[UUID, UUID]:
        """Verify access token and return (user_id, session_id)."""
        payload = self.decode_token(token)
        if payload.get("type") != "access":
            raise ValueError("Not an access token")
        return UUID(payload["sub"]), UUID(payload["sid"])

    def verify_refresh_token(self, token: str) -> tuple[UUID, UUID]:
        """Verify refresh token and return (user_id, session_id)."""
        payload = self.decode_token(token)
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        return UUID(payload["sub"]), UUID(payload["sid"])

    def create_token_pair(self, user_id: UUID) -> TokenPair:
        """Create a new token pair for a user."""
        session_id = uuid4()
        access_token = self.create_access_token(user_id, session_id)
        refresh_token = self.create_refresh_token(user_id, session_id)
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self._settings.jwt_access_token_expire_minutes * 60,
        )


class AuthService:
    """Authentication service."""

    def __init__(self, user_repo: "UserRepository", jwt_service: JwtService) -> None:
        self._user_repo = user_repo
        self._jwt = jwt_service

    def register(self, email: str, password: str, role: UserRole = UserRole.READER) -> User:
        """Register a new user."""
        existing = self._user_repo.get_by_email(email)
        if existing:
            raise ValueError("Email already registered")

        password_hash = User.hash_password(password)
        user = User.register(email, password_hash, role)
        self._user_repo.add(user)
        return user

    def login(self, email: str, password: str) -> TokenPair:
        """Authenticate user and return tokens."""
        user = self._user_repo.get_by_email(email)
        if not user or not user.verify_password(password):
            raise ValueError("Invalid credentials")
        if not user.is_active:
            raise ValueError("Account is deactivated")
        return self._jwt.create_token_pair(user.id)

    def refresh_tokens(self, refresh_token: str) -> TokenPair:
        """Refresh access token using refresh token."""
        user_id, session_id = self._jwt.verify_refresh_token(refresh_token)
        user = self._user_repo.get(user_id)
        if not user or not user.is_active:
            raise ValueError("User not found or inactive")
        # In production, verify session exists and refresh token matches hash
        return self._jwt.create_token_pair(user_id)

    def get_current_user(self, access_token: str) -> User:
        """Get user from access token."""
        user_id, _ = self._jwt.verify_access_token(access_token)
        user = self._user_repo.get(user_id)
        if not user or not user.is_active:
            raise ValueError("User not found or inactive")
        return user