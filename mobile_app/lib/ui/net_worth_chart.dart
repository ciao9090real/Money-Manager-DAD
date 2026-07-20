import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/finance_models.dart';
import '../theme/app_theme.dart';
import 'widgets.dart';

class NetWorthTrendChart extends StatelessWidget {
  const NetWorthTrendChart({super.key, required this.points});

  final List<NetWorthPoint> points;

  @override
  Widget build(BuildContext context) {
    if (points.isEmpty) {
      return const EmptyState(
        icon: Icons.show_chart,
        title: 'No history yet',
        message: 'Net-worth history will build as your records sync.',
      );
    }
    final first = points.first;
    final last = points.last;
    return Semantics(
      label:
          'Net worth trend from ${friendlyDate(first.date)} to ${friendlyDate(last.date)}. Current net worth ${money(last.netWorthCents)}.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Wrap(
            spacing: 13,
            runSpacing: 7,
            children: [
              _LegendItem(label: 'Net worth', color: AppColors.primary),
              _LegendItem(label: 'Assets', color: AppColors.blue),
              _LegendItem(label: 'Liabilities', color: AppColors.negative),
            ],
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 142,
            width: double.infinity,
            child: CustomPaint(painter: _NetWorthPainter(points)),
          ),
          const SizedBox(height: 6),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                _month(first.date),
                style: Theme.of(context).textTheme.bodySmall,
              ),
              Text(
                _month(last.date),
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ],
      ),
    );
  }

  static String _month(String value) {
    final parsed = DateTime.tryParse(value);
    return parsed == null ? value : DateFormat('MMM yyyy').format(parsed);
  }
}

class _LegendItem extends StatelessWidget {
  const _LegendItem({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(
        width: 9,
        height: 9,
        decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      ),
      const SizedBox(width: 5),
      Text(label, style: Theme.of(context).textTheme.bodySmall),
    ],
  );
}

class _NetWorthPainter extends CustomPainter {
  const _NetWorthPainter(this.points);

  final List<NetWorthPoint> points;

  @override
  void paint(Canvas canvas, Size size) {
    final values = <int>[
      0,
      for (final point in points) ...[
        point.assetsCents,
        point.liabilitiesCents,
        point.netWorthCents,
      ],
    ];
    var minimum = values.reduce(math.min).toDouble();
    var maximum = values.reduce(math.max).toDouble();
    if (minimum == maximum) {
      minimum -= 1;
      maximum += 1;
    }
    const topPadding = 6.0;
    const bottomPadding = 6.0;
    final chartHeight = size.height - topPadding - bottomPadding;

    double xFor(int index) {
      if (points.length == 1) return size.width / 2;
      return index * size.width / (points.length - 1);
    }

    double yFor(int cents) {
      final ratio = (cents - minimum) / (maximum - minimum);
      return topPadding + chartHeight * (1 - ratio);
    }

    final gridPaint = Paint()
      ..color = AppColors.border.withValues(alpha: .75)
      ..strokeWidth = 1;
    for (var index = 0; index < 4; index++) {
      final y = topPadding + chartHeight * index / 3;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    _drawSeries(
      canvas,
      xFor,
      yFor,
      (point) => point.liabilitiesCents,
      AppColors.negative,
      1.5,
    );
    _drawSeries(
      canvas,
      xFor,
      yFor,
      (point) => point.assetsCents,
      AppColors.blue,
      1.5,
    );
    _drawSeries(
      canvas,
      xFor,
      yFor,
      (point) => point.netWorthCents,
      AppColors.primary,
      2.8,
      markLast: true,
    );
  }

  void _drawSeries(
    Canvas canvas,
    double Function(int index) xFor,
    double Function(int cents) yFor,
    int Function(NetWorthPoint point) valueFor,
    Color color,
    double width, {
    bool markLast = false,
  }) {
    final path = Path();
    for (var index = 0; index < points.length; index++) {
      final offset = Offset(xFor(index), yFor(valueFor(points[index])));
      if (index == 0) {
        path.moveTo(offset.dx, offset.dy);
      } else {
        path.lineTo(offset.dx, offset.dy);
      }
    }
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = width;
    canvas.drawPath(path, paint);
    if (markLast) {
      final last = points.length - 1;
      canvas.drawCircle(
        Offset(xFor(last), yFor(valueFor(points[last]))),
        3.8,
        Paint()..color = color,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _NetWorthPainter oldDelegate) =>
      oldDelegate.points != points;
}
