import 'package:flutter_test/flutter_test.dart';
import 'package:money_manager/app_controller.dart';
import 'package:money_manager/data/local_database.dart';
import 'package:money_manager/data/sync_client.dart';
import 'package:money_manager/models/finance_models.dart';

void main() {
  group('portable finance records', () {
    test('parse new entities and the transaction goal link', () {
      final category = CategoryRecord.fromJson({
        'id': 'category-1',
        'name': 'Groceries',
        'type': 'expense',
        'is_active': 1,
      });
      final budget = BudgetRecord.fromJson({
        'id': 'budget-1',
        'category_id': 'category-1',
        'period': 'monthly',
        'amount_cents': 25013,
        'rollover': 1,
        'start_date': '2026-07-01',
        'is_active': 1,
      });
      final snapshot = NetWorthSnapshotRecord.fromJson({
        'date': '2026-07-20',
        'assets_cents': 125000,
        'liabilities_cents': 25000,
        'revision': 2,
      });
      final goal = SavingsGoalRecord.fromJson({
        'id': 'goal-1',
        'name': 'Emergency fund',
        'target_amount_cents': 500000,
        'target_date': '2027-01-31',
        'linked_account_id': 'account-1',
        'is_active': 1,
        'created_at': '2026-07-20T10:00:00.000Z',
        'revision': 3,
      });
      final loan = LoanRecord.fromJson({
        'id': 'loan-1',
        'direction': 'borrowed',
        'name': 'Car',
        'counterparty': 'Bank',
        'principal_cents': 1000000,
        'account_id': 'account-1',
        'start_date': '2026-01-01',
        'due_date': '2028-01-01',
        'interest_rate_bps': 600,
        'status': 'active',
        'revision': 1,
      });
      final payment = LoanPaymentRecord.fromJson({
        'id': 'payment-1',
        'loan_id': 'loan-1',
        'account_id': 'account-1',
        'transaction_id': 'transaction-1',
        'amount_cents': 10000,
        'date': '2026-07-01',
        'revision': 1,
      });
      final transaction = TransactionRecord.fromJson({
        'id': 'transaction-1',
        'date': '2026-07-01',
        'type': 'transfer_in',
        'account_id': 'account-1',
        'amount_cents': 10000,
        'savings_goal_id': 'goal-1',
      });

      expect(category.name, 'Groceries');
      expect(budget.amountCents, 25013);
      expect(budget.rollover, isTrue);
      expect(snapshot.netWorthCents, 100000);
      expect(goal.linkedAccountId, 'account-1');
      expect(loan.interestRateBps, 600);
      expect(payment.amountCents, 10000);
      expect(transaction.savingsGoalId, 'goal-1');
    });
  });

  test(
    'monthly budget status handles cumulative rollover and overspending',
    () {
      final controller = _controller()
        ..categories = const [
          CategoryRecord(
            id: 'household',
            name: 'Household',
            type: 'expense',
            isActive: true,
          ),
        ]
        ..budgets = const [
          BudgetRecord(
            id: 'budget-1',
            categoryId: 'household',
            period: 'monthly',
            amountCents: 10000,
            rollover: true,
            startDate: '2026-01-15',
            isActive: true,
          ),
        ]
        ..transactions = const [
          TransactionRecord(
            id: 'before',
            date: '2026-01-10',
            type: 'expense',
            accountId: 'account-1',
            amountCents: -8000,
            description: 'Before budget',
            categoryId: 'household',
          ),
          TransactionRecord(
            id: 'january',
            date: '2026-01-20',
            type: 'expense',
            accountId: 'account-1',
            amountCents: -4000,
            description: 'January',
            categoryId: 'household',
          ),
          TransactionRecord(
            id: 'february',
            date: '2026-02-02',
            type: 'expense',
            accountId: 'account-1',
            amountCents: -3000,
            description: 'February',
            categoryId: 'household',
          ),
          TransactionRecord(
            id: 'march',
            date: '2026-03-02',
            type: 'expense',
            accountId: 'account-1',
            amountCents: -25000,
            description: 'March overspend',
            categoryId: 'household',
          ),
        ];

      final march = controller
          .budgetStatuses(referenceDate: DateTime(2026, 3, 1))
          .single;
      final april = controller
          .budgetStatuses(referenceDate: DateTime(2026, 4, 1))
          .single;

      expect(march.rolledOverFromPriorCents, 13000);
      expect(march.limitCents, 23000);
      expect(march.spentCents, 25000);
      expect(march.percentUsedBasisPoints, 10870);
      expect(march.isOverspent, isTrue);
      expect(april.rolledOverFromPriorCents, 0);
      expect(april.limitCents, 10000);
    },
  );

  test('goal progress supports linked accounts and tagged transfers', () {
    final controller = _controller();
    const current = AccountRecord(
      id: 'current',
      name: 'Current',
      type: 'current_account',
      openingBalanceCents: 100000,
      isActive: true,
    );
    const savings = AccountRecord(
      id: 'savings',
      name: 'Savings',
      type: 'savings_account',
      openingBalanceCents: 25000,
      isActive: true,
    );
    controller
      ..allAccounts = const [current, savings]
      ..accounts = const [current, savings]
      ..savingsGoals = const [
        SavingsGoalRecord(
          id: 'linked',
          name: 'Deposit',
          targetAmountCents: 100000,
          targetDate: '2026-12-20',
          linkedAccountId: 'savings',
          isActive: true,
          createdAt: '2026-01-01T00:00:00.000Z',
          revision: 1,
        ),
        SavingsGoalRecord(
          id: 'manual',
          name: 'Holiday',
          targetAmountCents: 50000,
          targetDate: '2026-12-31',
          isActive: true,
          createdAt: '2026-01-01T00:00:00.000Z',
          revision: 1,
        ),
      ]
      ..transactions = const [
        TransactionRecord(
          id: 'out',
          date: '2026-07-10',
          type: 'transfer_out',
          accountId: 'current',
          amountCents: -10000,
          description: 'Contribution',
          savingsGoalId: 'manual',
        ),
        TransactionRecord(
          id: 'in',
          date: '2026-07-10',
          type: 'transfer_in',
          accountId: 'savings',
          amountCents: 10000,
          description: 'Contribution',
          savingsGoalId: 'manual',
        ),
        TransactionRecord(
          id: 'future',
          date: '2026-08-10',
          type: 'transfer_in',
          accountId: 'current',
          amountCents: 10000,
          description: 'Future contribution',
          savingsGoalId: 'manual',
        ),
      ];

    final linked = controller.goalProgress(
      'linked',
      referenceDate: DateTime(2026, 7, 20),
    );
    final manual = controller.goalProgress(
      'manual',
      referenceDate: DateTime(2026, 7, 20),
    );

    expect(linked.currentAmountCents, 35000);
    expect(linked.requiredMonthlyContributionCents, 13000);
    expect(manual.currentAmountCents, 10000);
    expect(manual.percentCompleteBasisPoints, 2000);
    expect(manual.requiredMonthlyContributionCents, 6667);
    expect(manual.onTrack, isFalse);
  });

  test('savings health uses exact cents and completed expense months', () {
    final controller = _controller();
    const account = AccountRecord(
      id: 'current',
      name: 'Current',
      type: 'current_account',
      openingBalanceCents: 1200000,
      isActive: true,
    );
    controller
      ..allAccounts = const [account]
      ..accounts = const [account]
      ..transactions = [
        for (var month = 1; month <= 6; month++)
          TransactionRecord(
            id: 'expense-$month',
            date: '2026-${month.toString().padLeft(2, '0')}-10',
            type: 'expense',
            accountId: 'current',
            amountCents: -100000,
            description: 'Living costs',
          ),
        const TransactionRecord(
          id: 'income-april',
          date: '2026-04-01',
          type: 'income',
          accountId: 'current',
          amountCents: 200000,
          description: 'Income',
        ),
        const TransactionRecord(
          id: 'income-may',
          date: '2026-05-01',
          type: 'income',
          accountId: 'current',
          amountCents: 100000,
          description: 'Income',
        ),
      ];

    expect(
      controller.savingsRateBasisPoints(
        months: 3,
        referenceDate: DateTime(2026, 6, 15),
      ),
      0,
    );
    expect(
      controller.emergencyFundCoverageHundredths(
        referenceDate: DateTime(2026, 7, 20),
      ),
      900,
    );
  });

  test('savings rate is zero when the period has no income', () {
    final controller = _controller()
      ..transactions = const [
        TransactionRecord(
          id: 'expense-only',
          date: '2026-07-10',
          type: 'expense',
          accountId: 'current',
          amountCents: -25000,
          description: 'Living costs',
        ),
      ];

    expect(
      controller.savingsRateBasisPoints(referenceDate: DateTime(2026, 7, 20)),
      0,
    );
  });

  test('net worth history prefers snapshots and backfills missing cutoffs', () {
    final controller = _controller();
    const account = AccountRecord(
      id: 'current',
      name: 'Current',
      type: 'current_account',
      openingBalanceCents: 100000,
      isActive: true,
    );
    controller
      ..allAccounts = const [account]
      ..accounts = const [account]
      ..transactions = const [
        TransactionRecord(
          id: 'jan',
          date: '2026-01-10',
          type: 'expense',
          accountId: 'current',
          amountCents: -10000,
          description: 'January',
        ),
        TransactionRecord(
          id: 'borrow',
          date: '2026-02-05',
          type: 'adjustment',
          accountId: 'current',
          amountCents: 50000,
          description: 'Loan proceeds',
          loanId: 'loan-1',
        ),
        TransactionRecord(
          id: 'feb',
          date: '2026-02-10',
          type: 'expense',
          accountId: 'current',
          amountCents: -20000,
          description: 'February',
        ),
        TransactionRecord(
          id: 'mar-income',
          date: '2026-03-01',
          type: 'income',
          accountId: 'current',
          amountCents: 5000,
          description: 'March',
        ),
        TransactionRecord(
          id: 'payment-transaction',
          date: '2026-03-05',
          type: 'expense',
          accountId: 'current',
          amountCents: -10000,
          description: 'Loan payment',
          loanId: 'loan-1',
        ),
      ]
      ..loanRecords = const [
        LoanRecord(
          id: 'loan-1',
          direction: 'borrowed',
          name: 'Loan',
          counterparty: 'Bank',
          principalCents: 50000,
          accountId: 'current',
          startDate: '2026-02-05',
          interestRateBps: 0,
          status: 'active',
          revision: 1,
        ),
      ]
      ..loanPayments = const [
        LoanPaymentRecord(
          id: 'payment-1',
          loanId: 'loan-1',
          accountId: 'current',
          transactionId: 'payment-transaction',
          amountCents: 10000,
          date: '2026-03-05',
          revision: 1,
        ),
      ]
      ..netWorthSnapshots = const [
        NetWorthSnapshotRecord(
          date: '2026-01-31',
          assetsCents: 12345,
          liabilitiesCents: 2345,
          revision: 1,
        ),
      ];

    final points = controller.netWorthHistory(
      months: 3,
      referenceDate: DateTime(2026, 3, 20),
    );

    expect(points.map((point) => point.date), [
      '2026-01-31',
      '2026-02-28',
      '2026-03-20',
    ]);
    expect(points.first.netWorthCents, 10000);
    expect(points.first.estimated, isFalse);
    expect(points[1].netWorthCents, 70000);
    expect(points[2].netWorthCents, 75000);
    expect(points[1].estimated, isTrue);
  });

  test('loan projection matches a 24 month six-percent fixture', () {
    final controller = _controller()
      ..loanRecords = const [
        LoanRecord(
          id: 'loan-1',
          direction: 'borrowed',
          name: 'Round loan',
          counterparty: 'Bank',
          principalCents: 1000000,
          accountId: 'current',
          startDate: '2026-01-01',
          dueDate: '2028-01-01',
          interestRateBps: 600,
          status: 'active',
          revision: 1,
        ),
      ];

    final schedule = controller.amortizationSchedule(
      'loan-1',
      referenceDate: DateTime(2026, 1, 1),
    );
    final comparison = controller.loanPayoffProjection(
      'loan-1',
      extraMonthlyPaymentCents: 5000,
      referenceDate: DateTime(2026, 1, 1),
    );
    final unchanged = controller.loanPayoffProjection(
      'loan-1',
      referenceDate: DateTime(2026, 1, 1),
    );

    expect(schedule, hasLength(24));
    expect(schedule.first.paymentCents, 44321);
    expect(schedule.first.interestPortionCents, 5000);
    expect(schedule.first.principalPortionCents, 39321);
    expect(schedule.first.remainingBalanceCents, 960679);
    expect(schedule.last.paymentCents, 44311);
    expect(schedule.last.remainingBalanceCents, 0);
    expect(comparison.withoutExtra.totalInterestPaidCents, 63694);
    expect(comparison.withExtra.entries.length, lessThan(24));
    expect(comparison.interestSavedCents, greaterThan(0));
    expect(unchanged.monthsSaved, 0);
    expect(unchanged.interestSavedCents, 0);
  });

  test('loan planning requires a payment when no due date is available', () {
    final controller = _controller()
      ..loanRecords = const [
        LoanRecord(
          id: 'open-loan',
          direction: 'borrowed',
          name: 'Open-ended loan',
          counterparty: 'Family',
          principalCents: 120000,
          accountId: 'current',
          startDate: '2026-01-01',
          interestRateBps: 0,
          status: 'active',
          revision: 1,
        ),
      ];

    expect(
      () => controller.amortizationSchedule(
        'open-loan',
        referenceDate: DateTime(2026, 7, 20),
      ),
      throwsStateError,
    );
    final schedule = controller.amortizationSchedule(
      'open-loan',
      monthlyPaymentCents: 10000,
      referenceDate: DateTime(2026, 7, 20),
    );
    expect(schedule, hasLength(12));
    expect(schedule.last.remainingBalanceCents, 0);
  });

  test('multi-loan strategies use snowball and avalanche priority', () {
    final controller = _controller()
      ..loanRecords = const [
        LoanRecord(
          id: 'small',
          direction: 'borrowed',
          name: 'Small balance',
          counterparty: 'A',
          principalCents: 50000,
          accountId: 'current',
          startDate: '2026-01-01',
          dueDate: '2027-07-01',
          interestRateBps: 300,
          status: 'active',
          revision: 1,
        ),
        LoanRecord(
          id: 'high-rate',
          direction: 'borrowed',
          name: 'High rate',
          counterparty: 'B',
          principalCents: 100000,
          accountId: 'current',
          startDate: '2026-01-01',
          dueDate: '2027-07-01',
          interestRateBps: 1200,
          status: 'active',
          revision: 1,
        ),
      ];

    final snowball = controller.multiLoanPayoffScenario(
      strategy: 'snowball',
      extraBudgetCents: 5000,
      referenceDate: DateTime(2026, 7, 1),
    );
    final avalanche = controller.multiLoanPayoffScenario(
      strategy: 'avalanche',
      extraBudgetCents: 5000,
      referenceDate: DateTime(2026, 7, 1),
    );

    expect(snowball.plans.first.loanId, 'small');
    expect(avalanche.plans.first.loanId, 'high-rate');
    expect(snowball.payoffDate, isNotNull);
    expect(avalanche.payoffDate, isNotNull);
  });

  test('manual goal contributions queue the dedicated command', () async {
    final database = _FakeDatabase()
      ..rows['accounts'] = [
        _stored('accounts', 'source', {
          'id': 'source',
          'name': 'Current',
          'type': 'current_account',
          'opening_balance_cents': 10000,
          'is_active': 1,
        }),
        _stored('accounts', 'target', {
          'id': 'target',
          'name': 'Savings',
          'type': 'savings_account',
          'opening_balance_cents': 0,
          'is_active': 1,
        }),
      ]
      ..rows['savings_goals'] = [
        _stored('savings_goals', 'goal-1', {
          'id': 'goal-1',
          'name': 'Holiday',
          'target_amount_cents': 50000,
          'is_active': 1,
          'revision': 1,
        }),
      ];
    final controller = AppController(
      database: database,
      syncClient: SyncClient(),
    );
    await controller.reload();

    await controller.queueGoalContribution(
      goalId: 'goal-1',
      sourceAccountId: 'source',
      targetAccountId: 'target',
      amountCents: 1250,
      date: '2026-07-20',
      notes: '  First step  ',
    );

    expect(database.queued, hasLength(1));
    expect(database.queued.single.type, 'add_goal_contribution');
    expect(database.queued.single.payload, {
      'goal_id': 'goal-1',
      'source_account_id': 'source',
      'target_account_id': 'target',
      'amount_cents': 1250,
      'date': '2026-07-20',
      'notes': 'First step',
    });
  });

  test('sync acknowledges the locally applied entity set version', () async {
    final database = _SyncDatabase();
    final syncClient = _RecordingSyncClient();
    final controller = AppController(database: database, syncClient: syncClient)
      ..credentials = const PairingCredentials(
        url: 'https://desktop.local:8765',
        deviceId: 'device-1',
        token: 'token',
        fingerprint: 'abcdef0123456789',
      );

    await controller.syncNow();

    expect(syncClient.cursor, 42);
    expect(syncClient.entitySetVersion, 0);
    expect(database.applied?['entity_set_version'], 1);
  });
}

AppController _controller() =>
    AppController(database: LocalDatabase(), syncClient: SyncClient());

StoredRecord _stored(String entity, String id, Map<String, dynamic> payload) =>
    StoredRecord(entity: entity, id: id, revision: 1, payload: payload);

class _FakeDatabase extends LocalDatabase {
  final Map<String, List<StoredRecord>> rows = {};
  final List<PendingCommand> queued = [];

  @override
  Future<List<StoredRecord>> records(String entity) async =>
      List.unmodifiable(rows[entity] ?? const []);

  @override
  Future<List<PendingCommand>> pendingCommands({
    bool includeFailed = true,
  }) async => List.unmodifiable(queued);

  @override
  Future<void> queueCommand(PendingCommand command) async {
    queued.add(command);
  }

  @override
  Future<String?> state(String key) async => null;
}

class _SyncDatabase extends _FakeDatabase {
  Map<String, dynamic>? applied;

  @override
  Future<int> cursor() async => 42;

  @override
  Future<int> entitySetVersion() async => 0;

  @override
  Future<void> applyExchange(Map<String, dynamic> response) async {
    applied = response;
  }
}

class _RecordingSyncClient extends SyncClient {
  int? cursor;
  int? entitySetVersion;

  @override
  Future<Map<String, dynamic>> sync({
    required PairingCredentials credentials,
    required int cursor,
    required int entitySetVersion,
    required List<PendingCommand> commands,
  }) async {
    this.cursor = cursor;
    this.entitySetVersion = entitySetVersion;
    return {
      'protocol_version': 1,
      'entity_set_version': 1,
      'snapshot': true,
      'cursor': 43,
      'has_more': false,
      'commands': <dynamic>[],
      'changes': <dynamic>[],
    };
  }
}
