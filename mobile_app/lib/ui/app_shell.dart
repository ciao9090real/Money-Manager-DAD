import 'package:flutter/material.dart';

import '../main.dart';
import '../theme/app_theme.dart';
import 'accounts_page.dart';
import 'budgets_page.dart';
import 'dashboard_page.dart';
import 'goals_page.dart';
import 'import_inbox_page.dart';
import 'insights_page.dart';
import 'loan_payoff_page.dart';
import 'more_page.dart';
import 'pairing_page.dart';
import 'transaction_sheet.dart';
import 'transactions_page.dart';
import 'upcoming_page.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int index = 0;

  Future<void> _pair() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => const PairingPage(),
        fullscreenDialog: true,
      ),
    );
  }

  Future<void> _addTransaction({
    String initialType = 'expense',
    String? accountId,
  }) async {
    await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      backgroundColor: Theme.of(context).colorScheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => TransactionSheet(
        initialType: initialType,
        initialAccountId: accountId,
      ),
    );
  }

  Future<void> _openBudgets() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => BudgetsPage(controller: AppScope.of(context)),
      ),
    );
  }

  Future<void> _openGoals() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => GoalsPage(controller: AppScope.of(context)),
      ),
    );
  }

  Future<void> _openImports() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ImportInboxPage(controller: AppScope.of(context)),
      ),
    );
  }

  Future<void> _openInsights() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => InsightsPage(controller: AppScope.of(context)),
      ),
    );
  }

  Future<void> _openLoan(String loanId) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) =>
            LoanPayoffPage(controller: AppScope.of(context), loanId: loanId),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final controller = AppScope.of(context);
    final pages = [
      DashboardPage(
        controller: controller,
        onAddTransaction: _addTransaction,
        onPair: _pair,
        onOpenBudgets: _openBudgets,
        onOpenGoals: _openGoals,
        onAddExpense: () => _addTransaction(initialType: 'expense'),
        onAddIncome: () => _addTransaction(initialType: 'income'),
        onAddTransfer: () => _addTransaction(initialType: 'transfer'),
      ),
      TransactionsPage(
        controller: controller,
        onAdd: _addTransaction,
        onOpenImports: _openImports,
      ),
      AccountsPage(
        controller: controller,
        onAddTransaction: (accountId, transactionType) =>
            _addTransaction(initialType: transactionType, accountId: accountId),
      ),
      UpcomingPage(controller: controller),
      MorePage(
        controller: controller,
        onPair: _pair,
        onOpenBudgets: _openBudgets,
        onOpenGoals: _openGoals,
        onOpenInsights: _openInsights,
        onOpenLoan: _openLoan,
      ),
    ];
    return Scaffold(
      body: SafeArea(
        top: true,
        bottom: false,
        child: IndexedStack(index: index, children: pages),
      ),
      floatingActionButton: index == 1 && controller.accounts.isNotEmpty
          ? FloatingActionButton(
              tooltip: 'Add transaction',
              onPressed: _addTransaction,
              child: const Icon(Icons.add),
            )
          : null,
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (value) => setState(() => index = value),
        destinations: [
          const NavigationDestination(
            icon: Icon(Icons.space_dashboard_outlined),
            selectedIcon: Icon(Icons.space_dashboard),
            label: 'Home',
          ),
          const NavigationDestination(
            icon: Icon(Icons.swap_horiz_outlined),
            selectedIcon: Icon(Icons.swap_horiz),
            label: 'Activity',
          ),
          const NavigationDestination(
            icon: Icon(Icons.account_balance_wallet_outlined),
            selectedIcon: Icon(Icons.account_balance_wallet),
            label: 'Accounts',
          ),
          NavigationDestination(
            icon: _ReminderBadge(
              count: controller.reminderAttentionCount,
              child: const Icon(Icons.event_repeat_outlined),
            ),
            selectedIcon: _ReminderBadge(
              count: controller.reminderAttentionCount,
              child: const Icon(Icons.event_repeat),
            ),
            label: 'Upcoming',
          ),
          const NavigationDestination(
            icon: Icon(Icons.more_horiz),
            selectedIcon: Icon(Icons.more),
            label: 'More',
          ),
        ],
      ),
    );
  }
}

class _ReminderBadge extends StatelessWidget {
  const _ReminderBadge({required this.count, required this.child});

  final int count;
  final Widget child;

  @override
  Widget build(BuildContext context) => Badge(
    isLabelVisible: count > 0,
    label: Text(count > 9 ? '9+' : '$count'),
    backgroundColor: AppColors.warning,
    textColor: Colors.white,
    child: child,
  );
}
