import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:money_manager/theme/app_theme.dart';
import 'package:money_manager/ui/widgets.dart';

void main() {
  test('money values use clean euro formatting', () {
    expect(money(0), '€0.00');
    expect(money(2999), '€29.99');
    expect(money(-2999), '-€29.99');
  });

  test('portable account types have readable labels', () {
    expect(prettyType('current_account'), 'Current Account');
    expect(prettyType('transfer_out'), 'Transfer Out');
  });

  testWidgets('status pill remains compact', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        home: const Scaffold(
          body: Center(child: Pill('Pending', tone: 'warning')),
        ),
      ),
    );

    expect(find.text('Pending'), findsOneWidget);
    expect(tester.getSize(find.byType(Pill)).height, lessThanOrEqualTo(30));
  });
}
