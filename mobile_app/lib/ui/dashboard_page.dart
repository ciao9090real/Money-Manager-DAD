import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../models/finance_models.dart';
import '../theme/app_theme.dart';
import 'widgets.dart';

class DashboardPage extends StatelessWidget {
  const DashboardPage({
    super.key,
    required this.controller,
    required this.onAddTransaction,
    required this.onPair,
  });

  final AppController controller;
  final VoidCallback onAddTransaction;
  final VoidCallback onPair;

  Future<void> _refresh(BuildContext context) async {
    if (!controller.isPaired) {
      onPair();
      return;
    }
    try {
      await controller.syncNow();
    } catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final recent = controller.transactions
        .where((transaction) => transaction.type != 'adjustment')
        .take(6)
        .toList();
    return RefreshIndicator(
      onRefresh: () => _refresh(context),
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(18, 12, 18, 108),
        children: [
          Row(
            children: [
              const BrandMark(),
              const SizedBox(width: 11),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Money Manager',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    Text(
                      controller.isPaired
                          ? 'Private finance, available offline'
                          : 'Local finance on your phone',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
              IconButton(
                tooltip: controller.isPaired ? 'Sync now' : 'Connect desktop',
                onPressed: controller.isSyncing
                    ? null
                    : () => _refresh(context),
                icon: controller.isSyncing
                    ? const SizedBox(
                        width: 21,
                        height: 21,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Icon(controller.isPaired ? Icons.sync : Icons.add_link),
              ),
            ],
          ),
          const SizedBox(height: 22),
          if (!controller.isPaired) ...[
            SurfaceCard(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.phonelink_lock_outlined,
                    color: AppColors.primary,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Connect your desktop',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: 5),
                        Text(
                          'Sync over local Wi-Fi, then keep browsing your finances when the desktop is off.',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        const SizedBox(height: 13),
                        FilledButton.icon(
                          onPressed: onPair,
                          icon: const Icon(Icons.link, size: 18),
                          label: const Text('Pair desktop'),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
          ],
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppColors.ink,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'NET WORTH',
                  style: TextStyle(
                    color: Color(0xFFAFC2BC),
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0,
                  ),
                ),
                const SizedBox(height: 8),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    money(controller.netWorthCents),
                    style: Theme.of(
                      context,
                    ).textTheme.displaySmall?.copyWith(color: Colors.white),
                  ),
                ),
                const SizedBox(height: 20),
                Row(
                  children: [
                    Expanded(
                      child: _PortfolioDetail(
                        label: 'Available liquidity',
                        value: money(controller.liquidityCents),
                        negative: controller.liquidityCents < 0,
                      ),
                    ),
                    Container(
                      width: 1,
                      height: 38,
                      color: const Color(0xFF3A4D47),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: _PortfolioDetail(
                        label: 'Debt & overdraft',
                        value: money(controller.debtCents),
                        negative: controller.debtCents > 0,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          GridView.count(
            crossAxisCount: 2,
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
            childAspectRatio: 1.62,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            children: [
              MetricCard(
                label: 'Income this month',
                value: money(controller.monthIncomeCents),
                icon: Icons.trending_up,
                tone: AppColors.positive,
              ),
              MetricCard(
                label: 'Spent this month',
                value: money(controller.monthExpenseCents),
                icon: Icons.trending_down,
                tone: controller.monthExpenseCents > 0
                    ? AppColors.negative
                    : AppColors.ink,
              ),
            ],
          ),
          if (controller.pendingCount > 0 || controller.failedCount > 0) ...[
            const SizedBox(height: 14),
            SurfaceCard(
              child: Row(
                children: [
                  Icon(
                    controller.failedCount > 0
                        ? Icons.error_outline
                        : Icons.cloud_upload_outlined,
                    color: controller.failedCount > 0
                        ? AppColors.negative
                        : AppColors.blue,
                  ),
                  const SizedBox(width: 11),
                  Expanded(
                    child: Text(
                      controller.failedCount > 0
                          ? '${controller.failedCount} change${controller.failedCount == 1 ? '' : 's'} need attention'
                          : '${controller.pendingCount} change${controller.pendingCount == 1 ? '' : 's'} waiting for the desktop',
                    ),
                  ),
                  const Icon(Icons.chevron_right),
                ],
              ),
            ),
          ],
          const SizedBox(height: 24),
          SectionHeader(
            title: 'Recent activity',
            subtitle: 'Adjustments are kept out of this everyday view',
            trailing: TextButton.icon(
              onPressed: controller.accounts.isEmpty ? null : onAddTransaction,
              icon: const Icon(Icons.add, size: 18),
              label: const Text('Add'),
            ),
          ),
          const SizedBox(height: 10),
          SurfaceCard(
            padding: EdgeInsets.zero,
            child: recent.isEmpty
                ? const EmptyState(
                    icon: Icons.receipt_long_outlined,
                    title: 'No transactions yet',
                    message:
                        'Your synced income and spending will appear here.',
                  )
                : Column(
                    children: [
                      for (var index = 0; index < recent.length; index++) ...[
                        _TransactionTile(
                          transaction: recent[index],
                          controller: controller,
                        ),
                        if (index != recent.length - 1)
                          const Divider(height: 1, indent: 56),
                      ],
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

class _PortfolioDetail extends StatelessWidget {
  const _PortfolioDetail({
    required this.label,
    required this.value,
    this.negative = false,
  });

  final String label;
  final String value;
  final bool negative;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        label,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: const TextStyle(
          color: Color(0xFFAFC2BC),
          fontSize: 11,
          letterSpacing: 0,
        ),
      ),
      const SizedBox(height: 4),
      FittedBox(
        fit: BoxFit.scaleDown,
        alignment: Alignment.centerLeft,
        child: Text(
          value,
          style: TextStyle(
            color: negative ? const Color(0xFFFF8C86) : Colors.white,
            fontSize: 16,
            fontWeight: FontWeight.w700,
            letterSpacing: 0,
          ),
        ),
      ),
    ],
  );
}

class _TransactionTile extends StatelessWidget {
  const _TransactionTile({required this.transaction, required this.controller});

  final TransactionRecord transaction;
  final AppController controller;

  @override
  Widget build(BuildContext context) {
    var account = 'Account';
    for (final item in controller.accounts) {
      if (item.id == transaction.accountId) {
        account = item.name;
        break;
      }
    }
    final tone = transaction.isIncome
        ? AppColors.positive
        : transaction.isExpense
        ? AppColors.negative
        : AppColors.blue;
    final icon = transaction.isIncome
        ? Icons.north_east
        : transaction.isExpense
        ? Icons.south_west
        : Icons.swap_horiz;
    return ListTile(
      minLeadingWidth: 36,
      leading: Container(
        width: 36,
        height: 36,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: tone.withValues(alpha: .10),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Icon(icon, size: 19, color: tone),
      ),
      title: Text(
        transaction.description.isEmpty
            ? prettyType(transaction.type)
            : transaction.description,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      subtitle: Text(
        '$account · ${friendlyDate(transaction.date)}',
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      trailing: AmountText(
        transaction.amountCents,
        neutral: transaction.isTransfer,
      ),
    );
  }
}
