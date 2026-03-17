"""Alembic environment configuration."""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine

from src.db.schema import Base

config = context.config

# Override URL from environment if available
url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(url)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
