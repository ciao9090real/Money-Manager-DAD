import 'dart:math' as math;

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
    this.onAddExpense,
    this.onAddIncome,
    this.onAddTransfer,
  });

  final AppController controller;
  final VoidCallback onAddTransaction;
  final VoidCallback onPair;
  final VoidCallback onOpenBudgets;
  final VoidCallback onOpenGoals;
  final VoidCallback? onAddExpense;
  final VoidCallback? onAddIncome;
  final VoidCallback? onAddTransfer;

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
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final upcoming = controller.recurring
        .where((rule) {
          final due = DateTime.tryParse(rule.nextDueDate);
          return rule.status == 'active' &&
              due != null &&
              !DateTime(due.year, due.month, due.day).isBefore(today);
        })
        .take(2)
        .toList();
    final monthNetCents =
        controller.monthIncomeCents - controller.monthExpenseCents;
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
                          ? 'Today · private and available offline'
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
          SurfaceCard(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 18),
            child: Stack(
              children: [
                Positioned.fill(
                  child: IgnorePointer(
                    child: CustomPaint(painter: _HeroSparklinePainter(history)),
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'TOTAL NET WORTH',
                      style: TextStyle(
                        color: AppColors.muted,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 1,
                      ),
                    ),
                    const SizedBox(height: 8),
                    FittedBox(
                      fit: BoxFit.scaleDown,
                      alignment: Alignment.centerLeft,
                      child: Text(
                        money(controller.netWorthCents),
                        style: Theme.of(context).textTheme.displaySmall,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Pill(
                      '${monthNetCents > 0 ? '+' : ''}${money(monthNetCents)} this month',
                      tone: monthNetCents >= 0 ? 'positive' : 'negative',
                    ),
                    const SizedBox(height: 24),
                    Row(
                      children: [
                        Expanded(
                          child: _PortfolioDetail(
                            label: 'Ready money',
                            value: money(controller.liquidityCents),
                            negative: controller.liquidityCents < 0,
                          ),
                        ),
                        Container(
                          width: 1,
                          height: 38,
                          color: AppColors.border,
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: _PortfolioDetail(
                            label: 'Owed',
                            value: money(controller.debtCents),
                            negative: controller.debtCents > 0,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          SurfaceCard(
            padding: EdgeInsets.zero,
            child: Row(
              children: [
                Expanded(
                  child: _QuickAction(
                    label: 'Expense',
                    icon: Icons.south_west,
                    tone: AppColors.negative,
                    onTap: controller.accounts.isEmpty
                        ? null
                        : onAddExpense ?? onAddTransaction,
                  ),
                ),
                const _ActionDivider(),
                Expanded(
                  child: _QuickAction(
                    label: 'Income',
                    icon: Icons.north_east,
                    tone: AppColors.positive,
                    onTap: controller.accounts.isEmpty
                        ? null
                        : onAddIncome ?? onAddTransaction,
                  ),
                ),
                const _ActionDivider(),
                Expanded(
                  child: _QuickAction(
                    label: 'Move',
                    icon: Icons.swap_horiz,
                    tone: AppColors.blue,
                    onTap: controller.accounts.length < 2
                        ? null
                        : onAddTransfer ?? onAddTransaction,
                  ),
                ),
                const _ActionDivider(),
                Expanded(
                  child: _QuickAction(
                    label: 'Sync',
                    icon: Icons.sync,
                    tone: AppColors.primary,
                    onTap: controller.isSyncing
                        ? null
                        : () => _refresh(context),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          const SectionHeader(
            title: 'Today',
            subtitle: 'Recorded movement and what is due next',
          ),
          const SizedBox(height: 10),
          _TodayBrief(upcoming: upcoming),
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
          _HealthBoard(
            incomeCents: controller.monthIncomeCents,
            expenseCents: controller.monthExpenseCents,
            savingsRateBasisPoints: savingsRateBasisPoints,
            emergencyCoverageHundredths: emergencyCoverageHundredths,
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

class _HeroSparklinePainter extends CustomPainter {
  const _HeroSparklinePainter(this.points);

  final List<NetWorthPoint> points;

  @override
  void paint(Canvas canvas, Size size) {
    if (points.length < 2) return;
    final values = points.map((point) => point.netWorthCents).toList();
    final minimum = values.reduce(math.min);
    final maximum = values.reduce(math.max);
    final span = math.max(1, maximum - minimum);
    final top = size.height * .44;
    final bottom = size.height;
    final path = Path();
    for (var index = 0; index < values.length; index++) {
      final x = index * size.width / (values.length - 1);
      final ratio = (values[index] - minimum) / span;
      final y = bottom - ratio * (bottom - top);
      if (index == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }

    final area = Path.from(path)
      ..lineTo(size.width, size.height)
      ..lineTo(0, size.height)
      ..close();
    canvas.drawPath(
      area,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            AppColors.primary.withValues(alpha: .13),
            AppColors.primary.withValues(alpha: 0),
          ],
        ).createShader(Offset.zero & size),
    );
    canvas.drawPath(
      path,
      Paint()
        ..color = AppColors.primary.withValues(alpha: .42)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );
  }

  @override
  bool shouldRepaint(covariant _HeroSparklinePainter oldDelegate) =>
      oldDelegate.points != points;
}

class _TodayBrief extends StatelessWidget {
  const _TodayBrief({required this.upcoming});

  final List<RecurringRecord> upcoming;

  @override
  Widget build(BuildContext context) => SurfaceCard(
    padding: EdgeInsets.zero,
    child: Column(
      children: [
        if (upcoming.isEmpty)
          const _TodayRow(
            icon: Icons.event_available_outlined,
            tone: AppColors.primary,
            title: 'Nothing scheduled next',
            subtitle: 'Recurring items from the desktop appear here',
            trailing: Icon(
              Icons.check_circle_outline,
              size: 20,
              color: AppColors.primary,
            ),
          )
        else
          for (var index = 0; index < upcoming.length; index++) ...[
            _TodayRow(
              icon: upcoming[index].transactionType == 'income'
                  ? Icons.north_east
                  : Icons.south_west,
              tone: upcoming[index].transactionType == 'income'
                  ? AppColors.positive
                  : AppColors.negative,
              title: upcoming[index].name,
              subtitle: 'Due ${friendlyDate(upcoming[index].nextDueDate)}',
              trailing: upcoming[index].amountCents == null
                  ? const Pill('Variable', tone: 'neutral')
                  : AmountText(
                      upcoming[index].transactionType == 'income'
                          ? upcoming[index].amountCents!
                          : -upcoming[index].amountCents!,
                    ),
            ),
            if (index != upcoming.length - 1)
              const Divider(height: 1, indent: 58, endIndent: 14),
          ],
      ],
    ),
  );
}

class _TodayRow extends StatelessWidget {
  const _TodayRow({
    required this.icon,
    required this.tone,
    required this.title,
    required this.subtitle,
    required this.trailing,
  });

  final IconData icon;
  final Color tone;
  final String title;
  final String subtitle;
  final Widget trailing;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(14, 13, 14, 13),
    child: Row(
      children: [
        Container(
          width: 34,
          height: 34,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: tone.withValues(alpha: .10),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(icon, color: tone, size: 19),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 2),
              Text(
                subtitle,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
        const SizedBox(width: 10),
        trailing,
      ],
    ),
  );
}

class _QuickAction extends StatelessWidget {
  const _QuickAction({
    required this.label,
    required this.icon,
    required this.tone,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final Color tone;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => Material(
    color: Colors.transparent,
    child: InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(13),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 4),
        child: Column(
          children: [
            Icon(icon, size: 21, color: onTap == null ? AppColors.muted : tone),
            const SizedBox(height: 6),
            Text(
              label,
              maxLines: 1,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: onTap == null ? AppColors.muted : AppColors.ink,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class _ActionDivider extends StatelessWidget {
  const _ActionDivider();

  @override
  Widget build(BuildContext context) =>
      const SizedBox(height: 34, child: VerticalDivider(width: 1));
}

class _HealthBoard extends StatelessWidget {
  const _HealthBoard({
    required this.incomeCents,
    required this.expenseCents,
    required this.savingsRateBasisPoints,
    required this.emergencyCoverageHundredths,
  });

  final int incomeCents;
  final int expenseCents;
  final int savingsRateBasisPoints;
  final int emergencyCoverageHundredths;

  @override
  Widget build(BuildContext context) => SurfaceCard(
    padding: EdgeInsets.zero,
    child: Column(
      children: [
        Row(
          children: [
            Expanded(
              child: _HealthMetric(
                label: 'Income this month',
                value: money(incomeCents),
                tone: AppColors.positive,
              ),
            ),
            const SizedBox(height: 72, child: VerticalDivider(width: 1)),
            Expanded(
              child: _HealthMetric(
                label: 'Spent this month',
                value: money(expenseCents),
                tone: expenseCents > 0 ? AppColors.negative : AppColors.ink,
              ),
            ),
          ],
        ),
        const Divider(height: 1),
        Row(
          children: [
            Expanded(
              child: _HealthMetric(
                label: 'Savings rate',
                value: _percentFromBasisPoints(savingsRateBasisPoints),
                tone: savingsRateBasisPoints < 0
                    ? AppColors.negative
                    : AppColors.positive,
              ),
            ),
            const SizedBox(height: 72, child: VerticalDivider(width: 1)),
            Expanded(
              child: _HealthMetric(
                label: 'Emergency fund',
                value:
                    '${(emergencyCoverageHundredths / 100).toStringAsFixed(1)} months',
                tone: _coverageTone(emergencyCoverageHundredths),
              ),
            ),
          ],
        ),
      ],
    ),
  );
}

class _HealthMetric extends StatelessWidget {
  const _HealthMetric({
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
        Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: Theme.of(context).textTheme.bodySmall,
        ),
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
          color: AppColors.muted,
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
            fontFamily: 'SpaceGrotesk',
            color: negative ? AppColors.negative : AppColors.ink,
            fontSize: 16,
            fontWeight: FontWeight.w600,
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
