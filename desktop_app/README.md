# Money Manager Desktop

Modern local-first Windows finance manager built with Python, PySide6, SQLite, and PyInstaller.

The interface includes a responsive financial dashboard, collapsible navigation,
searchable and paginated activity, contextual account controls, an upcoming
payment schedule, a manually valued investment portfolio, polished editors, and
dedicated local storage, backup, export, and category tools.

The current desktop baseline is tagged `desktop-baseline-v1`. Dependencies are
fully pinned in `requirements.lock`, and the Windows CI workflow compiles the
source, runs the database/migration tests, and packages the executable.

Schema version 5 adds ledger-backed investments to the recurring-payment and
synchronization-ready ledger foundation. Existing databases are backed up and
migrated automatically on first launch. Accounts, categories, payment methods,
transactions, recurring rules, and investments use UUIDs, exact integer cents,
UTC audit timestamps, per-record revisions, soft deletion, and tombstones.

The Upcoming page supports fixed subscriptions and variable bills, weekly
through yearly schedules, pausing, skipping, and explicitly recording a payment.
Recording creates a linked expense and advances the schedule atomically. The app
does not post payments automatically or send notifications while it is closed.

The Investments page moves contributions from a funding account into a managed
investment account. Manual valuation updates post only the gain or loss, so the
Dashboard and account hierarchy continue to use the central ledger. Portfolio
value, contributions, gain or loss, and return percentage are calculated
automatically; live market prices are not fetched.

Data is stored outside the repository in:

```text
C:\Users\<username>\AppData\Local\MoneyManagerDAD\money_manager.db
```

The app also creates local `backups`, `exports`, and `logs` folders beside the database. The folder name remains `MoneyManagerDAD` so existing local data keeps working after the visible app rename.

## Run In Development

```powershell
cd desktop_app
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Run Tests

```powershell
cd desktop_app
.\.venv\Scripts\python.exe -m pytest
```

## Build Windows Executable

```powershell
cd desktop_app
.\build.ps1
```

The executable is created at:

```text
desktop_app\dist\MoneyManager\MoneyManager.exe
```

The user database is not bundled into the executable.

## Database Safety

Every connection enables foreign keys, WAL mode, normal synchronous writes, and
a 10-second busy timeout. Migrations create a timestamped SQLite snapshot first
and run integrity and foreign-key checks before and after the schema change.
Manual backups use SQLite's online backup API so WAL data is included.

Every local mutation is recorded in an ordered `change_log` with its origin
device. The database also contains paired-device cursors, conflict records, and
content-hashed attachment metadata. These are foundations for the planned local
Wi-Fi synchronizer; the current desktop build does not yet advertise a network
service or synchronize with a phone.

Keep `money_manager.db` on a local disk. Do not put it in OneDrive, Dropbox, a
shared folder, SMB share, or any network filesystem. Each future phone or laptop
installation must own an independent database; synchronization will exchange
validated changes rather than database files.

Open a separate connection with `app.core.database.connect()` in every worker
thread. Never pass the UI connection to a report or synchronization thread.

## Performance Benchmark

Run the repeatable 100-account/50,000-transaction benchmark with:

```powershell
cd desktop_app
.\.venv\Scripts\python.exe -m tools.benchmark_desktop
```

## Render UI Previews

The headless preview tool renders every main screen, compact layouts, and editor
dialogs using a temporary synthetic database:

```powershell
cd desktop_app
.\.venv\Scripts\python.exe -m tools.render_ui
```

Preview images are written to the ignored repository-level `artifacts` folder.

## Implementation Order

The next product milestone is liabilities: loans and debts backed by explicit
accounts and payment schedules, without creating a second balance system. Local
desktop reminders can then build on recurring-rule reminder dates. Email or
calendar delivery remains a later opt-in integration and is not part of the
local-only desktop baseline.
