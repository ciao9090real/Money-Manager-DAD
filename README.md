# Money Manager

Money Manager is a local-first personal finance system with a Windows desktop app and an Android companion.

- The Windows app owns the complete editing workflow and stores data in local SQLite.
- The Android app keeps an independent SQLite cache for offline access.
- Sync is opt-in, direct over local Wi-Fi, authenticated, and protected with pinned local HTTPS.
- There is no cloud database, web deployment, or online account.

```text
Money-Manager-DAD/
  desktop_app/   PySide6 Windows application, tests, and packaging
  mobile_app/    Flutter Android companion
```

## Desktop

```powershell
cd desktop_app
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Build the Windows executable with:

```powershell
cd desktop_app
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

The database is stored by default at:

```text
%LOCALAPPDATA%\MoneyManagerDAD\money_manager.db
```

## Android

Android setup, run, validation, and pairing instructions are in [`mobile_app/README.md`](mobile_app/README.md).

To pair, start **Android phone sync** from the desktop Settings page. The local HTTPS server exists only while the desktop app is open and phone sync is enabled.
