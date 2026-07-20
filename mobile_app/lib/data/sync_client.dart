import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';

import '../models/finance_models.dart';

class SyncClient {
  Future<PairingCredentials> pair({
    required String url,
    required String code,
    required String fingerprintPrefix,
    required String deviceId,
    required String displayName,
  }) async {
    final normalizedUrl = _normalizeUrl(url);
    final prefix = _normalizeFingerprint(fingerprintPrefix);
    if (prefix.length < 8) {
      throw const SyncException(
        'Enter at least the first 8 fingerprint characters',
      );
    }
    String? observedFingerprint;
    final client = _client((certificate) {
      observedFingerprint = sha256.convert(certificate.der).toString();
      return observedFingerprint!.startsWith(prefix);
    });
    try {
      final response = await _post(
        client,
        '$normalizedUrl/v1/pair',
        body: {
          'code': code.trim(),
          'device_id': deviceId,
          'display_name': displayName,
        },
      );
      final serverFingerprint = _normalizeFingerprint(
        '${response['certificate_fingerprint'] ?? ''}',
      );
      if (observedFingerprint == null ||
          serverFingerprint != observedFingerprint) {
        throw const SyncException(
          'Desktop security fingerprint changed during pairing',
        );
      }
      return PairingCredentials(
        url: normalizedUrl,
        deviceId: '${response['device_id']}',
        token: '${response['auth_token']}',
        fingerprint: serverFingerprint,
      );
    } finally {
      client.close(force: true);
    }
  }

  Future<Map<String, dynamic>> sync({
    required PairingCredentials credentials,
    required int cursor,
    required int entitySetVersion,
    required List<PendingCommand> commands,
  }) async {
    final expected = _normalizeFingerprint(credentials.fingerprint);
    final client = _client(
      (certificate) => sha256.convert(certificate.der).toString() == expected,
    );
    try {
      return await _post(
        client,
        '${credentials.url}/v1/sync',
        bearerToken: credentials.token,
        body: {
          'device_id': credentials.deviceId,
          'cursor': cursor,
          'entity_set_version': entitySetVersion,
          'commands': commands.map((command) => command.toWire()).toList(),
        },
      );
    } finally {
      client.close(force: true);
    }
  }

  HttpClient _client(bool Function(X509Certificate) allowCertificate) {
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 8);
    client.badCertificateCallback = (certificate, host, port) =>
        allowCertificate(certificate);
    return client;
  }

  Future<Map<String, dynamic>> _post(
    HttpClient client,
    String url, {
    required Map<String, dynamic> body,
    String? bearerToken,
  }) async {
    try {
      final encodedBody = utf8.encode(jsonEncode(body));
      final request = await client.postUrl(Uri.parse(url));
      request.headers.contentType = ContentType.json;
      if (bearerToken != null) {
        request.headers.set(
          HttpHeaders.authorizationHeader,
          'Bearer $bearerToken',
        );
      }
      request.contentLength = encodedBody.length;
      request.add(encodedBody);
      final response = await request.close().timeout(
        const Duration(seconds: 15),
      );
      final decodedText = await response.transform(utf8.decoder).join();
      final decoded = decodedText.isEmpty
          ? <String, dynamic>{}
          : jsonDecode(decodedText) as Map<String, dynamic>;
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw SyncException(
          '${decoded['error'] ?? 'Desktop returned an error'}',
        );
      }
      return decoded;
    } on SyncException {
      rethrow;
    } on HandshakeException {
      throw const SyncException(
        'Security check failed. Compare the fingerprint again.',
      );
    } on SocketException {
      throw const SyncException(
        'Desktop not found. Keep both devices on the same Wi-Fi and start phone sync.',
      );
    } on FormatException {
      throw const SyncException('The desktop address or response is invalid');
    } on TimeoutException {
      throw const SyncException('The desktop did not respond in time');
    } on HttpException {
      throw const SyncException('The local sync connection was interrupted');
    }
  }

  static String _normalizeUrl(String value) {
    var normalized = value.trim();
    if (!normalized.startsWith('https://')) normalized = 'https://$normalized';
    while (normalized.endsWith('/')) {
      normalized = normalized.substring(0, normalized.length - 1);
    }
    final uri = Uri.tryParse(normalized);
    if (uri == null || uri.host.isEmpty || uri.scheme != 'https') {
      throw const SyncException(
        'Enter the HTTPS desktop address shown in Settings',
      );
    }
    return normalized;
  }

  static String _normalizeFingerprint(String value) =>
      value.toLowerCase().replaceAll(RegExp('[^0-9a-f]'), '');
}

class SyncException implements Exception {
  const SyncException(this.message);

  final String message;

  @override
  String toString() => message;
}
