import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';

import '../main.dart';
import '../models/finance_models.dart';
import 'widgets.dart';

class TransactionSheet extends StatefulWidget {
  const TransactionSheet({
    super.key,
    this.initialType = 'expense',
    this.initialAccountId,
  });

  final String initialType;
  final String? initialAccountId;

  @override
  State<TransactionSheet> createState() => _TransactionSheetState();
}

class _TransactionSheetState extends State<TransactionSheet> {
  late String type;
  String? accountId;
  String? targetAccountId;
  String? categoryId;
  String? paymentMethodId;
  DateTime date = DateTime.now();
  final amount = TextEditingController();
  final description = TextEditingController();
  final notes = TextEditingController();
  final formKey = GlobalKey<FormState>();
  bool saving = false;
  bool showNotes = false;

  @override
  void initState() {
    super.initState();
    type = widget.initialType;
    accountId = widget.initialAccountId;
  }

  @override
  void dispose() {
    amount.dispose();
    description.dispose();
    notes.dispose();
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
    setState(() => saving = true);
    try {
      await AppScope.of(context).queueTransaction(
        type: type,
        accountId: accountId!,
        targetAccountId: targetAccountId,
        amountCents: _parseCents(amount.text),
        date: DateFormat('yyyy-MM-dd').format(date),
        description: description.text,
        categoryId: type == 'transfer' ? null : categoryId,
        paymentMethodId: type == 'transfer' ? null : paymentMethodId,
        notes: notes.text,
      );
      if (mounted) Navigator.pop(context, true);
    } catch (error) {
      if (!mounted) return;
      setState(() => saving = false);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Could not save: $error')));
    }
  }

  void _selectType(String value) {
    setState(() {
      type = value;
      categoryId = null;
      if (type == 'transfer') paymentMethodId = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    final controller = AppScope.of(context);
    final accounts = controller.accounts;
    if (!accounts.any((account) => account.id == accountId)) {
      accountId = accounts.isNotEmpty ? accounts.first.id : null;
    }
    final targetOptions = accounts
        .where((account) => account.id != accountId)
        .toList();
    if (targetAccountId == accountId ||
        !targetOptions.any((account) => account.id == targetAccountId)) {
      targetAccountId = targetOptions.isNotEmpty
          ? targetOptions.first.id
          : null;
    }
    final categories = controller.categories
        .where(
          (category) =>
              category.isActive &&
              category.type == type &&
              (type == 'income' || type == 'expense'),
        )
        .toList();
    if (!categories.any((category) => category.id == categoryId)) {
      categoryId = null;
    }
    final methods = controller.paymentMethods
        .where((method) => method.accountId == accountId && method.isActive)
        .toList();
    if (!methods.any((method) => method.id == paymentMethodId)) {
      paymentMethodId = null;
    }
    final selectedAccount = accounts
        .where((account) => account.id == accountId)
        .firstOrNull;

    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 10, 20, 24),
          child: Form(
            key: formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'New transaction',
                            style: Theme.of(context).textTheme.headlineSmall,
                          ),
                          const SizedBox(height: 3),
                          Text(
                            'Saved offline and synced with your desktop',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ],
                      ),
                    ),
                    IconButton(
                      tooltip: 'Close',
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.close),
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: 'expense', label: Text('Expense')),
                    ButtonSegment(value: 'income', label: Text('Income')),
                    ButtonSegment(value: 'transfer', label: Text('Move')),
                  ],
                  selected: {type},
                  showSelectedIcon: false,
                  onSelectionChanged: (value) => _selectType(value.first),
                ),
                const SizedBox(height: 18),
                TextFormField(
                  controller: amount,
                  autofocus: true,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.displaySmall,
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
                    try {
                      return _parseCents(value ?? '') > 0
                          ? null
                          : 'Enter an amount greater than zero';
                    } on FormatException {
                      return 'Enter a valid amount';
                    }
                  },
                ),
                const SizedBox(height: 14),
                DropdownButtonFormField<String>(
                  key: ValueKey('account-$accountId-$type'),
                  initialValue: accountId,
                  isExpanded: true,
                  decoration: InputDecoration(
                    labelText: type == 'transfer' ? 'From account' : 'Account',
                    helperText: selectedAccount == null
                        ? null
                        : 'Available balance ${money(controller.balanceFor(selectedAccount.id))}',
                    prefixIcon: const Icon(
                      Icons.account_balance_wallet_outlined,
                    ),
                  ),
                  items: accounts.map(_accountItem).toList(),
                  onChanged: (value) => setState(() {
                    accountId = value;
                    paymentMethodId = null;
                  }),
                  validator: (value) =>
                      value == null ? 'Choose an account' : null,
                ),
                if (type == 'transfer') ...[
                  const SizedBox(height: 14),
                  DropdownButtonFormField<String>(
                    key: ValueKey('target-$targetAccountId-$accountId'),
                    initialValue: targetAccountId,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'To account',
                      prefixIcon: Icon(Icons.arrow_forward),
                    ),
                    items: targetOptions.map(_accountItem).toList(),
                    onChanged: (value) =>
                        setState(() => targetAccountId = value),
                    validator: (value) =>
                        value == null ? 'Choose a different account' : null,
                  ),
                ],
                const SizedBox(height: 14),
                TextFormField(
                  controller: description,
                  textCapitalization: TextCapitalization.sentences,
                  decoration: const InputDecoration(
                    labelText: 'Description',
                    hintText: 'What was this for?',
                    prefixIcon: Icon(Icons.edit_note_outlined),
                  ),
                ),
                if (type != 'transfer' && categories.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  DropdownButtonFormField<String>(
                    key: ValueKey('category-$categoryId-$type'),
                    initialValue: categoryId,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Category',
                      hintText: 'Optional',
                      prefixIcon: Icon(Icons.sell_outlined),
                    ),
                    items: [
                      const DropdownMenuItem<String>(
                        value: null,
                        child: Text('No category'),
                      ),
                      ...categories.map(
                        (category) => DropdownMenuItem(
                          value: category.id,
                          child: Text(
                            category.name,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ),
                    ],
                    onChanged: (value) => setState(() => categoryId = value),
                  ),
                ],
                if (type != 'transfer' && methods.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  DropdownButtonFormField<String>(
                    key: ValueKey('method-$paymentMethodId-$accountId'),
                    initialValue: paymentMethodId,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Paid with',
                      hintText: 'Optional',
                      prefixIcon: Icon(Icons.credit_card_outlined),
                    ),
                    items: [
                      const DropdownMenuItem<String>(
                        value: null,
                        child: Text('No payment method'),
                      ),
                      ...methods.map(
                        (method) => DropdownMenuItem(
                          value: method.id,
                          child: Text(
                            '${method.name} · ${prettyType(method.type)}',
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ),
                    ],
                    onChanged: (value) =>
                        setState(() => paymentMethodId = value),
                  ),
                ],
                const SizedBox(height: 14),
                InkWell(
                  onTap: chooseDate,
                  borderRadius: BorderRadius.circular(14),
                  child: InputDecorator(
                    decoration: const InputDecoration(
                      labelText: 'Date',
                      prefixIcon: Icon(Icons.calendar_today_outlined),
                    ),
                    child: Text(DateFormat('d MMMM yyyy').format(date)),
                  ),
                ),
                TextButton.icon(
                  onPressed: () => setState(() => showNotes = !showNotes),
                  icon: Icon(
                    showNotes ? Icons.expand_less : Icons.add_circle_outline,
                  ),
                  label: Text(showNotes ? 'Hide notes' : 'Add a note'),
                ),
                if (showNotes)
                  TextField(
                    controller: notes,
                    minLines: 2,
                    maxLines: 4,
                    textCapitalization: TextCapitalization.sentences,
                    decoration: const InputDecoration(
                      labelText: 'Private note',
                      hintText: 'Reference, context, or reminder',
                    ),
                  ),
                const SizedBox(height: 18),
                FilledButton.icon(
                  onPressed: saving ? null : save,
                  icon: saving
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Icon(Icons.check),
                  label: Text(
                    saving
                        ? 'Saving…'
                        : type == 'transfer'
                        ? 'Save transfer'
                        : 'Save ${type == 'income' ? 'income' : 'expense'}',
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

int _parseCents(String raw) {
  var value = raw.trim().replaceAll(' ', '');
  if (value.isEmpty) throw const FormatException('Amount is empty');
  if (value.contains(',') && value.contains('.')) {
    if (value.lastIndexOf(',') > value.lastIndexOf('.')) {
      value = value.replaceAll('.', '').replaceAll(',', '.');
    } else {
      value = value.replaceAll(',', '');
    }
  } else {
    value = value.replaceAll(',', '.');
  }
  final parts = value.split('.');
  if (parts.length > 2 || parts.first.isEmpty) {
    throw const FormatException('Invalid amount');
  }
  final whole = int.parse(parts.first);
  final decimals = parts.length == 1
      ? 0
      : int.parse(parts.last.padRight(2, '0').substring(0, 2));
  return whole * 100 + decimals;
}
