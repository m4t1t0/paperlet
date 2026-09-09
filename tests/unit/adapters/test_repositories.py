"""Unit adapter tests: repositories + UoW on SQLite (unique data per test)."""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import text

from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork
from backend.src.identity.domain.model import User, UserRole
from backend.src.identity.adapters.sqlalchemy_repository import (
    SqlAlchemyUserRepository,
)
from backend.src.subscriptions.domain.model import Subscription, SubscriptionStatus
from backend.src.subscriptions.adapters.sqlalchemy_repository import (
    SqlAlchemySubscriptionRepository,
)
from backend.src.subscriptions.adapters.read_model import AllocationLogProjection
from backend.src.publishing.domain.model import Post
from backend.src.publishing.adapters.sqlalchemy_repository import (
    SqlAlchemyPostRepository,
)


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}@test.com"


def _make_user(email: str, role: UserRole = UserRole.READER) -> User:
    return User.register(email, "hash-not-bcrypt", role)


class TestUserRepository:
    def test_add_get_and_roles_round_trip(self) -> None:
        email = _unique_email("urepo")
        with SqlAlchemyUnitOfWork() as uow:
            repo = SqlAlchemyUserRepository(uow.session)
            user = _make_user(email, UserRole.WRITER)
            user_id = user.id
            repo.add(user)
            uow.commit()

        with SqlAlchemyUnitOfWork() as uow:
            repo = SqlAlchemyUserRepository(uow.session)
            loaded = repo.get(user_id)
            assert loaded is not None
            assert loaded.email == email
            assert loaded.is_writer()
            assert repo.get_by_email(email).id == user_id
            assert any(u.id == user_id for u in repo.list())

    def test_add_role_persists(self) -> None:
        email = _unique_email("urole")
        with SqlAlchemyUnitOfWork() as uow:
            repo = SqlAlchemyUserRepository(uow.session)
            user = _make_user(email)
            user_id = user.id
            repo.add(user)
            uow.commit()

        with SqlAlchemyUnitOfWork() as uow:
            repo = SqlAlchemyUserRepository(uow.session)
            user = repo.get(user_id)
            user.add_role(UserRole.WRITER)
            uow.commit()

        with SqlAlchemyUnitOfWork() as uow:
            repo = SqlAlchemyUserRepository(uow.session)
            assert repo.get(user_id).is_writer()


class TestSubscriptionRepository:
    def _reader_id(self) -> object:
        email = _unique_email("srepo")
        with SqlAlchemyUnitOfWork() as uow:
            repo = SqlAlchemyUserRepository(uow.session)
            user = _make_user(email)
            repo.add(user)
            uow.commit()
            return user.id

    def test_add_get_and_lookups(self) -> None:
        reader_id = self._reader_id()
        with SqlAlchemyUnitOfWork() as uow:
            repo = SqlAlchemySubscriptionRepository(uow.session)
            sub = Subscription.create(reader_id, "ext-unit-1", SubscriptionStatus.ACTIVE)
            sub_id = sub.id
            repo.add(sub)
            uow.commit()

        with SqlAlchemyUnitOfWork() as uow:
            repo = SqlAlchemySubscriptionRepository(uow.session)
            assert repo.get(sub_id).id == sub_id
            assert repo.get_by_reader(reader_id).id == sub_id
            assert repo.get_by_external_id("ext-unit-1").id == sub_id

    def test_get_by_reader_only_returns_active(self) -> None:
        reader_id = self._reader_id()
        with SqlAlchemyUnitOfWork() as uow:
            repo = SqlAlchemySubscriptionRepository(uow.session)
            repo.add(
                Subscription.create(reader_id, "ext-unit-2", SubscriptionStatus.INCOMPLETE)
            )
            uow.commit()

        with SqlAlchemyUnitOfWork() as uow:
            repo = SqlAlchemySubscriptionRepository(uow.session)
            assert repo.get_by_reader(reader_id) is None


class TestPostRepository:
    def _writer_id(self) -> object:
        email = _unique_email("prepo")
        with SqlAlchemyUnitOfWork() as uow:
            repo = SqlAlchemyUserRepository(uow.session)
            user = _make_user(email, UserRole.WRITER)
            repo.add(user)
            uow.commit()
            return user.id

    def test_add_get_and_by_writer(self) -> None:
        writer_id = self._writer_id()
        with SqlAlchemyUnitOfWork() as uow:
            repo = SqlAlchemyPostRepository(uow.session)
            post = Post.create_draft(writer_id, "T", "PRE", "SUB")
            post_id = post.id
            repo.add(post)
            uow.commit()

        with SqlAlchemyUnitOfWork() as uow:
            repo = SqlAlchemyPostRepository(uow.session)
            assert repo.get(post_id).title == "T"
            assert len(repo.get_by_writer(writer_id)) == 1

    def test_published_feed_order_and_cursor(self) -> None:
        writer_id = self._writer_id()
        base = datetime.utcnow() - timedelta(days=2)
        with SqlAlchemyUnitOfWork() as uow:
            repo = SqlAlchemyPostRepository(uow.session)
            old = Post.create_draft(writer_id, "Old", "PRE", "SUB")
            old.publish()
            old.published_at = base
            new = Post.create_draft(writer_id, "New", "PRE", "SUB")
            new.publish()
            new.published_at = base + timedelta(days=1)
            repo.add(old)
            repo.add(new)
            uow.commit()

        with SqlAlchemyUnitOfWork() as uow:
            repo = SqlAlchemyPostRepository(uow.session)
            feed = repo.get_published_for_feed([writer_id], limit=10)
            titles = [p.title for p in feed]
            assert titles.index("New") < titles.index("Old")
            first_page = repo.get_published_for_feed([writer_id], limit=1)
            assert len(first_page) == 2  # limit+1 signals more
            cursor = first_page[0].published_at.isoformat()
            second = repo.get_published_for_feed([writer_id], limit=10, cursor=cursor)
            assert [p.title for p in second] == ["Old"]


class TestAllocationLogProjection:
    def test_persist_allocate_event(self) -> None:
        reader_email, writer_email = _unique_email("alog-r"), _unique_email("alog-w")
        with SqlAlchemyUnitOfWork() as uow:
            user_repo = SqlAlchemyUserRepository(uow.session)
            reader = _make_user(reader_email)
            writer = _make_user(writer_email, UserRole.WRITER)
            user_repo.add(reader)
            user_repo.add(writer)
            uow.commit()
            reader_id, writer_id = reader.id, writer.id

        with SqlAlchemyUnitOfWork() as uow:
            sub_repo = SqlAlchemySubscriptionRepository(uow.session)
            sub = Subscription.create(reader_id, "ext-alog-1", SubscriptionStatus.ACTIVE)
            sub_repo.add(sub)
            uow.commit()
            sub_id = sub.id

        with SqlAlchemyUnitOfWork() as uow:
            sub_repo = SqlAlchemySubscriptionRepository(uow.session)
            sub = sub_repo.get(sub_id)
            sub.allocate_writer(writer_id)
            AllocationLogProjection(uow.session).handle(sub.events[-1])
            uow.commit()

        with SqlAlchemyUnitOfWork() as uow:
            # Raw UUID params don't bind on SQLite (PG_UUID type) and stored
            # UUIDs are dashless hex; filter in Python.
            rows = uow.session.execute(
                text("SELECT subscription_id, action, credits_spent FROM allocation_log")
            ).all()
            mine = [r for r in rows if str(r[0]).replace("-", "") == sub_id.hex]
            assert len(mine) == 1
            assert mine[0][1] == "allocate"
            assert mine[0][2] == 0


class TestUnitOfWork:
    def test_rollback_discards_changes(self) -> None:
        email = _unique_email("uow")
        with SqlAlchemyUnitOfWork() as uow:
            repo = SqlAlchemyUserRepository(uow.session)
            repo.add(_make_user(email))
            uow.rollback()

        with SqlAlchemyUnitOfWork() as uow:
            repo = SqlAlchemyUserRepository(uow.session)
            assert repo.get_by_email(email) is None
