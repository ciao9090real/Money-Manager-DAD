import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../models/finance_models.dart';
import '../theme/app_theme.dart';
import 'goal_contribution_sheet.dart';
import 'widgets.dart';

class GoalsPage extends StatelessWidget {
  const GoalsPage({super.key, required this.controller});

  final AppController controller;

  Future<void> _contribute(BuildContext context, SavingsGoalRecord goal) async {
    final added = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: Theme.of(context).scaffoldBackgroundColor,
      builder: (_) => GoalContributionSheet(controller: controller, goal: goal),
    );
    if (added == true && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            controller.syncError == null
                ? 'Contribution recorded'
                : 'Saved on this phone and waiting to sync',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Savings goals')),
      body: SafeArea(
        top: false,
        child: AnimatedBuilder(
          animation: controller,
          builder: (context, _) {
            final progress = controller.goalProgresses;
            return ListView(
              padding: const EdgeInsets.fromLTRB(18, 8, 18, 32),
              children: [
                const ScreenHeader(
                  title: 'Savings goals',
                  subtitle: 'Turn long-term plans into visible progress',
                ),
                const SizedBox(height: 18),
                if (progress.isEmpty)
                  const SurfaceCard(
                    child: EmptyState(
                      icon: Icons.flag_outlined,
                      title: 'No savings goals yet',
                      message:
                          'Create a target on the desktop, then sync it to this phone.',
                    ),
                  )
                else
                  for (var index = 0; index < progress.length; index++) ...[
                    _GoalCard(
                      progress: progress[index],
                      linkedAccountName: _linkedAccountName(
                        progress[index].goal.linkedAccountId,
                      ),
                      onContribute: progress[index].goal.linkedAccountId == null
                          ? () => _contribute(context, progress[index].goal)
                          : null,
                    ),
                    if (index != progress.length - 1)
                      const SizedBox(height: 11),
                  ],
                const SizedBox(height: 16),
                Text(
                  'Create goals, change targets, and link accounts on the desktop. Manual contributions can be recorded here.',
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

  String? _linkedAccountName(String? accountId) {
    if (accountId == null) return null;
    for (final account in controller.accounts) {
      if (account.id == accountId) return account.name;
    }
    return 'Unavailable account';
  }
}

class _GoalCard extends StatelessWidget {
  const _GoalCard({
    required this.progress,
    required this.linkedAccountName,
    this.onContribute,
  });

  final GoalProgress progress;
  final String? linkedAccountName;
  final VoidCallback? onContribute;

  @override
  Widget build(BuildContext context) {
    final percent = progress.percentComplete;
    final complete =
        progress.currentAmountCents >= progress.goal.targetAmountCents;
    final tone = complete
        ? AppColors.positive
        : progress.onTrack == false
        ? AppColors.warning
        : AppColors.primary;
    return SurfaceCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 38,
                height: 38,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: tone.withValues(alpha: .10),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  complete ? Icons.flag : Icons.flag_outlined,
                  color: tone,
                  size: 20,
                ),
              ),
              const SizedBox(width: 11),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      progress.goal.name,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 5),
                    _GoalStatusPill(progress: progress, complete: complete),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          FinanceProgressBar(percent: percent, tone: tone),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: Text(
                  money(progress.currentAmountCents),
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              const SizedBox(width: 10),
              Text(
                'of ${money(progress.goal.targetAmountCents)}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
          const SizedBox(height: 11),
          Wrap(
            spacing: 7,
            runSpacing: 7,
            children: [
              Pill(
                linkedAccountName == null
                    ? 'Manual contributions'
                    : linkedAccountName!,
                tone: 'info',
              ),
              if (progress.goal.targetDate != null)
                Pill('Due ${friendlyDate(progress.goal.targetDate!)}'),
            ],
          ),
          if (progress.requiredMonthlyContributionCents != null) ...[
            const SizedBox(height: 10),
            Text(
              progress.requiredMonthlyContributionCents == 0
                  ? 'Target amount reached'
                  : '${money(progress.requiredMonthlyContributionCents!)} per month needed',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
          if (onContribute != null) ...[
            const SizedBox(height: 14),
            SizedBox(
              width: double.infinity,
              child: FilledButton.tonalIcon(
                onPressed: onContribute,
                icon: const Icon(Icons.add, size: 18),
                label: const Text('Add contribution'),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _GoalStatusPill extends StatelessWidget {
  const _GoalStatusPill({required this.progress, required this.complete});

  final GoalProgress progress;
  final bool complete;

  @override
  Widget build(BuildContext context) {
    if (complete) return const Pill('Complete', tone: 'positive');
    return switch (progress.onTrack) {
      true => const Pill('On track', tone: 'positive'),
      false => const Pill('Behind plan', tone: 'warning'),
      null => const Pill('No deadline'),
    };
  }
}
