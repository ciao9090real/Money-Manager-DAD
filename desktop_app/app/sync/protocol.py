from __future__ import annotations


PROTOCOL_VERSION = 1

# Additive changes to the portable entity set do not change the HTTP command
# envelope, so they keep protocol v1.  The phone acknowledges this independent
# version only after applying a snapshot to its local cache.
ENTITY_SET_VERSION = 1

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
    "budgets",
    "net_worth_snapshots",
    "savings_goals",
    "transactions",
)

# Most portable records are UUID entities.  Net-worth history intentionally
# uses its ISO date as the stable primary key instead.
SYNC_ENTITY_ID_COLUMNS = {
    "net_worth_snapshots": "date",
}

COMMAND_TYPES = {
    "create_income",
    "create_expense",
    "create_transfer",
    "record_recurring",
    "add_goal_contribution",
}
