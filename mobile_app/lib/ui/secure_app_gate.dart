import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../security/app_security.dart';
import '../theme/app_theme.dart';

class SecureAppGate extends StatefulWidget {
  const SecureAppGate({
    super.key,
    required this.controller,
    required this.security,
    required this.child,
  });

  final AppController controller;
  final AppSecurity security;
  final Widget child;

  @override
  State<SecureAppGate> createState() => _SecureAppGateState();
}

class _SecureAppGateState extends State<SecureAppGate>
    with WidgetsBindingObserver {
  bool _unlocked = false;
  bool _working = false;
  bool _foreground = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) => _unlock());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _foreground = state == AppLifecycleState.resumed;
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden ||
        state == AppLifecycleState.detached) {
      _lock();
    } else if (state == AppLifecycleState.resumed && !_unlocked && !_working) {
      _unlock();
    }
  }

  Future<void> _lock() async {
    if (!_unlocked) return;
    if (mounted) {
      setState(() {
        _unlocked = false;
        _error = null;
      });
    }
    try {
      await widget.controller.lock();
    } catch (_) {
      if (mounted) {
        setState(
          () => _error = 'The app is locked. Restart it before trying again.',
        );
      }
    }
  }

  Future<void> _unlock() async {
    if (_working || _unlocked) return;
    setState(() {
      _working = true;
      _error = null;
    });
    try {
      final databasePassword = await widget.security.unlock();
      await widget.controller.initialize(databasePassword: databasePassword);
      if (!_foreground) {
        await widget.controller.lock();
        return;
      }
      if (mounted) setState(() => _unlocked = true);
    } on AppUnlockException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'Your encrypted data could not be opened. Do not clear app data; reconnecting to the desktop may be required.',
        );
      }
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_unlocked) return widget.child;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(28),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    width: 80,
                    height: 80,
                    decoration: BoxDecoration(
                      color: AppColors.primarySoft,
                      borderRadius: BorderRadius.circular(24),
                    ),
                    child: const Icon(
                      Icons.fingerprint,
                      size: 46,
                      color: AppColors.primary,
                    ),
                  ),
                  const SizedBox(height: 24),
                  Text(
                    'Money Manager is locked',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 9),
                  Text(
                    _error ??
                        'Your financial data is encrypted. Use your fingerprint to open it.',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: _error == null
                          ? AppColors.muted
                          : AppColors.negative,
                    ),
                  ),
                  const SizedBox(height: 24),
                  FilledButton.icon(
                    onPressed: _working ? null : _unlock,
                    icon: _working
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.fingerprint),
                    label: Text(
                      _working ? 'Unlocking' : 'Unlock with fingerprint',
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
