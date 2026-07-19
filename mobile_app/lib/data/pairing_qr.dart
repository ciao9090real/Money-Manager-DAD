import 'dart:convert';

class PairingQrData {
  const PairingQrData({
    required this.url,
    required this.code,
    required this.fingerprint,
  });

  final String url;
  final String code;
  final String fingerprint;

  factory PairingQrData.parse(String value) {
    final Object? decoded;
    try {
      decoded = jsonDecode(value);
    } on FormatException {
      throw const FormatException('This is not a Money Manager pairing QR');
    }
    if (decoded is! Map<String, dynamic> ||
        decoded['type'] != 'money_manager_pairing' ||
        decoded['protocol_version'] != 1) {
      throw const FormatException('This is not a Money Manager pairing QR');
    }

    final url = '${decoded['url'] ?? ''}'.trim();
    final code = '${decoded['code'] ?? ''}'.trim();
    final fingerprint = '${decoded['fingerprint'] ?? ''}'
        .toLowerCase()
        .replaceAll(RegExp('[^0-9a-f]'), '');
    if (!url.startsWith('https://') ||
        !RegExp(r'^\d{6}$').hasMatch(code) ||
        fingerprint.length != 64) {
      throw const FormatException('This pairing QR is incomplete or invalid');
    }

    return PairingQrData(url: url, code: code, fingerprint: fingerprint);
  }
}
