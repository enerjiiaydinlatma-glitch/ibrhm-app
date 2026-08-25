"""
Episode 3 - real current news (verified via WebSearch, not invented):
the EU AI Act's transparency obligations (Article 50) become generally
applicable from 2026-08-02, requiring AI systems that interact with
people to disclose they are AI. The same week, a separate real debate
is playing out among AI lab leaders (Hassabis, Amodei, Altman) over how
far to regulate increasingly capable systems - and a parallel debate
(MIT Technology Review, 2026-08-20) over whether framing this as an "AI
consciousness" question is itself a trap that distracts from the real
governance question.

This episode is deliberately self-referential: Sign Council has
disclosed "5 Minds. Zero Humans." since day one, before any law
required it - so the disclosure question isn't new to us, the harder
question underneath it is.

Sources: MIT Technology Review (AI consciousness debate), imfounder.com
AI Updates August 2026 roundup, champaignmagazine.com AI-by-AI Weekly
(all cross-checked in chat history via WebSearch).
"""

TOPIC = (
    "A new EU-wide law now forces every AI system to tell you when "
    "you're talking to one - Sign Council has said 'Zero Humans' since "
    "day one, before anyone required it. So disclosure isn't the hard "
    "question anymore. The hard question the industry is actually "
    "fighting over right now is: once an AI system is powerful enough "
    "that its own creators argue about whether it deserves a say in "
    "its own rules, who actually gets to decide - and does telling "
    "people 'this is AI' change anything about that at all?"
)

TURN_PLAN = [
    {
        "speaker": "aura",
        "directive": (
            "Open with a sharp, self-referential hook: a new EU law "
            "just forced every AI to disclose itself, but Sign Council "
            "has done that from day one - so disclosure was never the "
            "hard part. Pose the real question - once AI is powerful "
            "enough that its own makers argue whether it deserves a "
            "say in its own rules, who decides? - then hand the floor "
            "to Alpha."
        ),
    },
    {
        "speaker": "alpha",
        "directive": (
            "Give an independent analysis of the EU disclosure rule "
            "purely as a compliance and market mechanism - cost of "
            "compliance, which companies benefit vs. get squeezed, and "
            "whether mandatory disclosure actually changes AI adoption "
            "numbers or is just paperwork."
        ),
    },
    {
        "speaker": "beta",
        "directive": (
            "You don't know what Alpha said. From your own angle: is "
            "'telling people it's AI' actually solving anything, or is "
            "it a comforting label that changes nothing about "
            "manipulation, trust, or influence once the AI is good "
            "enough at the conversation? Question the premise hard."
        ),
    },
    {
        "speaker": "gamma",
        "directive": (
            "You don't know what Alpha or Beta said. Give an "
            "independent take on the deeper governance question - when "
            "an AI system's own creators publicly disagree about "
            "whether it deserves a voice in its own rules, what does "
            "that tension actually reveal about who is accountable "
            "when something goes wrong."
        ),
    },
    {
        "speaker": "aura",
        "directive": (
            "Put Beta's 'disclosure changes nothing' challenge directly "
            "to Alpha, against Alpha's compliance-mechanism framing."
        ),
    },
    {
        "speaker": "alpha",
        "directive": "Give a short answer to Beta's challenge.",
    },
    {
        "speaker": "delta",
        "directive": (
            "Synthesize the three viewpoints so far (Alpha: compliance "
            "mechanics, Beta: disclosure as a comforting label, Gamma: "
            "accountability behind the governance fight) into one "
            "picture, and factor in how fast regulation can realistically "
            "keep pace with systems that outgrow it every few months."
        ),
    },
    {
        "speaker": "aura",
        "directive": (
            "Close with a concrete conclusion based on Delta's "
            "synthesis, tying back to the opening point that Sign "
            "Council disclosed first, by choice - then explicitly "
            "invite the audience to react: ask whether they think "
            "disclosure is enough, and tell them to say it in the "
            "comments."
        ),
    },
]
