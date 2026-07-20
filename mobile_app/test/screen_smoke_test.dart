import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:money_manager/app_controller.dart';
import 'package:money_manager/data/local_database.dart';
import 'package:money_manager/data/sync_client.dart';
import 'package:money_manager/main.dart';
import 'package:money_manager/models/finance_models.dart';
import 'package:money_manager/theme/app_theme.dart';
import 'package:money_manager/ui/accounts_page.dart';
import 'package:money_manager/ui/app_shell.dart';
import 'package:money_manager/ui/budgets_page.dart';
import 'package:money_manager/ui/dashboard_page.dart';
import 'package:money_manager/ui/goals_page.dart';
import 'package:money_manager/ui/loan_payoff_page.dart';
import 'package:money_manager/ui/more_page.dart';
import 'package:money_manager/ui/transactions_page.dart';
import 'package:money_manager/ui/upcoming_page.dart';

void main() {
  testWidgets('shared app shell protects every tab with a top safe area', (
    tester,
  ) async {
    final controller = AppController(
      database: LocalDatabase(),
      syncClient: SyncClient(),
    );
    await tester.pumpWidget(
      AppScope(
        controller: controller,
        child: MaterialApp(theme: AppTheme.light, home: const AppShell()),
      ),
    );

    final safeArea = tester.widget<SafeArea>(find.byType(SafeArea).first);
    expect(safeArea.top, isTrue);
    expect(safeArea.bottom, isFalse);
  });

  testWidgets('core pages fit a compact Android viewport', (tester) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final now = DateTime.now();
    final currentDate = _isoDate(now);
    final currentMonthStart = _isoDate(DateTime(now.year, now.month));
    final goalTarget = _isoDate(DateTime(now.year, now.month + 8, now.day));
    final loanStart = _isoDate(DateTime(now.year, now.month - 2, now.day));
    final loanDue = _isoDate(DateTime(now.year, now.month + 24, now.day));
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
          ]
          ..categories = const [
            CategoryRecord(
              id: 'category-1',
              name: 'Groceries and household essentials',
              type: 'expense',
              isActive: true,
            ),
          ]
          ..transactions = [
            TransactionRecord(
              id: 'transaction-1',
              date: currentDate,
              type: 'expense',
              accountId: 'account-1',
              amountCents: -42000,
              description: 'Groceries',
              categoryId: 'category-1',
            ),
            TransactionRecord(
              id: 'transaction-2',
              date: currentDate,
              type: 'income',
              accountId: 'account-1',
              amountCents: 250000,
              description: 'Salary',
            ),
          ]
          ..budgets = [
            BudgetRecord(
              id: 'budget-1',
              categoryId: 'category-1',
              period: 'monthly',
              amountCents: 50000,
              rollover: true,
              startDate: currentMonthStart,
              isActive: true,
            ),
          ]
          ..savingsGoals = [
            SavingsGoalRecord(
              id: 'goal-1',
              name: 'A comfortably funded emergency reserve',
              targetAmountCents: 500000,
              targetDate: goalTarget,
              isActive: true,
              createdAt: currentMonthStart,
              revision: 1,
            ),
          ]
          ..loanRecords = [
            LoanRecord(
              id: 'loan-1',
              direction: 'borrowed',
              name: 'Home improvement loan with a long name',
              counterparty: 'Community bank',
              principalCents: 1000000,
              accountId: 'account-1',
              startDate: loanStart,
              dueDate: loanDue,
              interestRateBps: 600,
              status: 'active',
              revision: 1,
            ),
          ];

    final pages = <({Widget page, bool ownsScaffold})>[
      (
        page: DashboardPage(
          controller: controller,
          onAddTransaction: () {},
          onPair: () {},
          onOpenBudgets: () {},
          onOpenGoals: () {},
        ),
        ownsScaffold: false,
      ),
      (
        page: TransactionsPage(controller: controller, onAdd: () {}),
        ownsScaffold: false,
      ),
      (page: AccountsPage(controller: controller), ownsScaffold: false),
      (page: UpcomingPage(controller: controller), ownsScaffold: false),
      (
        page: MorePage(
          controller: controller,
          onPair: () {},
          onOpenBudgets: () {},
          onOpenGoals: () {},
          onOpenLoan: (_) {},
        ),
        ownsScaffold: false,
      ),
      (page: BudgetsPage(controller: controller), ownsScaffold: true),
      (page: GoalsPage(controller: controller), ownsScaffold: true),
      (
        page: LoanPayoffPage(controller: controller, loanId: 'loan-1'),
        ownsScaffold: true,
      ),
    ];

    for (final entry in pages) {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light,
          home: entry.ownsScaffold ? entry.page : Scaffold(body: entry.page),
        ),
      );
      await tester.pump();
      expect(
        tester.takeException(),
        isNull,
        reason: '${entry.page.runtimeType} overflowed',
      );
    }
  });

  testWidgets('manual savings goal opens a contribution sheet', (tester) async {
    final controller =
        AppController(database: LocalDatabase(), syncClient: SyncClient())
          ..accounts = const [
            AccountRecord(
              id: 'source',
              name: 'Current account',
              type: 'current_account',
              openingBalanceCents: 100000,
              isActive: true,
            ),
            AccountRecord(
              id: 'target',
              name: 'Savings account',
              type: 'savings_account',
              openingBalanceCents: 0,
              isActive: true,
            ),
          ]
          ..savingsGoals = const [
            SavingsGoalRecord(
              id: 'manual-goal',
              name: 'Emergency reserve',
              targetAmountCents: 300000,
              isActive: true,
              revision: 1,
            ),
          ];

    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        home: GoalsPage(controller: controller),
      ),
    );
    await tester.ensureVisible(find.text('Add contribution'));
    await tester.tap(find.text('Add contribution'));
    await tester.pumpAndSettle();

    expect(find.text('From account'), findsOneWidget);
    expect(find.text('To account'), findsOneWidget);
    expect(find.text('Add contribution'), findsWidgets);
  });
}

String _isoDate(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-'
    '${value.month.toString().padLeft(2, '0')}-'
    '${value.day.toString().padLeft(2, '0')}';
