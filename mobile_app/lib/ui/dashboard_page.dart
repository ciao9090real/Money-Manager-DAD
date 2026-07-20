import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../models/finance_models.dart';
import '../theme/app_theme.dart';
import 'net_worth_chart.dart';
import 'widgets.dart';

class DashboardPage extends StatelessWidget {
  const DashboardPage({
    super.key,
    required this.controller,
    required this.onAddTransaction,
    required this.onPair,
    required this.onOpenBudgets,
    required this.onOpenGoals,
  });

  final AppController controller;
  final VoidCallback onAddTransaction;
  final VoidCallback onPair;
  final VoidCallback onOpenBudgets;
  final VoidCallback onOpenGoals;

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
    final budgets = [...controller.budgetStatuses()]
      ..sort((a, b) {
        final percent = b.percentUsedBasisPoints.compareTo(
          a.percentUsedBasisPoints,
        );
        return percent == 0 ? b.spentCents.compareTo(a.spentCents) : percent;
      });
    final goals = controller.goalProgresses.take(3).toList();
    final history = controller.netWorthHistory();
    final savingsRateBasisPoints = controller.savingsRateBasisPoints();
    final emergencyCoverageHundredths = controller
        .emergencyFundCoverageHundredths();
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
                          'Scan one QR code to connect over local Wi-Fi, then browse your finances offline.',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        const SizedBox(height: 13),
                        FilledButton.icon(
                          onPressed: onPair,
                          icon: const Icon(Icons.qr_code_scanner, size: 18),
                          label: const Text('Scan desktop QR'),
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
          SurfaceCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SectionHeader(
                  title: 'Net worth trend',
                  subtitle: 'Assets, liabilities, and your position over time',
                  trailing: history.any((point) => point.estimated)
                      ? const Pill('Estimated', tone: 'info')
                      : null,
                ),
                const SizedBox(height: 14),
                NetWorthTrendChart(points: history),
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
              MetricCard(
                label: 'Savings rate',
                value: _percentFromBasisPoints(savingsRateBasisPoints),
                icon: Icons.savings_outlined,
                tone: savingsRateBasisPoints < 0
                    ? AppColors.negative
                    : AppColors.positive,
              ),
              MetricCard(
                label: 'Emergency fund',
                value:
                    '${(emergencyCoverageHundredths / 100).toStringAsFixed(1)} months',
                icon: Icons.health_and_safety_outlined,
                tone: _coverageTone(emergencyCoverageHundredths),
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
            title: 'Budgets this month',
            subtitle: 'Categories closest to their limit',
            trailing: TextButton(
              onPressed: onOpenBudgets,
              child: const Text('View all'),
            ),
          ),
          const SizedBox(height: 10),
          SurfaceCard(
            padding: EdgeInsets.zero,
            child: budgets.isEmpty
                ? const _CompactDashboardEmpty(
                    icon: Icons.donut_small_outlined,
                    message: 'Set up category budgets on the desktop.',
                  )
                : Column(
                    children: [
                      for (
                        var index = 0;
                        index < budgets.take(3).length;
                        index++
                      ) ...[
                        _DashboardBudgetRow(
                          status: budgets[index],
                          categoryName: _categoryName(
                            controller,
                            budgets[index].budget.categoryId,
                          ),
                        ),
                        if (index != budgets.take(3).length - 1)
                          const Divider(height: 1, indent: 14, endIndent: 14),
                      ],
                    ],
                  ),
          ),
          const SizedBox(height: 22),
          SectionHeader(
            title: 'Savings goals',
            subtitle: 'Progress toward what matters next',
            trailing: TextButton(
              onPressed: onOpenGoals,
              child: const Text('View all'),
            ),
          ),
          const SizedBox(height: 10),
          SurfaceCard(
            padding: EdgeInsets.zero,
            child: goals.isEmpty
                ? const _CompactDashboardEmpty(
                    icon: Icons.flag_outlined,
                    message: 'Create a savings goal on the desktop.',
                  )
                : Column(
                    children: [
                      for (var index = 0; index < goals.length; index++) ...[
                        _DashboardGoalRow(progress: goals[index]),
                        if (index != goals.length - 1)
                          const Divider(height: 1, indent: 14, endIndent: 14),
                      ],
                    ],
                  ),
          ),
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

class _CompactDashboardEmpty extends StatelessWidget {
  const _CompactDashboardEmpty({required this.icon, required this.message});

  final IconData icon;
  final String message;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(16),
    child: Row(
      children: [
        Icon(icon, color: AppColors.muted, size: 20),
        const SizedBox(width: 10),
        Expanded(
          child: Text(message, style: Theme.of(context).textTheme.bodySmall),
        ),
      ],
    ),
  );
}

class _DashboardBudgetRow extends StatelessWidget {
  const _DashboardBudgetRow({required this.status, required this.categoryName});

  final BudgetStatus status;
  final String categoryName;

  @override
  Widget build(BuildContext context) {
    final percent = status.percentUsed;
    final tone = percent > 100
        ? AppColors.negative
        : percent >= 80
        ? AppColors.warning
        : AppColors.positive;
    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  categoryName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
              const SizedBox(width: 10),
              Text(
                '${money(status.spentCents)} / ${money(status.limitCents)}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
          const SizedBox(height: 8),
          FinanceProgressBar(percent: percent, tone: tone, height: 6),
        ],
      ),
    );
  }
}

class _DashboardGoalRow extends StatelessWidget {
  const _DashboardGoalRow({required this.progress});

  final GoalProgress progress;

  @override
  Widget build(BuildContext context) {
    final complete = progress.isComplete;
    final tone = complete
        ? AppColors.positive
        : progress.onTrack == false
        ? AppColors.warning
        : AppColors.primary;
    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  progress.goal.name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
              const SizedBox(width: 10),
              Text(
                '${money(progress.currentAmountCents)} / ${money(progress.goal.targetAmountCents)}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
          const SizedBox(height: 8),
          FinanceProgressBar(
            percent: progress.percentComplete,
            tone: tone,
            height: 6,
          ),
        ],
      ),
    );
  }
}

String _categoryName(AppController controller, String categoryId) {
  for (final category in controller.categories) {
    if (category.id == categoryId) return category.name;
  }
  return 'Archived category';
}

String _percentFromBasisPoints(int basisPoints) =>
    '${(basisPoints / 100).toStringAsFixed(1)}%';

Color _coverageTone(int coverageHundredths) {
  if (coverageHundredths <
      AppController.emergencyFundWarningCoverageHundredths) {
    return AppColors.negative;
  }
  if (coverageHundredths <
      AppController.emergencyFundHealthyCoverageHundredths) {
    return AppColors.warning;
  }
  return AppColors.positive;
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
