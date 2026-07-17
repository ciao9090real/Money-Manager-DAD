import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../models/finance_models.dart';
import '../theme/app_theme.dart';
import 'widgets.dart';

class AccountsPage extends StatelessWidget {
  const AccountsPage({super.key, required this.controller});

  final AppController controller;

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
    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 108),
      children: [
        const ScreenHeader(
          title: 'Accounts',
          subtitle: 'Banks, wallets, savings, investments, and liabilities',
        ),
        const SizedBox(height: 20),
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
                      ),
                      if (index != ordered.length - 1)
                        const Divider(height: 1, indent: 58),
                    ],
                  ],
                ),
        ),
        const SizedBox(height: 12),
        Text(
          'Inactive accounts stay hidden. Manage account structure on the desktop.',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    );
  }
}

class _AccountRow extends StatelessWidget {
  const _AccountRow({
    required this.account,
    required this.depth,
    required this.balance,
  });

  final AccountRecord account;
  final int depth;
  final int balance;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(14.0 + depth * 18, 13, 14, 13),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: depth == 0
                  ? AppColors.primarySoft
                  : const Color(0xFFF0F3F2),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(
              _iconFor(account.type),
              size: 19,
              color: depth == 0 ? AppColors.primary : AppColors.muted,
            ),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  account.name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontWeight: depth == 0 ? FontWeight.w700 : FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Align(
                  alignment: Alignment.centerLeft,
                  child: Pill(prettyType(account.type)),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          AmountText(balance, neutral: balance >= 0, emphasized: true),
        ],
      ),
    );
  }

  IconData _iconFor(String type) => switch (type) {
    'cash' => Icons.payments_outlined,
    'wallet' => Icons.account_balance_wallet_outlined,
    'savings_account' => Icons.savings_outlined,
    'investment' => Icons.show_chart,
    'loan' || 'mortgage' || 'liability' => Icons.account_balance_outlined,
    _ => Icons.credit_card_outlined,
  };
}
