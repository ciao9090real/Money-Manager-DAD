# Money Manager

Money Manager is a local-first personal finance system with a Windows desktop app and an Android companion.

- The Windows app owns the complete editing workflow, requires an app password or Windows Hello at launch, and stores data in a SQLCipher-encrypted local database. Its random key is protected for the signed-in Windows user.
- The Android app keeps an independent SQLCipher-encrypted cache for offline access and requires an enrolled fingerprint or other device biometric whenever it opens or returns from the background.
- Sync is opt-in, direct over local Wi-Fi, authenticated, and protected with pinned local HTTPS.
- There is no cloud database, web deployment, or online account.

The Android companion also calculates cash-flow and spending insights locally
from its encrypted cache. Upcoming schedules become in-app reminders according
to the lead time chosen on desktop; sensitive names and amounts never appear in
an operating-system notification or on the lock screen.

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

On the first protected launch, create an app password and optionally register Windows Hello. Later launches can use the password or Windows' face, fingerprint, or device verification prompt. The app also locks when minimized, and Settings includes password/Hello management plus a **Lock now** action.

Settings also includes a plain-language backup center plus checked CSV import/export. Debit-card statements can be imported from CSV or Excel `.xlsx` files by choosing the card, worksheet, statement period, date/description columns, and either a signed amount column or separate debit/credit columns. The preview ignores rows outside the chosen period, reports malformed rows, and skips transactions already present. Secure `.mmbak` backups use a password and are portable; automatic recovery copies are encrypted for the current Windows account. A recovery point is created before any imported rows are written.

## Android

Android setup, run, validation, and pairing instructions are in [`mobile_app/README.md`](mobile_app/README.md).

To pair, start **Android phone sync** from the desktop Settings page. The local HTTPS server exists only while the desktop app is open and phone sync is enabled.
