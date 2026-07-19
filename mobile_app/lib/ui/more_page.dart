import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../theme/app_theme.dart';
import 'widgets.dart';

class MorePage extends StatelessWidget {
  const MorePage({super.key, required this.controller, required this.onPair});

  final AppController controller;
  final VoidCallback onPair;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 108),
      children: [
        const ScreenHeader(
          title: 'Portfolio & sync',
          subtitle: 'Investments, loans, and this phone connection',
        ),
        const SizedBox(height: 22),
        const SectionHeader(title: 'Investments'),
        const SizedBox(height: 9),
        SurfaceCard(
          padding: EdgeInsets.zero,
          child: controller.investments.isEmpty
              ? const EmptyState(
                  icon: Icons.show_chart,
                  title: 'No investments',
                  message:
                      'Tracked portfolios from the desktop will appear here.',
                )
              : Column(
                  children: [
                    for (
                      var index = 0;
                      index < controller.investments.length;
                      index++
                    ) ...[
                      _PortfolioRow(
                        icon: Icons.show_chart,
                        title:
                            '${controller.investments[index].payload['name'] ?? 'Investment'}',
                        subtitle: prettyType(
                          '${controller.investments[index].payload['kind'] ?? 'other'}',
                        ),
                        amount: controller.balanceFor(
                          '${controller.investments[index].payload['account_id'] ?? ''}',
                        ),
                      ),
                      if (index != controller.investments.length - 1)
                        const Divider(height: 1, indent: 58),
                    ],
                  ],
                ),
        ),
        const SizedBox(height: 22),
        const SectionHeader(title: 'Loans & lending'),
        const SizedBox(height: 9),
        SurfaceCard(
          padding: EdgeInsets.zero,
          child: controller.loans.isEmpty
              ? const EmptyState(
                  icon: Icons.account_balance_outlined,
                  title: 'No loans',
                  message:
                      'Borrowed and lent balances from the desktop will appear here.',
                )
              : Column(
                  children: [
                    for (
                      var index = 0;
                      index < controller.loans.length;
                      index++
                    ) ...[
                      _PortfolioRow(
                        icon: Icons.account_balance_outlined,
                        title:
                            '${controller.loans[index].payload['name'] ?? 'Loan'}',
                        subtitle: prettyType(
                          '${controller.loans[index].payload['direction'] ?? controller.loans[index].payload['kind'] ?? 'loan'}',
                        ),
                        amount: controller.balanceFor(
                          '${controller.loans[index].payload['account_id'] ?? ''}',
                        ),
                      ),
                      if (index != controller.loans.length - 1)
                        const Divider(height: 1, indent: 58),
                    ],
                  ],
                ),
        ),
        const SizedBox(height: 22),
        const SectionHeader(title: 'Desktop connection'),
        const SizedBox(height: 9),
        SurfaceCard(
          child: controller.isPaired
              ? _ConnectedState(controller: controller)
              : _DisconnectedState(onPair: onPair),
        ),
        const SizedBox(height: 16),
        SurfaceCard(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.shield_outlined, color: AppColors.primary),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Local and private',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 5),
                    Text(
                      'No cloud account is used. This phone stores an offline SQLite cache and syncs only with your paired desktop over local Wi-Fi.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _PortfolioRow extends StatelessWidget {
  const _PortfolioRow({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.amount,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final int amount;

  @override
  Widget build(BuildContext context) => ListTile(
    leading: Container(
      width: 38,
      height: 38,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: AppColors.blueSoft,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Icon(icon, color: AppColors.blue, size: 20),
    ),
    title: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis),
    subtitle: Text(subtitle),
    trailing: AmountText(amount, neutral: true, emphasized: true),
  );
}

class _ConnectedState extends StatelessWidget {
  const _ConnectedState({required this.controller});

  final AppController controller;

  Future<void> _sync(BuildContext context) async {
    try {
      await controller.syncNow();
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Phone is up to date')));
      }
    } catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    }
  }

  Future<void> _unpair(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Disconnect this phone?'),
        content: const Text(
          'The offline cache and queued phone changes will be removed from this phone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Disconnect'),
          ),
        ],
      ),
    );
    if (confirmed == true) await controller.unpair();
  }

  @override
  Widget build(BuildContext context) {
    final fingerprint = controller.credentials!.fingerprint;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.verified_outlined, color: AppColors.positive),
            const SizedBox(width: 9),
            Expanded(
              child: Text(
                'Paired desktop',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            const Pill('Connected', tone: 'positive'),
          ],
        ),
        const SizedBox(height: 12),
        Text(
          controller.credentials!.url,
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const SizedBox(height: 4),
        Text(
          'Fingerprint ${fingerprint.substring(0, 12).toUpperCase()}',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        if (controller.lastSyncAt != null) ...[
          const SizedBox(height: 4),
          Text(
            'Last sync ${_lastSync(controller.lastSyncAt!)}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
        if (controller.syncError != null) ...[
          const SizedBox(height: 10),
          Text(
            controller.syncError!,
            style: const TextStyle(color: AppColors.negative, fontSize: 12),
          ),
        ],
        const SizedBox(height: 15),
        Row(
          children: [
            Expanded(
              child: FilledButton.icon(
                onPressed: controller.isSyncing ? null : () => _sync(context),
                icon: controller.isSyncing
                    ? const SizedBox(
                        width: 17,
                        height: 17,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.sync, size: 18),
                label: Text(controller.isSyncing ? 'Syncing' : 'Sync now'),
              ),
            ),
            const SizedBox(width: 10),
            IconButton.outlined(
              tooltip: 'Disconnect phone',
              onPressed: () => _unpair(context),
              icon: const Icon(Icons.link_off),
            ),
          ],
        ),
      ],
    );
  }

  String _lastSync(String value) {
    final parsed = DateTime.tryParse(value)?.toLocal();
    if (parsed == null) return value;
    final difference = DateTime.now().difference(parsed);
    if (difference.inMinutes < 1) return 'just now';
    if (difference.inHours < 1) return '${difference.inMinutes} min ago';
    return friendlyDate(parsed.toIso8601String());
  }
}

class _DisconnectedState extends StatelessWidget {
  const _DisconnectedState({required this.onPair});

  final VoidCallback onPair;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Row(
        children: [
          const Icon(Icons.phonelink_erase_outlined, color: AppColors.muted),
          const SizedBox(width: 9),
          Text('Not paired', style: Theme.of(context).textTheme.titleMedium),
        ],
      ),
      const SizedBox(height: 7),
      Text(
        'Start phone sync in desktop Settings, then scan its QR code.',
        style: Theme.of(context).textTheme.bodySmall,
      ),
      const SizedBox(height: 14),
      FilledButton.icon(
        onPressed: onPair,
        icon: const Icon(Icons.qr_code_scanner, size: 18),
        label: const Text('Scan desktop QR'),
      ),
    ],
  );
}
