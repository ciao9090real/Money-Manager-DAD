import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../models/finance_models.dart';
import '../theme/app_theme.dart';
import 'widgets.dart';

class ImportInboxPage extends StatelessWidget {
  const ImportInboxPage({super.key, required this.controller});

  final AppController controller;

  Future<void> _sync(BuildContext context) async {
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
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        final open = controller.openImportBatches;
        final history = controller.importBatches
            .where((batch) => !batch.isOpen)
            .toList(growable: false);
        return Scaffold(
          appBar: AppBar(
            title: const Text('Import inbox'),
            actions: [
              IconButton(
                tooltip: 'Sync imports',
                onPressed: controller.isPaired && !controller.isSyncing
                    ? () => _sync(context)
                    : null,
                icon: controller.isSyncing
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.sync),
              ),
            ],
          ),
          body: RefreshIndicator(
            onRefresh: () => _sync(context),
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(18, 8, 18, 36),
              children: [
                _InboxHero(
                  batches: open.length,
                  rows: controller.importAttentionCount,
                ),
                const SizedBox(height: 24),
                SectionHeader(
                  title: 'Waiting for you',
                  subtitle: open.isEmpty
                      ? 'Nothing needs a decision'
                      : 'Review on your phone; posting still happens on desktop',
                ),
                const SizedBox(height: 9),
                if (open.isEmpty)
                  const SurfaceCard(
                    child: EmptyState(
                      icon: Icons.mark_email_read_outlined,
                      title: 'Inbox zero—nice',
                      message:
                          'New files mapped on the desktop will appear here after sync.',
                    ),
                  )
                else
                  for (var index = 0; index < open.length; index++) ...[
                    _BatchCard(
                      batch: open[index],
                      rows: controller.rowsForImport(open[index].id),
                      pending: controller.importBatchHasPendingPost(
                        open[index].id,
                      ),
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => ImportBatchPage(
                            controller: controller,
                            batchId: open[index].id,
                          ),
                        ),
                      ),
                    ),
                    if (index != open.length - 1) const SizedBox(height: 10),
                  ],
                if (history.isNotEmpty) ...[
                  const SizedBox(height: 24),
                  const SectionHeader(
                    title: 'Import history',
                    subtitle: 'A clear trail of completed and cancelled files',
                  ),
                  const SizedBox(height: 9),
                  SurfaceCard(
                    padding: EdgeInsets.zero,
                    child: Column(
                      children: [
                        for (
                          var index = 0;
                          index < history.length;
                          index++
                        ) ...[
                          ListTile(
                            onTap: () => Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) => ImportBatchPage(
                                  controller: controller,
                                  batchId: history[index].id,
                                ),
                              ),
                            ),
                            leading: Icon(
                              history[index].status == 'posted'
                                  ? Icons.task_alt
                                  : Icons.do_not_disturb_alt_outlined,
                              color: history[index].status == 'posted'
                                  ? AppColors.positive
                                  : AppColors.muted,
                            ),
                            title: Text(
                              history[index].sourceName,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            subtitle: Text(
                              history[index].status == 'posted'
                                  ? 'Reconciled'
                                  : 'Cancelled',
                            ),
                            trailing: const Icon(Icons.chevron_right),
                          ),
                          if (index != history.length - 1)
                            const Divider(height: 1, indent: 56),
                        ],
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}

class ImportBatchPage extends StatefulWidget {
  const ImportBatchPage({
    super.key,
    required this.controller,
    required this.batchId,
  });

  final AppController controller;
  final String batchId;

  @override
  State<ImportBatchPage> createState() => _ImportBatchPageState();
}

class _ImportBatchPageState extends State<ImportBatchPage> {
  bool includeUncategorized = false;

  Future<void> _run(Future<void> Function() action, String success) async {
    try {
      await action();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            widget.controller.pendingCount == 0
                ? success
                : '$success It will finish when the desktop reconnects.',
          ),
        ),
      );
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    }
  }

  Future<void> _rowActions(ImportRowRecord row) async {
    if (widget.controller.importRowHasPendingChange(row.id)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('This row already has a queued change.')),
      );
      return;
    }
    final categories = widget.controller.categories
        .where(
          (category) =>
              category.isActive && category.type == row.transactionType,
        )
        .toList(growable: false);
    final action = await showModalBottomSheet<_RowAction>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(18, 0, 18, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                row.description.isEmpty
                    ? 'Source row ${row.sourceRowNumber}'
                    : row.description,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              if (row.issueText != null) ...[
                const SizedBox(height: 7),
                Text(
                  row.issueText!,
                  style: const TextStyle(color: AppColors.negative),
                ),
              ],
              if (row.canCategorize && !row.isResolved) ...[
                const SizedBox(height: 20),
                Text(
                  'Choose ${prettyType(row.transactionType!)} category',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                if (categories.isEmpty)
                  Text(
                    'Create a matching category on the desktop first.',
                    style: Theme.of(context).textTheme.bodySmall,
                  )
                else
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxHeight: 260),
                    child: ListView(
                      shrinkWrap: true,
                      children: [
                        for (final category in categories)
                          ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading: const Icon(Icons.sell_outlined),
                            title: Text(category.name),
                            trailing: row.categoryId == category.id
                                ? const Icon(
                                    Icons.check,
                                    color: AppColors.positive,
                                  )
                                : null,
                            onTap: () => Navigator.pop(
                              context,
                              _RowAction.category(category.id),
                            ),
                          ),
                      ],
                    ),
                  ),
              ],
              const SizedBox(height: 10),
              if (!row.isResolved)
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: () =>
                        Navigator.pop(context, const _RowAction.ignore()),
                    icon: const Icon(Icons.visibility_off_outlined),
                    label: const Text('Ignore this row'),
                  ),
                ),
              if (row.status == 'ignored')
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.tonalIcon(
                    onPressed: () =>
                        Navigator.pop(context, const _RowAction.restore()),
                    icon: const Icon(Icons.restore),
                    label: const Text('Restore this row'),
                  ),
                ),
              if (row.isResolved && row.status != 'ignored')
                Text(
                  'This row already has a final outcome.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
            ],
          ),
        ),
      ),
    );
    if (action == null) return;
    switch (action.kind) {
      case 'category':
        await _run(
          () => widget.controller.categorizeImportRows([
            row.id,
          ], action.categoryId!),
          'Category updated.',
        );
      case 'ignore':
        await _run(
          () => widget.controller.ignoreImportRows([row.id]),
          'Row ignored.',
        );
      case 'restore':
        await _run(
          () => widget.controller.restoreImportRows([row.id]),
          'Row restored.',
        );
    }
  }

  Future<void> _post(
    ImportBatchRecord batch,
    List<ImportRowRecord> rows,
  ) async {
    final count = rows
        .where(
          (row) => row.isReady || (includeUncategorized && row.needsCategory),
        )
        .length;
    if (count == 0) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Post $count imported ${count == 1 ? 'row' : 'rows'}?'),
        content: const Text(
          'The desktop creates a recovery point first, then posts the entire ready set atomically.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Not yet'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Post rows'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await _run(
      () => widget.controller.postImportBatch(
        batch.id,
        includeUncategorized: includeUncategorized,
      ),
      'Import posted.',
    );
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.controller,
      builder: (context, _) {
        final batch = widget.controller.importBatches
            .where((item) => item.id == widget.batchId)
            .firstOrNull;
        if (batch == null) {
          return const Scaffold(
            body: SafeArea(
              child: EmptyState(
                icon: Icons.inbox_outlined,
                title: 'Import unavailable',
                message: 'Sync with the desktop to refresh this batch.',
              ),
            ),
          );
        }
        final rows = widget.controller.rowsForImport(batch.id);
        final summary = _ImportSummary(rows);
        final postable =
            summary.ready + (includeUncategorized ? summary.needsCategory : 0);
        final postPending = widget.controller.importBatchHasPendingPost(
          batch.id,
        );
        return Scaffold(
          appBar: AppBar(title: Text(batch.sourceName)),
          body: ListView(
            padding: const EdgeInsets.fromLTRB(18, 8, 18, 132),
            children: [
              _BatchSummaryCard(batch: batch, summary: summary),
              const SizedBox(height: 22),
              SectionHeader(
                title: 'Source rows',
                subtitle: batch.isOpen
                    ? 'Tap a row to decide its outcome'
                    : 'This import is ${prettyType(batch.status).toLowerCase()}',
                trailing: Pill(
                  '${summary.resolved}/${rows.length} resolved',
                  tone: summary.resolved == rows.length ? 'positive' : 'info',
                ),
              ),
              const SizedBox(height: 9),
              SurfaceCard(
                padding: EdgeInsets.zero,
                child: Column(
                  children: [
                    for (var index = 0; index < rows.length; index++) ...[
                      _ImportRowTile(
                        row: rows[index],
                        category: rows[index].categoryId == null
                            ? null
                            : widget.controller.categoryName(
                                rows[index].categoryId!,
                              ),
                        pending: widget.controller.importRowHasPendingChange(
                          rows[index].id,
                        ),
                        onTap: () => _rowActions(rows[index]),
                      ),
                      if (index != rows.length - 1)
                        const Divider(height: 1, indent: 58),
                    ],
                  ],
                ),
              ),
              if (batch.isOpen && summary.needsCategory > 0) ...[
                const SizedBox(height: 14),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  value: includeUncategorized,
                  onChanged: postPending
                      ? null
                      : (value) => setState(() => includeUncategorized = value),
                  title: const Text('Post without categories'),
                  subtitle: Text(
                    '${summary.needsCategory} ${summary.needsCategory == 1 ? 'row' : 'rows'} will remain uncategorized',
                  ),
                ),
              ],
            ],
          ),
          bottomNavigationBar: batch.isOpen
              ? SafeArea(
                  top: false,
                  child: Container(
                    padding: const EdgeInsets.fromLTRB(18, 12, 18, 14),
                    decoration: const BoxDecoration(
                      color: AppColors.surface,
                      border: Border(top: BorderSide(color: AppColors.border)),
                    ),
                    child: FilledButton.icon(
                      onPressed: postable > 0 && !postPending
                          ? () => _post(batch, rows)
                          : null,
                      icon: postPending
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Icon(Icons.publish_outlined),
                      label: Text(
                        postPending
                            ? 'Waiting for desktop'
                            : 'Post $postable ready ${postable == 1 ? 'row' : 'rows'}',
                      ),
                    ),
                  ),
                )
              : null,
        );
      },
    );
  }
}

class _RowAction {
  const _RowAction.ignore() : kind = 'ignore', categoryId = null;
  const _RowAction.restore() : kind = 'restore', categoryId = null;
  const _RowAction.category(this.categoryId) : kind = 'category';

  final String kind;
  final String? categoryId;
}

class _ImportSummary {
  _ImportSummary(List<ImportRowRecord> rows)
    : ready = rows.where((row) => row.status == 'ready').length,
      needsCategory = rows
          .where((row) => row.status == 'needs_category')
          .length,
      errors = rows.where((row) => row.status == 'error').length,
      duplicates = rows.where((row) => row.status == 'duplicate').length,
      ignored = rows.where((row) => row.status == 'ignored').length,
      posted = rows.where((row) => row.status == 'posted').length;

  final int ready;
  final int needsCategory;
  final int errors;
  final int duplicates;
  final int ignored;
  final int posted;

  int get resolved => duplicates + ignored + posted;
}

class _InboxHero extends StatelessWidget {
  const _InboxHero({required this.batches, required this.rows});

  final int batches;
  final int rows;

  @override
  Widget build(BuildContext context) {
    final quiet = rows == 0;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: quiet ? AppColors.primarySoft : AppColors.primary,
        borderRadius: BorderRadius.circular(22),
        boxShadow: const [
          BoxShadow(
            color: Color(0x16000000),
            blurRadius: 18,
            offset: Offset(0, 5),
          ),
        ],
      ),
      child: Row(
        children: [
          _InboxBuddy(awake: !quiet),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  quiet ? 'All tucked away' : '$rows rows are peeking',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    color: quiet ? AppColors.ink : Colors.white,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  quiet
                      ? 'Your import inbox has nothing unresolved.'
                      : '$batches ${batches == 1 ? 'file needs' : 'files need'} a quick decision.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: quiet
                        ? AppColors.muted
                        : Colors.white.withValues(alpha: .78),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _InboxBuddy extends StatelessWidget {
  const _InboxBuddy({required this.awake});

  final bool awake;

  @override
  Widget build(BuildContext context) {
    final reduceMotion = MediaQuery.disableAnimationsOf(context);
    return TweenAnimationBuilder<double>(
      duration: reduceMotion
          ? Duration.zero
          : const Duration(milliseconds: 420),
      curve: Curves.elasticOut,
      tween: Tween(begin: 0, end: awake ? 1 : 0),
      builder: (context, value, child) =>
          Transform.rotate(angle: awake ? (value - 1) * -.08 : 0, child: child),
      child: Container(
        width: 62,
        height: 56,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            Positioned(
              left: 12,
              right: 12,
              top: -7,
              height: 24,
              child: Container(
                decoration: BoxDecoration(
                  color: const Color(0xFFFFE4A8),
                  borderRadius: BorderRadius.circular(5),
                ),
              ),
            ),
            Positioned(left: 15, top: 23, child: _BuddyEye(open: awake)),
            Positioned(right: 15, top: 23, child: _BuddyEye(open: awake)),
            Positioned(
              left: 23,
              top: 38,
              child: Container(
                width: 16,
                height: 2,
                decoration: BoxDecoration(
                  color: AppColors.ink,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BuddyEye extends StatelessWidget {
  const _BuddyEye({required this.open});

  final bool open;

  @override
  Widget build(BuildContext context) => AnimatedContainer(
    duration: MediaQuery.disableAnimationsOf(context)
        ? Duration.zero
        : const Duration(milliseconds: 220),
    width: 7,
    height: open ? 9 : 2,
    decoration: BoxDecoration(
      color: AppColors.ink,
      borderRadius: BorderRadius.circular(6),
    ),
  );
}

class _BatchCard extends StatelessWidget {
  const _BatchCard({
    required this.batch,
    required this.rows,
    required this.pending,
    required this.onTap,
  });

  final ImportBatchRecord batch;
  final List<ImportRowRecord> rows;
  final bool pending;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final summary = _ImportSummary(rows);
    final attention = summary.needsCategory + summary.errors;
    return SurfaceCard(
      padding: EdgeInsets.zero,
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 46,
                height: 46,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: attention > 0
                      ? const Color(0xFFF8F0DF)
                      : AppColors.primarySoft,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(
                  batch.isStatement
                      ? Icons.account_balance_outlined
                      : Icons.table_rows_outlined,
                  color: attention > 0 ? AppColors.warning : AppColors.primary,
                ),
              ),
              const SizedBox(width: 13),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      batch.sourceName,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      pending
                          ? 'Post queued for desktop'
                          : attention > 0
                          ? '$attention need a decision · ${summary.ready} ready'
                          : '${summary.ready} ready to post',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              pending
                  ? const Pill('Queued', tone: 'warning')
                  : const Icon(Icons.chevron_right),
            ],
          ),
        ),
      ),
    );
  }
}

class _BatchSummaryCard extends StatelessWidget {
  const _BatchSummaryCard({required this.batch, required this.summary});

  final ImportBatchRecord batch;
  final _ImportSummary summary;

  @override
  Widget build(BuildContext context) => SurfaceCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              batch.isStatement
                  ? Icons.account_balance_outlined
                  : Icons.table_rows_outlined,
              color: AppColors.primary,
            ),
            const SizedBox(width: 9),
            Expanded(
              child: Text(
                batch.isStatement ? 'Bank statement' : 'Money Manager CSV',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            Pill(
              prettyType(batch.status),
              tone: batch.status == 'posted' ? 'positive' : 'info',
            ),
          ],
        ),
        if (batch.periodStart != null && batch.periodEnd != null) ...[
          const SizedBox(height: 8),
          Text(
            '${friendlyDate(batch.periodStart!)} – ${friendlyDate(batch.periodEnd!)}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
        const SizedBox(height: 18),
        Row(
          children: [
            _MiniMetric('Ready', summary.ready, AppColors.positive),
            _MiniMetric('Category', summary.needsCategory, AppColors.warning),
            _MiniMetric('Issues', summary.errors, AppColors.negative),
          ],
        ),
      ],
    ),
  );
}

class _MiniMetric extends StatelessWidget {
  const _MiniMetric(this.label, this.value, this.color);

  final String label;
  final int value;
  final Color color;

  @override
  Widget build(BuildContext context) => Expanded(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: Theme.of(context).textTheme.bodySmall),
        const SizedBox(height: 3),
        Text(
          '$value',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(color: color),
        ),
      ],
    ),
  );
}

class _ImportRowTile extends StatelessWidget {
  const _ImportRowTile({
    required this.row,
    required this.category,
    required this.pending,
    required this.onTap,
  });

  final ImportRowRecord row;
  final String? category;
  final bool pending;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tone = switch (row.status) {
      'ready' || 'posted' => 'positive',
      'needs_category' => 'warning',
      'error' => 'negative',
      _ => 'neutral',
    };
    final title = row.description.isNotEmpty
        ? row.description
        : row.issueText ?? 'Source row ${row.sourceRowNumber}';
    final subtitle = [
      if (row.date != null) friendlyDate(row.date!),
      ?category,
      ?row.issueText,
    ].join(' · ');
    final amount = row.amountCents == null
        ? null
        : row.transactionType == 'expense'
        ? -row.amountCents!
        : row.amountCents!;
    return ListTile(
      onTap: onTap,
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
      leading: Container(
        width: 38,
        height: 38,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: _statusColor(tone).withValues(alpha: .11),
          borderRadius: BorderRadius.circular(11),
        ),
        child: Icon(
          _statusIcon(row.status),
          color: _statusColor(tone),
          size: 20,
        ),
      ),
      title: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (subtitle.isNotEmpty)
            Text(subtitle, maxLines: 1, overflow: TextOverflow.ellipsis),
          const SizedBox(height: 4),
          Pill(
            pending ? 'Change queued' : prettyType(row.status),
            tone: pending ? 'warning' : tone,
          ),
        ],
      ),
      trailing: amount == null
          ? const Icon(Icons.chevron_right)
          : Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                AmountText(amount, neutral: false),
                const SizedBox(height: 3),
                const Icon(Icons.chevron_right, size: 18),
              ],
            ),
    );
  }
}

Color _statusColor(String tone) => switch (tone) {
  'positive' => AppColors.positive,
  'warning' => AppColors.warning,
  'negative' => AppColors.negative,
  _ => AppColors.muted,
};

IconData _statusIcon(String status) => switch (status) {
  'ready' => Icons.check_circle_outline,
  'posted' => Icons.task_alt,
  'needs_category' => Icons.sell_outlined,
  'error' => Icons.error_outline,
  'duplicate' => Icons.content_copy_outlined,
  'ignored' => Icons.visibility_off_outlined,
  _ => Icons.receipt_long_outlined,
};
