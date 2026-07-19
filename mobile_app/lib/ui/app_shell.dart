import 'package:flutter/material.dart';

import '../main.dart';
import 'accounts_page.dart';
import 'dashboard_page.dart';
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

  Future<void> _addTransaction() async {
    await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: Theme.of(context).scaffoldBackgroundColor,
      builder: (_) => const TransactionSheet(),
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
      ),
      TransactionsPage(controller: controller, onAdd: _addTransaction),
      AccountsPage(controller: controller),
      UpcomingPage(controller: controller),
      MorePage(controller: controller, onPair: _pair),
    ];
    return Scaffold(
      body: SafeArea(
        top: true,
        bottom: false,
        child: IndexedStack(index: index, children: pages),
      ),
      floatingActionButton: index <= 1 && controller.accounts.isNotEmpty
          ? FloatingActionButton(
              tooltip: 'Add transaction',
              onPressed: _addTransaction,
              child: const Icon(Icons.add),
            )
          : null,
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (value) => setState(() => index = value),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.space_dashboard_outlined),
            selectedIcon: Icon(Icons.space_dashboard),
            label: 'Home',
          ),
          NavigationDestination(
            icon: Icon(Icons.swap_horiz_outlined),
            selectedIcon: Icon(Icons.swap_horiz),
            label: 'Activity',
          ),
          NavigationDestination(
            icon: Icon(Icons.account_balance_wallet_outlined),
            selectedIcon: Icon(Icons.account_balance_wallet),
            label: 'Accounts',
          ),
          NavigationDestination(
            icon: Icon(Icons.event_repeat_outlined),
            selectedIcon: Icon(Icons.event_repeat),
            label: 'Upcoming',
          ),
          NavigationDestination(
            icon: Icon(Icons.more_horiz),
            selectedIcon: Icon(Icons.more),
            label: 'More',
          ),
        ],
      ),
    );
  }
}
