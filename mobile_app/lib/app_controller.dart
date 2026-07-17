import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

import 'data/local_database.dart';
import 'data/sync_client.dart';
import 'models/finance_models.dart';

class AppController extends ChangeNotifier {
  AppController({
    required this.database,
    required this.syncClient,
    FlutterSecureStorage? secureStorage,
  }) : secureStorage = secureStorage ?? const FlutterSecureStorage();

  final LocalDatabase database;
  final SyncClient syncClient;
  final FlutterSecureStorage secureStorage;

  List<AccountRecord> accounts = const [];
  List<TransactionRecord> transactions = const [];
  List<RecurringRecord> recurring = const [];
  List<StoredRecord> investments = const [];
  List<StoredRecord> loans = const [];
  List<PendingCommand> pendingCommands = const [];
  PairingCredentials? credentials;
  bool isSyncing = false;
  String? syncError;
  String? lastSyncAt;

  bool get isPaired => credentials != null;
  int get pendingCount =>
      pendingCommands.where((command) => command.status == 'pending').length;
  int get failedCount =>
      pendingCommands.where((command) => command.status == 'failed').length;

  Future<void> initialize() async {
    await database.initialize();
    credentials = await _readCredentials();
    await reload();
  }

  Future<void> reload() async {
    final accountRows = await database.records('accounts');
    final transactionRows = await database.records('transactions');
    final recurringRows = await database.records('recurring_rules');
    accounts =
        accountRows
            .map((row) => AccountRecord.fromJson(row.payload))
            .where((account) => account.isActive)
            .toList()
          ..sort(
            (a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()),
          );
    transactions =
        transactionRows
            .map((row) => TransactionRecord.fromJson(row.payload))
            .toList()
          ..sort((a, b) {
            final date = b.date.compareTo(a.date);
            return date == 0 ? b.id.compareTo(a.id) : date;
          });
    recurring =
        recurringRows
            .map((row) => RecurringRecord.fromJson(row.payload))
            .toList()
          ..sort((a, b) => a.nextDueDate.compareTo(b.nextDueDate));
    investments = await database.records('investments');
    loans = await database.records('loans');
    pendingCommands = await database.pendingCommands();
    lastSyncAt = await database.state('last_sync_at');
    notifyListeners();
  }

  int balanceFor(String accountId) {
    AccountRecord? account;
    for (final item in accounts) {
      if (item.id == accountId) {
        account = item;
        break;
      }
    }
    if (account == null) return 0;
    return account.openingBalanceCents +
        transactions
            .where((transaction) => transaction.accountId == accountId)
            .fold<int>(0, (sum, transaction) => sum + transaction.amountCents);
  }

  int get netWorthCents =>
      accounts.fold<int>(0, (sum, account) => sum + balanceFor(account.id));

  int get liquidityCents {
    const liquidTypes = {
      'bank',
      'current_account',
      'savings_account',
      'cash',
      'wallet',
      'benefit',
    };
    return accounts
        .where((account) => liquidTypes.contains(account.type))
        .fold<int>(0, (sum, account) => sum + balanceFor(account.id));
  }

  int get debtCents => accounts.fold<int>(0, (sum, account) {
    final balance = balanceFor(account.id);
    return balance < 0 ? sum + -balance : sum;
  });

  int get monthIncomeCents => _monthTotal('income');
  int get monthExpenseCents => -_monthTotal('expense');

  int _monthTotal(String type) {
    final now = DateTime.now();
    final prefix =
        '${now.year.toString().padLeft(4, '0')}-'
        '${now.month.toString().padLeft(2, '0')}';
    return transactions
        .where(
          (transaction) =>
              transaction.type == type && transaction.date.startsWith(prefix),
        )
        .fold<int>(0, (sum, transaction) => sum + transaction.amountCents);
  }

  Future<void> pair({
    required String url,
    required String code,
    required String fingerprintPrefix,
  }) async {
    final existingDeviceId = await secureStorage.read(key: 'device_id');
    final deviceId = existingDeviceId ?? const Uuid().v4();
    isSyncing = true;
    syncError = null;
    notifyListeners();
    try {
      final paired = await syncClient.pair(
        url: url,
        code: code,
        fingerprintPrefix: fingerprintPrefix,
        deviceId: deviceId,
        displayName: 'Android phone',
      );
      await _writeCredentials(paired);
      credentials = paired;
      isSyncing = false;
      notifyListeners();
      await syncNow();
    } catch (error) {
      syncError = '$error';
      rethrow;
    } finally {
      isSyncing = false;
      notifyListeners();
    }
  }

  Future<void> syncNow() async {
    final paired = credentials;
    if (paired == null || isSyncing) return;
    isSyncing = true;
    syncError = null;
    notifyListeners();
    try {
      var hasMore = true;
      var includeCommands = true;
      while (hasMore) {
        final cursor = await database.cursor();
        final commands = includeCommands
            ? await database.pendingCommands(includeFailed: false)
            : const <PendingCommand>[];
        final response = await syncClient.sync(
          credentials: paired,
          cursor: cursor,
          commands: commands,
        );
        await database.applyExchange(response);
        hasMore = response['has_more'] == true;
        includeCommands = false;
      }
      await reload();
    } catch (error) {
      syncError = '$error';
      await reload();
      rethrow;
    } finally {
      isSyncing = false;
      notifyListeners();
    }
  }

  Future<void> queueTransaction({
    required String type,
    required String accountId,
    required int amountCents,
    required String date,
    String description = '',
    String? targetAccountId,
  }) async {
    final commandType = switch (type) {
      'income' => 'create_income',
      'expense' => 'create_expense',
      'transfer' => 'create_transfer',
      _ => throw ArgumentError('Unsupported transaction type'),
    };
    final payload = <String, dynamic>{
      'amount_cents': amountCents,
      'date': date,
      'description': description.trim(),
    };
    if (type == 'transfer') {
      payload['source_account_id'] = accountId;
      payload['target_account_id'] = targetAccountId;
    } else {
      payload['account_id'] = accountId;
    }
    await database.queueCommand(
      PendingCommand(
        id: const Uuid().v4(),
        type: commandType,
        payload: payload,
        status: 'pending',
      ),
    );
    await reload();
    await _tryBackgroundSync();
  }

  Future<void> recordRecurring(String ruleId, {int? amountCents}) async {
    final payload = <String, dynamic>{
      'rule_id': ruleId,
      'date': _isoDate(DateTime.now()),
    };
    if (amountCents != null) {
      payload['amount_cents'] = amountCents;
    }
    await database.queueCommand(
      PendingCommand(
        id: const Uuid().v4(),
        type: 'record_recurring',
        payload: payload,
        status: 'pending',
      ),
    );
    await reload();
    await _tryBackgroundSync();
  }

  Future<void> dismissFailedCommand(String id) async {
    await database.dismissCommand(id);
    await reload();
  }

  Future<void> unpair() async {
    await secureStorage.deleteAll();
    await database.clearSyncedData();
    credentials = null;
    syncError = null;
    await reload();
  }

  Future<void> _tryBackgroundSync() async {
    if (!isPaired) return;
    try {
      await syncNow();
    } catch (_) {
      // The command remains queued; the visible pending state is intentional.
    }
  }

  Future<PairingCredentials?> _readCredentials() async {
    final url = await secureStorage.read(key: 'desktop_url');
    final deviceId = await secureStorage.read(key: 'device_id');
    final token = await secureStorage.read(key: 'auth_token');
    final fingerprint = await secureStorage.read(key: 'fingerprint');
    if ([url, deviceId, token, fingerprint].any((value) => value == null)) {
      return null;
    }
    return PairingCredentials(
      url: url!,
      deviceId: deviceId!,
      token: token!,
      fingerprint: fingerprint!,
    );
  }

  Future<void> _writeCredentials(PairingCredentials value) async {
    await secureStorage.write(key: 'desktop_url', value: value.url);
    await secureStorage.write(key: 'device_id', value: value.deviceId);
    await secureStorage.write(key: 'auth_token', value: value.token);
    await secureStorage.write(key: 'fingerprint', value: value.fingerprint);
  }

  static String _isoDate(DateTime value) =>
      '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}
