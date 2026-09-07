"""Alembic environment configuration."""
from __future__ import annotations
from logging.config import fileConfig
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

# Import all models to register them
from backend.src.identity.adapters.orm import mapper_registry as identity_registry
from backend.src.subscriptions.adapters.orm import mapper_registry as subscriptions_registry
from backend.src.publishing.adapters.orm import mapper_registry as publishing_registry
from backend.src.shared.config import get_settings

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Combine all metadata
target_metadata = [
    identity_registry.metadata,
    subscriptions_registry.metadata,
    publishing_registry.metadata,
]


def get_database_url() -> str:
    """Get database URL from settings."""
    return get_settings().database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_engine(
        get_database_url(),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()