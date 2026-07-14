# Money Manager Desktop

Modern local-first Windows finance manager built with Python, PySide6, SQLite, and PyInstaller.

The interface includes a responsive financial dashboard, collapsible navigation,
searchable and paginated activity, contextual account controls, polished editors,
and dedicated local storage, backup, export, and category tools.

The current desktop baseline is tagged `desktop-baseline-v1`. Dependencies are
fully pinned in `requirements.lock`, and the Windows CI workflow compiles the
source, runs the database/migration tests, and packages the executable.

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
