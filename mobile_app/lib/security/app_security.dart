import 'dart:convert';
import 'dart:math';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:local_auth/local_auth.dart';

abstract interface class BiometricAuthenticator {
  Future<bool> isAvailable();

  Future<bool> authenticate();
}

class DeviceBiometricAuthenticator implements BiometricAuthenticator {
  DeviceBiometricAuthenticator({LocalAuthentication? localAuthentication})
    : _localAuthentication = localAuthentication ?? LocalAuthentication();

  final LocalAuthentication _localAuthentication;

  @override
  Future<bool> isAvailable() async {
    final supported = await _localAuthentication.isDeviceSupported();
    if (!supported || !await _localAuthentication.canCheckBiometrics) {
      return false;
    }
    return (await _localAuthentication.getAvailableBiometrics()).contains(
      BiometricType.fingerprint,
    );
  }

  @override
  Future<bool> authenticate() => _localAuthentication.authenticate(
    localizedReason: 'Use your fingerprint to unlock Money Manager',
    biometricOnly: true,
    persistAcrossBackgrounding: true,
  );
}

class AppSecurity {
  AppSecurity({
    required this.authenticator,
    required this.keyStorage,
    Random? random,
  }) : _random = random ?? Random.secure();

  factory AppSecurity.device() => AppSecurity(
    authenticator: DeviceBiometricAuthenticator(),
    keyStorage: const FlutterSecureStorage(
      aOptions: AndroidOptions(
        storageNamespace: 'money_manager_database',
        resetOnError: false,
        migrateWithBackup: true,
      ),
    ),
  );

  static const databaseKeyName = 'database_key_v1';

  final BiometricAuthenticator authenticator;
  final FlutterSecureStorage keyStorage;
  final Random _random;

  Future<String> unlock() async {
    try {
      if (!await authenticator.isAvailable()) {
        throw const AppUnlockException(
          'Add a fingerprint in your phone settings before using Money Manager.',
        );
      }
      if (!await authenticator.authenticate()) {
        throw const AppUnlockException('Fingerprint was not accepted.');
      }
      var key = await keyStorage.read(key: databaseKeyName);
      if (key == null || key.isEmpty) {
        key = base64UrlEncode(
          List<int>.generate(32, (_) => _random.nextInt(256)),
        );
        await keyStorage.write(key: databaseKeyName, value: key);
      }
      return key;
    } on AppUnlockException {
      rethrow;
    } on LocalAuthException catch (error) {
      throw AppUnlockException(_friendlyLocalAuthError(error));
    } catch (_) {
      throw const AppUnlockException(
        'Money Manager could not access the phone security system. Try again.',
      );
    }
  }

  static String _friendlyLocalAuthError(
    LocalAuthException error,
  ) => switch (error.code) {
    LocalAuthExceptionCode.noBiometricHardware ||
    LocalAuthExceptionCode.noBiometricsEnrolled =>
      'Add a fingerprint in your phone settings before using Money Manager.',
    LocalAuthExceptionCode.temporaryLockout =>
      'Fingerprint unlock is temporarily paused. Wait a moment and try again.',
    LocalAuthExceptionCode.biometricLockout =>
      'Fingerprint unlock is locked. Unlock your phone once, then try again.',
    _ => 'Fingerprint unlock was cancelled or unavailable.',
  };
}

class AppUnlockException implements Exception {
  const AppUnlockException(this.message);

  final String message;

  @override
  String toString() => message;
}
