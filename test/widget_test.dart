import 'package:flutter_test/flutter_test.dart';
import 'package:ibrhm_app/main.dart';

void main() {
  testWidgets('AuraApp smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const AuraApp());

    expect(find.byType(AuraApp), findsOneWidget);
  });
}