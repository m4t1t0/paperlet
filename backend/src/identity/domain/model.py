"""Identity domain model."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from backend.src.shared.domain.events import AggregateRoot, DomainEvent


class UserRole(str, Enum):
    """User capabilities - a user can have multiple."""

    READER = "reader"
    WRITER = "writer"


class UserRegistered(DomainEvent):
    """Event emitted when a user registers."""

    email: str
    role: UserRole


class UserCapabilitiesChanged(DomainEvent):
    """Event emitted when user capabilities change."""

    added_roles: list[UserRole]
    removed_roles: list[UserRole]


@dataclass
class Session:
    """Session for refresh token management."""

    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    refresh_token_hash: str = ""
    expires_at: datetime = field(default_factory=datetime.utcnow)
    revoked_at: Optional[datetime] = None
    user_agent: Optional[str] = None
    ip: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at

    def is_valid(self) -> bool:
        return not self.is_revoked() and not self.is_expired()

    def revoke(self) -> None:
        self.revoked_at = datetime.utcnow()


@dataclass
class User(AggregateRoot):
    """User aggregate - single identity with reader/writer capabilities."""

    id: UUID = field(default_factory=uuid4)
    email: str = ""
    password_hash: str = ""
    roles: set[UserRole] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True
    _events: list = field(default_factory=list, init=False, repr=False)
    # Internal field for ORM mapping - stores roles as JSON
    _roles_json: str = field(default="[]", init=False, repr=False)

    def __post_init__(self) -> None:
        super().__init__()
        if not self.roles:
            self.roles = {UserRole.READER}

    @classmethod
    def register(
        cls, email: str, password_hash: str, role: UserRole = UserRole.READER
    ) -> User:
        """Register a new user."""
        user = cls(
            email=email.lower().strip(),
            password_hash=password_hash,
            roles={role},
        )
        user.add_event(
            UserRegistered(
                aggregate_id=user.id,
                aggregate_type="User",
                email=user.email,
                role=role,
            )
        )
        return user

    def add_role(self, role: UserRole) -> None:
        """Add a capability/role to the user."""
        if role not in self.roles:
            self.roles.add(role)
            self.updated_at = datetime.utcnow()
            self.add_event(
                UserCapabilitiesChanged(
                    aggregate_id=self.id,
                    aggregate_type="User",
                    added_roles=[role],
                    removed_roles=[],
                )
            )

    def remove_role(self, role: UserRole) -> None:
        """Remove a capability/role from the user."""
        if role in self.roles:
            self.roles.discard(role)
            self.updated_at = datetime.utcnow()
            self.add_event(
                UserCapabilitiesChanged(
                    aggregate_id=self.id,
                    aggregate_type="User",
                    added_roles=[],
                    removed_roles=[role],
                )
            )

    def has_role(self, role: UserRole) -> bool:
        """Check if user has a specific role."""
        return role in self.roles

    def is_writer(self) -> bool:
        """Check if user has writer capability."""
        return UserRole.WRITER in self.roles

    def is_reader(self) -> bool:
        """Check if user has reader capability."""
        return UserRole.READER in self.roles

    def verify_password(self, password: str) -> bool:
        """Verify password against hash."""
        from passlib.hash import bcrypt

        return bcrypt.verify(password, self.password_hash)

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password."""
        from passlib.hash import bcrypt

        return bcrypt.hash(password)

    # ORM serialization helpers
    def _sync_roles_to_json(self) -> None:
        """Sync roles set to JSON string for ORM persistence."""
        import json

        self._roles_json = json.dumps([r.value for r in self.roles])

    def _load_roles_from_json(self) -> None:
        """Load roles set from JSON string after ORM load."""
        import json

        if not self._roles_json:
            self.roles = {UserRole.READER}
        else:
            try:
                role_values = json.loads(self._roles_json)
                self.roles = {UserRole(r) for r in role_values}
            except (json.JSONDecodeError, ValueError):
                self.roles = {UserRole.READER}
