from __future__ import annotations

import calendar
import sqlite3
from datetime import date
from decimal import Decimal

from app.core.database import unit_of_work
from app.models.net_worth import NetWorthPoint
from app.services.dashboard_service import DashboardService
from app.utils.money import cents_to_decimal, decimal_to_cents


UTC_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
ZERO = Decimal("0")


class NetWorthService:
    """Current and historical gross asset and liability positions."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.dashboard = DashboardService(db)

    def current(self) -> NetWorthPoint:
        snapshot = self.dashboard.global_snapshot()

        # Investment market values already live in their linked investment
        # accounts, so the account balances must only be counted once here.
        assets = sum(
            (max(row["balance"], ZERO) for row in snapshot["accounts"]),
            ZERO,
        ) + snapshot["loan_receivables"]
        liabilities = sum(
            (max(-row["balance"], ZERO) for row in snapshot["accounts"]),
            ZERO,
        ) + snapshot["borrowed_loans"]

        return NetWorthPoint(
            date=date.today().isoformat(),
            assets=assets,
            liabilities=liabilities,
            net_worth=assets - liabilities,
        )

    def record_snapshot(self) -> NetWorthPoint:
        """Store today's point, updating it only if its values changed."""

        point = self.current()
        assets_cents = decimal_to_cents(point.assets)
        liabilities_cents = decimal_to_cents(point.liabilities)

        with unit_of_work(self.db):
            existing = self.db.execute(
                """
                SELECT assets_cents, liabilities_cents, deleted_at
                FROM net_worth_snapshots
                WHERE date = ?
                """,
                (point.date,),
            ).fetchone()
            if existing is None:
                self.db.execute(
                    """
                    INSERT INTO net_worth_snapshots (
                        date, assets_cents, liabilities_cents
                    ) VALUES (?, ?, ?)
                    """,
                    (point.date, assets_cents, liabilities_cents),
                )
            elif (
                int(existing["assets_cents"]) != assets_cents
                or int(existing["liabilities_cents"]) != liabilities_cents
                or existing["deleted_at"] is not None
            ):
                self.db.execute(
                    f"""
                    UPDATE net_worth_snapshots
                    SET assets_cents = ?, liabilities_cents = ?, deleted_at = NULL,
                        updated_at = {UTC_NOW}, revision = revision + 1
                    WHERE date = ?
                    """,
                    (assets_cents, liabilities_cents, point.date),
                )
        return point

    def history(
        self,
        months: int = 12,
        reference_date: date | None = None,
    ) -> list[NetWorthPoint]:
        """Return deterministic month-end points, ending at the reference date.

        An exact recorded snapshot is authoritative. Missing dates are rebuilt
        from the current ledger schema and marked estimated because account
        opening balances and activation changes do not have effective dates.
        """

        if months < 1:
            raise ValueError("Months must be at least 1")

        reference = reference_date or date.today()
        points: list[NetWorthPoint] = []
        for cutoff in self._monthly_cutoffs(months, reference):
            recorded = self._recorded_point(cutoff.isoformat())
            if recorded is not None:
                points.append(recorded)
            elif cutoff == date.today():
                points.append(self.current())
            else:
                points.append(self._historical_point(cutoff))
        return points

    def _recorded_point(self, point_date: str) -> NetWorthPoint | None:
        row = self.db.execute(
            """
            SELECT date, assets_cents, liabilities_cents
            FROM net_worth_snapshots
            WHERE date = ? AND deleted_at IS NULL
            """,
            (point_date,),
        ).fetchone()
        if row is None:
            return None
        assets = cents_to_decimal(row["assets_cents"])
        liabilities = cents_to_decimal(row["liabilities_cents"])
        return NetWorthPoint(
            date=row["date"],
            assets=assets,
            liabilities=liabilities,
            net_worth=assets - liabilities,
        )

    def _historical_point(self, cutoff: date) -> NetWorthPoint:
        cutoff_iso = cutoff.isoformat()
        account_rows = self.db.execute(
            """
            SELECT a.opening_balance_cents
                       + COALESCE(SUM(t.amount_cents), 0) AS balance_cents
            FROM accounts AS a
            LEFT JOIN transactions AS t
              ON t.account_id = a.id
             AND t.deleted_at IS NULL
             AND t.date <= ?
            WHERE a.deleted_at IS NULL
              AND a.is_active = 1
            GROUP BY a.id
            """,
            (cutoff_iso,),
        ).fetchall()

        asset_cents = 0
        liability_cents = 0
        for row in account_rows:
            balance_cents = int(row["balance_cents"] or 0)
            if balance_cents >= 0:
                asset_cents += balance_cents
            else:
                liability_cents += -balance_cents

        loan_rows = self.db.execute(
            """
            SELECT loans.direction,
                   loans.principal_cents - COALESCE(SUM(payments.amount_cents), 0)
                       AS outstanding_cents
            FROM loans
            LEFT JOIN loan_payments AS payments
              ON payments.loan_id = loans.id
             AND payments.deleted_at IS NULL
             AND payments.date <= ?
            WHERE loans.deleted_at IS NULL
              AND loans.start_date <= ?
            GROUP BY loans.id
            """,
            (cutoff_iso, cutoff_iso),
        ).fetchall()
        for row in loan_rows:
            outstanding_cents = max(int(row["outstanding_cents"] or 0), 0)
            if row["direction"] == "borrowed":
                liability_cents += outstanding_cents
            else:
                asset_cents += outstanding_cents

        assets = cents_to_decimal(asset_cents)
        liabilities = cents_to_decimal(liability_cents)
        return NetWorthPoint(
            date=cutoff_iso,
            assets=assets,
            liabilities=liabilities,
            net_worth=assets - liabilities,
            estimated=True,
        )

    @staticmethod
    def _monthly_cutoffs(months: int, reference: date) -> list[date]:
        reference_index = reference.year * 12 + reference.month - 1
        cutoffs: list[date] = []
        for offset in reversed(range(months)):
            month_index = reference_index - offset
            year, zero_based_month = divmod(month_index, 12)
            month = zero_based_month + 1
            if year == reference.year and month == reference.month:
                cutoffs.append(reference)
            else:
                last_day = calendar.monthrange(year, month)[1]
                cutoffs.append(date(year, month, last_day))
        return cutoffs
