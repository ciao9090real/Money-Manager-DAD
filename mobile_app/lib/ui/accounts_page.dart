import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../models/finance_models.dart';
import '../theme/app_theme.dart';
import 'widgets.dart';

typedef AccountTransactionAction =
    void Function(String accountId, String transactionType);

class AccountsPage extends StatelessWidget {
  const AccountsPage({
    super.key,
    required this.controller,
    this.onAddTransaction,
  });

  final AppController controller;
  final AccountTransactionAction? onAddTransaction;

  @override
  Widget build(BuildContext context) {
    final roots = controller.accounts
        .where((account) => account.parentId == null)
        .toList();
    final ordered = <({AccountRecord account, int depth})>[];
    for (final root in roots) {
      ordered.add((account: root, depth: 0));
      for (final child in controller.accounts.where(
        (item) => item.parentId == root.id,
      )) {
        ordered.add((account: child, depth: 1));
        for (final grandchild in controller.accounts.where(
          (item) => item.parentId == child.id,
        )) {
          ordered.add((account: grandchild, depth: 2));
        }
      }
    }
    for (final account in controller.accounts) {
      if (!ordered.any((entry) => entry.account.id == account.id)) {
        ordered.add((account: account, depth: 0));
      }
    }
    final total = controller.accounts.fold<int>(
      0,
      (sum, account) => sum + controller.balanceFor(account.id),
    );
    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 112),
      children: [
        const ScreenHeader(
          title: 'Accounts',
          subtitle: 'Balances, cards, and account activity',
        ),
        const SizedBox(height: 18),
        Container(
          padding: const EdgeInsets.fromLTRB(2, 8, 2, 14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'TOTAL ACROSS ACCOUNTS',
                style: TextStyle(
                  color: AppColors.primary,
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 8),
              FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: Text(
                  money(total),
                  style: Theme.of(context).textTheme.displaySmall,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                '${controller.accounts.length} active account${controller.accounts.length == 1 ? '' : 's'}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        SectionHeader(
          title: 'Your accounts',
          subtitle: ordered.isEmpty
              ? null
              : 'Tap an account to see its activity',
        ),
        const SizedBox(height: 9),
        SurfaceCard(
          padding: EdgeInsets.zero,
          child: ordered.isEmpty
              ? const EmptyState(
                  icon: Icons.account_balance_wallet_outlined,
                  title: 'No accounts yet',
                  message:
                      'Add your first account on the desktop, then sync it here.',
                )
              : Column(
                  children: [
                    for (var index = 0; index < ordered.length; index++) ...[
                      _AccountRow(
                        account: ordered[index].account,
                        depth: ordered[index].depth,
                        balance: controller.balanceFor(
                          ordered[index].account.id,
                        ),
                        onTap: () => Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => AccountDetailPage(
                              controller: controller,
                              account: ordered[index].account,
                              onAddTransaction: onAddTransaction,
                            ),
                          ),
                        ),
                      ),
                      if (index != ordered.length - 1)
                        const Divider(height: 1, indent: 62),
                    ],
                  ],
                ),
        ),
        const SizedBox(height: 12),
        Text(
          'Account setup and structure stay on the desktop.',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    );
  }
}

class AccountDetailPage extends StatelessWidget {
  const AccountDetailPage({
    super.key,
    required this.controller,
    required this.account,
    this.onAddTransaction,
  });

  final AppController controller;
  final AccountRecord account;
  final AccountTransactionAction? onAddTransaction;

  @override
  Widget build(BuildContext context) {
    final transactions = controller.transactions
        .where((transaction) => transaction.accountId == account.id)
        .toList();
    final now = DateTime.now();
    final monthPrefix =
        '${now.year.toString().padLeft(4, '0')}-${now.month.toString().padLeft(2, '0')}';
    final monthIncome = transactions
        .where(
          (transaction) =>
              transaction.isIncome && transaction.date.startsWith(monthPrefix),
        )
        .fold<int>(0, (sum, transaction) => sum + transaction.amountCents);
    final monthSpent = transactions
        .where(
          (transaction) =>
              transaction.isExpense && transaction.date.startsWith(monthPrefix),
        )
        .fold<int>(
          0,
          (sum, transaction) => sum + transaction.amountCents.abs(),
        );
    final methods = controller.paymentMethods
        .where((method) => method.accountId == account.id)
        .toList();

    return Scaffold(
      appBar: AppBar(title: Text(account.name)),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(18, 8, 18, 32),
        children: [
          Container(
            padding: const EdgeInsets.fromLTRB(2, 8, 2, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(_iconFor(account.type), color: AppColors.primary),
                    const SizedBox(width: 8),
                    Text(
                      prettyType(account.type),
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Text(
                  'Available balance',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 4),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Text(
                    money(controller.balanceFor(account.id)),
                    style: Theme.of(context).textTheme.displaySmall,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          SurfaceCard(
            padding: EdgeInsets.zero,
            child: Row(
              children: [
                Expanded(
                  child: _AccountMonthMetric(
                    label: 'In this month',
                    value: money(monthIncome),
                    tone: AppColors.positive,
                  ),
                ),
                const SizedBox(height: 72, child: VerticalDivider(width: 1)),
                Expanded(
                  child: _AccountMonthMetric(
                    label: 'Out this month',
                    value: money(monthSpent),
                    tone: AppColors.negative,
                  ),
                ),
              ],
            ),
          ),
          if (onAddTransaction != null) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: () => onAddTransaction!(account.id, 'expense'),
                    icon: const Icon(Icons.south_west),
                    label: const Text('Add expense'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => onAddTransaction!(account.id, 'income'),
                    icon: const Icon(Icons.north_east),
                    label: const Text('Add income'),
                  ),
                ),
              ],
            ),
          ],
          if (methods.isNotEmpty) ...[
            const SizedBox(height: 22),
            const SectionHeader(title: 'Payment methods'),
            const SizedBox(height: 9),
            SurfaceCard(
              padding: EdgeInsets.zero,
              child: Column(
                children: [
                  for (var index = 0; index < methods.length; index++) ...[
                    ListTile(
                      leading: const Icon(Icons.credit_card_outlined),
                      title: Text(methods[index].name),
                      subtitle: Text(prettyType(methods[index].type)),
                    ),
                    if (index != methods.length - 1)
                      const Divider(height: 1, indent: 56),
                  ],
                ],
              ),
            ),
          ],
          const SizedBox(height: 22),
          SectionHeader(
            title: 'Recent activity',
            trailing: Text(
              '${transactions.length} total',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
          const SizedBox(height: 9),
          SurfaceCard(
            padding: EdgeInsets.zero,
            child: transactions.isEmpty
                ? const EmptyState(
                    icon: Icons.receipt_long_outlined,
                    title: 'No activity yet',
                    message: 'Transactions for this account appear here.',
                  )
                : Column(
                    children: [
                      for (
                        var index = 0;
                        index < transactions.take(30).length;
                        index++
                      ) ...[
                        _AccountTransactionRow(
                          transaction: transactions[index],
                          controller: controller,
                        ),
                        if (index != transactions.take(30).length - 1)
                          const Divider(height: 1, indent: 60),
                      ],
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

class _AccountMonthMetric extends StatelessWidget {
  const _AccountMonthMetric({
    required this.label,
    required this.value,
    required this.tone,
  });

  final String label;
  final String value;
  final Color tone;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(14, 14, 12, 15),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: Theme.of(context).textTheme.bodySmall),
        const SizedBox(height: 7),
        FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: Text(
            value,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
              color: tone,
              fontFamily: 'SpaceGrotesk',
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    ),
  );
}

class _AccountRow extends StatelessWidget {
  const _AccountRow({
    required this.account,
    required this.depth,
    required this.balance,
    required this.onTap,
  });

  final AccountRecord account;
  final int depth;
  final int balance;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      onTap: onTap,
      contentPadding: EdgeInsets.fromLTRB(14.0 + depth * 18, 7, 12, 7),
      leading: Container(
        width: 40,
        height: 40,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: depth == 0 ? AppColors.primarySoft : const Color(0xFFF0F3F2),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Icon(
          _iconFor(account.type),
          size: 20,
          color: depth == 0 ? AppColors.primary : AppColors.muted,
        ),
      ),
      title: Text(
        account.name,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: TextStyle(
          fontWeight: depth == 0 ? FontWeight.w700 : FontWeight.w600,
        ),
      ),
      subtitle: Text(prettyType(account.type)),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          AmountText(balance, neutral: balance >= 0, emphasized: true),
          const SizedBox(width: 2),
          const Icon(Icons.chevron_right, color: AppColors.muted),
        ],
      ),
    );
  }
}

class _AccountTransactionRow extends StatelessWidget {
  const _AccountTransactionRow({
    required this.transaction,
    required this.controller,
  });

  final TransactionRecord transaction;
  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final category = controller.categoryFor(transaction.categoryId ?? '');
    final transfer = transaction.isTransfer;
    final tone = transaction.isIncome
        ? AppColors.positive
        : transaction.isExpense
        ? AppColors.negative
        : AppColors.blue;
    return ListTile(
      leading: Container(
        width: 38,
        height: 38,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: tone.withValues(alpha: .10),
          borderRadius: BorderRadius.circular(11),
        ),
        child: Icon(
          transfer
              ? Icons.swap_horiz
              : transaction.isIncome
              ? Icons.north_east
              : Icons.south_west,
          color: tone,
          size: 19,
        ),
      ),
      title: Text(
        transaction.description.isEmpty
            ? prettyType(transaction.type)
            : transaction.description,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      subtitle: Text(
        '${category?.name ?? prettyType(transaction.type)} · ${friendlyDate(transaction.date)}',
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      trailing: AmountText(transaction.amountCents, neutral: transfer),
    );
  }
}

IconData _iconFor(String type) => switch (type) {
  'cash' => Icons.payments_outlined,
  'wallet' => Icons.account_balance_wallet_outlined,
  'savings_account' => Icons.savings_outlined,
  'investment' => Icons.show_chart,
  'loan' || 'mortgage' || 'liability' => Icons.account_balance_outlined,
  _ => Icons.credit_card_outlined,
};
