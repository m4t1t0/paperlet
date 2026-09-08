"""Identity context exports."""

from backend.src.identity.api import auth_bp
from backend.src.identity.commands import (
    GetProfileCommand,
    LoginCommand,
    RefreshTokenCommand,
    RegisterCommand,
)
from backend.src.identity.domain import (
    User,
    UserRole,
    Session,
    UserRegistered,
    UserCapabilitiesChanged,
    UserRepository,
    SessionRepository,
)
from backend.src.identity.handlers import (
    GetProfileHandler,
    LoginHandler,
    RefreshTokenHandler,
    RegisterHandler,
)
from backend.src.identity.service import AuthService, JwtService, TokenPair

__all__ = [
    "auth_bp",
    "RegisterCommand",
    "LoginCommand",
    "RefreshTokenCommand",
    "GetProfileCommand",
    "RegisterHandler",
    "LoginHandler",
    "RefreshTokenHandler",
    "GetProfileHandler",
    "User",
    "UserRole",
    "Session",
    "UserRegistered",
    "UserCapabilitiesChanged",
    "UserRepository",
    "SessionRepository",
    "AuthService",
    "JwtService",
    "TokenPair",
]
