package com.auraapp.assistant

import io.flutter.embedding.android.FlutterFragmentActivity

// local_auth (biyometrik kilit, 2026-08-26 eklendi) bir FragmentActivity
// gerektiriyor - normal FlutterActivity ile BiometricPrompt gosterilemiyor.
class MainActivity : FlutterFragmentActivity()
