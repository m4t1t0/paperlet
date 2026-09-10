"""Integration tests for authentication."""
from __future__ import annotations
import pytest

from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork
from backend.src.identity.service import JwtService, AuthService
from backend.src.identity.adapters.sqlalchemy_repository import SqlAlchemyUserRepository, SqlAlchemySessionRepository


# No need for setup_db fixture - tables are created at session scope
# Data is cleared between tests by the _clear_data fixture in conftest.py


class TestAuthIntegration:
    """Integration tests for authentication flow."""

    def test_register_and_login(self) -> None:
        with SqlAlchemyUnitOfWork() as uow:
            user_repo = SqlAlchemyUserRepository(uow.session)
            session_repo = SqlAlchemySessionRepository(uow.session)
            jwt_service = JwtService()
            auth = AuthService(user_repo, session_repo, jwt_service)

            # Register (no roles at signup — inferred from activity)
            user = auth.register("test@example.com", "password123")
            uow.commit()

            assert user.email == "test@example.com"
            assert user.roles == set()

            # Login
            tokens = auth.login("test@example.com", "password123")
            assert tokens.access_token
            assert tokens.refresh_token
            assert tokens.expires_in == 900  # 15 minutes

    def test_login_fails_with_wrong_password(self) -> None:
        with SqlAlchemyUnitOfWork() as uow:
            user_repo = SqlAlchemyUserRepository(uow.session)
            session_repo = SqlAlchemySessionRepository(uow.session)
            jwt_service = JwtService()
            auth = AuthService(user_repo, session_repo, jwt_service)

            auth.register("test@example.com", "password123")
            uow.commit()

            with pytest.raises(ValueError, match="Invalid credentials"):
                auth.login("test@example.com", "wrong_password")

    def test_login_fails_for_nonexistent_user(self) -> None:
        with SqlAlchemyUnitOfWork() as uow:
            user_repo = SqlAlchemyUserRepository(uow.session)
            session_repo = SqlAlchemySessionRepository(uow.session)
            jwt_service = JwtService()
            auth = AuthService(user_repo, session_repo, jwt_service)

            with pytest.raises(ValueError, match="Invalid credentials"):
                auth.login("nonexistent@example.com", "password123")

    def test_refresh_token(self) -> None:
        with SqlAlchemyUnitOfWork() as uow:
            user_repo = SqlAlchemyUserRepository(uow.session)
            session_repo = SqlAlchemySessionRepository(uow.session)
            jwt_service = JwtService()
            auth = AuthService(user_repo, session_repo, jwt_service)

            auth.register("test@example.com", "password123")
            uow.commit()

            tokens = auth.login("test@example.com", "password123")
            new_tokens = auth.refresh_tokens(tokens.refresh_token)

            assert new_tokens.access_token != tokens.access_token
            assert new_tokens.refresh_token != tokens.refresh_token

    def test_get_current_user(self) -> None:
        with SqlAlchemyUnitOfWork() as uow:
            user_repo = SqlAlchemyUserRepository(uow.session)
            session_repo = SqlAlchemySessionRepository(uow.session)
            jwt_service = JwtService()
            auth = AuthService(user_repo, session_repo, jwt_service)

            user = auth.register("test@example.com", "password123")
            uow.commit()

            tokens = auth.login("test@example.com", "password123")
            # Use token immediately
            current_user = auth.get_current_user(tokens.access_token)

            assert current_user.id == user.id
            assert not current_user.is_writer()

    def test_register_duplicate_email_fails(self) -> None:
        with SqlAlchemyUnitOfWork() as uow:
            user_repo = SqlAlchemyUserRepository(uow.session)
            session_repo = SqlAlchemySessionRepository(uow.session)
            jwt_service = JwtService()
            auth = AuthService(user_repo, session_repo, jwt_service)

            auth.register("test@example.com", "password123")
            uow.commit()

            with pytest.raises(ValueError, match="already registered"):
                auth.register("test@example.com", "different_password")

    def test_inactive_user_cannot_login(self) -> None:
        with SqlAlchemyUnitOfWork() as uow:
            user_repo = SqlAlchemyUserRepository(uow.session)
            session_repo = SqlAlchemySessionRepository(uow.session)
            jwt_service = JwtService()
            auth = AuthService(user_repo, session_repo, jwt_service)

            user = auth.register("test@example.com", "password123")
            uow.commit()

            # Deactivate user
            user.is_active = False
            uow.session.add(user)
            uow.commit()

            with pytest.raises(ValueError, match="deactivated"):
                auth.login("test@example.com", "password123")