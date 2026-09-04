import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/chat_state.dart';
import '../models/message.dart';
import '../repository/chat_repository_impl.dart';

final chatProvider =
    NotifierProvider<ChatNotifier, ChatState>(ChatNotifier.new);

class ChatNotifier extends Notifier<ChatState> {
  String? _token;

  // Mesaj ID'leri icin: microsecondsSinceEpoch tek basina, ard arda iki
  // kullanicida (or. userMessage + placeholder) AYNI degeri dondurebilir
  // ve o zaman ID-bazli bulma (indexWhere m.id == ...) yanlis mesaji
  // yakalar. Monotonik bir sayac ekleyerek carpismayi imkansiz kiliyoruz.
  int _idSeq = 0;
  String _newId() =>
      '${DateTime.now().microsecondsSinceEpoch}-${_idSeq++}';

  /// Verilen ID'li mesaji yerinde (nerede olursa olsun) [updated] ile
  /// degistirir; bulunamazsa sona ekler. sendMessage / sendFileForAnalysis
  /// gibi UZUN suren await'lerden sonra "SON mesaj hala benim yer
  /// tutucumdur" varsayimi YANLIS - bu arada sesli gorusme turn_complete'i
  /// veya eszamanli bir gonderim listeye baska mesaj eklemis olabilir.
  void _replaceMessageById(String id, Message updated) {
    final msgs = state.messages;
    final idx = msgs.indexWhere((m) => m.id == id);
    final newList = [...msgs];
    if (idx >= 0) {
      newList[idx] = updated;
    } else {
      newList.add(updated);
    }
    state = state.copyWith(messages: newList, isLoading: false);
  }

  @override
  ChatState build() {
    return ChatState();
  }

  void setToken(String token) {
    _token = token;
  }

  ChatRepositoryImpl get _repository {
    final token = _token;

    if (token == null || token.isEmpty) {
      throw StateError('Aura oturum anahtarı bulunamadı.');
    }

    return ChatRepositoryImpl(token: token);
  }

  Future<void> loadHistory() async {
    try {
      final messages = await _repository.getHistory();

      state = state.copyWith(
        messages: messages,
        isLoading: false,
        errorMessage: null,
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Geçmiş yüklenemedi.',
      );
    }
  }

  /// Kullanicinin gecmisi bomsa Aura'nin ilk sozu kendisinin almasi
  /// icin cagrilir. Gecmis doluysa sessizce hicbir sey yapmaz.
  Future<void> fetchGreeting() async {
    if (state.messages.isNotEmpty) return;

    state = state.copyWith(isLoading: true, errorMessage: null);

    try {
      final greeting = await _repository.getGreeting();

      if (greeting != null && greeting.trim().isNotEmpty) {
        state = state.copyWith(
          messages: [
            ...state.messages,
            Message(
              id: _newId(),
              text: greeting,
              isUser: false,
            ),
          ],
          isLoading: false,
          errorMessage: null,
        );
      } else {
        state = state.copyWith(isLoading: false);
      }
    } catch (_) {
      // Kod sagligi taramasinda bulundu: bu catch diger tum catch
      // bloklarindan farkli olarak errorMessage set etmiyordu - agdan
      // kaynakli bir hata olursa kullanici bomboş bir sohbet ekraniyla
      // kaliyor, hicbir uyari gormuyordu.
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Karşılama mesajı alınamadı.',
      );
    }
  }

  Future<void> sendMessage(String text) async {
    final cleanText = text.trim();

    if (cleanText.isEmpty) {
      return;
    }

    final userMessage = Message(
      id: _newId(),
      text: cleanText,
      isUser: true,
    );

    state = state.copyWith(
      messages: [
        ...state.messages,
        userMessage,
      ],
      isLoading: true,
      errorMessage: null,
    );

    final assistantId = _newId();

    final assistantMessage = Message(
      id: assistantId,
      text: '',
      isUser: false,
    );

    state = state.copyWith(
      messages: [
        ...state.messages,
        assistantMessage,
      ],
      isLoading: true,
      errorMessage: null,
    );

    try {
      final reply = await _repository.sendMessage(cleanText);
      // Eskiden 'messages.last' yer tutucu sanilip kosulsuz degistiriliyordu -
      // await sirasinda sesli gorusme turn_complete'i (addUserMessage/
      // addAssistantMessage) veya eszamanli bir gonderim araya mesaj
      // eklerse YANLIS mesaj degisiyor ve bos yer tutucu balon oksuz
      // kaliyordu. Artik yer tutucu ID'siyle bulunuyor (bkz. sendFileForAnalysis,
      // ayni sinif - fix e7a15a6). ID esitleme icin _newId() monotonik.
      _replaceMessageById(
        assistantId,
        Message(id: assistantId, text: reply.text, isUser: false),
      );
      state = state.copyWith(errorMessage: null);
    } catch (e) {
      _replaceMessageById(
        assistantId,
        Message(
          id: assistantId,
          text: 'Aura şu an cevap veremiyor. Biraz sonra tekrar deneyelim.',
          isUser: false,
        ),
      );
      state = state.copyWith(errorMessage: 'Aura bağlantısında bir sorun oluştu.');
    }
  }
  /// Bir fotograf VEYA PDF gonderip Aura'nin incelemesini alir - sendMessage
  /// ile ayni desen: kullanici (ek) + bos asistan mesaji eklenir, isLoading
  /// acilir, sonuc/hata yerine yazilir.
  ///
  /// [mimeType] "image/*" ya da "application/pdf". PDF ise [fileName] balonda
  /// belge cipi olarak gosterilir, [question] varsa Aura ona gore yanitlar.
  Future<void> sendFileForAnalysis(
    Uint8List bytes, {
    required String mimeType,
    String? fileName,
    String question = '',
  }) async {
    final isPdf = mimeType == 'application/pdf';

    final userMessage = Message(
      id: _newId(),
      text: isPdf ? question : '',
      isUser: true,
      imageBytes: isPdf ? null : bytes,
      fileName: isPdf ? (fileName ?? 'belge.pdf') : null,
      animateIn: true,
    );

    final assistantId = _newId();
    final assistantMessage = Message(id: assistantId, text: '', isUser: false);

    state = state.copyWith(
      messages: [...state.messages, userMessage, assistantMessage],
      isLoading: true,
      errorMessage: null,
    );

    // BULUNDU (gece incelemesi): eskiden kosulsuz 'sublist(0, length-1)' ile
    // SON mesaji degistiriyordu - PDF analizi 10-45sn surer, o arada sesli
    // gorusme turn_complete'i ya da eszamanli bir gonderim listeye baska
    // mesaj eklerse YANLIS mesaj dusuyordu. Artik ortak _replaceMessageById
    // ile yer tutucu ID'siyle bulunup yerinde degistiriliyor.
    Message assistantReply(String text) =>
        Message(id: assistantId, text: text, isUser: false);

    try {
      final reply = await _repository.analyzeFile(
        base64Encode(bytes),
        mimeType: mimeType,
        question: question,
        fileName: fileName ?? '',
      );
      _replaceMessageById(assistantId, assistantReply(reply.text));
      state = state.copyWith(errorMessage: null);
    } catch (e) {
      _replaceMessageById(
        assistantId,
        assistantReply(isPdf
            ? 'Belgeyi şu an inceleyemedim, tekrar dener misin?'
            : 'Fotoğrafı şu an inceleyemedim, tekrar dener misin?'),
      );
      state = state.copyWith(
        errorMessage: isPdf ? 'Belge incelenemedi.' : 'Fotoğraf analiz edilemedi.',
      );
    }
  }

  /// Kombin onerisi - sendFileForAnalysis ile AYNI desen (kullanici eki +
  /// bos asistan mesaji + yerinde degistirme) ama /api/wardrobe'a gider,
  /// hava durumuna gore ne giyecegi onerisini getirir.
  Future<void> sendWardrobePhoto(
    Uint8List bytes, {
    required String mimeType,
    String question = '',
  }) async {
    final userMessage = Message(
      id: _newId(),
      text: question,
      isUser: true,
      imageBytes: bytes,
      animateIn: true,
    );

    final assistantId = _newId();
    final assistantMessage = Message(id: assistantId, text: '', isUser: false);

    state = state.copyWith(
      messages: [...state.messages, userMessage, assistantMessage],
      isLoading: true,
      errorMessage: null,
    );

    Message assistantReply(String text) =>
        Message(id: assistantId, text: text, isUser: false);

    try {
      final reply = await _repository.suggestOutfit(
        base64Encode(bytes),
        mimeType: mimeType,
        question: question,
      );
      _replaceMessageById(assistantId, assistantReply(reply.text));
      state = state.copyWith(errorMessage: null);
    } catch (e) {
      _replaceMessageById(
        assistantId,
        assistantReply('Kombini şu an göremedim, tekrar dener misin?'),
      );
      state = state.copyWith(errorMessage: 'Kombin önerisi alınamadı.');
    }
  }

  void addUserMessage(String text) {
    final cleanText = text.trim();

    if (cleanText.isEmpty) {
      return;
    }

    state = state.copyWith(
      messages: [
        ...state.messages,
        Message(
          id: _newId(),
          text: cleanText,
          isUser: true,
        ),
      ],
      errorMessage: null,
    );
  }

  void addAssistantMessage(String text) {
    final cleanText = text.trim();

    if (cleanText.isEmpty) {
      return;
    }

    state = state.copyWith(
      messages: [
        ...state.messages,
        Message(
          id: _newId(),
          text: cleanText,
          isUser: false,
        ),
      ],
      errorMessage: null,
    );
  }

  void clear() {
    state = ChatState();
  }
}
