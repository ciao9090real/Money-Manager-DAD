import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:money_manager/app_controller.dart';
import 'package:money_manager/data/local_database.dart';
import 'package:money_manager/data/sync_client.dart';
import 'package:money_manager/models/finance_models.dart';
import 'package:money_manager/security/app_security.dart';
import 'package:money_manager/theme/app_theme.dart';
import 'package:money_manager/ui/secure_app_gate.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  test(
    'database key is created only after biometric acceptance and is reused',
    () async {
      final authenticator = _FakeAuthenticator();
      final security = AppSecurity(
        authenticator: authenticator,
        keyStorage: const FlutterSecureStorage(),
      );

      final first = await security.unlock();
      final second = await security.unlock();

      expect(first, isNotEmpty);
      expect(second, first);
      expect(authenticator.authenticationCount, 2);
    },
  );

  test('missing fingerprint enrollment prevents key access', () async {
    final security = AppSecurity(
      authenticator: _FakeAuthenticator(available: false),
      keyStorage: const FlutterSecureStorage(),
    );

    await expectLater(
      security.unlock(),
      throwsA(
        isA<AppUnlockException>().having(
          (error) => error.message,
          'message',
          contains('Add a fingerprint'),
        ),
      ),
    );
  });

  test('rejected fingerprint never releases the database key', () async {
    final security = AppSecurity(
      authenticator: _FakeAuthenticator(accepted: false),
      keyStorage: const FlutterSecureStorage(),
    );

    await expectLater(
      security.unlock(),
      throwsA(
        isA<AppUnlockException>().having(
          (error) => error.message,
          'message',
          contains('not accepted'),
        ),
      ),
    );
  });

  testWidgets(
    'secure gate unlocks and clears data when the app is backgrounded',
    (tester) async {
      final database = _GateDatabase();
      final controller = AppController(
        database: database,
        syncClient: SyncClient(),
      );
      final security = AppSecurity(
        authenticator: _FakeAuthenticator(),
        keyStorage: const FlutterSecureStorage(),
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light,
          home: SecureAppGate(
            controller: controller,
            security: security,
            child: const Text('Private dashboard'),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Private dashboard'), findsOneWidget);
      expect(controller.accounts, hasLength(1));

      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      await tester.pumpAndSettle();

      expect(find.text('Money Manager is locked'), findsOneWidget);
      expect(controller.accounts, isEmpty);
      expect(database.closeCount, 1);
    },
  );
}

class _FakeAuthenticator implements BiometricAuthenticator {
  _FakeAuthenticator({this.available = true, this.accepted = true});

  final bool available;
  final bool accepted;
  int authenticationCount = 0;

  @override
  Future<bool> isAvailable() async => available;

  @override
  Future<bool> authenticate() async {
    authenticationCount += 1;
    return accepted;
  }
}

class _GateDatabase extends LocalDatabase {
  int closeCount = 0;

  @override
  Future<void> initialize({String? password}) async {}

  @override
  Future<void> close() async {
    closeCount += 1;
  }

  @override
  Future<List<StoredRecord>> records(String entity) async =>
      entity == 'accounts'
      ? [
          const StoredRecord(
            entity: 'accounts',
            id: 'current',
            revision: 1,
            payload: {
              'id': 'current',
              'name': 'Current',
              'type': 'current_account',
              'opening_balance_cents': 10000,
              'is_active': 1,
            },
          ),
        ]
      : const [];

  @override
  Future<List<PendingCommand>> pendingCommands({
    bool includeFailed = true,
  }) async => const [];

  @override
  Future<String?> state(String key) async => null;
}
