import "package:dio/dio.dart";
import "package:flutter/material.dart";
import "package:google_fonts/google_fonts.dart";

class StoryScreen extends StatefulWidget {
  final String token;
  final String? lastAuraMessage;
  const StoryScreen({super.key, required this.token, this.lastAuraMessage});

  @override
  State<StoryScreen> createState() => _StoryScreenState();
}

class _StoryScreenState extends State<StoryScreen> {
  final _dio = Dio();
  final _contentController = TextEditingController();
  // bkz. friends_screen.dart'taki ayni not - localhost'tan production'a cekildi.
  static const _baseUrl = "https://aura-backend-production-bc9c.up.railway.app";
  static const _indigo = Color(0xFF6C63FF);
  static const _bg = Color(0xFF0A0A1A);
  List<dynamic> _feed = [];
  bool _loading = true;
  bool _generating = false;
  bool _sharing = false;
  int _selectedTab = 0;

  @override
  void initState() {
    super.initState();
    _loadFeed();
    if (widget.lastAuraMessage != null) {
      _selectedTab = 1;
      _generateWiseQuote(widget.lastAuraMessage!);
    }
  }

  Options get _auth => Options(headers: {"Authorization": "Bearer ${widget.token}"});

  Future<void> _loadFeed() async {
    try {
      final r = await _dio.get("$_baseUrl/api/stories/feed", options: _auth);
      setState(() {
        _feed = r.data as List;
        _loading = false;
      });
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  Future<void> _generateWiseQuote(String message) async {
    setState(() => _generating = true);
    try {
      final r = await _dio.post(
        "$_baseUrl/api/chat",
        data: {
          "message":
              "Åu metinden yola Ã§Ä±karak, paylaÅŸÄ±labilir, kÄ±sa ve felsefi bir 'bilge yorum' Ã¼ret. Sanki bir dÃ¼ÅŸÃ¼nÃ¼rÃ¼n gÃ¼nlÃ¼ÄŸÃ¼nden alÄ±nmÄ±ÅŸ gibi, 1-2 cÃ¼mle, gÃ¼Ã§lÃ¼ ve Ã¶zgÃ¼n olsun: '$message'"
        },
        options: _auth,
      );
      setState(() {
        _contentController.text = r.data["reply"] ?? "";
        _generating = false;
      });
    } catch (_) {
      setState(() => _generating = false);
    }
  }

  Future<void> _shareStory() async {
    final content = _contentController.text.trim();
    if (content.isEmpty) return;
    setState(() => _sharing = true);
    try {
      await _dio.post(
        "$_baseUrl/api/stories",
        data: {"content": content, "image_url": ""},
        options: _auth,
      );
      // BULUNDU (kod sagligi taramasi): await sonrasi widget agactan
      // kaldirilmis olabilir - mounted kontrolu olmadan context/setState
      // kullanmak framework assertion hatasina yol acabilir.
      if (!mounted) return;
      _contentController.clear();
      setState(() {
        _selectedTab = 0;
        _sharing = false;
      });
      _loadFeed();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Story paylaşıldı!", style: GoogleFonts.poppins()), backgroundColor: _indigo),
      );
    } catch (_) {
      setState(() => _sharing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: Colors.white70),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text("Story", style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600)),
        actions: [
          TextButton(
            onPressed: () => setState(() => _selectedTab = _selectedTab == 0 ? 1 : 0),
            child: Text(
              _selectedTab == 0 ? "+ PaylaÅŸ" : "Feed",
              style: GoogleFonts.poppins(color: _indigo, fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFF0A0A1A), Color(0xFF0D0B2A), Color(0xFF0A0A1A)],
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
          ),
        ),
        child: _selectedTab == 0 ? _buildFeed() : _buildCompose(),
      ),
    );
  }

  Widget _buildFeed() {
    if (_loading) return const Center(child: CircularProgressIndicator(color: _indigo));
    if (_feed.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text("âœ¨", style: TextStyle(fontSize: 48)),
            const SizedBox(height: 16),
            Text("ArkadaÅŸlarÄ±nÄ±n henÃ¼z story'si yok.\nÄ°lk story'yi sen paylaÅŸ!",
                textAlign: TextAlign.center,
                style: GoogleFonts.poppins(color: Colors.white38, fontSize: 14)),
            const SizedBox(height: 24),
            GestureDetector(
              onTap: () => setState(() => _selectedTab = 1),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(colors: [Color(0xFF6C63FF), Color(0xFF9C8FFF)]),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Text("Story OluÅŸtur", style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600)),
              ),
            ),
          ],
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(16, 100, 16, 16),
      itemCount: _feed.length,
      itemBuilder: (_, i) => _storyCard(_feed[i]),
    );
  }

  Widget _storyCard(Map<String, dynamic> story) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white.withValues(alpha: 0.1)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 36, height: 36,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: LinearGradient(colors: [_indigo, _indigo.withValues(alpha: 0.6)]),
                ),
                child: Center(
                  child: Text(
                    (story["author_name"] ?? "?")[0].toUpperCase(),
                    style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 14),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Text(story["author_name"] ?? "KullanÄ±cÄ±", style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600)),
            ],
          ),
          const SizedBox(height: 12),
          Text(story["content"] ?? "", style: GoogleFonts.poppins(color: Colors.white.withValues(alpha: 0.9), fontSize: 14, height: 1.5)),
        ],
      ),
    );
  }

  Widget _buildCompose() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 100, 20, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text("Story PaylaÅŸ", style: GoogleFonts.poppins(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w600)),
          const SizedBox(height: 16),
          TextField(
            controller: _contentController,
            maxLines: 5,
            style: GoogleFonts.poppins(color: Colors.white),
            decoration: InputDecoration(
              hintText: "DÃ¼ÅŸÃ¼nceni veya Aura'nÄ±n bilge yorumunu paylaÅŸ...",
              hintStyle: GoogleFonts.poppins(color: Colors.white38),
              fillColor: Colors.white.withValues(alpha: 0.05),
              filled: true,
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
            ),
          ),
          const SizedBox(height: 16),
          if (_generating)
            const Center(child: CircularProgressIndicator(color: _indigo))
          else
            SizedBox(
              width: double.infinity,
              height: 50,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(backgroundColor: _indigo, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))),
                onPressed: _sharing ? null : _shareStory,
                child: _sharing
                    ? const CircularProgressIndicator(color: Colors.white)
                    : Text("PaylaÅŸ", style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600)),
              ),
            ),
        ],
      ),
    );
  }
}
