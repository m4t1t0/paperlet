"""Unit tests for User domain model."""
from __future__ import annotations

from backend.src.identity.domain.model import User, UserRole


class TestUser:
    """Tests for User aggregate."""

    def test_register_creates_user_without_roles(self) -> None:
        # Roles are inferred from activity, never assigned at registration.
        user = User.register("test@example.com", "hashed_password")
        assert user.email == "test@example.com"
        assert user.password_hash == "hashed_password"
        assert user.roles == set()
        assert not user.is_reader()
        assert not user.is_writer()
        assert user.is_active is True

    def test_register_emits_event(self) -> None:
        user = User.register("test@example.com", "hashed_password")
        events = user.events
        assert len(events) == 1
        assert events[0].__class__.__name__ == "UserRegistered"

    def test_add_role(self) -> None:
        user = User.register("test@example.com", "hash")
        user.clear_events()
        user.add_role(UserRole.WRITER)
        assert UserRole.WRITER in user.roles
        events = user.events
        assert len(events) == 1
        assert events[0].__class__.__name__ == "UserCapabilitiesChanged"

    def test_remove_role(self) -> None:
        user = User.register("test@example.com", "hash")
        user.add_role(UserRole.WRITER)
        user.clear_events()
        user.remove_role(UserRole.WRITER)
        assert UserRole.WRITER not in user.roles
        events = user.events
        assert len(events) == 1

    def test_has_role(self) -> None:
        user = User.register("test@example.com", "hash")
        assert not user.has_role(UserRole.READER)
        user.add_role(UserRole.READER)
        assert user.has_role(UserRole.READER)
        assert not user.has_role(UserRole.WRITER)

    def test_is_writer(self) -> None:
        user = User.register("test@example.com", "hash")
        assert not user.is_writer()
        user.add_role(UserRole.WRITER)
        assert user.is_writer()

    def test_is_reader(self) -> None:
        user = User.register("test@example.com", "hash")
        assert not user.is_reader()
        user.add_role(UserRole.READER)
        assert user.is_reader()

    def test_verify_password(self) -> None:
        password = "secure_password"
        user = User.register("test@example.com", User.hash_password(password))
        assert user.verify_password(password)
        assert not user.verify_password("wrong_password")

    def test_email_normalization(self) -> None:
        user = User.register("  TEST@EXAMPLE.COM  ", "hash")
        assert user.email == "test@example.com"
