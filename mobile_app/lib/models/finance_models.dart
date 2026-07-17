import 'dart:convert';

class StoredRecord {
  const StoredRecord({
    required this.entity,
    required this.id,
    required this.revision,
    required this.payload,
  });

  final String entity;
  final String id;
  final int revision;
  final Map<String, dynamic> payload;

  bool get isDeleted => payload['deleted_at'] != null;
}

class AccountRecord {
  const AccountRecord({
    required this.id,
    required this.name,
    required this.type,
    required this.openingBalanceCents,
    required this.isActive,
    this.parentId,
  });

  factory AccountRecord.fromJson(Map<String, dynamic> json) => AccountRecord(
    id: '${json['id']}',
    name: '${json['name'] ?? 'Account'}',
    type: '${json['type'] ?? 'other'}',
    parentId: json['parent_id'] as String?,
    openingBalanceCents: _asInt(json['opening_balance_cents']),
    isActive: _asInt(json['is_active']) == 1,
  );

  final String id;
  final String name;
  final String type;
  final String? parentId;
  final int openingBalanceCents;
  final bool isActive;
}

class TransactionRecord {
  const TransactionRecord({
    required this.id,
    required this.date,
    required this.type,
    required this.accountId,
    required this.amountCents,
    required this.description,
    this.categoryId,
    this.transferGroupId,
    this.recurringRuleId,
    this.investmentId,
    this.loanId,
    this.notes,
  });

  factory TransactionRecord.fromJson(Map<String, dynamic> json) =>
      TransactionRecord(
        id: '${json['id']}',
        date: '${json['date'] ?? ''}',
        type: '${json['type'] ?? 'adjustment'}',
        accountId: '${json['account_id'] ?? ''}',
        amountCents: _asInt(json['amount_cents']),
        description: '${json['description'] ?? ''}',
        categoryId: json['category_id'] as String?,
        transferGroupId: json['transfer_group_id'] as String?,
        recurringRuleId: json['recurring_rule_id'] as String?,
        investmentId: json['investment_id'] as String?,
        loanId: json['loan_id'] as String?,
        notes: json['notes'] as String?,
      );

  final String id;
  final String date;
  final String type;
  final String accountId;
  final int amountCents;
  final String description;
  final String? categoryId;
  final String? transferGroupId;
  final String? recurringRuleId;
  final String? investmentId;
  final String? loanId;
  final String? notes;

  bool get isIncome => type == 'income';
  bool get isExpense => type == 'expense';
  bool get isTransfer => type == 'transfer_in' || type == 'transfer_out';
}

class RecurringRecord {
  const RecurringRecord({
    required this.id,
    required this.name,
    required this.kind,
    required this.transactionType,
    required this.accountId,
    required this.frequency,
    required this.nextDueDate,
    required this.status,
    this.amountCents,
  });

  factory RecurringRecord.fromJson(Map<String, dynamic> json) =>
      RecurringRecord(
        id: '${json['id']}',
        name: '${json['name'] ?? 'Recurring payment'}',
        kind: '${json['kind'] ?? 'other'}',
        transactionType: '${json['transaction_type'] ?? 'expense'}',
        accountId: '${json['account_id'] ?? ''}',
        frequency: '${json['frequency'] ?? ''}',
        nextDueDate: '${json['next_due_date'] ?? ''}',
        status: '${json['status'] ?? 'active'}',
        amountCents: json['amount_cents'] == null
            ? null
            : _asInt(json['amount_cents']),
      );

  final String id;
  final String name;
  final String kind;
  final String transactionType;
  final String accountId;
  final String frequency;
  final String nextDueDate;
  final String status;
  final int? amountCents;
}

class PendingCommand {
  const PendingCommand({
    required this.id,
    required this.type,
    required this.payload,
    required this.status,
    this.error,
  });

  factory PendingCommand.fromRow(Map<String, Object?> row) => PendingCommand(
    id: '${row['id']}',
    type: '${row['type']}',
    payload: jsonDecode('${row['payload_json']}') as Map<String, dynamic>,
    status: '${row['status']}',
    error: row['error_message'] as String?,
  );

  final String id;
  final String type;
  final Map<String, dynamic> payload;
  final String status;
  final String? error;

  Map<String, dynamic> toWire() => {'id': id, 'type': type, 'payload': payload};
}

class PairingCredentials {
  const PairingCredentials({
    required this.url,
    required this.deviceId,
    required this.token,
    required this.fingerprint,
  });

  final String url;
  final String deviceId;
  final String token;
  final String fingerprint;
}

int _asInt(Object? value) {
  if (value is int) return value;
  return int.tryParse('$value') ?? 0;
}
