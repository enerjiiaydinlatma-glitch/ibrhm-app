import 'dart:convert';
import 'dart:ui' as ui;
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ibrhm_app/features/chat/models/chat_state.dart';
import 'package:ibrhm_app/features/chat/models/message.dart';
import 'package:ibrhm_app/features/chat/repository/chat_repository_impl.dart';
import 'package:ibrhm_app/features/chat/widgets/aura_hale.dart';

/// Backend yanitini sabit donduren sahte HTTP adaptoru.
class _FakeAdapter implements HttpClientAdapter {
  _FakeAdapter(this.body);
  final Map<String, dynamic> body;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    return ResponseBody.fromString(
      jsonEncode(body),
      200,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

Future<Message> _reply(Map<String, dynamic> body) {
  final dio = Dio()..httpClientAdapter = _FakeAdapter(body);
  return ChatRepositoryImpl(
    dio: dio,
    token: 't',
    baseUrl: 'http://x',
  ).sendMessage('merhaba');
}

Widget _host(
  List<String>? moods, {
  String? mood,
  bool disableAnimations = false,
}) {
  return MediaQuery(
    data: MediaQueryData(disableAnimations: disableAnimations),
    child: Directionality(
      textDirection: TextDirection.ltr,
      child: AuraHale(mood: mood, moods: moods),
    ),
  );
}

void main() {
  group('AuraHaleLook.forMoods', () {
    test('bos liste -> notr indigo, tek merkez, cosku yok', () {
      final look = AuraHaleLook.forMoods(const []);
      expect(look.a, AuraHaleLook.neutral);
      expect(look.spread, 0);
      expect(look.joy, 0);
    });

    test('bilinmeyen etiket yok sayilir', () {
      final look = AuraHaleLook.forMoods(const ['bilinmeyen']);
      expect(look.a, AuraHaleLook.neutral);
      expect(look.spread, 0);
    });

    test('tek uzgun -> kendi rengi, harman ve cosku yok', () {
      final look = AuraHaleLook.forMoods(const ['uzgun']);
      expect(look.a, AuraHaleLook.moodColors['uzgun']);
      expect(look.spread, 0);
      expect(look.joy, 0);
    });

    test('tek mutlu -> altin agirlikli cosku, hafif mercan eslik', () {
      final look = AuraHaleLook.forMoods(const ['mutlu']);
      expect(look.a, AuraHaleLook.moodColors['mutlu']);
      expect(look.b, AuraHaleLook.moodColors['enerjik']);
      expect(look.spread, closeTo(0.35, 1e-9));
      expect(look.joy, 1);
    });

    test('tek enerjik -> mercan agirlikli cosku', () {
      final look = AuraHaleLook.forMoods(const ['enerjik']);
      expect(look.a, AuraHaleLook.moodColors['enerjik']);
      expect(look.b, AuraHaleLook.moodColors['mutlu']);
      expect(look.joy, 1);
    });

    test('mutlu + enerjik -> tam harman + cosku', () {
      final look = AuraHaleLook.forMoods(const ['mutlu', 'enerjik']);
      expect(look.spread, 1);
      expect(look.joy, 1);
    });

    test('yorgun + mutlu -> iki ton yan yana, cosku YOK', () {
      final look = AuraHaleLook.forMoods(const ['yorgun', 'mutlu']);
      expect(look.a, AuraHaleLook.moodColors['yorgun']);
      expect(look.b, AuraHaleLook.moodColors['mutlu']);
      expect(look.spread, 1);
      expect(look.joy, 0);
    });

    test('sira mesajdaki sirayi izler', () {
      final look = AuraHaleLook.forMoods(const ['mutlu', 'yorgun']);
      expect(look.a, AuraHaleLook.moodColors['mutlu']);
      expect(look.b, AuraHaleLook.moodColors['yorgun']);
    });

    test('ikiden fazla duygu -> yalnizca ilk ikisi', () {
      final look = AuraHaleLook.forMoods(const ['stresli', 'uzgun', 'yorgun']);
      expect(look.a, AuraHaleLook.moodColors['stresli']);
      expect(look.b, AuraHaleLook.moodColors['uzgun']);
    });

    test('tekrar eden etiket tek sayilir', () {
      final look = AuraHaleLook.forMoods(const ['uzgun', 'uzgun']);
      expect(look.spread, 0);
    });

    test('isJoy: yalniz mutlu/enerjik ailesi', () {
      expect(AuraHaleLook.isJoy(const ['mutlu']), isTrue);
      expect(AuraHaleLook.isJoy(const ['mutlu', 'enerjik']), isTrue);
      expect(AuraHaleLook.isJoy(const ['mutlu', 'yorgun']), isFalse);
      expect(AuraHaleLook.isJoy(const []), isFalse);
    });

    test('lerp uc noktalari korur', () {
      final x = AuraHaleLook.forMoods(const ['uzgun']);
      final y = AuraHaleLook.forMoods(const ['mutlu', 'enerjik']);
      expect(AuraHaleLook.lerp(x, y, 0).a, x.a);
      expect(AuraHaleLook.lerp(x, y, 1).spread, y.spread);
      expect(AuraHaleLook.lerp(x, y, 0.5).joy, closeTo(0.5, 1e-9));
    });
  });

  group('Message / ChatState', () {
    test('effectiveMoods: moods oncelikli, yoksa tek mood, yoksa bos', () {
      expect(
        Message(
          id: '1',
          text: '',
          isUser: false,
          mood: 'a',
          moods: const ['b', 'c'],
        ).effectiveMoods,
        ['b', 'c'],
      );
      expect(
        Message(id: '1', text: '', isUser: false, mood: 'a').effectiveMoods,
        ['a'],
      );
      expect(Message(id: '1', text: '', isUser: false).effectiveMoods, isEmpty);
    });

    test('copyWith moods listesini korur', () {
      final m = Message(
        id: '1',
        text: 'x',
        isUser: false,
        moods: const ['mutlu'],
      );
      expect(m.copyWith(text: 'y').moods, ['mutlu']);
    });

    test('ChatState.copyWith onceki currentMoods listesini korur', () {
      final s = ChatState(currentMood: 'mutlu', currentMoods: const ['mutlu']);
      final s2 = s.copyWith(errorMessage: null);
      expect(s2.currentMoods, ['mutlu']);
      expect(s2.currentMood, 'mutlu');
      final s3 = s.copyWith(currentMoods: const ['uzgun', 'yorgun']);
      expect(s3.currentMoods, ['uzgun', 'yorgun']);
    });
  });

  group('ChatRepositoryImpl.sendMessage', () {
    test('yeni backend: mood + moods okunur', () async {
      final m = await _reply({
        'reply': 'selam',
        'mood': 'yorgun',
        'moods': ['yorgun', 'mutlu'],
      });
      expect(m.mood, 'yorgun');
      expect(m.moods, ['yorgun', 'mutlu']);
    });

    test('eski backend: moods yok -> bos liste, mood calisir', () async {
      final m = await _reply({'reply': 'selam', 'mood': 'mutlu'});
      expect(m.moods, isEmpty);
      expect(m.effectiveMoods, ['mutlu']);
    });

    test('mood null ve moods bos -> duygu yok', () async {
      final m = await _reply({'reply': 'selam', 'mood': null, 'moods': []});
      expect(m.effectiveMoods, isEmpty);
    });
  });

  group('AuraHale widget', () {
    testWidgets('mood olmadan cizilir, parilti yok', (tester) async {
      await tester.pumpWidget(_host(null));
      expect(find.byType(CustomPaint), findsNothing);
    });

    testWidgets(
      'cosku duygusu yeni yakalaninca parilti acilir, 5sn sonra biter',
      (tester) async {
        await tester.pumpWidget(_host(null));
        await tester.pumpWidget(_host(const ['mutlu']));
        await tester.pump(const Duration(seconds: 1));
        expect(find.byType(CustomPaint), findsOneWidget);

        await tester.pump(const Duration(seconds: 6));
        expect(find.byType(CustomPaint), findsNothing);
      },
    );

    testWidgets('acilis ilk olusumda OYNAMAZ (zaten coskulu baslarsa)', (
      tester,
    ) async {
      await tester.pumpWidget(_host(const ['mutlu']));
      await tester.pump(const Duration(seconds: 1));
      expect(find.byType(CustomPaint), findsNothing);
    });

    testWidgets('hareket azaltma aciksa parilti hic oynamaz', (tester) async {
      await tester.pumpWidget(_host(null, disableAnimations: true));
      await tester.pumpWidget(
        _host(const ['mutlu', 'enerjik'], disableAnimations: true),
      );
      await tester.pump(const Duration(seconds: 1));
      expect(find.byType(CustomPaint), findsNothing);
    });

    testWidgets('2 dk bekleme suresi: hemen tekrar coskuda parilti yok', (
      tester,
    ) async {
      await tester.pumpWidget(_host(null));
      await tester.pumpWidget(_host(const ['mutlu']));
      await tester.pump(const Duration(seconds: 6)); // ilk acilis bitti
      expect(find.byType(CustomPaint), findsNothing);

      await tester.pumpWidget(_host(const ['uzgun']));
      await tester.pump(const Duration(seconds: 4));
      await tester.pumpWidget(_host(const ['mutlu']));
      await tester.pump(const Duration(seconds: 1));
      expect(find.byType(CustomPaint), findsNothing);
    });

    testWidgets('karisik duygu (yorgun+mutlu) parilti OYNATMAZ', (
      tester,
    ) async {
      await tester.pumpWidget(_host(null));
      await tester.pumpWidget(_host(const ['yorgun', 'mutlu']));
      await tester.pump(const Duration(seconds: 1));
      expect(find.byType(CustomPaint), findsNothing);
    });

    testWidgets('eski API: yalniz mood verilince de calisir', (tester) async {
      await tester.pumpWidget(_host(null));
      await tester.pumpWidget(_host(null, mood: 'mutlu'));
      await tester.pump(const Duration(seconds: 1));
      expect(find.byType(CustomPaint), findsOneWidget);
    });

    testWidgets('hizli ard arda degisim istisna firlatmaz', (tester) async {
      for (final moods in [
        const <String>[],
        const ['uzgun'],
        const ['mutlu', 'enerjik'],
        const ['yorgun', 'stresli'],
        const ['mutlu'],
        const <String>[],
      ]) {
        await tester.pumpWidget(_host(moods));
        await tester.pump(const Duration(milliseconds: 700));
      }
      await tester.pump(const Duration(seconds: 10));
      expect(tester.takeException(), isNull);
    });
  });

  group(
    'AuraHale parilti kenari (gercek ekranda gorulen sert cizgi hatasi)',
    () {
      // Parilti gradyani kutunun kenarinda sifirlanmali. Aksi halde parilti
      // sert bir dikdortgen gibi kesilir. Siyah zeminde bir sutunun satirlari
      // arasindaki en buyuk ani sicrayis kucuk kalmali.
      Future<int> maxRowStep(WidgetTester tester, List<String> moods) async {
        final key = GlobalKey();
        await tester.binding.setSurfaceSize(const Size(430, 900));
        addTearDown(() => tester.binding.setSurfaceSize(null));
        await tester.pumpWidget(
          RepaintBoundary(
            key: key,
            child: MediaQuery(
              data: const MediaQueryData(size: Size(430, 900)),
              child: Directionality(
                textDirection: TextDirection.ltr,
                child: ColoredBox(
                  color: const Color(0xFF000000),
                  child: SizedBox(
                    width: 430,
                    height: 900,
                    child: AuraHale(moods: moods),
                  ),
                ),
              ),
            ),
          ),
        );
        // Gecis + nefes sirasinda en parlak ana yakin bir kare.
        await tester.pump(const Duration(seconds: 4));
        await tester.pump(const Duration(seconds: 3));
        late int step;
        await tester.runAsync(() async {
          final boundary =
              key.currentContext!.findRenderObject() as RenderRepaintBoundary;
          final image = await boundary.toImage();
          final data = (await image.toByteData(
            format: ui.ImageByteFormat.rawRgba,
          ))!;
          final w = image.width;
          final h = image.height;
          var maxStep = 0;
          for (final x in [w ~/ 4, w ~/ 2, 3 * w ~/ 4]) {
            for (var y = 1; y < h; y++) {
              final a = (y - 1) * w * 4 + x * 4;
              final b = y * w * 4 + x * 4;
              for (var c = 0; c < 3; c++) {
                final d = (data.getUint8(b + c) - data.getUint8(a + c)).abs();
                if (d > maxStep) maxStep = d;
              }
            }
          }
          step = maxStep;
        });
        return step;
      }

      for (final entry in {
        'cosku (mutlu)': ['mutlu'],
        'cosku (mutlu+enerjik)': ['mutlu', 'enerjik'],
        'harman (yorgun+mutlu)': ['yorgun', 'mutlu'],
        'tek duygu (uzgun)': ['uzgun'],
      }.entries) {
        testWidgets('${entry.key}: yatay/dikey sert kenar yok', (tester) async {
          final step = await maxRowStep(tester, entry.value);
          expect(step, lessThan(6), reason: 'en buyuk ani sicrayis: $step');
        });
      }
    },
  );
}
