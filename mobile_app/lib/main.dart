import 'package:flutter/material.dart';

import 'app_controller.dart';
import 'data/local_database.dart';
import 'data/sync_client.dart';
import 'security/app_security.dart';
import 'theme/app_theme.dart';
import 'ui/app_shell.dart';
import 'ui/secure_app_gate.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final controller = AppController(
    database: LocalDatabase(),
    syncClient: SyncClient(),
  );
  runApp(MoneyManagerApp(controller: controller));
}

class MoneyManagerApp extends StatelessWidget {
  const MoneyManagerApp({super.key, required this.controller, this.security});

  final AppController controller;
  final AppSecurity? security;

  @override
  Widget build(BuildContext context) {
    return AppScope(
      controller: controller,
      child: MaterialApp(
        debugShowCheckedModeBanner: false,
        title: 'Money Manager',
        theme: AppTheme.light,
        home: SecureAppGate(
          controller: controller,
          security: security ?? AppSecurity.device(),
          child: const AppShell(),
        ),
      ),
    );
  }
}

class AppScope extends InheritedNotifier<AppController> {
  const AppScope({
    super.key,
    required AppController controller,
    required super.child,
  }) : super(notifier: controller);

  static AppController of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AppScope>();
    assert(scope != null, 'AppScope is missing above this widget');
    return scope!.notifier!;
  }
}
