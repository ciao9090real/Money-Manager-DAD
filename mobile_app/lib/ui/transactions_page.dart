import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../models/finance_models.dart';
import '../theme/app_theme.dart';
import 'widgets.dart';

class TransactionsPage extends StatefulWidget {
  const TransactionsPage({
    super.key,
    required this.controller,
    required this.onAdd,
  });

  final AppController controller;
  final VoidCallback onAdd;

  @override
  State<TransactionsPage> createState() => _TransactionsPageState();
}

class _TransactionsPageState extends State<TransactionsPage> {
  String filter = 'all';

  @override
  Widget build(BuildContext context) {
    final entries = _entries(widget.controller).where((entry) {
      return filter == 'all' || entry.filterType == filter;
    }).toList();
    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 108),
      children: [
        ScreenHeader(
          title: 'Activity',
          subtitle: 'Income, expenses, and transfers',
          action: IconButton.filled(
            tooltip: 'Add transaction',
            onPressed: widget.controller.accounts.isEmpty ? null : widget.onAdd,
            icon: const Icon(Icons.add),
          ),
        ),
        const SizedBox(height: 18),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'all', label: Text('All')),
              ButtonSegment(value: 'income', label: Text('Income')),
              ButtonSegment(value: 'expense', label: Text('Expenses')),
              ButtonSegment(value: 'transfer', label: Text('Transfers')),
            ],
            selected: {filter},
            showSelectedIcon: false,
            onSelectionChanged: (selection) =>
                setState(() => filter = selection.first),
          ),
        ),
        if (widget.controller.pendingCommands.isNotEmpty) ...[
          const SizedBox(height: 18),
          const SectionHeader(title: 'Phone changes'),
          const SizedBox(height: 9),
          SurfaceCard(
            padding: EdgeInsets.zero,
            child: Column(
              children: [
                for (
                  var index = 0;
                  index < widget.controller.pendingCommands.length;
                  index++
                ) ...[
                  _PendingRow(
                    command: widget.controller.pendingCommands[index],
                    onDismiss:
                        widget.controller.pendingCommands[index].status ==
                            'failed'
                        ? () => widget.controller.dismissFailedCommand(
                            widget.controller.pendingCommands[index].id,
                          )
                        : null,
                  ),
                  if (index != widget.controller.pendingCommands.length - 1)
                    const Divider(height: 1, indent: 52),
                ],
              ],
            ),
          ),
        ],
        const SizedBox(height: 22),
        SectionHeader(
          title: 'Transactions',
          trailing: Text(
            '${entries.length} shown',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
        const SizedBox(height: 9),
        SurfaceCard(
          padding: EdgeInsets.zero,
          child: entries.isEmpty
              ? EmptyState(
                  icon: Icons.receipt_long_outlined,
                  title: 'Nothing to show',
                  message: filter == 'all'
                      ? 'Synced transactions will appear here.'
                      : 'There are no ${filter == 'expense' ? 'expenses' : '${filter}s'} in this view.',
                  action: widget.controller.accounts.isEmpty
                      ? null
                      : OutlinedButton.icon(
                          onPressed: widget.onAdd,
                          icon: const Icon(Icons.add),
                          label: const Text('Add transaction'),
                        ),
                )
              : Column(
                  children: [
                    for (var index = 0; index < entries.length; index++) ...[
                      _ActivityRow(entry: entries[index]),
                      if (index != entries.length - 1)
                        const Divider(height: 1, indent: 58),
                    ],
                  ],
                ),
        ),
      ],
    );
  }
}

List<_ActivityEntry> _entries(AppController controller) {
  final names = {
    for (final account in controller.accounts) account.id: account.name,
  };
  final result = <_ActivityEntry>[];
  final seenTransfers = <String>{};
  for (final transaction in controller.transactions) {
    if (transaction.type == 'adjustment') continue;
    if (transaction.isTransfer && transaction.transferGroupId != null) {
      if (!seenTransfers.add(transaction.transferGroupId!)) continue;
      final pair = controller.transactions
          .where((item) => item.transferGroupId == transaction.transferGroupId)
          .toList();
      TransactionRecord? outgoing;
      TransactionRecord? incoming;
      for (final item in pair) {
        if (item.type == 'transfer_out') outgoing = item;
        if (item.type == 'transfer_in') incoming = item;
      }
      final amount =
          outgoing?.amountCents.abs() ?? incoming?.amountCents.abs() ?? 0;
      result.add(
        _ActivityEntry(
          title:
              '${names[outgoing?.accountId] ?? 'Account'} → ${names[incoming?.accountId] ?? 'Account'}',
          subtitle: transaction.description.isEmpty
              ? friendlyDate(transaction.date)
              : '${transaction.description} · ${friendlyDate(transaction.date)}',
          amountCents: amount,
          filterType: 'transfer',
          neutral: true,
          icon: Icons.swap_horiz,
          tone: AppColors.blue,
        ),
      );
      continue;
    }
    final filterType = transaction.isIncome
        ? 'income'
        : transaction.isExpense
        ? 'expense'
        : 'all';
    result.add(
      _ActivityEntry(
        title: transaction.description.isEmpty
            ? prettyType(transaction.type)
            : transaction.description,
        subtitle:
            '${names[transaction.accountId] ?? 'Account'} · ${friendlyDate(transaction.date)}',
        amountCents: transaction.amountCents,
        filterType: filterType,
        neutral: false,
        icon: transaction.isIncome ? Icons.north_east : Icons.south_west,
        tone: transaction.isIncome ? AppColors.positive : AppColors.negative,
      ),
    );
  }
  return result;
}

class _ActivityEntry {
  const _ActivityEntry({
    required this.title,
    required this.subtitle,
    required this.amountCents,
    required this.filterType,
    required this.neutral,
    required this.icon,
    required this.tone,
  });

  final String title;
  final String subtitle;
  final int amountCents;
  final String filterType;
  final bool neutral;
  final IconData icon;
  final Color tone;
}

class _ActivityRow extends StatelessWidget {
  const _ActivityRow({required this.entry});

  final _ActivityEntry entry;

  @override
  Widget build(BuildContext context) => ListTile(
    leading: Container(
      width: 38,
      height: 38,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: entry.tone.withValues(alpha: .10),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Icon(entry.icon, color: entry.tone, size: 20),
    ),
    title: Text(entry.title, maxLines: 1, overflow: TextOverflow.ellipsis),
    subtitle: Text(
      entry.subtitle,
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
    ),
    trailing: AmountText(entry.amountCents, neutral: entry.neutral),
  );
}

class _PendingRow extends StatelessWidget {
  const _PendingRow({required this.command, this.onDismiss});

  final PendingCommand command;
  final VoidCallback? onDismiss;

  @override
  Widget build(BuildContext context) {
    final failed = command.status == 'failed';
    return ListTile(
      leading: Icon(
        failed ? Icons.error_outline : Icons.schedule,
        color: failed ? AppColors.negative : AppColors.warning,
      ),
      title: Text(prettyType(command.type.replaceFirst('create_', ''))),
      subtitle: Text(
        failed
            ? command.error ?? 'Desktop rejected this change'
            : 'Waiting for the desktop',
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
      ),
      trailing: onDismiss == null
          ? const Pill('Pending', tone: 'warning')
          : IconButton(
              tooltip: 'Dismiss',
              onPressed: onDismiss,
              icon: const Icon(Icons.close),
            ),
    );
  }
}
