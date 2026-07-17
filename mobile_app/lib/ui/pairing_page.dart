import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../main.dart';
import '../theme/app_theme.dart';
import 'widgets.dart';

class PairingPage extends StatefulWidget {
  const PairingPage({super.key});

  @override
  State<PairingPage> createState() => _PairingPageState();
}

class _PairingPageState extends State<PairingPage> {
  final address = TextEditingController();
  final code = TextEditingController();
  final fingerprint = TextEditingController();
  final formKey = GlobalKey<FormState>();
  String? error;

  @override
  void dispose() {
    address.dispose();
    code.dispose();
    fingerprint.dispose();
    super.dispose();
  }

  Future<void> pair() async {
    if (!formKey.currentState!.validate()) return;
    setState(() => error = null);
    try {
      await AppScope.of(context).pair(
        url: address.text,
        code: code.text,
        fingerprintPrefix: fingerprint.text,
      );
      if (mounted) Navigator.pop(context, true);
    } catch (exception) {
      if (mounted) setState(() => error = '$exception');
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
        title: const Text('Connect desktop'),
      ),
      body: SafeArea(
        child: Form(
          key: formKey,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
            children: [
              const BrandMark(size: 46),
              const SizedBox(height: 18),
              Text(
                'Keep your money local',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 7),
              Text(
                'On the desktop, open Settings and start Android phone sync. Enter the three values shown there.',
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium?.copyWith(color: AppColors.muted),
              ),
              const SizedBox(height: 24),
              TextFormField(
                controller: address,
                keyboardType: TextInputType.url,
                textInputAction: TextInputAction.next,
                autocorrect: false,
                decoration: const InputDecoration(
                  labelText: 'Desktop address',
                  hintText: 'https://192.168.1.20:8765',
                  prefixIcon: Icon(Icons.laptop_windows_outlined),
                ),
                validator: (value) => (value ?? '').trim().isEmpty
                    ? 'Desktop address is required'
                    : null,
              ),
              const SizedBox(height: 13),
              TextFormField(
                controller: code,
                keyboardType: TextInputType.number,
                textInputAction: TextInputAction.next,
                inputFormatters: [
                  FilteringTextInputFormatter.digitsOnly,
                  LengthLimitingTextInputFormatter(6),
                ],
                decoration: const InputDecoration(
                  labelText: 'One-time pairing code',
                  hintText: '000000',
                  prefixIcon: Icon(Icons.password_outlined),
                ),
                validator: (value) =>
                    (value ?? '').length != 6 ? 'Enter the 6-digit code' : null,
              ),
              const SizedBox(height: 13),
              TextFormField(
                controller: fingerprint,
                textCapitalization: TextCapitalization.characters,
                autocorrect: false,
                inputFormatters: [
                  FilteringTextInputFormatter.allow(RegExp('[0-9a-fA-F ]')),
                  LengthLimitingTextInputFormatter(17),
                ],
                decoration: const InputDecoration(
                  labelText: 'Fingerprint check',
                  hintText: 'First 8 or more characters',
                  prefixIcon: Icon(Icons.verified_user_outlined),
                ),
                validator: (value) {
                  final clean = (value ?? '').replaceAll(' ', '');
                  return clean.length < 8
                      ? 'Enter at least the first 8 characters'
                      : null;
                },
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
              const SizedBox(height: 22),
              FilledButton(
                onPressed: controller.isSyncing ? null : pair,
                child: LoadingButtonContent(
                  loading: controller.isSyncing,
                  label: 'Pair and sync',
                ),
              ),
              const SizedBox(height: 12),
              Text(
                'The connection stays on your local Wi-Fi. Financial data is cached in this phone\'s SQLite database for offline viewing.',
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
