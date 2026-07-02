# Runs Alembic migrations at container start (see entrypoint.sh).
#
# Databases created before Alembic was introduced already have the tables
# from revision 0001 (via postgres-init SQL or create_all) but no
# alembic_version table — stamp those at 0001 so upgrade only applies
# newer revisions instead of failing on CREATE TABLE.
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.database import engine

BASELINE_REVISION = "0001"
BASELINE_TABLE = "users"


def main() -> None:
    cfg = Config("alembic.ini")
    tables = inspect(engine).get_table_names()

    if "alembic_version" not in tables and BASELINE_TABLE in tables:
        print(f"[migrations] Existing schema without alembic_version; stamping {BASELINE_REVISION}")
        command.stamp(cfg, BASELINE_REVISION)

    command.upgrade(cfg, "head")
    print("[migrations] Database is up to date")


if __name__ == "__main__":
    main()
