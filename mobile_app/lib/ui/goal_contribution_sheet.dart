import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';

import '../app_controller.dart';
import '../models/finance_models.dart';
import '../theme/app_theme.dart';
import 'widgets.dart';

class GoalContributionSheet extends StatefulWidget {
  const GoalContributionSheet({
    super.key,
    required this.controller,
    required this.goal,
  });

  final AppController controller;
  final SavingsGoalRecord goal;

  @override
  State<GoalContributionSheet> createState() => _GoalContributionSheetState();
}

class _GoalContributionSheetState extends State<GoalContributionSheet> {
  final amount = TextEditingController();
  final notes = TextEditingController();
  final formKey = GlobalKey<FormState>();
  late DateTime date;
  String? sourceAccountId;
  String? targetAccountId;
  bool saving = false;
  String? error;

  @override
  void initState() {
    super.initState();
    date = DateTime.now();
    final accounts = widget.controller.accounts;
    if (accounts.isNotEmpty) sourceAccountId = accounts.first.id;
    if (accounts.length > 1) targetAccountId = accounts[1].id;
  }

  @override
  void dispose() {
    amount.dispose();
    notes.dispose();
    super.dispose();
  }

  Future<void> _chooseDate() async {
    final chosen = await showDatePicker(
      context: context,
      initialDate: date,
      firstDate: DateTime(2000),
      lastDate: DateTime.now(),
      helpText: 'Contribution date',
    );
    if (chosen != null) setState(() => date = chosen);
  }

  void _chooseSource(String? value) {
    if (value == null) return;
    setState(() {
      sourceAccountId = value;
      if (targetAccountId == value) {
        targetAccountId = widget.controller.accounts
            .where((account) => account.id != value)
            .first
            .id;
      }
    });
  }

  Future<void> _save() async {
    if (!formKey.currentState!.validate()) return;
    final cents = _parseCents(amount.text)!;
    setState(() {
      saving = true;
      error = null;
    });
    try {
      await widget.controller.queueGoalContribution(
        goalId: widget.goal.id,
        sourceAccountId: sourceAccountId!,
        targetAccountId: targetAccountId!,
        amountCents: cents,
        date: DateFormat('yyyy-MM-dd').format(date),
        notes: notes.text.trim().isEmpty ? null : notes.text.trim(),
      );
      if (mounted) Navigator.pop(context, true);
    } catch (exception) {
      if (!mounted) return;
      setState(() {
        saving = false;
        error = '$exception';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final accounts = widget.controller.accounts;
    if (accounts.length < 2) {
      return SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
          child: EmptyState(
            icon: Icons.account_balance_wallet_outlined,
            title: 'Two accounts are needed',
            message:
                'A manual contribution is recorded as a transfer between two accounts. Add another account on the desktop first.',
            action: FilledButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Close'),
            ),
          ),
        ),
      );
    }
    final targetOptions = accounts
        .where((account) => account.id != sourceAccountId)
        .toList();
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
          child: Form(
            key: formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Center(
                  child: Container(
                    width: 42,
                    height: 4,
                    decoration: BoxDecoration(
                      color: Theme.of(context).dividerColor,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
                const SizedBox(height: 18),
                Text(
                  'Contribute to ${widget.goal.name}',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 6),
                Text(
                  'This records a transfer and counts its incoming side toward the goal.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  key: ValueKey('source-$sourceAccountId'),
                  initialValue: sourceAccountId,
                  decoration: const InputDecoration(labelText: 'From account'),
                  items: accounts.map(_accountItem).toList(),
                  onChanged: _chooseSource,
                  validator: (value) =>
                      value == null ? 'Choose an account' : null,
                ),
                const SizedBox(height: 13),
                DropdownButtonFormField<String>(
                  key: ValueKey('target-$sourceAccountId-$targetAccountId'),
                  initialValue: targetAccountId,
                  decoration: const InputDecoration(labelText: 'To account'),
                  items: targetOptions.map(_accountItem).toList(),
                  onChanged: (value) => setState(() => targetAccountId = value),
                  validator: (value) =>
                      value == null ? 'Choose a different account' : null,
                ),
                const SizedBox(height: 13),
                TextFormField(
                  controller: amount,
                  autofocus: true,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  inputFormatters: [
                    FilteringTextInputFormatter.allow(RegExp(r'[0-9,.]')),
                  ],
                  decoration: const InputDecoration(
                    labelText: 'Amount',
                    prefixText: '€ ',
                  ),
                  validator: (value) {
                    final cents = _parseCents(value ?? '');
                    return cents == null || cents <= 0
                        ? 'Enter an amount greater than zero'
                        : null;
                  },
                ),
                const SizedBox(height: 13),
                InkWell(
                  onTap: _chooseDate,
                  borderRadius: BorderRadius.circular(8),
                  child: InputDecorator(
                    decoration: const InputDecoration(
                      labelText: 'Date',
                      prefixIcon: Icon(Icons.calendar_today_outlined),
                    ),
                    child: Text(DateFormat('d MMMM yyyy').format(date)),
                  ),
                ),
                const SizedBox(height: 13),
                TextField(
                  controller: notes,
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) => saving ? null : _save(),
                  decoration: const InputDecoration(
                    labelText: 'Notes',
                    hintText: 'Optional',
                  ),
                ),
                if (error != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    error!,
                    style: const TextStyle(
                      color: AppColors.negative,
                      fontSize: 12,
                    ),
                  ),
                ],
                const SizedBox(height: 20),
                FilledButton(
                  onPressed: saving ? null : _save,
                  child: LoadingButtonContent(
                    loading: saving,
                    label: saving ? 'Saving' : 'Add contribution',
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  DropdownMenuItem<String> _accountItem(AccountRecord account) =>
      DropdownMenuItem(
        value: account.id,
        child: Text(account.name, overflow: TextOverflow.ellipsis),
      );
}

int? _parseCents(String value) {
  final normalized = value.trim().replaceAll(',', '.');
  final match = RegExp(r'^(\d+)(?:\.(\d{1,2}))?$').firstMatch(normalized);
  if (match == null) return null;
  final whole = int.tryParse(match.group(1)!);
  if (whole == null) return null;
  final decimals = (match.group(2) ?? '').padRight(2, '0');
  final fractional = decimals.isEmpty ? 0 : int.parse(decimals);
  return whole * 100 + fractional;
}
