import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../app_controller.dart';
import '../models/finance_models.dart';
import '../theme/app_theme.dart';
import 'widgets.dart';

class BudgetsPage extends StatefulWidget {
  const BudgetsPage({super.key, required this.controller});

  final AppController controller;

  @override
  State<BudgetsPage> createState() => _BudgetsPageState();
}

class _BudgetsPageState extends State<BudgetsPage> {
  late DateTime referenceMonth;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    referenceMonth = DateTime(now.year, now.month);
  }

  void _moveMonth(int offset) {
    setState(() {
      referenceMonth = DateTime(
        referenceMonth.year,
        referenceMonth.month + offset,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Budgets')),
      body: SafeArea(
        top: false,
        child: AnimatedBuilder(
          animation: widget.controller,
          builder: (context, _) {
            final statuses = widget.controller.budgetStatuses(
              referenceDate: referenceMonth,
            );
            return ListView(
              padding: const EdgeInsets.fromLTRB(18, 8, 18, 32),
              children: [
                const ScreenHeader(
                  title: 'Monthly budgets',
                  subtitle: 'See where your spending stands at a glance',
                ),
                const SizedBox(height: 18),
                _MonthSelector(
                  month: referenceMonth,
                  onPrevious: () => _moveMonth(-1),
                  onNext: () => _moveMonth(1),
                ),
                const SizedBox(height: 14),
                if (statuses.isEmpty)
                  const SurfaceCard(
                    child: EmptyState(
                      icon: Icons.donut_small_outlined,
                      title: 'No budgets for this month',
                      message:
                          'Create category budgets on the desktop, then sync this phone.',
                    ),
                  )
                else
                  for (var index = 0; index < statuses.length; index++) ...[
                    _BudgetCard(
                      status: statuses[index],
                      categoryName: _categoryName(
                        statuses[index].budget.categoryId,
                      ),
                    ),
                    if (index != statuses.length - 1)
                      const SizedBox(height: 11),
                  ],
                const SizedBox(height: 16),
                Text(
                  'Budget limits and rollover settings are managed on the desktop.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  String _categoryName(String categoryId) {
    for (final category in widget.controller.categories) {
      if (category.id == categoryId) return category.name;
    }
    return 'Archived category';
  }
}

class _MonthSelector extends StatelessWidget {
  const _MonthSelector({
    required this.month,
    required this.onPrevious,
    required this.onNext,
  });

  final DateTime month;
  final VoidCallback onPrevious;
  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) => SurfaceCard(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
    child: Row(
      children: [
        IconButton(
          tooltip: 'Previous month',
          onPressed: onPrevious,
          icon: const Icon(Icons.chevron_left),
        ),
        Expanded(
          child: Text(
            DateFormat('MMMM yyyy').format(month),
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ),
        IconButton(
          tooltip: 'Next month',
          onPressed: onNext,
          icon: const Icon(Icons.chevron_right),
        ),
      ],
    ),
  );
}

class _BudgetCard extends StatelessWidget {
  const _BudgetCard({required this.status, required this.categoryName});

  final BudgetStatus status;
  final String categoryName;

  @override
  Widget build(BuildContext context) {
    final percent = status.percentUsed;
    final tone = _budgetTone(percent);
    final remaining = status.remainingCents;
    return SurfaceCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  categoryName,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              const SizedBox(width: 10),
              Pill(
                '${percent.toStringAsFixed(percent >= 100 ? 0 : 1)}% used',
                tone: percent > 100
                    ? 'negative'
                    : percent >= 80
                    ? 'warning'
                    : 'positive',
              ),
            ],
          ),
          const SizedBox(height: 12),
          FinanceProgressBar(percent: percent, tone: tone),
          const SizedBox(height: 11),
          Row(
            children: [
              Expanded(
                child: Text(
                  '${money(status.spentCents)} of ${money(status.limitCents)}',
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
              const SizedBox(width: 10),
              Text(
                remaining < 0
                    ? '${money(-remaining)} over'
                    : '${money(remaining)} left',
                textAlign: TextAlign.right,
                style: TextStyle(
                  color: remaining < 0 ? AppColors.negative : AppColors.muted,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          if (status.budget.rollover) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 7,
              runSpacing: 6,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                const Pill('Rollover', tone: 'info'),
                if (status.rolledOverFromPriorCents > 0)
                  Text(
                    '${money(status.rolledOverFromPriorCents)} carried forward',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

Color _budgetTone(double percent) {
  if (percent > 100) return AppColors.negative;
  if (percent >= 80) return AppColors.warning;
  return AppColors.positive;
}
