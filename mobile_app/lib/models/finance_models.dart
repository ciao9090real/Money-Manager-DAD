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

class ImportBatchRecord {
  const ImportBatchRecord({
    required this.id,
    required this.sourceName,
    required this.sourceType,
    required this.status,
    required this.createdAt,
    required this.revision,
    this.sheetName,
    this.paymentMethodId,
    this.periodStart,
    this.periodEnd,
  });

  factory ImportBatchRecord.fromJson(Map<String, dynamic> json) =>
      ImportBatchRecord(
        id: '${json['id']}',
        sourceName: '${json['source_name'] ?? 'Imported file'}',
        sourceType: '${json['source_type'] ?? 'money_manager_csv'}',
        sheetName: _asOptionalString(json['sheet_name']),
        paymentMethodId: _asOptionalString(json['payment_method_id']),
        periodStart: _asOptionalString(json['period_start']),
        periodEnd: _asOptionalString(json['period_end']),
        status: '${json['status'] ?? 'review'}',
        createdAt: '${json['created_at'] ?? ''}',
        revision: _asInt(json['revision'], fallback: 1),
      );

  final String id;
  final String sourceName;
  final String sourceType;
  final String? sheetName;
  final String? paymentMethodId;
  final String? periodStart;
  final String? periodEnd;
  final String status;
  final String createdAt;
  final int revision;

  bool get isOpen => status == 'review';
  bool get isStatement => sourceType == 'bank_statement';
}

class ImportRowRecord {
  const ImportRowRecord({
    required this.id,
    required this.batchId,
    required this.sourceRowNumber,
    required this.description,
    required this.status,
    required this.revision,
    this.date,
    this.transactionType,
    this.accountId,
    this.targetAccountId,
    this.paymentMethodId,
    this.categoryId,
    this.amountCents,
    this.issueCode,
    this.issueText,
    this.postedTransactionId,
  });

  factory ImportRowRecord.fromJson(Map<String, dynamic> json) =>
      ImportRowRecord(
        id: '${json['id']}',
        batchId: '${json['batch_id']}',
        sourceRowNumber: _asInt(json['source_row_number']),
        date: _asOptionalString(json['date']),
        transactionType: _asOptionalString(json['transaction_type']),
        accountId: _asOptionalString(json['account_id']),
        targetAccountId: _asOptionalString(json['target_account_id']),
        paymentMethodId: _asOptionalString(json['payment_method_id']),
        categoryId: _asOptionalString(json['category_id']),
        amountCents: json['amount_cents'] == null
            ? null
            : _asInt(json['amount_cents']),
        description: '${json['description'] ?? ''}',
        status: '${json['status'] ?? 'error'}',
        issueCode: _asOptionalString(json['issue_code']),
        issueText: _asOptionalString(json['issue_text']),
        postedTransactionId: _asOptionalString(json['posted_transaction_id']),
        revision: _asInt(json['revision'], fallback: 1),
      );

  final String id;
  final String batchId;
  final int sourceRowNumber;
  final String? date;
  final String? transactionType;
  final String? accountId;
  final String? targetAccountId;
  final String? paymentMethodId;
  final String? categoryId;
  final int? amountCents;
  final String description;
  final String status;
  final String? issueCode;
  final String? issueText;
  final String? postedTransactionId;
  final int revision;

  bool get canCategorize =>
      transactionType == 'income' || transactionType == 'expense';
  bool get isReady => status == 'ready';
  bool get needsCategory => status == 'needs_category';
  bool get isResolved =>
      status == 'posted' || status == 'duplicate' || status == 'ignored';
}

class CategoryRecord {
  const CategoryRecord({
    required this.id,
    required this.name,
    required this.type,
    required this.isActive,
  });

  factory CategoryRecord.fromJson(Map<String, dynamic> json) => CategoryRecord(
    id: '${json['id']}',
    name: '${json['name'] ?? 'Category'}',
    type: '${json['type'] ?? 'expense'}',
    isActive: _asBool(json['is_active'], fallback: true),
  );

  final String id;
  final String name;
  final String type;
  final bool isActive;
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

class PaymentMethodRecord {
  const PaymentMethodRecord({
    required this.id,
    required this.name,
    required this.accountId,
    required this.type,
    required this.isActive,
  });

  factory PaymentMethodRecord.fromJson(Map<String, dynamic> json) =>
      PaymentMethodRecord(
        id: '${json['id']}',
        name: '${json['name'] ?? 'Payment method'}',
        accountId: '${json['account_id'] ?? ''}',
        type: '${json['type'] ?? 'other'}',
        isActive: _asBool(json['is_active'], fallback: true),
      );

  final String id;
  final String name;
  final String accountId;
  final String type;
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
    this.paymentMethodId,
    this.transferGroupId,
    this.recurringRuleId,
    this.investmentId,
    this.loanId,
    this.savingsGoalId,
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
        paymentMethodId: json['payment_method_id'] as String?,
        transferGroupId: json['transfer_group_id'] as String?,
        recurringRuleId: json['recurring_rule_id'] as String?,
        investmentId: json['investment_id'] as String?,
        loanId: json['loan_id'] as String?,
        savingsGoalId: json['savings_goal_id'] as String?,
        notes: json['notes'] as String?,
      );

  final String id;
  final String date;
  final String type;
  final String accountId;
  final int amountCents;
  final String description;
  final String? categoryId;
  final String? paymentMethodId;
  final String? transferGroupId;
  final String? recurringRuleId;
  final String? investmentId;
  final String? loanId;
  final String? savingsGoalId;
  final String? notes;

  bool get isIncome => type == 'income';
  bool get isExpense => type == 'expense';
  bool get isTransfer => type == 'transfer_in' || type == 'transfer_out';
}

class BudgetRecord {
  const BudgetRecord({
    required this.id,
    required this.categoryId,
    required this.period,
    required this.amountCents,
    required this.rollover,
    required this.startDate,
    required this.isActive,
  });

  factory BudgetRecord.fromJson(Map<String, dynamic> json) => BudgetRecord(
    id: '${json['id']}',
    categoryId: '${json['category_id'] ?? ''}',
    period: '${json['period'] ?? 'monthly'}',
    amountCents: _asInt(json['amount_cents']),
    rollover: _asBool(json['rollover']),
    startDate: '${json['start_date'] ?? ''}',
    isActive: _asBool(json['is_active'], fallback: true),
  );

  final String id;
  final String categoryId;
  final String period;
  final int amountCents;
  final bool rollover;
  final String startDate;
  final bool isActive;
}

class BudgetStatus {
  const BudgetStatus({
    required this.budget,
    required this.periodLabel,
    required this.limitCents,
    required this.spentCents,
    required this.remainingCents,
    required this.percentUsedBasisPoints,
    required this.rolledOverFromPriorCents,
  });

  final BudgetRecord budget;
  final String periodLabel;
  final int limitCents;
  final int spentCents;
  final int remainingCents;

  /// Hundredths of one percent: 10,000 means 100.00%.
  final int percentUsedBasisPoints;
  final int rolledOverFromPriorCents;

  double get percentUsed => percentUsedBasisPoints / 100;
  double get usageFraction => percentUsedBasisPoints / 10000;
  bool get isOverspent => percentUsedBasisPoints > 10000;
}

class NetWorthSnapshotRecord {
  const NetWorthSnapshotRecord({
    required this.date,
    required this.assetsCents,
    required this.liabilitiesCents,
    required this.revision,
  });

  factory NetWorthSnapshotRecord.fromJson(Map<String, dynamic> json) =>
      NetWorthSnapshotRecord(
        date: '${json['date'] ?? ''}',
        assetsCents: _asInt(json['assets_cents']),
        liabilitiesCents: _asInt(json['liabilities_cents']),
        revision: _asInt(json['revision'], fallback: 1),
      );

  final String date;
  final int assetsCents;
  final int liabilitiesCents;
  final int revision;

  int get netWorthCents => assetsCents - liabilitiesCents;
}

class NetWorthPoint {
  const NetWorthPoint({
    required this.date,
    required this.assetsCents,
    required this.liabilitiesCents,
    required this.netWorthCents,
    this.estimated = false,
  });

  factory NetWorthPoint.fromSnapshot(NetWorthSnapshotRecord snapshot) =>
      NetWorthPoint(
        date: snapshot.date,
        assetsCents: snapshot.assetsCents,
        liabilitiesCents: snapshot.liabilitiesCents,
        netWorthCents: snapshot.netWorthCents,
      );

  final String date;
  final int assetsCents;
  final int liabilitiesCents;
  final int netWorthCents;
  final bool estimated;
}

class SavingsGoalRecord {
  const SavingsGoalRecord({
    required this.id,
    required this.name,
    required this.targetAmountCents,
    required this.isActive,
    required this.revision,
    this.targetDate,
    this.linkedAccountId,
    this.createdAt,
  });

  factory SavingsGoalRecord.fromJson(Map<String, dynamic> json) =>
      SavingsGoalRecord(
        id: '${json['id']}',
        name: '${json['name'] ?? 'Savings goal'}',
        targetAmountCents: _asInt(json['target_amount_cents']),
        targetDate: _asOptionalString(json['target_date']),
        linkedAccountId: _asOptionalString(json['linked_account_id']),
        isActive: _asBool(json['is_active'], fallback: true),
        createdAt: _asOptionalString(json['created_at']),
        revision: _asInt(json['revision'], fallback: 1),
      );

  final String id;
  final String name;
  final int targetAmountCents;
  final String? targetDate;
  final String? linkedAccountId;
  final bool isActive;
  final String? createdAt;
  final int revision;

  bool get usesLinkedAccount => linkedAccountId != null;
}

class GoalProgress {
  const GoalProgress({
    required this.goal,
    required this.currentAmountCents,
    required this.percentCompleteBasisPoints,
    required this.onTrack,
    required this.requiredMonthlyContributionCents,
  });

  final SavingsGoalRecord goal;
  final int currentAmountCents;

  /// Hundredths of one percent: 10,000 means 100.00%.
  final int percentCompleteBasisPoints;
  final bool? onTrack;
  final int? requiredMonthlyContributionCents;

  double get percentComplete => percentCompleteBasisPoints / 100;
  double get completionFraction => percentCompleteBasisPoints / 10000;
  bool get isComplete => currentAmountCents >= goal.targetAmountCents;
}

class LoanRecord {
  const LoanRecord({
    required this.id,
    required this.direction,
    required this.name,
    required this.counterparty,
    required this.principalCents,
    required this.accountId,
    required this.startDate,
    required this.interestRateBps,
    required this.status,
    required this.revision,
    this.dueDate,
    this.notes,
  });

  factory LoanRecord.fromJson(Map<String, dynamic> json) => LoanRecord(
    id: '${json['id']}',
    direction: '${json['direction'] ?? 'borrowed'}',
    name: '${json['name'] ?? 'Loan'}',
    counterparty: '${json['counterparty'] ?? ''}',
    principalCents: _asInt(json['principal_cents']),
    accountId: '${json['account_id'] ?? ''}',
    startDate: '${json['start_date'] ?? ''}',
    dueDate: _asOptionalString(json['due_date']),
    interestRateBps: _asInt(json['interest_rate_bps']),
    notes: _asOptionalString(json['notes']),
    status: '${json['status'] ?? 'active'}',
    revision: _asInt(json['revision'], fallback: 1),
  );

  final String id;
  final String direction;
  final String name;
  final String counterparty;
  final int principalCents;
  final String accountId;
  final String startDate;
  final String? dueDate;
  final int interestRateBps;
  final String? notes;
  final String status;
  final int revision;

  bool get isBorrowed => direction == 'borrowed';
  bool get isActive => status == 'active';
}

class LoanPaymentRecord {
  const LoanPaymentRecord({
    required this.id,
    required this.loanId,
    required this.accountId,
    required this.transactionId,
    required this.amountCents,
    required this.date,
    required this.revision,
    this.notes,
  });

  factory LoanPaymentRecord.fromJson(Map<String, dynamic> json) =>
      LoanPaymentRecord(
        id: '${json['id']}',
        loanId: '${json['loan_id'] ?? ''}',
        accountId: '${json['account_id'] ?? ''}',
        transactionId: '${json['transaction_id'] ?? ''}',
        amountCents: _asInt(json['amount_cents']),
        date: '${json['date'] ?? ''}',
        notes: _asOptionalString(json['notes']),
        revision: _asInt(json['revision'], fallback: 1),
      );

  final String id;
  final String loanId;
  final String accountId;
  final String transactionId;
  final int amountCents;
  final String date;
  final String? notes;
  final int revision;
}

class AmortizationEntry {
  const AmortizationEntry({
    required this.period,
    required this.date,
    required this.paymentCents,
    required this.principalPortionCents,
    required this.interestPortionCents,
    required this.remainingBalanceCents,
  });

  final int period;
  final String date;
  final int paymentCents;
  final int principalPortionCents;
  final int interestPortionCents;
  final int remainingBalanceCents;
}

class PayoffPlan {
  const PayoffPlan({
    required this.loanId,
    required this.strategy,
    required this.entries,
    required this.payoffDate,
    required this.totalInterestPaidCents,
  });

  final String loanId;
  final String strategy;
  final List<AmortizationEntry> entries;
  final String payoffDate;
  final int totalInterestPaidCents;
}

class PayoffComparison {
  const PayoffComparison({
    required this.withoutExtra,
    required this.withExtra,
    required this.interestSavedCents,
    required this.monthsSaved,
  });

  final PayoffPlan withoutExtra;
  final PayoffPlan withExtra;
  final int interestSavedCents;
  final int monthsSaved;
}

class MultiLoanPayoffScenario {
  const MultiLoanPayoffScenario({
    required this.strategy,
    required this.plans,
    required this.totalInterestPaidCents,
    required this.payoffDate,
  });

  final String strategy;
  final List<PayoffPlan> plans;
  final int totalInterestPaidCents;
  final String? payoffDate;
}

class SavingsHealth {
  const SavingsHealth({
    required this.savingsRateBasisPoints,
    required this.emergencyFundCoverageHundredths,
  });

  /// Ten-thousandths of the ratio: 7,500 means a 75.00% savings rate.
  final int savingsRateBasisPoints;

  /// Hundredths of a month: 625 means 6.25 months of coverage.
  final int emergencyFundCoverageHundredths;

  double get savingsRate => savingsRateBasisPoints / 10000;
  double get emergencyFundCoverage => emergencyFundCoverageHundredths / 100;
}

class CashFlowPeriod {
  const CashFlowPeriod({
    required this.month,
    required this.incomeCents,
    required this.expenseCents,
  });

  final String month;
  final int incomeCents;
  final int expenseCents;

  int get netCents => incomeCents - expenseCents;
}

class CategorySpending {
  const CategorySpending({
    required this.categoryId,
    required this.name,
    required this.amountCents,
    required this.transactionCount,
    required this.shareBasisPoints,
  });

  final String? categoryId;
  final String name;
  final int amountCents;
  final int transactionCount;

  /// Ten-thousandths of total expense: 2,500 means 25.00%.
  final int shareBasisPoints;

  double get sharePercent => shareBasisPoints / 100;
}

class SpendingReport {
  const SpendingReport({
    required this.months,
    required this.startDate,
    required this.endDate,
    required this.incomeCents,
    required this.expenseCents,
    required this.previousExpenseCents,
    required this.expenseChangeBasisPoints,
    required this.cashFlow,
    required this.categories,
  });

  final int months;
  final String startDate;
  final String endDate;
  final int incomeCents;
  final int expenseCents;
  final int previousExpenseCents;
  final int? expenseChangeBasisPoints;
  final List<CashFlowPeriod> cashFlow;
  final List<CategorySpending> categories;

  int get netCents => incomeCents - expenseCents;
  int get averageMonthlyExpenseCents =>
      months <= 0 ? 0 : (expenseCents / months).round();
  CategorySpending? get topCategory =>
      categories.isEmpty ? null : categories.first;
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
    this.reminderDays = 3,
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
        reminderDays: _asInt(json['reminder_days'], fallback: 3),
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
  final int reminderDays;
}

class ReminderItem {
  const ReminderItem({required this.rule, required this.daysUntil});

  final RecurringRecord rule;
  final int daysUntil;

  bool get isOverdue => daysUntil < 0;
  bool get isToday => daysUntil == 0;
  bool get isIncome => rule.transactionType == 'income';
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

int _asInt(Object? value, {int fallback = 0}) {
  if (value is int) return value;
  return int.tryParse('$value') ?? fallback;
}

bool _asBool(Object? value, {bool fallback = false}) {
  if (value is bool) return value;
  if (value is num) return value != 0;
  final normalized = '$value'.trim().toLowerCase();
  if (normalized == 'true' || normalized == '1') return true;
  if (normalized == 'false' || normalized == '0') return false;
  return fallback;
}

String? _asOptionalString(Object? value) {
  if (value == null) return null;
  final text = '$value'.trim();
  return text.isEmpty ? null : text;
}
