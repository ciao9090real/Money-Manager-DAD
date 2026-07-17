from __future__ import annotations


PROTOCOL_VERSION = 1

# The phone keeps its own SQLite database. These are the portable financial
# records it can mirror; desktop-only preferences and attachments stay local.
SYNC_ENTITIES = (
    "accounts",
    "categories",
    "payment_methods",
    "recurring_rules",
    "investments",
    "investment_value_history",
    "loans",
    "loan_payments",
    "transactions",
)

COMMAND_TYPES = {
    "create_income",
    "create_expense",
    "create_transfer",
    "record_recurring",
}
