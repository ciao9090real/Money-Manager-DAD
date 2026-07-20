# Money Manager Android

The Android companion keeps its own SQLite cache and works offline after pairing. Sync is direct between the phone and the Windows desktop over the same local Wi-Fi network; there is no cloud account or shared database file.

## Tooling

1. Install Android Studio and its Android SDK.
2. Add `C:\Users\leona\development\flutter\bin` to `PATH`, or call `flutter.bat` by its full path.
3. Run `flutter doctor` and complete the Android SDK license prompts yourself.
4. Connect an Android phone with USB debugging enabled, or start an Android emulator.

## Run

```powershell
cd mobile_app
C:\Users\leona\development\flutter\bin\flutter.bat pub get
C:\Users\leona\development\flutter\bin\flutter.bat run
```

## Pair

1. Keep the phone and PC on the same private Wi-Fi network.
2. In the desktop app, open **Settings > Android phone sync** and select **Start phone sync**.
3. In the Android app, open **More > Connect desktop**.
4. Scan the QR code shown on the PC. The app securely reads the desktop address, one-time code, and certificate fingerprint from it.
5. Leave the desktop app open while synchronizing.

The phone can browse accounts, balances, transactions, investments, loans, recurring schedules, monthly budgets, and savings goals. Its dashboard also shows net-worth history, savings rate, emergency-fund coverage, budget pressure, and goal progress. Each borrowed loan includes an offline payoff planner with an extra-payment comparison and monthly amortization schedule.

Budget and goal setup remains on the desktop, which is the source of truth. The phone can queue income, expenses, transfers, recurring-payment records, and manual savings-goal contributions offline. The desktop validates and applies those commands exactly once on the next sync.

When a release adds newly synchronized record types, the phone requests one fresh snapshot and stores the new data-set version atomically with its cursor. Existing offline records and pending commands remain safe if a sync is interrupted.

## Validate

```powershell
C:\Users\leona\development\flutter\bin\cache\dart-sdk\bin\dart.exe analyze
C:\Users\leona\development\flutter\bin\flutter.bat test
C:\Users\leona\development\flutter\bin\flutter.bat build apk --debug
```
