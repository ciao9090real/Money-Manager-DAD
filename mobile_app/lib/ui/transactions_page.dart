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
  final search = TextEditingController();
  String filter = 'all';
  String period = 'all';

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final query = search.text.trim().toLowerCase();
    final entries = _entries(widget.controller).where((entry) {
      if (filter != 'all' && entry.filterType != filter) return false;
      if (!_inPeriod(entry.date, period)) return false;
      return query.isEmpty || entry.searchText.contains(query);
    }).toList();
    final income = entries
        .where((entry) => entry.filterType == 'income')
        .fold<int>(0, (sum, entry) => sum + entry.amountCents.abs());
    final spent = entries
        .where((entry) => entry.filterType == 'expense')
        .fold<int>(0, (sum, entry) => sum + entry.amountCents.abs());

    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 112),
      children: [
        ScreenHeader(
          title: 'Activity',
          subtitle: 'Find, understand, and add transactions',
          action: IconButton.filled(
            tooltip: 'Add transaction',
            onPressed: widget.controller.accounts.isEmpty ? null : widget.onAdd,
            icon: const Icon(Icons.add),
          ),
        ),
        const SizedBox(height: 18),
        SearchBar(
          controller: search,
          hintText: 'Search description, account, or category',
          leading: const Icon(Icons.search),
          trailing: [
            if (search.text.isNotEmpty)
              IconButton(
                tooltip: 'Clear search',
                onPressed: () => setState(search.clear),
                icon: const Icon(Icons.close),
              ),
          ],
          onChanged: (_) => setState(() {}),
          elevation: const WidgetStatePropertyAll(0),
          backgroundColor: const WidgetStatePropertyAll(AppColors.surface),
          side: const WidgetStatePropertyAll(
            BorderSide(color: AppColors.border),
          ),
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: 'all', label: Text('All')),
                    ButtonSegment(value: 'expense', label: Text('Spent')),
                    ButtonSegment(value: 'income', label: Text('Income')),
                    ButtonSegment(value: 'transfer', label: Text('Moves')),
                  ],
                  selected: {filter},
                  showSelectedIcon: false,
                  onSelectionChanged: (selection) =>
                      setState(() => filter = selection.first),
                ),
              ),
            ),
            const SizedBox(width: 8),
            PopupMenuButton<String>(
              tooltip: 'Choose period',
              initialValue: period,
              onSelected: (value) => setState(() => period = value),
              itemBuilder: (_) => const [
                PopupMenuItem(value: 'all', child: Text('All time')),
                PopupMenuItem(value: 'month', child: Text('This month')),
                PopupMenuItem(value: '30', child: Text('Last 30 days')),
                PopupMenuItem(value: 'year', child: Text('This year')),
              ],
              child: Container(
                height: 48,
                padding: const EdgeInsets.symmetric(horizontal: 12),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  border: Border.all(color: AppColors.border),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.calendar_month_outlined, size: 19),
                    const SizedBox(width: 6),
                    Text(_periodLabel(period)),
                    const Icon(Icons.arrow_drop_down),
                  ],
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 14),
        SurfaceCard(
          child: Row(
            children: [
              Expanded(
                child: _ActivityMetric(
                  label: 'Money in',
                  value: money(income),
                  tone: AppColors.positive,
                ),
              ),
              Container(width: 1, height: 40, color: AppColors.border),
              const SizedBox(width: 16),
              Expanded(
                child: _ActivityMetric(
                  label: 'Money out',
                  value: money(spent),
                  tone: AppColors.negative,
                ),
              ),
            ],
          ),
        ),
        if (widget.controller.pendingCommands.isNotEmpty) ...[
          const SizedBox(height: 20),
          SectionHeader(
            title: 'Phone changes',
            subtitle: '${widget.controller.pendingCount} waiting to sync',
          ),
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
                  title: 'Nothing matches',
                  message: query.isNotEmpty
                      ? 'Try a shorter search or a wider period.'
                      : 'There are no transactions in this view yet.',
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
                      _ActivityRow(
                        entry: entries[index],
                        onTap: () => _showDetails(context, entries[index]),
                      ),
                      if (index != entries.length - 1)
                        const Divider(height: 1, indent: 62),
                    ],
                  ],
                ),
        ),
      ],
    );
  }
}

List<_ActivityEntry> _entries(AppController controller) {
  final accountNames = {
    for (final account in controller.accounts) account.id: account.name,
  };
  final categoryNames = {
    for (final category in controller.categories) category.id: category.name,
  };
  final methodNames = {
    for (final method in controller.paymentMethods) method.id: method.name,
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
      final source = accountNames[outgoing?.accountId] ?? 'Account';
      final target = accountNames[incoming?.accountId] ?? 'Account';
      final description = transaction.description;
      result.add(
        _ActivityEntry(
          title: '$source → $target',
          subtitle: description.isEmpty
              ? friendlyDate(transaction.date)
              : '$description · ${friendlyDate(transaction.date)}',
          amountCents:
              outgoing?.amountCents.abs() ?? incoming?.amountCents.abs() ?? 0,
          filterType: 'transfer',
          neutral: true,
          icon: Icons.swap_horiz,
          tone: AppColors.blue,
          date: transaction.date,
          account: '$source → $target',
          category: null,
          paymentMethod: null,
          notes: transaction.notes,
        ),
      );
      continue;
    }
    final account = accountNames[transaction.accountId] ?? 'Account';
    final category = categoryNames[transaction.categoryId];
    final method = methodNames[transaction.paymentMethodId];
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
            '$account · ${category ?? friendlyDate(transaction.date)}'
            '${category == null ? '' : ' · ${friendlyDate(transaction.date)}'}',
        amountCents: transaction.amountCents,
        filterType: filterType,
        neutral: false,
        icon: transaction.isIncome ? Icons.north_east : Icons.south_west,
        tone: transaction.isIncome ? AppColors.positive : AppColors.negative,
        date: transaction.date,
        account: account,
        category: category,
        paymentMethod: method,
        notes: transaction.notes,
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
    required this.date,
    required this.account,
    required this.category,
    required this.paymentMethod,
    required this.notes,
  });

  final String title;
  final String subtitle;
  final int amountCents;
  final String filterType;
  final bool neutral;
  final IconData icon;
  final Color tone;
  final String date;
  final String account;
  final String? category;
  final String? paymentMethod;
  final String? notes;

  String get searchText =>
      '$title $subtitle $account ${category ?? ''} ${paymentMethod ?? ''} ${notes ?? ''}'
          .toLowerCase();
}

class _ActivityRow extends StatelessWidget {
  const _ActivityRow({required this.entry, required this.onTap});

  final _ActivityEntry entry;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => ListTile(
    onTap: onTap,
    contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 3),
    leading: Container(
      width: 40,
      height: 40,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: entry.tone.withValues(alpha: .10),
        borderRadius: BorderRadius.circular(12),
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

class _ActivityMetric extends StatelessWidget {
  const _ActivityMetric({
    required this.label,
    required this.value,
    required this.tone,
  });

  final String label;
  final String value;
  final Color tone;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(label, style: Theme.of(context).textTheme.bodySmall),
      const SizedBox(height: 5),
      FittedBox(
        fit: BoxFit.scaleDown,
        alignment: Alignment.centerLeft,
        child: Text(
          value,
          style: Theme.of(context).textTheme.titleLarge?.copyWith(color: tone),
        ),
      ),
    ],
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

bool _inPeriod(String rawDate, String period) {
  if (period == 'all') return true;
  final value = DateTime.tryParse(rawDate);
  if (value == null) return false;
  final now = DateTime.now();
  return switch (period) {
    'month' => value.year == now.year && value.month == now.month,
    'year' => value.year == now.year,
    '30' => !value.isBefore(
      DateTime(now.year, now.month, now.day).subtract(const Duration(days: 29)),
    ),
    _ => true,
  };
}

String _periodLabel(String period) => switch (period) {
  'month' => 'Month',
  '30' => '30 days',
  'year' => 'Year',
  _ => 'Any time',
};

Future<void> _showDetails(BuildContext context, _ActivityEntry entry) async {
  await showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    useSafeArea: true,
    isScrollControlled: true,
    builder: (context) => Padding(
      padding: const EdgeInsets.fromLTRB(20, 4, 20, 28),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 46,
                height: 46,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: entry.tone.withValues(alpha: .10),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(entry.icon, color: entry.tone),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      entry.title,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    Text(
                      prettyType(entry.filterType),
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
              AmountText(
                entry.amountCents,
                neutral: entry.neutral,
                emphasized: true,
              ),
            ],
          ),
          const SizedBox(height: 22),
          _DetailRow(
            icon: Icons.calendar_today_outlined,
            label: 'Date',
            value: friendlyDate(entry.date),
          ),
          _DetailRow(
            icon: Icons.account_balance_wallet_outlined,
            label: 'Account',
            value: entry.account,
          ),
          if (entry.category != null)
            _DetailRow(
              icon: Icons.sell_outlined,
              label: 'Category',
              value: entry.category!,
            ),
          if (entry.paymentMethod != null)
            _DetailRow(
              icon: Icons.credit_card_outlined,
              label: 'Paid with',
              value: entry.paymentMethod!,
            ),
          if (entry.notes != null && entry.notes!.trim().isNotEmpty)
            _DetailRow(
              icon: Icons.notes_outlined,
              label: 'Note',
              value: entry.notes!,
            ),
        ],
      ),
    ),
  );
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 9),
    child: Row(
      children: [
        Icon(icon, color: AppColors.muted, size: 20),
        const SizedBox(width: 12),
        SizedBox(
          width: 78,
          child: Text(label, style: Theme.of(context).textTheme.bodySmall),
        ),
        Expanded(
          child: Text(
            value,
            textAlign: TextAlign.right,
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
        ),
      ],
    ),
  );
}
