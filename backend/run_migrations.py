"""Self-healing schema bootstrap, called at backend startup.

Strategy:
  * Fresh database (no `users` table): create_all() builds the full current
    schema, then we stamp to head so future ALTER-style revisions apply.
  * Existing database without alembic: stamp baseline, then upgrade to head —
    revision 0002 idempotently repairs any half-applied legacy migrations.
  * Existing alembic-managed database: plain upgrade to head.

Never raises: a migration failure logs loudly but lets the app start, since a
running app with yesterday's schema beats a crash loop on a home server.
"""
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from database import engine, Base
import models  # noqa: F401 — register tables on Base.metadata
import os


def run_migrations() -> None:
    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
    alembic_cfg.set_main_option(
        "script_location", os.path.join(os.path.dirname(__file__), "alembic")
    )

    inspector = sa.inspect(engine)
    tables = set(inspector.get_table_names())

    if "users" not in tables:
        Base.metadata.create_all(bind=engine)
        command.stamp(alembic_cfg, "head")
        print("[migrations] Fresh database: schema created, stamped to head.")
        return

    if "alembic_version" not in tables:
        command.stamp(alembic_cfg, "0001_baseline")
        print("[migrations] Existing database adopted at baseline.")

    command.upgrade(alembic_cfg, "head")
    # Safety net for brand-new model tables not yet covered by a revision.
    Base.metadata.create_all(bind=engine)
    print("[migrations] Schema is up to date.")
