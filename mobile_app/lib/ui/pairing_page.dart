import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../data/pairing_qr.dart';
import '../main.dart';
import '../theme/app_theme.dart';

class PairingPage extends StatefulWidget {
  const PairingPage({super.key});

  @override
  State<PairingPage> createState() => _PairingPageState();
}

class _PairingPageState extends State<PairingPage> {
  final scanner = MobileScannerController(
    formats: const [BarcodeFormat.qrCode],
    detectionSpeed: DetectionSpeed.normal,
  );
  bool isProcessing = false;
  String? error;

  @override
  void dispose() {
    scanner.dispose();
    super.dispose();
  }

  Future<void> _handleScan(BarcodeCapture capture) async {
    if (isProcessing) return;
    String? rawValue;
    for (final barcode in capture.barcodes) {
      if (barcode.rawValue != null) {
        rawValue = barcode.rawValue;
        break;
      }
    }
    if (rawValue == null) return;

    late final PairingQrData pairing;
    try {
      pairing = PairingQrData.parse(rawValue);
    } on FormatException catch (exception) {
      setState(() => error = exception.message);
      return;
    }

    setState(() {
      isProcessing = true;
      error = null;
    });
    final controller = AppScope.of(context);
    await scanner.stop();
    try {
      await controller.pair(
        url: pairing.url,
        code: pairing.code,
        fingerprintPrefix: pairing.fingerprint,
      );
      if (mounted) Navigator.of(context).pop(true);
    } catch (exception) {
      if (!mounted) return;
      setState(() {
        isProcessing = false;
        error = '$exception';
      });
      await scanner.start();
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = AppScope.of(context);
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          tooltip: 'Close',
          onPressed: () => Navigator.pop(context),
          icon: const Icon(Icons.close),
        ),
        title: const Text('Scan desktop QR'),
      ),
      body: SafeArea(
        top: true,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'On the desktop, open Settings, start phone sync, and point this camera at the QR code.',
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium?.copyWith(color: AppColors.muted),
              ),
              const SizedBox(height: 18),
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      MobileScanner(controller: scanner, onDetect: _handleScan),
                      Center(
                        child: Container(
                          width: 230,
                          height: 230,
                          decoration: BoxDecoration(
                            border: Border.all(color: Colors.white, width: 3),
                            borderRadius: BorderRadius.circular(16),
                          ),
                        ),
                      ),
                      if (isProcessing)
                        ColoredBox(
                          color: Colors.black54,
                          child: Center(
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: const [
                                CircularProgressIndicator(color: Colors.white),
                                SizedBox(height: 14),
                                Text(
                                  'Connecting securely…',
                                  style: TextStyle(color: Colors.white),
                                ),
                              ],
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
              if (error != null) ...[
                const SizedBox(height: 14),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFBEAEA),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    error!,
                    style: const TextStyle(color: AppColors.negative),
                  ),
                ),
              ],
              const SizedBox(height: 14),
              Text(
                controller.isSyncing
                    ? 'Pairing and loading your data…'
                    : 'The QR includes a one-time code and security fingerprint. Pairing stays on your local Wi-Fi.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
