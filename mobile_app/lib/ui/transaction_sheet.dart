import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';

import '../main.dart';
import '../models/finance_models.dart';

class TransactionSheet extends StatefulWidget {
  const TransactionSheet({super.key});

  @override
  State<TransactionSheet> createState() => _TransactionSheetState();
}

class _TransactionSheetState extends State<TransactionSheet> {
  String type = 'expense';
  String? accountId;
  String? targetAccountId;
  DateTime date = DateTime.now();
  final amount = TextEditingController();
  final description = TextEditingController();
  final formKey = GlobalKey<FormState>();
  bool saving = false;

  @override
  void dispose() {
    amount.dispose();
    description.dispose();
    super.dispose();
  }

  Future<void> chooseDate() async {
    final chosen = await showDatePicker(
      context: context,
      initialDate: date,
      firstDate: DateTime(2000),
      lastDate: DateTime.now(),
      helpText: 'Transaction date',
    );
    if (chosen != null) setState(() => date = chosen);
  }

  Future<void> save() async {
    if (!formKey.currentState!.validate()) return;
    final decimal = double.parse(amount.text.replaceAll(',', '.'));
    final cents = (decimal * 100).round();
    setState(() => saving = true);
    await AppScope.of(context).queueTransaction(
      type: type,
      accountId: accountId!,
      targetAccountId: targetAccountId,
      amountCents: cents,
      date: DateFormat('yyyy-MM-dd').format(date),
      description: description.text,
    );
    if (mounted) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    final accounts = AppScope.of(context).accounts;
    accountId ??= accounts.isNotEmpty ? accounts.first.id : null;
    final targetOptions = accounts
        .where((account) => account.id != accountId)
        .toList();
    if (targetAccountId == accountId ||
        !targetOptions.any((account) => account.id == targetAccountId)) {
      targetAccountId = targetOptions.isNotEmpty
          ? targetOptions.first.id
          : null;
    }
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
                  'Add transaction',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 16),
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(
                      value: 'expense',
                      label: Text('Expense'),
                      icon: Icon(Icons.south_west),
                    ),
                    ButtonSegment(
                      value: 'income',
                      label: Text('Income'),
                      icon: Icon(Icons.north_east),
                    ),
                    ButtonSegment(
                      value: 'transfer',
                      label: Text('Transfer'),
                      icon: Icon(Icons.swap_horiz),
                    ),
                  ],
                  selected: {type},
                  showSelectedIcon: false,
                  onSelectionChanged: (value) =>
                      setState(() => type = value.first),
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  initialValue: accountId,
                  decoration: InputDecoration(
                    labelText: type == 'transfer' ? 'From account' : 'Account',
                  ),
                  items: accounts.map(_accountItem).toList(),
                  onChanged: (value) => setState(() => accountId = value),
                  validator: (value) =>
                      value == null ? 'Choose an account' : null,
                ),
                if (type == 'transfer') ...[
                  const SizedBox(height: 13),
                  DropdownButtonFormField<String>(
                    initialValue: targetAccountId,
                    decoration: const InputDecoration(labelText: 'To account'),
                    items: targetOptions.map(_accountItem).toList(),
                    onChanged: (value) =>
                        setState(() => targetAccountId = value),
                    validator: (value) =>
                        value == null ? 'Choose a different account' : null,
                  ),
                ],
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
                    final parsed = double.tryParse(
                      (value ?? '').replaceAll(',', '.'),
                    );
                    return parsed == null || parsed <= 0
                        ? 'Enter an amount greater than zero'
                        : null;
                  },
                ),
                const SizedBox(height: 13),
                InkWell(
                  onTap: chooseDate,
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
                  controller: description,
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) => saving ? null : save(),
                  decoration: const InputDecoration(
                    labelText: 'Description',
                    hintText: 'Optional',
                  ),
                ),
                const SizedBox(height: 20),
                FilledButton(
                  onPressed: saving ? null : save,
                  child: Text(saving ? 'Saving…' : 'Save transaction'),
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
