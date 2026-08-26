import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import 'features/chat/screens/auth_screen.dart';
import 'features/chat/screens/chat_screen.dart';
import 'features/lock/screens/lock_screen.dart';
import 'services/app_lock_service.dart';
import 'services/auth_service.dart';

void main() {
  runApp(
    const ProviderScope(
      child: AuraApp(),
    ),
  );
}

final GlobalKey<NavigatorState> auraNavigatorKey = GlobalKey<NavigatorState>();

class AuraApp extends StatefulWidget {
  const AuraApp({super.key});

  @override
  State<AuraApp> createState() => _AuraAppState();
}

/// Kullanici istegi uzerine eklendi (2026-08-26): uygulama arka plana
/// alinip geri donuldugunde, PIN kilidi acikken ekran hicbir koruma
/// olmadan aynen kaldigi yerden devam ediyordu - PIN sadece SOGUK
/// baslangicta (SplashRouter) soruluyordu. Bu gozlemci, oturum acikken
/// VE kilit etkinken her arka-plan-donusunde LockScreen'i navigator'in
/// EN USTUNE iter - hangi ekranda oldugunun onemi yok.
class _AuraAppState extends State<AuraApp> with WidgetsBindingObserver {
  bool _lockScreenShowing = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _maybeShowLockScreen();
    }
  }

  Future<void> _maybeShowLockScreen() async {
    if (_lockScreenShowing) return;
    final token = await AuthService().getToken();
    if (token == null || token.isEmpty) return;
    final lockEnabled = await AppLockService.instance.isLockEnabled();
    if (!lockEnabled) return;
    final navState = auraNavigatorKey.currentState;
    if (navState == null) return;
    _lockScreenShowing = true;
    await navState.push(
      MaterialPageRoute(
        builder: (_) => LockScreen(
          onUnlocked: () {
            _lockScreenShowing = false;
            navState.pop();
          },
        ),
        fullscreenDialog: true,
      ),
    );
    _lockScreenShowing = false;
  }

  @override
  Widget build(BuildContext context) {
    const Color bgColor = Color(0xFF0A0A1A);
    const Color primaryIndigo = Color(0xFF6C63FF);
    const Color surfaceColor = Color(0xFF12122A);

    final textTheme = GoogleFonts.poppinsTextTheme().apply(
      bodyColor: Colors.white,
      displayColor: Colors.white,
    );

    return MaterialApp(
      navigatorKey: auraNavigatorKey,
      title: 'Aura',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: bgColor,

        colorScheme: const ColorScheme.dark(
          primary: primaryIndigo,
          secondary: Color(0xFF9C8FFF),
          surface: surfaceColor,
          onPrimary: Colors.white,
          onSurface: Colors.white,
        ),

        appBarTheme: AppBarTheme(
          backgroundColor: Colors.transparent,
          elevation: 0,
          centerTitle: true,
          titleTextStyle: GoogleFonts.poppins(
            color: Colors.white,
            fontSize: 20,
            fontWeight: FontWeight.w600,
            letterSpacing: 1.2,
          ),
          iconTheme: const IconThemeData(
            color: Colors.white70,
          ),
        ),

        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: const Color(0xFF1A1A3A),
          hintStyle: GoogleFonts.poppins(
            color: Colors.white38,
            fontSize: 14,
          ),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(24),
            borderSide: BorderSide.none,
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(24),
            borderSide: const BorderSide(
              color: Color(0xFF2A2A4A),
              width: 1,
            ),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(24),
            borderSide: const BorderSide(
              color: primaryIndigo,
              width: 1.5,
            ),
          ),
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 20,
            vertical: 14,
          ),
        ),

        textTheme: textTheme,
      ),

      home: const SplashRouter(),
    );
  }
}

class SplashRouter extends StatefulWidget {
  const SplashRouter({super.key});

  @override
  State<SplashRouter> createState() => _SplashRouterState();
}

class _SplashRouterState extends State<SplashRouter> {
  @override
  void initState() {
    super.initState();
    _checkAuth();
  }

  Future<void> _checkAuth() async {
    final authService = AuthService();

    final token = await authService.getToken();

    if (!mounted) return;

    if (token != null && token.isNotEmpty) {
      final valid = await authService.isLoggedIn();

      if (!mounted) return;

      if (valid) {
        final lockEnabled = await AppLockService.instance.isLockEnabled();
        if (!mounted) return;

        if (lockEnabled) {
          // BULUNDU (kendi kendini inceleme, 2026-08-26): onUnlocked burada
          // SplashRouter'in KENDI context'ini kullanıyordu - ama
          // pushReplacement zaten SplashRouter'in route'unu degistirdigi
          // icin, onUnlocked calisincaya kadar (kullanici PIN'i girene
          // kadar) bu context DEAKTIVE olmus oluyordu. Sonuc: kilit acik
          // her SOGUK baslangicta, dogru PIN girilince "Looking up a
          // deactivated widget's ancestor is unsafe" hatasi/cokmesi -
          // ozelligin en temel yolu hic test edilmemis, sadece arka
          // plandan donus (auraNavigatorKey kullanan) yolu test edilmisti.
          // Duzeltme: _AuraAppState._maybeShowLockScreen ile AYNI deseni
          // kullan - global, HER ZAMAN gecerli navigator anahtari.
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(
              builder: (_) => LockScreen(
                onUnlocked: () {
                  auraNavigatorKey.currentState?.pushReplacement(
                    MaterialPageRoute(builder: (_) => ChatScreen(token: token)),
                  );
                },
              ),
            ),
          );
          return;
        }

        Navigator.of(context).pushReplacement(
          MaterialPageRoute(
            builder: (_) => ChatScreen(
              token: token,
            ),
          ),
        );

        return;
      }

      await authService.clearToken();

      if (!mounted) return;
    }

    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => const AuthScreen(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: Color(0xFF0A0A1A),
      body: Center(
        child: CircularProgressIndicator(
          color: Color(0xFF6C63FF),
        ),
      ),
    );
  }
}