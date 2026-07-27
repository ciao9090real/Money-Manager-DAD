import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../app_controller.dart';
import '../models/finance_models.dart';
import '../theme/app_theme.dart';
import 'widgets.dart';

class InsightsPage extends StatefulWidget {
  const InsightsPage({super.key, required this.controller});

  final AppController controller;

  @override
  State<InsightsPage> createState() => _InsightsPageState();
}

class _InsightsPageState extends State<InsightsPage> {
  int months = 6;

  @override
  Widget build(BuildContext context) {
    final report = widget.controller.spendingReport(months: months);
    final hasActivity = report.incomeCents > 0 || report.expenseCents > 0;
    final clues = _clues(report);
    return Scaffold(
      appBar: AppBar(title: const Text('Insights')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(18, 6, 18, 40),
        children: [
          const ScreenHeader(
            title: 'Your money, translated',
            subtitle: 'Patterns from the records already on this phone',
          ),
          const SizedBox(height: 18),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: SegmentedButton<int>(
              segments: const [
                ButtonSegment(value: 1, label: Text('1 month')),
                ButtonSegment(value: 3, label: Text('3 months')),
                ButtonSegment(value: 6, label: Text('6 months')),
                ButtonSegment(value: 12, label: Text('1 year')),
              ],
              selected: {months},
              showSelectedIcon: false,
              onSelectionChanged: (selection) =>
                  setState(() => months = selection.first),
            ),
          ),
          const SizedBox(height: 18),
          _StoryHero(report: report),
          const SizedBox(height: 14),
          _MetricGrid(report: report),
          const SizedBox(height: 24),
          const SectionHeader(
            title: 'Recorded cash flow',
            subtitle: 'Income and spending; transfers stay out of the way',
          ),
          const SizedBox(height: 9),
          SurfaceCard(
            child: hasActivity
                ? Column(
                    children: [
                      const _ChartLegend(),
                      const SizedBox(height: 14),
                      SizedBox(
                        height: 190,
                        child: _CashFlowChart(periods: report.cashFlow),
                      ),
                    ],
                  )
                : const EmptyState(
                    icon: Icons.query_stats,
                    title: 'Nothing to translate yet',
                    message:
                        'Income and spending in this period will build the report.',
                  ),
          ),
          const SizedBox(height: 24),
          const SectionHeader(
            title: 'Where spending went',
            subtitle: 'Categories ranked by their share of the selected period',
          ),
          const SizedBox(height: 9),
          SurfaceCard(
            padding: EdgeInsets.zero,
            child: report.categories.isEmpty
                ? const EmptyState(
                    icon: Icons.category_outlined,
                    title: 'No spending categories yet',
                    message:
                        'Categorized expenses will make this breakdown useful.',
                  )
                : Column(
                    children: [
                      for (
                        var index = 0;
                        index < math.min(6, report.categories.length);
                        index++
                      ) ...[
                        _CategoryRow(category: report.categories[index]),
                        if (index != math.min(6, report.categories.length) - 1)
                          const Divider(height: 1, indent: 18, endIndent: 18),
                      ],
                    ],
                  ),
          ),
          const SizedBox(height: 24),
          const SectionHeader(
            title: 'Useful clues',
            subtitle: 'Observations, not predictions',
          ),
          const SizedBox(height: 9),
          SurfaceCard(
            padding: EdgeInsets.zero,
            child: Column(
              children: [
                for (var index = 0; index < clues.length; index++) ...[
                  _ClueRow(clue: clues[index]),
                  if (index != clues.length - 1)
                    const Divider(height: 1, indent: 58),
                ],
              ],
            ),
          ),
          const SizedBox(height: 14),
          Text(
            'Calculated locally from ${friendlyDate(report.startDate)} to '
            '${friendlyDate(report.endDate)}. Sync refreshes the source records; '
            'the report itself never leaves this device.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _StoryHero extends StatelessWidget {
  const _StoryHero({required this.report});

  final SpendingReport report;

  @override
  Widget build(BuildContext context) {
    final hasActivity = report.incomeCents > 0 || report.expenseCents > 0;
    final positive = report.netCents >= 0;
    final headline = !hasActivity
        ? 'The little report creature is waiting for some numbers.'
        : positive
        ? 'You kept ${money(report.netCents)} after recorded spending.'
        : 'Spending ran ${money(-report.netCents)} ahead of recorded income.';
    final detail = _comparisonCopy(report);
    return Semantics(
      container: true,
      label: 'Report summary. $headline $detail',
      child: Container(
        padding: const EdgeInsets.fromLTRB(20, 20, 18, 20),
        decoration: BoxDecoration(
          color: AppColors.primary,
          borderRadius: BorderRadius.circular(22),
          boxShadow: const [
            BoxShadow(
              color: Color(0x1C000000),
              blurRadius: 22,
              offset: Offset(0, 7),
            ),
          ],
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'THE SHORT VERSION',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: Colors.white.withValues(alpha: .7),
                      fontWeight: FontWeight.w800,
                      letterSpacing: 1.1,
                    ),
                  ),
                  const SizedBox(height: 9),
                  Text(
                    headline,
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      color: Colors.white,
                      fontSize: 22,
                      height: 1.18,
                    ),
                  ),
                  const SizedBox(height: 9),
                  Text(
                    detail,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Colors.white.withValues(alpha: .78),
                      height: 1.35,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            _ReportBuddy(positive: positive, awake: hasActivity),
          ],
        ),
      ),
    );
  }
}

class _ReportBuddy extends StatelessWidget {
  const _ReportBuddy({required this.positive, required this.awake});

  final bool positive;
  final bool awake;

  @override
  Widget build(BuildContext context) {
    final reduceMotion = MediaQuery.disableAnimationsOf(context);
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: reduceMotion ? 1 : 0, end: 1),
      duration: const Duration(milliseconds: 650),
      curve: Curves.elasticOut,
      builder: (context, value, child) => Transform.translate(
        offset: Offset(0, (1 - value) * 9),
        child: Transform.rotate(angle: (1 - value) * -.05, child: child),
      ),
      child: CustomPaint(
        size: const Size(66, 58),
        painter: _ReportBuddyPainter(positive: positive, awake: awake),
      ),
    );
  }
}

class _ReportBuddyPainter extends CustomPainter {
  const _ReportBuddyPainter({required this.positive, required this.awake});

  final bool positive;
  final bool awake;

  @override
  void paint(Canvas canvas, Size size) {
    final body = Paint()..color = Colors.white.withValues(alpha: .93);
    final ink = Paint()
      ..color = AppColors.primary
      ..strokeWidth = 2
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;
    final face = RRect.fromRectAndRadius(
      Rect.fromLTWH(4, 7, size.width - 8, size.height - 11),
      const Radius.circular(17),
    );
    canvas.drawRRect(face, body);
    canvas.drawLine(const Offset(18, 7), const Offset(13, 1), ink);
    canvas.drawLine(
      Offset(size.width - 18, 7),
      Offset(size.width - 13, 1),
      ink,
    );

    if (awake) {
      final pupil = Paint()
        ..color = AppColors.primary
        ..style = PaintingStyle.fill;
      canvas.drawCircle(const Offset(24, 28), 3, pupil);
      canvas.drawCircle(Offset(size.width - 24, 28), 3, pupil);
    } else {
      canvas.drawLine(const Offset(20, 28), const Offset(27, 28), ink);
      canvas.drawLine(
        Offset(size.width - 27, 28),
        Offset(size.width - 20, 28),
        ink,
      );
    }
    final mouth = Path()..moveTo(size.width / 2 - 7, 38);
    if (positive) {
      mouth.quadraticBezierTo(size.width / 2, 45, size.width / 2 + 7, 38);
    } else {
      mouth.quadraticBezierTo(size.width / 2, 33, size.width / 2 + 7, 38);
    }
    canvas.drawPath(mouth, ink);
  }

  @override
  bool shouldRepaint(_ReportBuddyPainter oldDelegate) =>
      oldDelegate.positive != positive || oldDelegate.awake != awake;
}

class _MetricGrid extends StatelessWidget {
  const _MetricGrid({required this.report});

  final SpendingReport report;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final width = (constraints.maxWidth - 12) / 2;
      return Wrap(
        spacing: 12,
        runSpacing: 12,
        children: [
          SizedBox(
            width: width,
            child: MetricCard(
              label: 'Recorded income',
              value: money(report.incomeCents),
              icon: Icons.south_west,
              tone: AppColors.positive,
            ),
          ),
          SizedBox(
            width: width,
            child: MetricCard(
              label: 'Recorded spending',
              value: money(report.expenseCents),
              icon: Icons.north_east,
              tone: AppColors.negative,
            ),
          ),
          SizedBox(
            width: constraints.maxWidth,
            child: MetricCard(
              label: 'Average monthly spending',
              value: money(report.averageMonthlyExpenseCents),
              icon: Icons.calendar_view_month,
              tone: AppColors.ink,
            ),
          ),
        ],
      );
    },
  );
}

class _ChartLegend extends StatelessWidget {
  const _ChartLegend();

  @override
  Widget build(BuildContext context) => const Row(
    mainAxisAlignment: MainAxisAlignment.end,
    children: [
      _LegendDot(color: AppColors.positive, label: 'Income'),
      SizedBox(width: 14),
      _LegendDot(color: AppColors.warning, label: 'Spending'),
    ],
  );
}

class _LegendDot extends StatelessWidget {
  const _LegendDot({required this.color, required this.label});

  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(
        width: 8,
        height: 8,
        decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      ),
      const SizedBox(width: 5),
      Text(label, style: Theme.of(context).textTheme.bodySmall),
    ],
  );
}

class _CashFlowChart extends StatelessWidget {
  const _CashFlowChart({required this.periods});

  final List<CashFlowPeriod> periods;

  @override
  Widget build(BuildContext context) {
    final totalIncome = periods.fold<int>(
      0,
      (sum, period) => sum + period.incomeCents,
    );
    final totalSpending = periods.fold<int>(
      0,
      (sum, period) => sum + period.expenseCents,
    );
    return Semantics(
      label:
          'Cash flow chart. Total income ${money(totalIncome)}. '
          'Total spending ${money(totalSpending)}.',
      image: true,
      child: CustomPaint(
        painter: _CashFlowPainter(periods),
        size: Size.infinite,
      ),
    );
  }
}

class _CashFlowPainter extends CustomPainter {
  const _CashFlowPainter(this.periods);

  final List<CashFlowPeriod> periods;

  @override
  void paint(Canvas canvas, Size size) {
    if (periods.isEmpty) return;
    const labelHeight = 27.0;
    const topPadding = 8.0;
    final chartHeight = size.height - labelHeight - topPadding;
    final maximum = periods.fold<int>(
      1,
      (value, period) =>
          math.max(value, math.max(period.incomeCents, period.expenseCents)),
    );
    final groupWidth = size.width / periods.length;
    final barWidth = math.min(13.0, math.max(4.0, (groupWidth - 10) / 2));
    final baseline = topPadding + chartHeight;
    final baselinePaint = Paint()
      ..color = AppColors.border
      ..strokeWidth = 1;
    canvas.drawLine(
      Offset(0, baseline),
      Offset(size.width, baseline),
      baselinePaint,
    );

    for (var index = 0; index < periods.length; index++) {
      final period = periods[index];
      final center = groupWidth * index + groupWidth / 2;
      _drawBar(
        canvas,
        center - barWidth - 2,
        baseline,
        barWidth,
        chartHeight * period.incomeCents / maximum,
        AppColors.positive,
      );
      _drawBar(
        canvas,
        center + 2,
        baseline,
        barWidth,
        chartHeight * period.expenseCents / maximum,
        AppColors.warning,
      );
      final parsed = DateTime.tryParse('${period.month}-01');
      final label = parsed == null
          ? period.month
          : DateFormat.MMM().format(parsed);
      final textPainter = TextPainter(
        text: TextSpan(
          text: label,
          style: const TextStyle(
            color: AppColors.muted,
            fontFamily: 'Inter',
            fontSize: 10,
            fontWeight: FontWeight.w600,
          ),
        ),
        textDirection: TextDirection.ltr,
        maxLines: 1,
      )..layout(maxWidth: groupWidth);
      textPainter.paint(
        canvas,
        Offset(center - textPainter.width / 2, baseline + 8),
      );
    }
  }

  void _drawBar(
    Canvas canvas,
    double left,
    double baseline,
    double width,
    double height,
    Color color,
  ) {
    if (height <= 0) return;
    final rect = RRect.fromRectAndRadius(
      Rect.fromLTWH(left, baseline - height, width, height),
      const Radius.circular(4),
    );
    canvas.drawRRect(rect, Paint()..color = color);
  }

  @override
  bool shouldRepaint(_CashFlowPainter oldDelegate) =>
      oldDelegate.periods != periods;
}

class _CategoryRow extends StatelessWidget {
  const _CategoryRow({required this.category});

  final CategorySpending category;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
    child: Column(
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                category.name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
            ),
            const SizedBox(width: 12),
            AmountText(-category.amountCents, emphasized: true),
          ],
        ),
        const SizedBox(height: 8),
        FinanceProgressBar(
          percent: category.sharePercent,
          tone: category.categoryId == null
              ? AppColors.warning
              : AppColors.primary,
          height: 6,
        ),
        const SizedBox(height: 5),
        Row(
          children: [
            Text(
              '${category.transactionCount} '
              '${category.transactionCount == 1 ? 'transaction' : 'transactions'}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const Spacer(),
            Text(
              '${category.sharePercent.toStringAsFixed(1)}%',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ],
    ),
  );
}

class _Clue {
  const _Clue(this.icon, this.title, this.detail, this.tone);

  final IconData icon;
  final String title;
  final String detail;
  final Color tone;
}

class _ClueRow extends StatelessWidget {
  const _ClueRow({required this.clue});

  final _Clue clue;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(14),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 34,
          height: 34,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: clue.tone.withValues(alpha: .11),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(clue.icon, size: 18, color: clue.tone),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                clue.title,
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 3),
              Text(clue.detail, style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
        ),
      ],
    ),
  );
}

String _comparisonCopy(SpendingReport report) {
  final change = report.expenseChangeBasisPoints;
  if (change == null) {
    return 'There is not enough earlier activity for a fair comparison yet.';
  }
  final percent = (change.abs() / 100).toStringAsFixed(1);
  if (change > 0) {
    return 'Spending is $percent% higher than the previous matching period.';
  }
  if (change < 0) {
    return 'Spending is $percent% lower than the previous matching period.';
  }
  return 'Spending matches the previous period almost exactly.';
}

List<_Clue> _clues(SpendingReport report) {
  final clues = <_Clue>[];
  final top = report.topCategory;
  if (top != null) {
    clues.add(
      _Clue(
        Icons.category_outlined,
        '${top.name} is the largest category',
        '${top.sharePercent.toStringAsFixed(1)}% of recorded spending '
            'went here.',
        AppColors.primary,
      ),
    );
  } else {
    clues.add(
      const _Clue(
        Icons.category_outlined,
        'Categories are still quiet',
        'Categorized expenses will reveal where spending concentrates.',
        AppColors.primary,
      ),
    );
  }

  final change = report.expenseChangeBasisPoints;
  if (change != null) {
    final lower = change < 0;
    clues.add(
      _Clue(
        lower ? Icons.south_east : Icons.north_east,
        lower ? 'Spending moved down' : 'Spending moved up',
        _comparisonCopy(report),
        lower ? AppColors.positive : AppColors.warning,
      ),
    );
  } else {
    clues.add(
      const _Clue(
        Icons.compare_arrows,
        'The comparison needs more history',
        'A previous matching period will appear after more records sync.',
        AppColors.warning,
      ),
    );
  }

  clues.add(
    _Clue(
      Icons.calendar_view_month,
      '${money(report.averageMonthlyExpenseCents)} per month on average',
      'This is a simple average across the selected calendar months.',
      AppColors.blue,
    ),
  );
  return clues;
}
