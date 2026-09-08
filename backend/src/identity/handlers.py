"""Identity command handlers."""

from __future__ import annotations

from backend.src.identity.commands import (
    GetProfileCommand,
    LoginCommand,
    RefreshTokenCommand,
    RegisterCommand,
)
from backend.src.identity.domain.model import User
from backend.src.identity.service import AuthService, JwtService, TokenPair
from backend.src.shared.service_layer.messagebus import CommandHandler
from backend.src.identity.adapters.repository import UserRepository, SessionRepository


class RegisterHandler(CommandHandler[RegisterCommand, User]):
    """Handler for user registration."""

    def __init__(
        self,
        user_repo: UserRepository,
        session_repo: SessionRepository,
        jwt_service: JwtService,
    ) -> None:
        self._auth = AuthService(user_repo, session_repo, jwt_service)

    def handle(self, command: RegisterCommand) -> User:
        return self._auth.register(command.email, command.password, command.role)


class LoginHandler(CommandHandler[LoginCommand, TokenPair]):
    """Handler for user login."""

    def __init__(
        self,
        user_repo: UserRepository,
        session_repo: SessionRepository,
        jwt_service: JwtService,
    ) -> None:
        self._auth = AuthService(user_repo, session_repo, jwt_service)

    def handle(self, command: LoginCommand) -> TokenPair:
        return self._auth.login(command.email, command.password)


class RefreshTokenHandler(CommandHandler[RefreshTokenCommand, TokenPair]):
    """Handler for token refresh."""

    def __init__(
        self,
        user_repo: UserRepository,
        session_repo: SessionRepository,
        jwt_service: JwtService,
    ) -> None:
        self._auth = AuthService(user_repo, session_repo, jwt_service)

    def handle(self, command: RefreshTokenCommand) -> TokenPair:
        return self._auth.refresh_tokens(command.refresh_token)


class GetProfileHandler(CommandHandler[GetProfileCommand, User]):
    """Handler for getting user profile."""

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    def handle(self, command: GetProfileCommand) -> User:
        user = self._user_repo.get(command.user_id)
        if not user:
            raise ValueError("User not found")
        return user
