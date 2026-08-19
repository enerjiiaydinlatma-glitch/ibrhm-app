import "dart:ui";
import "package:dio/dio.dart";
import "package:flutter/material.dart";
import "package:google_fonts/google_fonts.dart";

class FriendsScreen extends StatefulWidget {
  final String token;

  const FriendsScreen({super.key, required this.token});

  @override
  State<FriendsScreen> createState() => _FriendsScreenState();
}

class _FriendsScreenState extends State<FriendsScreen>
    with TickerProviderStateMixin {
  final _dio = Dio();
  final _searchController = TextEditingController();

  static const _baseUrl =
      "http://127.0.0.1:8000";

  static const _indigo = Color(0xFF6C63FF);
  static const _bg = Color(0xFF0A0A1A);

  List _friends = [];
  List _requests = [];

  bool _loading = true;

  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  Options get _auth =>
      Options(headers: {"Authorization": "Bearer ${widget.token}"});

  Future _loadData() async {
    try {
      final f =
          await _dio.get("$_baseUrl/api/friends", options: _auth);

      final r =
          await _dio.get("$_baseUrl/api/friends/requests", options: _auth);

      setState(() {
        _friends = f.data as List;
        _requests = r.data as List;
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  Future _sendRequest() async {
    final email = _searchController.text.trim();

    if (email.isEmpty) return;

    try {
      await _dio.post(
        "$_baseUrl/api/friends/request",
        data: {"email": email},
        options: _auth,
      );

      _searchController.clear();

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content:
              Text("Ä°stek gÃ¶nderildi!", style: GoogleFonts.poppins()),
          backgroundColor: _indigo,
        ),
      );
    } catch (e) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("KullanÄ±cÄ± bulunamadÄ±",
              style: GoogleFonts.poppins()),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Future _acceptRequest(int id) async {
    try {
      await _dio.post(
        "$_baseUrl/api/friends/$id/accept",
        options: _auth,
      );

      _loadData();
    } catch (e) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        leading: IconButton(
          icon:
              const Icon(Icons.arrow_back_ios, color: Colors.white70),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(
          "ArkadaÅŸlar",
          style: GoogleFonts.poppins(
              color: Colors.white, fontWeight: FontWeight.w600),
        ),
        bottom: TabBar(
          controller: _tabController,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white38,
          indicatorColor: _indigo,
          labelStyle:
              GoogleFonts.poppins(fontWeight: FontWeight.w600),
          tabs: [
            const Tab(text: "ArkadaÅŸlar"),
            Tab(
                text:
                    "Ä°stekler${_requests.isNotEmpty ? ' (${_requests.length})' : ''}"),
          ],
        ),
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [
              Color(0xFF0A0A1A),
              Color(0xFF0D0B2A),
              Color(0xFF0A0A1A)
            ],
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
          ),
        ),
        child: Column(
          children: [
            const SizedBox(height: 130),

            /// SEARCH
            Padding(
              padding: const EdgeInsets.symmetric(
                  horizontal: 16, vertical: 8),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _searchController,
                      style: GoogleFonts.poppins(
                          color: Colors.white, fontSize: 14),
                      decoration: const InputDecoration(
                        hintText: "Email ile arkadaÅŸ ekle...",
                        prefixIcon: Icon(
                            Icons.person_add_outlined,
                            color: Colors.white38),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  GestureDetector(
                    onTap: _sendRequest,
                    child: Container(
                      width: 48,
                      height: 48,
                      decoration: const BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: LinearGradient(colors: [
                          Color(0xFF6C63FF),
                          Color(0xFF9C8FFF)
                        ]),
                      ),
                      child: const Icon(Icons.send_rounded,
                          color: Colors.white, size: 20),
                    ),
                  ),
                ],
              ),
            ),

            /// CONTENT
            Expanded(
              child: _loading
                  ? Center(
                      child: CircularProgressIndicator(
                          color: _indigo),
                    )
                  : TabBarView(
                      controller: _tabController,
                      children: [
                        _buildFriendsList(),
                        _buildRequestsList(),
                      ],
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFriendsList() {
    if (_friends.isEmpty) {
      return Center(
        child: Text(
          "HenÃ¼z arkadaÅŸ yok.\nEmail ile ekle!",
          textAlign: TextAlign.center,
          style: GoogleFonts.poppins(
              color: Colors.white38, fontSize: 14),
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _friends.length,
      itemBuilder: (context, i) => _friendTile(
        name: _friends[i]["friend_name"] ?? "KullanÄ±cÄ±",
        email: _friends[i]["friend_email"] ?? "",
      ),
    );
  }

  Widget _buildRequestsList() {
    if (_requests.isEmpty) {
      return Center(
        child: Text(
          "Bekleyen istek yok.",
          style: GoogleFonts.poppins(
              color: Colors.white38, fontSize: 14),
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _requests.length,
      itemBuilder: (context, i) => _requestTile(
        id: _requests[i]["id"],
        name: _requests[i]["sender_name"] ?? "KullanÄ±cÄ±",
        email: _requests[i]["sender_email"] ?? "",
      ),
    );
  }

  Widget _friendTile(
      {required String name, required String email}) {
    return ListTile(
      title: Text(name,
          style: GoogleFonts.poppins(color: Colors.white)),
      subtitle: Text(email,
          style: GoogleFonts.poppins(color: Colors.white38)),
    );
  }

  Widget _requestTile(
      {required int id,
      required String name,
      required String email}) {
    return ListTile(
      title: Text(name,
          style: GoogleFonts.poppins(color: Colors.white)),
      subtitle: Text(email,
          style: GoogleFonts.poppins(color: Colors.white38)),
      trailing: TextButton(
        onPressed: () => _acceptRequest(id),
        child: const Text("Kabul"),
      ),
    );
  }
}
