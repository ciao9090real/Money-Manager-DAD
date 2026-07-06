from __future__ import annotations

from pathlib import Path

from sqlalchemy import MetaData, create_engine, delete, insert, select

from app.core.config import settings


BASE_DIR = Path(__file__).resolve().parent
SQLITE_URL = f"sqlite:///{BASE_DIR / 'money_manager.db'}"
POSTGRES_URL = settings.database_url

TABLE_ORDER = [
    "users",
    "user_settings",
    "categories",
    "banks",
    "accounts",
    "cards",
    "assets",
    "portfolios",
    "investment_summaries",
    "holdings",
    "import_templates",
    "import_batches",
    "transactions",
    "imported_rows",
    "investment_transactions",
    "insurance_policies",
    "insurance_payments",
    "recurring_payments",
]


def table_counts(engine, metadata: MetaData) -> dict[str, int]:
    counts: dict[str, int] = {}
    with engine.connect() as connection:
        for table_name in TABLE_ORDER:
            table = metadata.tables[table_name]
            counts[table_name] = len(connection.execute(select(table)).mappings().all())
    return counts


def main() -> None:
    if not POSTGRES_URL.startswith("postgresql"):
        raise RuntimeError("DATABASE_URL must point to Postgres before running this migration.")

    sqlite_engine = create_engine(SQLITE_URL, future=True)
    postgres_engine = create_engine(POSTGRES_URL, future=True)

    sqlite_metadata = MetaData()
    postgres_metadata = MetaData()
    sqlite_metadata.reflect(bind=sqlite_engine)
    postgres_metadata.reflect(bind=postgres_engine)

    missing = [name for name in TABLE_ORDER if name not in sqlite_metadata.tables or name not in postgres_metadata.tables]
    if missing:
        raise RuntimeError(f"Missing tables: {', '.join(missing)}")

    copied: dict[str, int] = {}
    with sqlite_engine.connect() as source, postgres_engine.begin() as target:
        for table_name in reversed(TABLE_ORDER):
            target.execute(delete(postgres_metadata.tables[table_name]))

        for table_name in TABLE_ORDER:
            source_table = sqlite_metadata.tables[table_name]
            target_table = postgres_metadata.tables[table_name]
            rows = [dict(row) for row in source.execute(select(source_table)).mappings().all()]
            copied[table_name] = len(rows)
            if rows:
                target.execute(insert(target_table), rows)

        for table_name in TABLE_ORDER:
            table = postgres_metadata.tables[table_name]
            if "id" in table.c:
                target.exec_driver_sql(
                    "SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE((SELECT MAX(id) FROM "
                    + table_name
                    + "), 1), true)",
                    (table_name,),
                )

    print("Copied SQLite data to Postgres:")
    for table_name, count in copied.items():
        print(f"{table_name}: {count}")


if __name__ == "__main__":
    main()
