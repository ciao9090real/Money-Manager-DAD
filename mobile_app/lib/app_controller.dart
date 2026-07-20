import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

import 'data/local_database.dart';
import 'data/sync_client.dart';
import 'models/finance_models.dart';

class AppController extends ChangeNotifier {
  AppController({
    required this.database,
    required this.syncClient,
    FlutterSecureStorage? secureStorage,
  }) : secureStorage = secureStorage ?? const FlutterSecureStorage();

  final LocalDatabase database;
  final SyncClient syncClient;
  final FlutterSecureStorage secureStorage;

  static const int emergencyFundWarningCoverageHundredths = 300;
  static const int emergencyFundHealthyCoverageHundredths = 600;
  static const int _maxAmortizationPeriods = 1200;

  List<AccountRecord> allAccounts = const [];
  List<AccountRecord> accounts = const [];
  List<CategoryRecord> categories = const [];
  List<TransactionRecord> transactions = const [];
  List<RecurringRecord> recurring = const [];
  List<StoredRecord> investments = const [];
  List<StoredRecord> loans = const [];
  List<BudgetRecord> budgets = const [];
  List<NetWorthSnapshotRecord> netWorthSnapshots = const [];
  List<SavingsGoalRecord> savingsGoals = const [];
  List<LoanRecord> loanRecords = const [];
  List<LoanPaymentRecord> loanPayments = const [];
  List<PendingCommand> pendingCommands = const [];
  PairingCredentials? credentials;
  bool isSyncing = false;
  String? syncError;
  String? lastSyncAt;

  bool get isPaired => credentials != null;
  int get pendingCount =>
      pendingCommands.where((command) => command.status == 'pending').length;
  int get failedCount =>
      pendingCommands.where((command) => command.status == 'failed').length;

  Future<void> initialize() async {
    await database.initialize();
    credentials = await _readCredentials();
    await reload();
  }

  Future<void> reload() async {
    final accountRows = await database.records('accounts');
    final categoryRows = await database.records('categories');
    final transactionRows = await database.records('transactions');
    final recurringRows = await database.records('recurring_rules');
    final investmentRows = await database.records('investments');
    final loanRows = await database.records('loans');
    final loanPaymentRows = await database.records('loan_payments');
    final budgetRows = await database.records('budgets');
    final netWorthRows = await database.records('net_worth_snapshots');
    final savingsGoalRows = await database.records('savings_goals');
    allAccounts = accountRows
        .map((row) => AccountRecord.fromJson(row.payload))
        .toList(growable: false);
    accounts = allAccounts.where((account) => account.isActive).toList()
      ..sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
    categories =
        categoryRows.map((row) => CategoryRecord.fromJson(row.payload)).toList()
          ..sort((a, b) {
            final type = a.type.compareTo(b.type);
            return type == 0
                ? a.name.toLowerCase().compareTo(b.name.toLowerCase())
                : type;
          });
    transactions =
        transactionRows
            .map((row) => TransactionRecord.fromJson(row.payload))
            .toList()
          ..sort((a, b) {
            final date = b.date.compareTo(a.date);
            return date == 0 ? b.id.compareTo(a.id) : date;
          });
    recurring =
        recurringRows
            .map((row) => RecurringRecord.fromJson(row.payload))
            .toList()
          ..sort((a, b) => a.nextDueDate.compareTo(b.nextDueDate));
    investments = investmentRows;
    loans = loanRows;
    loanRecords =
        loanRows.map((row) => LoanRecord.fromJson(row.payload)).toList()
          ..sort(_compareLoans);
    loanPayments =
        loanPaymentRows
            .map((row) => LoanPaymentRecord.fromJson(row.payload))
            .toList()
          ..sort((a, b) {
            final date = b.date.compareTo(a.date);
            return date == 0 ? b.id.compareTo(a.id) : date;
          });
    budgets =
        budgetRows.map((row) => BudgetRecord.fromJson(row.payload)).toList()
          ..sort((a, b) {
            final category = categoryName(
              a.categoryId,
            ).toLowerCase().compareTo(categoryName(b.categoryId).toLowerCase());
            return category == 0 ? a.period.compareTo(b.period) : category;
          });
    netWorthSnapshots =
        netWorthRows
            .map((row) => NetWorthSnapshotRecord.fromJson(row.payload))
            .toList()
          ..sort((a, b) => a.date.compareTo(b.date));
    savingsGoals =
        savingsGoalRows
            .map((row) => SavingsGoalRecord.fromJson(row.payload))
            .toList()
          ..sort(_compareGoals);
    pendingCommands = await database.pendingCommands();
    lastSyncAt = await database.state('last_sync_at');
    notifyListeners();
  }

  int balanceFor(String accountId) {
    AccountRecord? account;
    for (final item in allAccounts.isEmpty ? accounts : allAccounts) {
      if (item.id == accountId) {
        account = item;
        break;
      }
    }
    if (account == null) return 0;
    return account.openingBalanceCents +
        transactions
            .where((transaction) => transaction.accountId == accountId)
            .fold<int>(0, (sum, transaction) => sum + transaction.amountCents);
  }

  int get netWorthCents => currentNetWorthPoint().netWorthCents;

  int get liquidityCents {
    const liquidTypes = {
      'bank',
      'current_account',
      'savings_account',
      'cash',
      'wallet',
      'benefit',
    };
    return accounts
        .where((account) => liquidTypes.contains(account.type))
        .fold<int>(0, (sum, account) => sum + balanceFor(account.id));
  }

  int get debtCents {
    final accountDebt = accounts.fold<int>(0, (sum, account) {
      final balance = balanceFor(account.id);
      return balance < 0 ? sum + -balance : sum;
    });
    final borrowed = loanRecords
        .where((loan) => loan.isActive && loan.isBorrowed)
        .fold<int>(0, (sum, loan) => sum + outstandingForLoan(loan.id));
    return accountDebt + borrowed;
  }

  int get monthIncomeCents => _monthTotal('income');
  int get monthExpenseCents => -_monthTotal('expense');

  int _monthTotal(String type) {
    final now = DateTime.now();
    final prefix =
        '${now.year.toString().padLeft(4, '0')}-'
        '${now.month.toString().padLeft(2, '0')}';
    return transactions
        .where(
          (transaction) =>
              transaction.type == type && transaction.date.startsWith(prefix),
        )
        .fold<int>(0, (sum, transaction) => sum + transaction.amountCents);
  }

  CategoryRecord? categoryFor(String categoryId) {
    for (final category in categories) {
      if (category.id == categoryId) return category;
    }
    return null;
  }

  String categoryName(String categoryId) =>
      categoryFor(categoryId)?.name ?? 'Unknown category';

  SavingsGoalRecord? savingsGoalFor(String goalId) {
    for (final goal in savingsGoals) {
      if (goal.id == goalId) return goal;
    }
    return null;
  }

  LoanRecord? loanFor(String loanId) {
    for (final loan in loanRecords) {
      if (loan.id == loanId) return loan;
    }
    return null;
  }

  List<BudgetStatus> budgetStatuses({DateTime? referenceDate}) {
    final reference = _dateOnly(referenceDate ?? DateTime.now());
    final targetMonth = _monthStart(reference);
    final nextMonth = _shiftMonth(targetMonth, 1);
    final statuses = <BudgetStatus>[];

    for (final budget in budgets) {
      if (!budget.isActive || budget.period != 'monthly') continue;
      final start = _parseIsoDate(budget.startDate, 'Budget start date');
      if (_monthStart(start).isAfter(targetMonth)) continue;

      var rolledOver = 0;
      if (budget.rollover) {
        var month = _monthStart(start);
        while (month.isBefore(targetMonth)) {
          final followingMonth = _shiftMonth(month, 1);
          final spendingStart = start.isAfter(month) ? start : month;
          final spent = _spentForCategory(
            budget.categoryId,
            spendingStart,
            followingMonth,
          );
          final available = budget.amountCents + rolledOver - spent;
          rolledOver = available > 0 ? available : 0;
          month = followingMonth;
        }
      }

      final spendingStart = start.isAfter(targetMonth) ? start : targetMonth;
      final spent = _spentForCategory(
        budget.categoryId,
        spendingStart,
        nextMonth,
      );
      final limit = budget.amountCents + rolledOver;
      statuses.add(
        BudgetStatus(
          budget: budget,
          periodLabel: _monthLabel(targetMonth),
          limitCents: limit,
          spentCents: spent,
          remainingCents: limit - spent,
          percentUsedBasisPoints: limit <= 0
              ? 0
              : _roundHalfUpRatio(spent * 10000, limit),
          rolledOverFromPriorCents: rolledOver,
        ),
      );
    }

    statuses.sort((a, b) {
      final category = categoryName(a.budget.categoryId)
          .toLowerCase()
          .compareTo(categoryName(b.budget.categoryId).toLowerCase());
      return category == 0 ? a.budget.id.compareTo(b.budget.id) : category;
    });
    return List.unmodifiable(statuses);
  }

  List<BudgetStatus> overspentBudgets({DateTime? referenceDate}) =>
      budgetStatuses(
        referenceDate: referenceDate,
      ).where((status) => status.isOverspent).toList(growable: false);

  GoalProgress goalProgress(String goalId, {DateTime? referenceDate}) {
    final goal = savingsGoalFor(goalId);
    if (goal == null) {
      throw ArgumentError.value(goalId, 'goalId', 'Goal not found');
    }
    final reference = _dateOnly(referenceDate ?? DateTime.now());
    final referenceIso = _isoDate(reference);

    final int current;
    if (goal.linkedAccountId != null) {
      current = _nonNegative(balanceFor(goal.linkedAccountId!));
    } else {
      current = transactions
          .where(
            (transaction) =>
                transaction.savingsGoalId == goal.id &&
                transaction.type == 'transfer_in' &&
                transaction.date.compareTo(referenceIso) <= 0,
          )
          .fold<int>(0, (sum, transaction) => sum + transaction.amountCents);
    }

    final percent = goal.targetAmountCents <= 0
        ? 0
        : _roundHalfUpRatio(current * 10000, goal.targetAmountCents);
    final targetDate = goal.targetDate == null
        ? null
        : _parseIsoDate(goal.targetDate!, 'Goal target date');
    int? requiredMonthly;
    bool? onTrack;
    if (targetDate != null) {
      final remaining = _nonNegative(goal.targetAmountCents - current);
      if (remaining == 0) {
        requiredMonthly = 0;
      } else if (targetDate.isBefore(reference)) {
        requiredMonthly = null;
      } else {
        var months =
            (targetDate.year - reference.year) * 12 +
            targetDate.month -
            reference.month;
        if (targetDate.day > reference.day) months += 1;
        if (months < 1) months = 1;
        requiredMonthly = _ceilDivide(remaining, months);
      }

      final created = goal.createdAt == null
          ? reference
          : _parseIsoDate(
              goal.createdAt!.substring(0, 10),
              'Goal creation date',
            );
      if (!targetDate.isAfter(created) || !reference.isBefore(targetDate)) {
        onTrack = current >= goal.targetAmountCents;
      } else if (!reference.isAfter(created)) {
        onTrack = true;
      } else {
        final totalDays = targetDate.difference(created).inDays;
        final elapsedDays = reference.difference(created).inDays;
        onTrack = current * totalDays >= goal.targetAmountCents * elapsedDays;
      }
    }

    return GoalProgress(
      goal: goal,
      currentAmountCents: current,
      percentCompleteBasisPoints: percent,
      onTrack: onTrack,
      requiredMonthlyContributionCents: requiredMonthly,
    );
  }

  List<GoalProgress> get goalProgresses => savingsGoals
      .where((goal) => goal.isActive)
      .map((goal) => goalProgress(goal.id))
      .toList(growable: false);

  int savingsRateBasisPoints({int months = 1, DateTime? referenceDate}) {
    if (months < 1) {
      throw ArgumentError.value(months, 'months', 'Must be at least 1');
    }
    final reference = _dateOnly(referenceDate ?? DateTime.now());
    final currentMonth = _monthStart(reference);
    final start = _shiftMonth(currentMonth, -(months - 1));
    final end = _shiftMonth(currentMonth, 1);
    final totals = _incomeAndExpenses(start, end);
    final income = totals.$1;
    final expenses = totals.$2;
    if (income <= 0) return 0;
    return _roundHalfUpRatio((income - expenses) * 10000, income);
  }

  double savingsRate({int months = 1, DateTime? referenceDate}) =>
      savingsRateBasisPoints(months: months, referenceDate: referenceDate) /
      10000;

  int emergencyFundCoverageHundredths({
    int months = 6,
    DateTime? referenceDate,
  }) {
    if (months < 1) {
      throw ArgumentError.value(months, 'months', 'Must be at least 1');
    }
    if (liquidityCents <= 0) return 0;
    final reference = _dateOnly(referenceDate ?? DateTime.now());
    final end = _monthStart(reference);
    final start = _shiftMonth(end, -months);
    final expenses = _incomeAndExpenses(start, end).$2;
    if (expenses <= 0) return 0;
    return _roundHalfUpRatio(liquidityCents * months * 100, expenses);
  }

  double emergencyFundCoverage({int months = 6, DateTime? referenceDate}) =>
      emergencyFundCoverageHundredths(
        months: months,
        referenceDate: referenceDate,
      ) /
      100;

  SavingsHealth savingsHealth({
    int savingsRateMonths = 1,
    int emergencyCoverageMonths = 6,
    DateTime? referenceDate,
  }) => SavingsHealth(
    savingsRateBasisPoints: savingsRateBasisPoints(
      months: savingsRateMonths,
      referenceDate: referenceDate,
    ),
    emergencyFundCoverageHundredths: emergencyFundCoverageHundredths(
      months: emergencyCoverageMonths,
      referenceDate: referenceDate,
    ),
  );

  NetWorthPoint currentNetWorthPoint({DateTime? referenceDate}) {
    var assets = 0;
    var liabilities = 0;
    for (final account in accounts) {
      final balance = balanceFor(account.id);
      if (balance >= 0) {
        assets += balance;
      } else {
        liabilities += -balance;
      }
    }
    for (final loan in loanRecords.where((item) => item.isActive)) {
      final outstanding = outstandingForLoan(loan.id);
      if (loan.isBorrowed) {
        liabilities += outstanding;
      } else {
        assets += outstanding;
      }
    }
    return NetWorthPoint(
      date: _isoDate(_dateOnly(referenceDate ?? DateTime.now())),
      assetsCents: assets,
      liabilitiesCents: liabilities,
      netWorthCents: assets - liabilities,
    );
  }

  List<NetWorthPoint> netWorthHistory({
    int months = 12,
    DateTime? referenceDate,
  }) {
    if (months < 1) {
      throw ArgumentError.value(months, 'months', 'Must be at least 1');
    }
    final reference = _dateOnly(referenceDate ?? DateTime.now());
    final today = _dateOnly(DateTime.now());
    final snapshots = <String, NetWorthSnapshotRecord>{
      for (final snapshot in netWorthSnapshots) snapshot.date: snapshot,
    };
    final points = <NetWorthPoint>[];
    final referenceMonth = _monthStart(reference);

    for (var offset = months - 1; offset >= 0; offset--) {
      final month = _shiftMonth(referenceMonth, -offset);
      final cutoff =
          month.year == reference.year && month.month == reference.month
          ? reference
          : DateTime(month.year, month.month + 1, 0);
      final key = _isoDate(cutoff);
      final snapshot = snapshots[key];
      if (snapshot != null) {
        points.add(NetWorthPoint.fromSnapshot(snapshot));
      } else if (_sameDate(cutoff, today)) {
        points.add(currentNetWorthPoint(referenceDate: cutoff));
      } else {
        points.add(_historicalNetWorthPoint(cutoff));
      }
    }
    return List.unmodifiable(points);
  }

  int paidForLoan(String loanId, {DateTime? throughDate}) {
    final cutoff = throughDate == null
        ? null
        : _isoDate(_dateOnly(throughDate));
    return loanPayments
        .where(
          (payment) =>
              payment.loanId == loanId &&
              (cutoff == null || payment.date.compareTo(cutoff) <= 0),
        )
        .fold<int>(0, (sum, payment) => sum + payment.amountCents);
  }

  int outstandingForLoan(String loanId, {DateTime? throughDate}) {
    final loan = loanFor(loanId);
    if (loan == null) return 0;
    return _nonNegative(
      loan.principalCents - paidForLoan(loanId, throughDate: throughDate),
    );
  }

  List<AmortizationEntry> amortizationSchedule(
    String loanId, {
    int? monthlyPaymentCents,
    DateTime? referenceDate,
  }) {
    final loan = loanFor(loanId);
    if (loan == null) {
      throw ArgumentError.value(loanId, 'loanId', 'Loan not found');
    }
    final balanceAtStart = outstandingForLoan(loanId);
    if (balanceAtStart <= 0 || !loan.isActive) return const [];
    final reference = _dateOnly(referenceDate ?? DateTime.now());
    final firstPaymentDate = _firstPaymentDate(loan, reference);
    List<DateTime>? derivedDates;
    final int payment;
    if (monthlyPaymentCents == null) {
      derivedDates = _datesThroughDueDate(loan, firstPaymentDate, reference);
      payment = _amortizingPaymentCents(
        balanceAtStart,
        loan.interestRateBps,
        derivedDates.length,
      );
    } else {
      if (monthlyPaymentCents <= 0) {
        throw ArgumentError.value(
          monthlyPaymentCents,
          'monthlyPaymentCents',
          'Must be greater than zero',
        );
      }
      payment = monthlyPaymentCents;
    }

    final firstInterest = _monthlyInterestCents(
      balanceAtStart,
      loan.interestRateBps,
    );
    if (payment <= firstInterest) {
      throw ArgumentError.value(
        payment,
        'monthlyPaymentCents',
        'Must be greater than the monthly interest',
      );
    }

    var balance = balanceAtStart;
    final anchorDay = _parseIsoDate(loan.startDate, 'Loan start date').day;
    final entries = <AmortizationEntry>[];
    for (var period = 1; period <= _maxAmortizationPeriods; period++) {
      final paymentDate = derivedDates != null && period <= derivedDates.length
          ? derivedDates[period - 1]
          : _addMonthsAnchored(firstPaymentDate, period - 1, anchorDay);
      final interest = _monthlyInterestCents(balance, loan.interestRateBps);
      final settle =
          balance + interest <= payment ||
          (derivedDates != null && period == derivedDates.length);
      final int actualPayment;
      final int principal;
      final int remaining;
      if (settle) {
        actualPayment = balance + interest;
        principal = balance;
        remaining = 0;
      } else {
        actualPayment = payment;
        principal = actualPayment - interest;
        if (principal <= 0) {
          throw StateError(
            'Monthly payment is too small to reduce the loan balance',
          );
        }
        remaining = balance - principal;
      }
      entries.add(
        AmortizationEntry(
          period: period,
          date: _isoDate(paymentDate),
          paymentCents: actualPayment,
          principalPortionCents: principal,
          interestPortionCents: interest,
          remainingBalanceCents: remaining,
        ),
      );
      if (remaining == 0) return List.unmodifiable(entries);
      balance = remaining;
    }
    throw StateError(
      'Monthly payment does not repay the loan within 100 years',
    );
  }

  PayoffComparison loanPayoffProjection(
    String loanId, {
    int? monthlyPaymentCents,
    int extraMonthlyPaymentCents = 0,
    DateTime? referenceDate,
  }) {
    if (extraMonthlyPaymentCents < 0) {
      throw ArgumentError.value(
        extraMonthlyPaymentCents,
        'extraMonthlyPaymentCents',
        'Cannot be negative',
      );
    }
    final baselineEntries = amortizationSchedule(
      loanId,
      monthlyPaymentCents: monthlyPaymentCents,
      referenceDate: referenceDate,
    );
    if (baselineEntries.isEmpty) {
      throw StateError('This loan is already settled');
    }
    final regularPayment =
        monthlyPaymentCents ?? baselineEntries.first.paymentCents;
    final extraEntries = extraMonthlyPaymentCents == 0
        ? baselineEntries
        : amortizationSchedule(
            loanId,
            monthlyPaymentCents: regularPayment + extraMonthlyPaymentCents,
            referenceDate: referenceDate,
          );
    final withoutExtra = _payoffPlan(loanId, 'minimum', baselineEntries);
    final withExtra = _payoffPlan(loanId, 'custom', extraEntries);
    return PayoffComparison(
      withoutExtra: withoutExtra,
      withExtra: withExtra,
      interestSavedCents:
          withoutExtra.totalInterestPaidCents -
          withExtra.totalInterestPaidCents,
      monthsSaved: baselineEntries.length - extraEntries.length,
    );
  }

  MultiLoanPayoffScenario multiLoanPayoffScenario({
    required String strategy,
    int extraBudgetCents = 0,
    DateTime? referenceDate,
  }) {
    final normalizedStrategy = strategy.trim().toLowerCase();
    if (normalizedStrategy != 'snowball' && normalizedStrategy != 'avalanche') {
      throw ArgumentError.value(
        strategy,
        'strategy',
        'Must be snowball or avalanche',
      );
    }
    if (extraBudgetCents < 0) {
      throw ArgumentError.value(
        extraBudgetCents,
        'extraBudgetCents',
        'Cannot be negative',
      );
    }

    final orderedLoans = loanRecords
        .where(
          (loan) =>
              loan.isActive &&
              loan.isBorrowed &&
              outstandingForLoan(loan.id) > 0,
        )
        .toList();
    orderedLoans.sort((a, b) {
      final aOutstanding = outstandingForLoan(a.id);
      final bOutstanding = outstandingForLoan(b.id);
      int result;
      if (normalizedStrategy == 'snowball') {
        result = aOutstanding.compareTo(bOutstanding);
        if (result == 0) {
          result = b.interestRateBps.compareTo(a.interestRateBps);
        }
      } else {
        result = b.interestRateBps.compareTo(a.interestRateBps);
        if (result == 0) result = aOutstanding.compareTo(bOutstanding);
      }
      if (result == 0) {
        result = a.name.toLowerCase().compareTo(b.name.toLowerCase());
      }
      return result == 0 ? a.id.compareTo(b.id) : result;
    });
    if (orderedLoans.isEmpty) {
      return MultiLoanPayoffScenario(
        strategy: normalizedStrategy,
        plans: const [],
        totalInterestPaidCents: 0,
        payoffDate: null,
      );
    }

    final reference = _dateOnly(referenceDate ?? DateTime.now());
    final states = <_LoanPayoffState>[];
    for (final loan in orderedLoans) {
      final balance = outstandingForLoan(loan.id);
      final firstPayment = _firstPaymentDate(loan, reference);
      final dates = _datesThroughDueDate(loan, firstPayment, reference);
      states.add(
        _LoanPayoffState(
          loan: loan,
          balanceCents: balance,
          minimumPaymentCents: _amortizingPaymentCents(
            balance,
            loan.interestRateBps,
            dates.length,
          ),
          firstPaymentDate: firstPayment,
          anchorDay: _parseIsoDate(loan.startDate, 'Loan start date').day,
        ),
      );
    }

    for (var period = 1; period <= _maxAmortizationPeriods; period++) {
      if (states.every((state) => state.balanceCents == 0)) break;
      var extraPool = extraBudgetCents;
      for (final state in states) {
        if (state.balanceCents == 0) extraPool += state.minimumPaymentCents;
      }
      final periodEntries = <int, AmortizationEntry>{};

      for (var index = 0; index < states.length; index++) {
        final state = states[index];
        final balance = state.balanceCents;
        if (balance == 0) continue;
        final interest = _monthlyInterestCents(
          balance,
          state.loan.interestRateBps,
        );
        final amountDue = balance + interest;
        final actual = state.minimumPaymentCents < amountDue
            ? state.minimumPaymentCents
            : amountDue;
        final principal = actual - interest;
        if (principal <= 0) {
          throw StateError(
            "The derived monthly payment for '${state.loan.name}' "
            'does not reduce its balance',
          );
        }
        final remaining = _nonNegative(balance - principal);
        extraPool += state.minimumPaymentCents - actual;
        final paymentDate = _addMonthsAnchored(
          state.firstPaymentDate,
          period - 1,
          state.anchorDay,
        );
        periodEntries[index] = AmortizationEntry(
          period: period,
          date: _isoDate(paymentDate),
          paymentCents: actual,
          principalPortionCents: principal,
          interestPortionCents: interest,
          remainingBalanceCents: remaining,
        );
        state.balanceCents = remaining;
      }

      for (var index = 0; index < states.length && extraPool > 0; index++) {
        final state = states[index];
        final entry = periodEntries[index];
        if (entry == null || entry.remainingBalanceCents <= 0) continue;
        final applied = extraPool < entry.remainingBalanceCents
            ? extraPool
            : entry.remainingBalanceCents;
        final remaining = entry.remainingBalanceCents - applied;
        periodEntries[index] = AmortizationEntry(
          period: entry.period,
          date: entry.date,
          paymentCents: entry.paymentCents + applied,
          principalPortionCents: entry.principalPortionCents + applied,
          interestPortionCents: entry.interestPortionCents,
          remainingBalanceCents: remaining,
        );
        state.balanceCents = remaining;
        extraPool -= applied;
      }

      for (final item in periodEntries.entries) {
        states[item.key].entries.add(item.value);
      }
    }
    if (states.any((state) => state.balanceCents != 0)) {
      throw StateError(
        'The payoff strategy does not settle every loan within 100 years',
      );
    }

    final plans = states
        .map(
          (state) =>
              _payoffPlan(state.loan.id, normalizedStrategy, state.entries),
        )
        .toList(growable: false);
    final payoffDate = plans
        .map((plan) => plan.payoffDate)
        .reduce((a, b) => a.compareTo(b) >= 0 ? a : b);
    return MultiLoanPayoffScenario(
      strategy: normalizedStrategy,
      plans: plans,
      totalInterestPaidCents: plans.fold<int>(
        0,
        (sum, plan) => sum + plan.totalInterestPaidCents,
      ),
      payoffDate: payoffDate,
    );
  }

  int _spentForCategory(String categoryId, DateTime start, DateTime end) {
    final startIso = _isoDate(start);
    final endIso = _isoDate(end);
    return transactions
        .where(
          (transaction) =>
              transaction.type == 'expense' &&
              transaction.categoryId == categoryId &&
              transaction.date.compareTo(startIso) >= 0 &&
              transaction.date.compareTo(endIso) < 0,
        )
        .fold<int>(0, (sum, transaction) => sum - transaction.amountCents);
  }

  (int, int) _incomeAndExpenses(DateTime start, DateTime end) {
    final startIso = _isoDate(start);
    final endIso = _isoDate(end);
    var income = 0;
    var expenses = 0;
    for (final transaction in transactions) {
      if (transaction.date.compareTo(startIso) < 0 ||
          transaction.date.compareTo(endIso) >= 0) {
        continue;
      }
      if (transaction.type == 'income') {
        income += transaction.amountCents;
      } else if (transaction.type == 'expense') {
        expenses -= transaction.amountCents;
      }
    }
    return (income, expenses);
  }

  NetWorthPoint _historicalNetWorthPoint(DateTime cutoff) {
    final cutoffIso = _isoDate(cutoff);
    var assets = 0;
    var liabilities = 0;
    for (final account in accounts) {
      var balance = account.openingBalanceCents;
      for (final transaction in transactions) {
        if (transaction.accountId == account.id &&
            transaction.date.compareTo(cutoffIso) <= 0) {
          balance += transaction.amountCents;
        }
      }
      if (balance >= 0) {
        assets += balance;
      } else {
        liabilities += -balance;
      }
    }
    for (final loan in loanRecords) {
      if (loan.startDate.compareTo(cutoffIso) > 0) continue;
      final outstanding = outstandingForLoan(loan.id, throughDate: cutoff);
      if (loan.isBorrowed) {
        liabilities += outstanding;
      } else {
        assets += outstanding;
      }
    }
    return NetWorthPoint(
      date: cutoffIso,
      assetsCents: assets,
      liabilitiesCents: liabilities,
      netWorthCents: assets - liabilities,
      estimated: true,
    );
  }

  DateTime _firstPaymentDate(LoanRecord loan, DateTime reference) {
    final started = _parseIsoDate(loan.startDate, 'Loan start date');
    var baseline = reference.isAfter(started) ? reference : started;
    for (final payment in loanPayments.where(
      (item) => item.loanId == loan.id,
    )) {
      final paidAt = _parseIsoDate(payment.date, 'Loan payment date');
      if (paidAt.isAfter(baseline)) baseline = paidAt;
    }
    final candidate = DateTime(
      baseline.year,
      baseline.month,
      _clampDay(baseline.year, baseline.month, started.day),
    );
    return candidate.isAfter(baseline)
        ? candidate
        : _addMonthsAnchored(candidate, 1, started.day);
  }

  List<DateTime> _datesThroughDueDate(
    LoanRecord loan,
    DateTime firstPayment,
    DateTime reference,
  ) {
    if (loan.dueDate == null) {
      throw StateError(
        "A due date is required to derive a monthly payment for '${loan.name}'",
      );
    }
    final due = _parseIsoDate(loan.dueDate!, 'Loan due date');
    if (!due.isAfter(reference)) {
      throw StateError('Loan due date must be after the payoff-plan date');
    }
    final anchorDay = _parseIsoDate(loan.startDate, 'Loan start date').day;
    final dates = <DateTime>[];
    var paymentDate = firstPayment;
    while (paymentDate.isBefore(due)) {
      dates.add(paymentDate);
      if (dates.length >= _maxAmortizationPeriods) {
        throw StateError('Loan due date is more than 100 years away');
      }
      paymentDate = _addMonthsAnchored(paymentDate, 1, anchorDay);
    }
    dates.add(due);
    return dates;
  }

  static PayoffPlan _payoffPlan(
    String loanId,
    String strategy,
    List<AmortizationEntry> entries,
  ) {
    if (entries.isEmpty) {
      throw StateError('A payoff plan requires an active loan');
    }
    return PayoffPlan(
      loanId: loanId,
      strategy: strategy,
      entries: List.unmodifiable(entries),
      payoffDate: entries.last.date,
      totalInterestPaidCents: entries.fold<int>(
        0,
        (sum, entry) => sum + entry.interestPortionCents,
      ),
    );
  }

  Future<void> pair({
    required String url,
    required String code,
    required String fingerprintPrefix,
  }) async {
    final existingDeviceId = await secureStorage.read(key: 'device_id');
    final deviceId = existingDeviceId ?? const Uuid().v4();
    isSyncing = true;
    syncError = null;
    notifyListeners();
    try {
      final paired = await syncClient.pair(
        url: url,
        code: code,
        fingerprintPrefix: fingerprintPrefix,
        deviceId: deviceId,
        displayName: 'Android phone',
      );
      await _writeCredentials(paired);
      credentials = paired;
      isSyncing = false;
      notifyListeners();
      await syncNow();
    } catch (error) {
      syncError = '$error';
      rethrow;
    } finally {
      isSyncing = false;
      notifyListeners();
    }
  }

  Future<void> syncNow() async {
    final paired = credentials;
    if (paired == null || isSyncing) return;
    isSyncing = true;
    syncError = null;
    notifyListeners();
    try {
      var hasMore = true;
      var includeCommands = true;
      while (hasMore) {
        final cursor = await database.cursor();
        final entitySetVersion = await database.entitySetVersion();
        final commands = includeCommands
            ? await database.pendingCommands(includeFailed: false)
            : const <PendingCommand>[];
        final response = await syncClient.sync(
          credentials: paired,
          cursor: cursor,
          entitySetVersion: entitySetVersion,
          commands: commands,
        );
        await database.applyExchange(response);
        hasMore = response['has_more'] == true;
        includeCommands = false;
      }
      await reload();
    } catch (error) {
      syncError = '$error';
      await reload();
      rethrow;
    } finally {
      isSyncing = false;
      notifyListeners();
    }
  }

  Future<void> queueTransaction({
    required String type,
    required String accountId,
    required int amountCents,
    required String date,
    String description = '',
    String? targetAccountId,
  }) async {
    final commandType = switch (type) {
      'income' => 'create_income',
      'expense' => 'create_expense',
      'transfer' => 'create_transfer',
      _ => throw ArgumentError('Unsupported transaction type'),
    };
    final payload = <String, dynamic>{
      'amount_cents': amountCents,
      'date': date,
      'description': description.trim(),
    };
    if (type == 'transfer') {
      payload['source_account_id'] = accountId;
      payload['target_account_id'] = targetAccountId;
    } else {
      payload['account_id'] = accountId;
    }
    await database.queueCommand(
      PendingCommand(
        id: const Uuid().v4(),
        type: commandType,
        payload: payload,
        status: 'pending',
      ),
    );
    await reload();
    await _tryBackgroundSync();
  }

  Future<void> recordRecurring(String ruleId, {int? amountCents}) async {
    final payload = <String, dynamic>{
      'rule_id': ruleId,
      'date': _isoDate(DateTime.now()),
    };
    if (amountCents != null) {
      payload['amount_cents'] = amountCents;
    }
    await database.queueCommand(
      PendingCommand(
        id: const Uuid().v4(),
        type: 'record_recurring',
        payload: payload,
        status: 'pending',
      ),
    );
    await reload();
    await _tryBackgroundSync();
  }

  Future<void> queueGoalContribution({
    required String goalId,
    required String sourceAccountId,
    required String targetAccountId,
    required int amountCents,
    required String date,
    String? notes,
  }) async {
    final goal = savingsGoalFor(goalId);
    if (goal == null) {
      throw ArgumentError.value(goalId, 'goalId', 'Goal not found');
    }
    if (!goal.isActive) {
      throw StateError('Contributions require an active goal');
    }
    if (goal.usesLinkedAccount) {
      throw StateError('Linked-account goals do not use manual contributions');
    }
    if (sourceAccountId == targetAccountId) {
      throw ArgumentError('Contribution accounts must be different');
    }
    if (!accounts.any((account) => account.id == sourceAccountId) ||
        !accounts.any((account) => account.id == targetAccountId)) {
      throw ArgumentError('Contribution accounts must be active');
    }
    if (amountCents <= 0) {
      throw ArgumentError.value(
        amountCents,
        'amountCents',
        'Must be greater than zero',
      );
    }
    _parseIsoDate(date, 'Contribution date');
    final cleanedNotes = notes?.trim();
    await database.queueCommand(
      PendingCommand(
        id: const Uuid().v4(),
        type: 'add_goal_contribution',
        payload: {
          'goal_id': goalId,
          'source_account_id': sourceAccountId,
          'target_account_id': targetAccountId,
          'amount_cents': amountCents,
          'date': date,
          if (cleanedNotes != null && cleanedNotes.isNotEmpty)
            'notes': cleanedNotes,
        },
        status: 'pending',
      ),
    );
    await reload();
    await _tryBackgroundSync();
  }

  Future<void> dismissFailedCommand(String id) async {
    await database.dismissCommand(id);
    await reload();
  }

  Future<void> unpair() async {
    await secureStorage.deleteAll();
    await database.clearSyncedData();
    credentials = null;
    syncError = null;
    await reload();
  }

  Future<void> _tryBackgroundSync() async {
    if (!isPaired) return;
    try {
      await syncNow();
    } catch (_) {
      // The command remains queued; the visible pending state is intentional.
    }
  }

  Future<PairingCredentials?> _readCredentials() async {
    final url = await secureStorage.read(key: 'desktop_url');
    final deviceId = await secureStorage.read(key: 'device_id');
    final token = await secureStorage.read(key: 'auth_token');
    final fingerprint = await secureStorage.read(key: 'fingerprint');
    if ([url, deviceId, token, fingerprint].any((value) => value == null)) {
      return null;
    }
    return PairingCredentials(
      url: url!,
      deviceId: deviceId!,
      token: token!,
      fingerprint: fingerprint!,
    );
  }

  Future<void> _writeCredentials(PairingCredentials value) async {
    await secureStorage.write(key: 'desktop_url', value: value.url);
    await secureStorage.write(key: 'device_id', value: value.deviceId);
    await secureStorage.write(key: 'auth_token', value: value.token);
    await secureStorage.write(key: 'fingerprint', value: value.fingerprint);
  }

  static String _isoDate(DateTime value) =>
      '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}

class _LoanPayoffState {
  _LoanPayoffState({
    required this.loan,
    required this.balanceCents,
    required this.minimumPaymentCents,
    required this.firstPaymentDate,
    required this.anchorDay,
  });

  final LoanRecord loan;
  int balanceCents;
  final int minimumPaymentCents;
  final DateTime firstPaymentDate;
  final int anchorDay;
  final List<AmortizationEntry> entries = [];
}

int _compareLoans(LoanRecord a, LoanRecord b) {
  final status = a.status.compareTo(b.status);
  if (status != 0) return status;
  final due = (a.dueDate ?? '9999-12-31').compareTo(b.dueDate ?? '9999-12-31');
  if (due != 0) return due;
  final name = a.name.toLowerCase().compareTo(b.name.toLowerCase());
  return name == 0 ? a.id.compareTo(b.id) : name;
}

int _compareGoals(SavingsGoalRecord a, SavingsGoalRecord b) {
  if (a.isActive != b.isActive) return a.isActive ? -1 : 1;
  final target = (a.targetDate ?? '9999-12-31').compareTo(
    b.targetDate ?? '9999-12-31',
  );
  if (target != 0) return target;
  final name = a.name.toLowerCase().compareTo(b.name.toLowerCase());
  return name == 0 ? a.id.compareTo(b.id) : name;
}

DateTime _dateOnly(DateTime value) =>
    DateTime(value.year, value.month, value.day);

DateTime _parseIsoDate(String value, String label) {
  if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value)) {
    throw FormatException('$label must use YYYY-MM-DD');
  }
  final parsed = DateTime.tryParse(value);
  if (parsed == null || _isoDate(parsed) != value) {
    throw FormatException('$label is invalid');
  }
  return _dateOnly(parsed);
}

String _isoDate(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-'
    '${value.month.toString().padLeft(2, '0')}-'
    '${value.day.toString().padLeft(2, '0')}';

bool _sameDate(DateTime a, DateTime b) =>
    a.year == b.year && a.month == b.month && a.day == b.day;

DateTime _monthStart(DateTime value) => DateTime(value.year, value.month, 1);

DateTime _shiftMonth(DateTime value, int months) {
  final monthIndex = value.year * 12 + value.month - 1 + months;
  final year = monthIndex ~/ 12;
  final month = monthIndex % 12 + 1;
  return DateTime(year, month, 1);
}

String _monthLabel(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-'
    '${value.month.toString().padLeft(2, '0')}';

int _nonNegative(int value) => value < 0 ? 0 : value;

int _ceilDivide(int numerator, int denominator) {
  if (denominator <= 0) throw ArgumentError.value(denominator, 'denominator');
  return (numerator + denominator - 1) ~/ denominator;
}

int _roundHalfUpRatio(int numerator, int denominator) {
  if (denominator <= 0) throw ArgumentError.value(denominator, 'denominator');
  if (numerator < 0) {
    return -((-numerator + denominator ~/ 2) ~/ denominator);
  }
  return (numerator + denominator ~/ 2) ~/ denominator;
}

int _monthlyInterestCents(int balanceCents, int annualRateBps) =>
    _roundHalfUpRatio(balanceCents * annualRateBps, 120000);

int _amortizingPaymentCents(int balanceCents, int annualRateBps, int periods) {
  if (periods < 1) throw ArgumentError.value(periods, 'periods');
  if (balanceCents <= 0) {
    throw ArgumentError.value(balanceCents, 'balanceCents');
  }
  if (annualRateBps < 0) {
    throw ArgumentError.value(annualRateBps, 'annualRateBps');
  }
  if (annualRateBps == 0) {
    return _roundHalfUpRatio(balanceCents, periods);
  }

  const monthlyRateDenominator = 120000;
  final rate = BigInt.from(annualRateBps);
  final denominator = BigInt.from(monthlyRateDenominator);
  final compounded = (denominator + rate).pow(periods);
  final unchanged = denominator.pow(periods);
  final numerator = BigInt.from(balanceCents) * rate * compounded;
  final divisor = denominator * (compounded - unchanged);
  return _roundBigIntHalfUp(numerator, divisor);
}

int _roundBigIntHalfUp(BigInt numerator, BigInt denominator) {
  if (denominator <= BigInt.zero) {
    throw ArgumentError.value(denominator, 'denominator');
  }
  final rounded = (numerator + denominator ~/ BigInt.two) ~/ denominator;
  return rounded.toInt();
}

DateTime _addMonthsAnchored(DateTime value, int months, int anchorDay) {
  final monthIndex = value.year * 12 + value.month - 1 + months;
  final year = monthIndex ~/ 12;
  final month = monthIndex % 12 + 1;
  return DateTime(year, month, _clampDay(year, month, anchorDay));
}

int _clampDay(int year, int month, int anchorDay) {
  final lastDay = DateTime(year, month + 1, 0).day;
  if (anchorDay < 1) return 1;
  return anchorDay > lastDay ? lastDay : anchorDay;
}
