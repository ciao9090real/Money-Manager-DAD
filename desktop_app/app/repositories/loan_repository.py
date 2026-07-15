from __future__ import annotations

import sqlite3
from decimal import Decimal
from uuid import uuid4

from app.models.loan import Loan, LoanPayment
from app.utils.money import cents_to_decimal, decimal_to_cents


UTC_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def row_to_loan(row: sqlite3.Row) -> Loan:
    return Loan(
        id=row["id"],
        direction=row["direction"],
        name=row["name"],
        counterparty=row["counterparty"],
        principal=cents_to_decimal(row["principal_cents"]),
        account_id=row["account_id"],
        start_date=row["start_date"],
        due_date=row["due_date"],
        interest_rate=(Decimal(int(row["interest_rate_bps"])) / Decimal("100")),
        notes=row["notes"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
        revision=row["revision"],
    )


def row_to_payment(row: sqlite3.Row) -> LoanPayment:
    return LoanPayment(
        id=row["id"],
        loan_id=row["loan_id"],
        account_id=row["account_id"],
        transaction_id=row["transaction_id"],
        amount=cents_to_decimal(row["amount_cents"]),
        date=row["date"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
        revision=row["revision"],
    )


class LoanRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def list_with_balances(
        self,
        *,
        direction: str | None = None,
        include_settled: bool = True,
    ) -> list[tuple[Loan, Decimal, Decimal]]:
        query = """
            WITH payment_totals AS (
                SELECT loan_id, SUM(amount_cents) AS paid_cents
                FROM loan_payments
                WHERE deleted_at IS NULL
                GROUP BY loan_id
            )
            SELECT loans.*,
                   COALESCE(payment_totals.paid_cents, 0) AS paid_cents,
                   loans.principal_cents - COALESCE(payment_totals.paid_cents, 0)
                       AS outstanding_cents
            FROM loans
            LEFT JOIN payment_totals ON payment_totals.loan_id = loans.id
            WHERE loans.deleted_at IS NULL
        """
        params: list[object] = []
        if direction is not None:
            query += " AND loans.direction = ?"
            params.append(direction)
        if not include_settled:
            query += " AND loans.status = 'active'"
        query += " ORDER BY loans.status, COALESCE(loans.due_date, '9999-12-31'), loans.name"
        return [
            (
                row_to_loan(row),
                cents_to_decimal(row["paid_cents"]),
                cents_to_decimal(row["outstanding_cents"]),
            )
            for row in self.db.execute(query, params)
        ]

    def get(self, loan_id: str) -> Loan | None:
        row = self.db.execute(
            "SELECT * FROM loans WHERE id = ? AND deleted_at IS NULL",
            (loan_id,),
        ).fetchone()
        return row_to_loan(row) if row else None

    def create(self, loan: Loan) -> Loan:
        loan_id = loan.id or str(uuid4())
        self.db.execute(
            """
            INSERT INTO loans (
                id, direction, name, counterparty, principal_cents, account_id,
                start_date, due_date, interest_rate_bps, notes, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                loan_id,
                loan.direction,
                loan.name,
                loan.counterparty,
                decimal_to_cents(loan.principal),
                loan.account_id,
                loan.start_date,
                loan.due_date,
                int(loan.interest_rate * 100),
                loan.notes,
                loan.status,
            ),
        )
        created = self.get(loan_id)
        assert created is not None
        return created

    def update(self, loan: Loan) -> Loan:
        if loan.id is None:
            raise ValueError("Loan id is required")
        self.db.execute(
            f"""
            UPDATE loans
            SET name = ?, counterparty = ?, due_date = ?, interest_rate_bps = ?,
                notes = ?, status = ?, updated_at = {UTC_NOW}, revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
            """,
            (
                loan.name,
                loan.counterparty,
                loan.due_date,
                int(loan.interest_rate * 100),
                loan.notes,
                loan.status,
                loan.id,
            ),
        )
        updated = self.get(loan.id)
        assert updated is not None
        return updated

    def list_payments(self, loan_id: str) -> list[LoanPayment]:
        return [
            row_to_payment(row)
            for row in self.db.execute(
                """
                SELECT * FROM loan_payments
                WHERE loan_id = ? AND deleted_at IS NULL
                ORDER BY date DESC, id DESC
                """,
                (loan_id,),
            )
        ]

    def create_payment(self, payment: LoanPayment) -> LoanPayment:
        payment_id = payment.id or str(uuid4())
        self.db.execute(
            """
            INSERT INTO loan_payments (
                id, loan_id, account_id, transaction_id, amount_cents, date, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payment_id,
                payment.loan_id,
                payment.account_id,
                payment.transaction_id,
                decimal_to_cents(payment.amount),
                payment.date,
                payment.notes,
            ),
        )
        row = self.db.execute(
            "SELECT * FROM loan_payments WHERE id = ? AND deleted_at IS NULL",
            (payment_id,),
        ).fetchone()
        assert row is not None
        return row_to_payment(row)
