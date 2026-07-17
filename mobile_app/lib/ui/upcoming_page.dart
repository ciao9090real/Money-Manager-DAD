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
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            widget.controller.syncError == null
                ? 'Payment recorded'
                : 'Saved on phone and waiting to sync',
          ),
        ),
      );
    }
  }
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
                tooltip: 'Record payment',
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
