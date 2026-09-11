"""Identity commands."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from backend.src.shared.domain.value_objects import UserId
from backend.src.shared.service_layer.messagebus import Command


@dataclass(frozen=True)
class RegisterCommand(Command):
    """Command to register a new user (no role — inferred from activity)."""

    email: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None


@dataclass(frozen=True)
class LoginCommand(Command):
    """Command to login."""

    email: str
    password: str
    user_agent: Optional[str] = None
    ip: Optional[str] = None


@dataclass(frozen=True)
class RefreshTokenCommand(Command):
    """Command to refresh access token."""

    refresh_token: str
    user_agent: Optional[str] = None
    ip: Optional[str] = None


@dataclass(frozen=True)
class GetProfileCommand(Command):
    """Command to get current user profile."""

    user_id: UserId
