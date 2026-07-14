from __future__ import annotations

import tempfile
from datetime import date, timedelta
from pathlib import Path
from time import perf_counter

from app.core.database import connect
from app.repositories.transaction_repository import TransactionRepository
from app.services.account_service import AccountService
from app.services.dashboard_service import DashboardService


ACCOUNT_COUNT = 100
TRANSACTION_COUNT = 50_000


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="money_manager_benchmark_") as directory:
        db = connect(Path(directory) / "benchmark.db")
        try:
            seed(db)
            dashboard = DashboardService(db)
            accounts = AccountService(db)
            transactions = TransactionRepository(db)

            dashboard.summary()
            accounts.account_tree()
            transactions.list(limit=100)

            report(db, "Dashboard summary", dashboard.summary)
            report(db, "Account tree", accounts.account_tree)
            report(db, "Latest 100 transactions", lambda: transactions.list(limit=100))

            plan = db.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT * FROM transactions
                WHERE type = ?
                ORDER BY date DESC, id DESC
                LIMIT 100
                """,
                ("expense",),
            ).fetchall()
            print("Filtered-list query plan:")
            for row in plan:
                print(f"  {row[3]}")
        finally:
            db.close()


def seed(db) -> None:
    with db:
        db.executemany(
            """
            INSERT INTO accounts (name, type, opening_balance, display_order)
            VALUES (?, 'current_account', 1000, ?)
            """,
            ((f"Account {index:03}", index) for index in range(ACCOUNT_COUNT)),
        )
        start = date(2024, 1, 1)
        rows = []
        for index in range(TRANSACTION_COUNT):
            transaction_type = "income" if index % 5 == 0 else "expense"
            amount = "100" if transaction_type == "income" else "-12.34"
            transaction_date = (start + timedelta(days=index % 1_000)).isoformat()
            rows.append(
                (
                    transaction_date,
                    transaction_type,
                    (index % ACCOUNT_COUNT) + 1,
                    amount,
                    f"Benchmark transaction {index}",
                )
            )
        db.executemany(
            """
            INSERT INTO transactions (date, type, account_id, amount, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )


def report(db, label: str, action) -> None:
    durations = []
    select_count = 0

    def trace(sql: str) -> None:
        nonlocal select_count
        if sql.lstrip().upper().startswith(("SELECT", "WITH")):
            select_count += 1

    for _ in range(5):
        select_count = 0
        db.set_trace_callback(trace)
        started = perf_counter()
        action()
        durations.append((perf_counter() - started) * 1_000)
        db.set_trace_callback(None)
    print(f"{label}: {min(durations):.1f} ms, {select_count} SELECT(s)")


if __name__ == "__main__":
    main()
