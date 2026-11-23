from alembic import context
from sqlalchemy import engine_from_config, pool

# add your model's MetaData here for 'autogenerate' support
# from myproject import mymodel
# target_metadata = mymodel.Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This is used by 'alembic upgrade' without specifying a database.
    """
    url = context.get_x_argument(as_dict=True).get("sqlalchemy.url")
    if url is None:
        raise RuntimeError(
            "SQLAlchemy url not specified. "
            "Set it with --sqlalchemy.url or in .ini file."
        )
    context.configure(url=url, target_metadata=None, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    This is used by 'alembic upgrade head', etc.
    """
    connectable = engine_from_config(
        context.get_x_argument(as_dict=True),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)

        with context.begin_transaction():
            context.run_migrations()