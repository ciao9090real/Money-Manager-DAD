import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../app_controller.dart';
import '../models/finance_models.dart';
import '../theme/app_theme.dart';
import 'widgets.dart';

class UpcomingPage extends StatefulWidget {
  const UpcomingPage({super.key, required this.controller});

  final AppController controller;

  @override
  State<UpcomingPage> createState() => _UpcomingPageState();
}

class _UpcomingPageState extends State<UpcomingPage> {
  String filter = 'all';

  @override
  Widget build(BuildContext context) {
    final reminders = widget.controller.reminders();
    final rules = widget.controller.recurring.where((rule) {
      return switch (filter) {
        'income' => rule.transactionType == 'income',
        'subscription' => rule.kind == 'subscription',
        'bill' => rule.kind == 'bill',
        _ => true,
      };
    }).toList();
    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 108),
      children: [
        const ScreenHeader(
          title: 'Upcoming',
          subtitle: 'Expected income, subscriptions, and bills',
        ),
        if (reminders.isNotEmpty) ...[
          const SizedBox(height: 18),
          _ReminderCenter(
            reminders: reminders,
            hasPendingRecord: widget.controller.recurringHasPendingRecord,
            onRecord: _record,
          ),
        ] else if (widget.controller.recurring.any(
          (rule) => rule.status == 'active',
        )) ...[
          const SizedBox(height: 18),
          const _QuietReminderStrip(),
        ],
        const SizedBox(height: 18),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'all', label: Text('All')),
              ButtonSegment(value: 'income', label: Text('Income')),
              ButtonSegment(
                value: 'subscription',
                label: Text('Subscriptions'),
              ),
              ButtonSegment(value: 'bill', label: Text('Bills')),
            ],
            selected: {filter},
            showSelectedIcon: false,
            onSelectionChanged: (value) => setState(() => filter = value.first),
          ),
        ),
        const SizedBox(height: 18),
        SurfaceCard(
          padding: EdgeInsets.zero,
          child: rules.isEmpty
              ? const EmptyState(
                  icon: Icons.event_repeat_outlined,
                  title: 'No recurring schedules',
                  message:
                      'Create wages, subscriptions, and bills on the desktop, then sync them here.',
                )
              : Column(
                  children: [
                    for (var index = 0; index < rules.length; index++) ...[
                      _RecurringRow(
                        rule: rules[index],
                        accountName: _accountName(rules[index].accountId),
                        onRecord: rules[index].status == 'active'
                            ? () => _record(rules[index])
                            : null,
                      ),
                      if (index != rules.length - 1)
                        const Divider(height: 1, indent: 58),
                    ],
                  ],
                ),
        ),
      ],
    );
  }

  String _accountName(String id) {
    for (final account in widget.controller.accounts) {
      if (account.id == id) return account.name;
    }
    return 'Account';
  }

  Future<void> _record(RecurringRecord rule) async {
    int? amount = rule.amountCents;
    if (amount == null) {
      amount = await showDialog<int>(
        context: context,
        builder: (context) => const _VariableAmountDialog(),
      );
      if (amount == null) return;
    }
    await widget.controller.recordRecurring(rule.id, amountCents: amount);
    if (mounted) {
      setState(() {});
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            widget.controller.syncError == null
                ? 'Schedule recorded'
                : 'Saved on phone and waiting to sync',
          ),
        ),
      );
    }
  }
}

class _ReminderCenter extends StatelessWidget {
  const _ReminderCenter({
    required this.reminders,
    required this.hasPendingRecord,
    required this.onRecord,
  });

  final List<ReminderItem> reminders;
  final bool Function(String ruleId) hasPendingRecord;
  final ValueChanged<RecurringRecord> onRecord;

  @override
  Widget build(BuildContext context) => Container(
    clipBehavior: Clip.antiAlias,
    decoration: BoxDecoration(
      color: const Color(0xFFFFFCF5),
      borderRadius: BorderRadius.circular(18),
      boxShadow: const [
        BoxShadow(
          color: Color(0x12000000),
          blurRadius: 16,
          offset: Offset(0, 4),
        ),
      ],
    ),
    child: Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 15, 14, 13),
          child: Row(
            children: [
              const _KnockingBell(),
              const SizedBox(width: 11),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      reminders.length == 1
                          ? 'One thing is knocking'
                          : '${reminders.length} things are knocking',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Inside the reminder window you chose on desktop',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
              Pill(
                '${reminders.length}',
                tone: reminders.any((item) => item.isOverdue)
                    ? 'negative'
                    : 'warning',
              ),
            ],
          ),
        ),
        const Divider(height: 1),
        for (var index = 0; index < math.min(reminders.length, 4); index++) ...[
          _ReminderRow(
            item: reminders[index],
            pending: hasPendingRecord(reminders[index].rule.id),
            onRecord: () => onRecord(reminders[index].rule),
          ),
          if (index != math.min(reminders.length, 4) - 1)
            const Divider(height: 1, indent: 54),
        ],
        if (reminders.length > 4)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 13),
            child: Text(
              '+${reminders.length - 4} more in the full schedule below',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
      ],
    ),
  );
}

class _KnockingBell extends StatelessWidget {
  const _KnockingBell();

  @override
  Widget build(BuildContext context) {
    final reduceMotion = MediaQuery.disableAnimationsOf(context);
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: reduceMotion ? 1 : 0, end: 1),
      duration: const Duration(milliseconds: 620),
      curve: Curves.elasticOut,
      builder: (context, value, child) => Transform.rotate(
        angle: math.sin(value * math.pi * 3) * (1 - value) * .22,
        child: child,
      ),
      child: Container(
        width: 40,
        height: 40,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: AppColors.warning.withValues(alpha: .12),
          borderRadius: BorderRadius.circular(12),
        ),
        child: const Icon(
          Icons.notifications_active_outlined,
          color: AppColors.warning,
          size: 21,
        ),
      ),
    );
  }
}

class _ReminderRow extends StatelessWidget {
  const _ReminderRow({
    required this.item,
    required this.pending,
    required this.onRecord,
  });

  final ReminderItem item;
  final bool pending;
  final VoidCallback onRecord;

  @override
  Widget build(BuildContext context) {
    final tone = item.isOverdue ? AppColors.negative : AppColors.warning;
    return Padding(
      padding: const EdgeInsets.fromLTRB(15, 11, 9, 11),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: tone, shape: BoxShape.circle),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.rule.name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 2),
                Text(
                  _dueCopy(item),
                  style: Theme.of(
                    context,
                  ).textTheme.bodySmall?.copyWith(color: tone),
                ),
              ],
            ),
          ),
          if (item.rule.amountCents != null) ...[
            const SizedBox(width: 8),
            AmountText(
              item.isIncome ? item.rule.amountCents! : -item.rule.amountCents!,
            ),
          ],
          const SizedBox(width: 5),
          IconButton(
            tooltip: pending ? 'Waiting to sync' : 'Record now',
            onPressed: pending ? null : onRecord,
            icon: Icon(
              pending ? Icons.schedule : Icons.check_circle_outline,
              size: 21,
            ),
          ),
        ],
      ),
    );
  }
}

class _QuietReminderStrip extends StatelessWidget {
  const _QuietReminderStrip();

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 13),
    decoration: BoxDecoration(
      color: AppColors.primarySoft,
      borderRadius: BorderRadius.circular(16),
    ),
    child: Row(
      children: [
        const Icon(
          Icons.notifications_none,
          color: AppColors.primary,
          size: 21,
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            'Nothing is knocking. Your reminder windows are quiet.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppColors.ink,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    ),
  );
}

String _dueCopy(ReminderItem item) {
  if (item.isOverdue) {
    final days = -item.daysUntil;
    return '$days ${days == 1 ? 'day' : 'days'} overdue';
  }
  if (item.isToday) return 'Due today';
  if (item.daysUntil == 1) return 'Due tomorrow';
  return 'Due in ${item.daysUntil} days';
}

class _RecurringRow extends StatelessWidget {
  const _RecurringRow({
    required this.rule,
    required this.accountName,
    this.onRecord,
  });

  final RecurringRecord rule;
  final String accountName;
  final VoidCallback? onRecord;

  @override
  Widget build(BuildContext context) {
    final income = rule.transactionType == 'income';
    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 13, 10, 13),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: (income ? AppColors.positive : AppColors.blue).withValues(
                alpha: .10,
              ),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(
              income ? Icons.payments_outlined : Icons.event_repeat,
              color: income ? AppColors.positive : AppColors.blue,
              size: 20,
            ),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  rule.name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 3),
                Text(
                  '${friendlyDate(rule.nextDueDate)} · $accountName',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 5),
                Wrap(
                  spacing: 6,
                  runSpacing: 4,
                  children: [
                    Pill(prettyType(rule.kind), tone: 'info'),
                    Pill(
                      prettyType(rule.status),
                      tone: rule.status == 'active' ? 'positive' : 'neutral',
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              if (rule.amountCents != null)
                AmountText(income ? rule.amountCents! : -rule.amountCents!),
              const SizedBox(height: 5),
              IconButton.filledTonal(
                tooltip: income ? 'Record income' : 'Record payment',
                onPressed: onRecord,
                icon: const Icon(Icons.play_arrow, size: 19),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _VariableAmountDialog extends StatefulWidget {
  const _VariableAmountDialog();

  @override
  State<_VariableAmountDialog> createState() => _VariableAmountDialogState();
}

class _VariableAmountDialogState extends State<_VariableAmountDialog> {
  final controller = TextEditingController();

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Actual amount'),
    content: TextField(
      controller: controller,
      autofocus: true,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9,.]'))],
      decoration: const InputDecoration(prefixText: '€ '),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Cancel'),
      ),
      FilledButton(
        onPressed: () {
          final value = double.tryParse(controller.text.replaceAll(',', '.'));
          if (value != null && value > 0) {
            Navigator.pop(context, (value * 100).round());
          }
        },
        child: const Text('Record'),
      ),
    ],
  );
}
