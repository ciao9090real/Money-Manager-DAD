PRAGMA foreign_keys = ON;

CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    parent_id INTEGER REFERENCES accounts(id),
    opening_balance NUMERIC NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE payment_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    type TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    type TEXT NOT NULL,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    payment_method_id INTEGER REFERENCES payment_methods(id),
    amount NUMERIC NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category_id INTEGER REFERENCES categories(id),
    transfer_group_id TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX idx_accounts_parent ON accounts(parent_id);
CREATE INDEX idx_transactions_account ON transactions(account_id);
CREATE INDEX idx_transactions_date ON transactions(date);
CREATE INDEX idx_transactions_transfer_group ON transactions(transfer_group_id);

INSERT INTO accounts (id, name, type, opening_balance, display_order)
VALUES (1, 'Current', 'current_account', 100, 1),
       (2, 'Savings', 'savings_account', 50, 2);
INSERT INTO payment_methods (id, name, account_id, type)
VALUES (1, 'Debit card', 1, 'debit_card');
INSERT INTO categories (id, name, type)
VALUES (1, 'Salary', 'income'), (2, 'Groceries', 'expense');
INSERT INTO transactions
    (id, date, type, account_id, payment_method_id, amount, description, category_id, transfer_group_id)
VALUES
    (1, '2026-07-01', 'income', 1, 1, 25, 'Salary', 1, NULL),
    (2, '2026-07-02', 'expense', 1, 1, -10, 'Food', 2, NULL),
    (3, '2026-07-03', 'transfer_out', 1, NULL, -20, 'Move', NULL, 'fixture-transfer'),
    (4, '2026-07-03', 'transfer_in', 2, NULL, 20, 'Move', NULL, 'fixture-transfer');
PRAGMA user_version = 1;
