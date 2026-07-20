import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../app_controller.dart';
import '../models/finance_models.dart';
import '../theme/app_theme.dart';
import 'widgets.dart';

class LoanPayoffPage extends StatefulWidget {
  const LoanPayoffPage({
    super.key,
    required this.controller,
    required this.loanId,
  });

  final AppController controller;
  final String loanId;

  @override
  State<LoanPayoffPage> createState() => _LoanPayoffPageState();
}

class _LoanPayoffPageState extends State<LoanPayoffPage> {
  final formKey = GlobalKey<FormState>();
  final monthlyPayment = TextEditingController();
  final extraPayment = TextEditingController();
  PayoffComparison? comparison;
  String? error;
  bool showFullSchedule = false;

  @override
  void dispose() {
    monthlyPayment.dispose();
    extraPayment.dispose();
    super.dispose();
  }

  LoanRecord? get _loan {
    for (final loan in widget.controller.loanRecords) {
      if (loan.id == widget.loanId) return loan;
    }
    return null;
  }

  void _calculate() {
    final loan = _loan;
    if (loan == null || !formKey.currentState!.validate()) return;
    final regular = monthlyPayment.text.trim().isEmpty
        ? null
        : _parseCents(monthlyPayment.text);
    final extra = extraPayment.text.trim().isEmpty
        ? 0
        : _parseCents(extraPayment.text)!;
    try {
      final result = widget.controller.loanPayoffProjection(
        loan.id,
        monthlyPaymentCents: regular,
        extraMonthlyPaymentCents: extra,
      );
      setState(() {
        comparison = result;
        error = null;
        showFullSchedule = false;
      });
    } catch (exception) {
      setState(() {
        comparison = null;
        error = '$exception';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Payoff planner')),
      body: SafeArea(
        top: false,
        child: AnimatedBuilder(
          animation: widget.controller,
          builder: (context, _) {
            final loan = _loan;
            if (loan == null) {
              return const Center(
                child: EmptyState(
                  icon: Icons.account_balance_outlined,
                  title: 'Loan unavailable',
                  message: 'Sync this phone and try again.',
                ),
              );
            }
            final outstanding = widget.controller.outstandingForLoan(loan.id);
            return ListView(
              padding: const EdgeInsets.fromLTRB(18, 8, 18, 32),
              children: [
                ScreenHeader(
                  title: loan.name,
                  subtitle:
                      '${prettyType(loan.direction)} · ${loan.counterparty}',
                ),
                const SizedBox(height: 18),
                _LoanOverview(loan: loan, outstandingCents: outstanding),
                const SizedBox(height: 18),
                if (outstanding == 0 || loan.status == 'settled')
                  const SurfaceCard(
                    child: EmptyState(
                      icon: Icons.check_circle_outline,
                      title: 'Loan settled',
                      message: 'There is no remaining balance to project.',
                    ),
                  )
                else ...[
                  const SectionHeader(
                    title: 'What if I pay more?',
                    subtitle:
                        'Compare payoff time and interest without changing the loan',
                  ),
                  const SizedBox(height: 10),
                  SurfaceCard(child: _plannerForm(loan)),
                  if (error != null) ...[
                    const SizedBox(height: 12),
                    SurfaceCard(
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(
                            Icons.error_outline,
                            color: AppColors.negative,
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              error!,
                              style: const TextStyle(color: AppColors.negative),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                  if (comparison != null) ...[
                    const SizedBox(height: 20),
                    _ComparisonSummary(comparison: comparison!),
                    const SizedBox(height: 20),
                    _ScheduleSection(
                      entries: comparison!.withExtra.entries,
                      showFull: showFullSchedule,
                      onToggle: () =>
                          setState(() => showFullSchedule = !showFullSchedule),
                    ),
                  ],
                ],
                const SizedBox(height: 16),
                Text(
                  'This is a planning estimate. Loan terms and recorded payments are managed on the desktop.',
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

  Widget _plannerForm(LoanRecord loan) {
    return Form(
      key: formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextFormField(
            controller: monthlyPayment,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [
              FilteringTextInputFormatter.allow(RegExp(r'[0-9,.]')),
            ],
            decoration: InputDecoration(
              labelText: 'Regular monthly payment',
              hintText: loan.dueDate == null
                  ? 'Required because this loan has no due date'
                  : 'Optional · derived from the due date',
              prefixText: '€ ',
            ),
            validator: (value) {
              final text = (value ?? '').trim();
              if (text.isEmpty) {
                return loan.dueDate == null
                    ? 'Enter the regular monthly payment'
                    : null;
              }
              final cents = _parseCents(text);
              return cents == null || cents <= 0
                  ? 'Enter an amount greater than zero'
                  : null;
            },
          ),
          const SizedBox(height: 13),
          TextFormField(
            controller: extraPayment,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [
              FilteringTextInputFormatter.allow(RegExp(r'[0-9,.]')),
            ],
            decoration: const InputDecoration(
              labelText: 'Extra each month',
              hintText: '0.00',
              prefixText: '€ ',
            ),
            validator: (value) {
              final text = (value ?? '').trim();
              if (text.isEmpty) return null;
              final cents = _parseCents(text);
              return cents == null ? 'Enter a valid amount' : null;
            },
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: _calculate,
            icon: const Icon(Icons.calculate_outlined, size: 18),
            label: const Text('Calculate payoff'),
          ),
        ],
      ),
    );
  }
}

class _LoanOverview extends StatelessWidget {
  const _LoanOverview({required this.loan, required this.outstandingCents});

  final LoanRecord loan;
  final int outstandingCents;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(20),
    decoration: BoxDecoration(
      color: AppColors.ink,
      borderRadius: BorderRadius.circular(8),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'OUTSTANDING PRINCIPAL',
          style: TextStyle(
            color: Color(0xFFAFC2BC),
            fontSize: 11,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 7),
        FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: Text(
            money(outstandingCents),
            style: Theme.of(
              context,
            ).textTheme.displaySmall?.copyWith(color: Colors.white),
          ),
        ),
        const SizedBox(height: 14),
        Wrap(
          spacing: 7,
          runSpacing: 7,
          children: [
            _DarkPill('${_rate(loan.interestRateBps)} APR'),
            if (loan.dueDate != null)
              _DarkPill('Due ${friendlyDate(loan.dueDate!)}'),
          ],
        ),
      ],
    ),
  );
}

class _DarkPill extends StatelessWidget {
  const _DarkPill(this.label);

  final String label;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
    decoration: BoxDecoration(
      color: Colors.white.withValues(alpha: .10),
      borderRadius: BorderRadius.circular(6),
    ),
    child: Text(
      label,
      style: const TextStyle(
        color: Colors.white,
        fontSize: 11,
        fontWeight: FontWeight.w600,
      ),
    ),
  );
}

class _ComparisonSummary extends StatelessWidget {
  const _ComparisonSummary({required this.comparison});

  final PayoffComparison comparison;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(
          title: 'Payoff comparison',
          subtitle: 'Based on the monthly amounts above',
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: _ComparisonTile(
                label: 'Regular plan',
                value: friendlyDate(comparison.withoutExtra.payoffDate),
                detail:
                    '${money(comparison.withoutExtra.totalInterestPaidCents)} interest',
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _ComparisonTile(
                label: 'With extra',
                value: friendlyDate(comparison.withExtra.payoffDate),
                detail:
                    '${money(comparison.withExtra.totalInterestPaidCents)} interest',
                highlighted: true,
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        SurfaceCard(
          child: Row(
            children: [
              const Icon(Icons.savings_outlined, color: AppColors.positive),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  '${money(comparison.interestSavedCents)} interest saved',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              Text(
                '${comparison.monthsSaved} mo sooner',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _ComparisonTile extends StatelessWidget {
  const _ComparisonTile({
    required this.label,
    required this.value,
    required this.detail,
    this.highlighted = false,
  });

  final String label;
  final String value;
  final String detail;
  final bool highlighted;

  @override
  Widget build(BuildContext context) => Container(
    constraints: const BoxConstraints(minHeight: 112),
    padding: const EdgeInsets.all(13),
    decoration: BoxDecoration(
      color: highlighted ? AppColors.primarySoft : AppColors.surface,
      border: Border.all(
        color: highlighted ? AppColors.primary : AppColors.border,
      ),
      borderRadius: BorderRadius.circular(8),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: Theme.of(context).textTheme.bodySmall),
        const SizedBox(height: 7),
        Text(
          value,
          maxLines: 2,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 5),
        Text(detail, style: Theme.of(context).textTheme.bodySmall),
      ],
    ),
  );
}

class _ScheduleSection extends StatelessWidget {
  const _ScheduleSection({
    required this.entries,
    required this.showFull,
    required this.onToggle,
  });

  final List<AmortizationEntry> entries;
  final bool showFull;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    final visible = showFull ? entries : entries.take(12).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(
          title: 'Payment schedule',
          subtitle: '${entries.length} monthly payments',
        ),
        const SizedBox(height: 10),
        SurfaceCard(
          padding: EdgeInsets.zero,
          child: Column(
            children: [
              for (var index = 0; index < visible.length; index++) ...[
                _ScheduleRow(entry: visible[index]),
                if (index != visible.length - 1)
                  const Divider(height: 1, indent: 54),
              ],
            ],
          ),
        ),
        if (entries.length > 12) ...[
          const SizedBox(height: 8),
          Center(
            child: TextButton.icon(
              onPressed: onToggle,
              icon: Icon(
                showFull ? Icons.expand_less : Icons.expand_more,
                size: 18,
              ),
              label: Text(showFull ? 'Show first year' : 'Show full schedule'),
            ),
          ),
        ],
      ],
    );
  }
}

class _ScheduleRow extends StatelessWidget {
  const _ScheduleRow({required this.entry});

  final AmortizationEntry entry;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 30,
          height: 30,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: AppColors.primarySoft,
            borderRadius: BorderRadius.circular(7),
          ),
          child: Text(
            '${entry.period}',
            style: const TextStyle(
              color: AppColors.primary,
              fontSize: 11,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                friendlyDate(entry.date),
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 3),
              Text(
                '${money(entry.principalPortionCents)} principal · ${money(entry.interestPortionCents)} interest',
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
        const SizedBox(width: 8),
        Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              money(entry.paymentCents),
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 3),
            Text(
              '${money(entry.remainingBalanceCents)} left',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ],
    ),
  );
}

String _rate(int basisPoints) {
  final value = basisPoints / 100;
  return '${value.toStringAsFixed(value == value.roundToDouble() ? 0 : 2)}%';
}

int? _parseCents(String value) {
  final normalized = value.trim().replaceAll(',', '.');
  final match = RegExp(r'^(\d+)(?:\.(\d{1,2}))?$').firstMatch(normalized);
  if (match == null) return null;
  final whole = int.tryParse(match.group(1)!);
  if (whole == null) return null;
  final fractional = (match.group(2) ?? '').padRight(2, '0');
  return whole * 100 + int.parse(fractional);
}
