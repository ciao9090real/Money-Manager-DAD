import 'package:flutter_test/flutter_test.dart';
import 'package:money_manager/data/pairing_qr.dart';

void main() {
  test('parses a Money Manager pairing QR', () {
    final data = PairingQrData.parse(
      '{"type":"money_manager_pairing","protocol_version":1,'
      '"url":"https://192.168.1.20:8765","code":"123456",'
      '"fingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}',
    );

    expect(data.url, 'https://192.168.1.20:8765');
    expect(data.code, '123456');
    expect(data.fingerprint, 'a' * 64);
  });

  test('rejects unrelated and incomplete QR codes', () {
    expect(
      () => PairingQrData.parse('https://example.com'),
      throwsFormatException,
    );
    expect(
      () => PairingQrData.parse(
        '{"type":"money_manager_pairing","protocol_version":1}',
      ),
      throwsFormatException,
    );
  });
}
