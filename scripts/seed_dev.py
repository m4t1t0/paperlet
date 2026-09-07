"""Seed development data."""
from __future__ import annotations
from uuid import uuid4

from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork
from backend.src.identity.adapters.orm import create_tables as create_identity_tables
from backend.src.subscriptions.adapters.orm import create_tables as create_sub_tables
from backend.src.publishing.adapters.orm import create_tables as create_pub_tables
from backend.src.identity.domain.model import User, UserRole
from backend.src.subscriptions.domain.model import Subscription, SubscriptionStatus, AllocationSlot
from backend.src.publishing.domain.model import Post, PostStatus


def seed() -> None:
    """Seed development database with test data."""
    print("Creating tables...")
    with SqlAlchemyUnitOfWork() as uow:
        create_identity_tables(uow.session.bind)
        create_sub_tables(uow.session.bind)
        create_pub_tables(uow.session.bind)
        uow.commit()

    print("Seeding users...")
    with SqlAlchemyUnitOfWork() as uow:
        # Create test users
        reader1 = User.register(
            email="reader1@example.com",
            password_hash=User.hash_password("password123"),
            role=UserRole.READER,
        )
        reader2 = User.register(
            email="reader2@example.com",
            password_hash=User.hash_password("password123"),
            role=UserRole.READER,
        )
        writer1 = User.register(
            email="writer1@example.com",
            password_hash=User.hash_password("password123"),
            role=UserRole.WRITER,
        )
        writer1.add_role(UserRole.READER)  # Writers can also be readers
        writer2 = User.register(
            email="writer2@example.com",
            password_hash=User.hash_password("password123"),
            role=UserRole.WRITER,
        )
        writer2.add_role(UserRole.READER)

        uow.session.add_all([reader1, reader2, writer1, writer2])
        uow.commit()

        print(f"Created users: {reader1.email}, {reader2.email}, {writer1.email}, {writer2.email}")

    print("Seeding subscriptions and allocations...")
    with SqlAlchemyUnitOfWork() as uow:
        # Create subscription for reader1
        sub1 = Subscription.create(
            reader_id=reader1.id,
            external_subscription_id="sub_mock_reader1",
            status=SubscriptionStatus.ACTIVE,
        )
        # Allocate to writer1 and writer2
        sub1.allocate_writer(writer1.id)
        sub1.allocate_writer(writer2.id)

        # Create subscription for reader2
        sub2 = Subscription.create(
            reader_id=reader2.id,
            external_subscription_id="sub_mock_reader2",
            status=SubscriptionStatus.ACTIVE,
        )
        # Allocate to writer1 only
        sub2.allocate_writer(writer1.id)

        uow.session.add_all([sub1, sub2])
        uow.commit()

        print(f"Created subscriptions for {reader1.email} and {reader2.email}")

    print("Seeding posts...")
    with SqlAlchemyUnitOfWork() as uow:
        # Writer1 posts
        post1 = Post.create_draft(
            writer_id=writer1.id,
            title="Welcome to My Newsletter",
            preview_content="This is a preview of my first post. Subscribe to read more!",
            subscriber_content="This is the full subscriber-only content. Thanks for subscribing!",
        )
        post1.publish()

        post2 = Post.create_scheduled(
            writer_id=writer1.id,
            title="Upcoming Post",
            preview_content="This post is scheduled for later.",
            subscriber_content="Full content for subscribers.",
            scheduled_for=__import__("datetime").datetime.utcnow() + __import__("datetime").timedelta(days=1),
        )

        # Writer2 posts
        post3 = Post.create_draft(
            writer_id=writer2.id,
            title="Writer 2's First Post",
            preview_content="Preview from writer 2.",
            subscriber_content="Full content from writer 2.",
        )
        post3.publish()

        uow.session.add_all([post1, post2, post3])
        uow.commit()

        print(f"Created posts: {post1.title}, {post2.title}, {post3.title}")

    print("\nSeed complete!")
    print("\nTest accounts:")
    print("  Reader 1: reader1@example.com / password123")
    print("  Reader 2: reader2@example.com / password123")
    print("  Writer 1: writer1@example.com / password123")
    print("  Writer 2: writer2@example.com / password123")


if __name__ == "__main__":
    seed()