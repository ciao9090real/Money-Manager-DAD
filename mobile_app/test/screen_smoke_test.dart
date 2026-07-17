import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:money_manager/app_controller.dart';
import 'package:money_manager/data/local_database.dart';
import 'package:money_manager/data/sync_client.dart';
import 'package:money_manager/models/finance_models.dart';
import 'package:money_manager/theme/app_theme.dart';
import 'package:money_manager/ui/accounts_page.dart';
import 'package:money_manager/ui/dashboard_page.dart';
import 'package:money_manager/ui/more_page.dart';
import 'package:money_manager/ui/transactions_page.dart';
import 'package:money_manager/ui/upcoming_page.dart';

void main() {
  testWidgets('core pages fit a compact Android viewport', (tester) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final controller =
        AppController(database: LocalDatabase(), syncClient: SyncClient())
          ..accounts = const [
            AccountRecord(
              id: 'account-1',
              name: 'Everyday current account',
              type: 'current_account',
              openingBalanceCents: 100000,
              isActive: true,
            ),
            AccountRecord(
              id: 'account-2',
              name: 'Savings',
              type: 'savings_account',
              openingBalanceCents: 50000,
              isActive: true,
              parentId: 'account-1',
            ),
          ]
          ..transactions = const [
            TransactionRecord(
              id: 'transaction-1',
              date: '2026-07-17',
              type: 'expense',
              accountId: 'account-1',
              amountCents: -2999,
              description: 'Groceries',
            ),
          ]
          ..recurring = const [
            RecurringRecord(
              id: 'rule-1',
              name: 'Salary',
              kind: 'other',
              transactionType: 'income',
              accountId: 'account-1',
              frequency: 'monthly',
              nextDueDate: '2026-07-31',
              status: 'active',
              amountCents: 250000,
            ),
          ];

    final pages = <Widget>[
      DashboardPage(
        controller: controller,
        onAddTransaction: () {},
        onPair: () {},
      ),
      TransactionsPage(controller: controller, onAdd: () {}),
      AccountsPage(controller: controller),
      UpcomingPage(controller: controller),
      MorePage(controller: controller, onPair: () {}),
    ];

    for (final page in pages) {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light,
          home: Scaffold(body: page),
        ),
      );
      await tester.pump();
      expect(
        tester.takeException(),
        isNull,
        reason: '${page.runtimeType} overflowed',
      );
    }
  });
}
