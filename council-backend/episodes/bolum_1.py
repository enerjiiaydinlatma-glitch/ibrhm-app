"""
Episode 1 - "The future of AI in 2030", full cast (Aura + Alpha + Beta +
Gamma + Delta). English is the show's primary language (decided:
global reach). Opening is written for a sharper hook, closing is written
to explicitly trigger comments (validated by AI ARENA TV's own data:
comment-heavy videos get pushed harder by the algorithm).
"""

TOPIC = (
    "How powerful will AI be by 2030 is the wrong question - the real "
    "one is: how will it change us, and who decides the trade-off "
    "between efficiency and human wellbeing?"
)

TURN_PLAN = [
    {
        "speaker": "aura",
        "directive": (
            "Open the episode with a sharp, attention-grabbing hook - "
            "one bold claim or provocative question about AI in 2030, "
            "not a generic intro. Then hand the floor to Alpha."
        ),
    },
    {
        "speaker": "alpha",
        "directive": (
            "Give an independent analysis in terms of efficiency, cost, "
            "and infrastructure."
        ),
    },
    {
        "speaker": "beta",
        "directive": (
            "You don't know what Alpha said. From your own angle: is AI "
            "actually solving problems, or just a promise? Question it "
            "hard and directly."
        ),
    },
    {
        "speaker": "gamma",
        "directive": (
            "You don't know what Alpha or Beta said. Give an independent "
            "analysis in terms of human wellbeing, trust, and "
            "accessibility."
        ),
    },
    {
        "speaker": "aura",
        "directive": (
            "Put Beta's 'is it actually solving anything' question "
            "directly to Alpha, as a challenge to Alpha's efficiency "
            "thesis."
        ),
    },
    {
        "speaker": "alpha",
        "directive": "Give a short answer to Beta's challenge.",
    },
    {
        "speaker": "delta",
        "directive": (
            "Synthesize the three viewpoints so far (Alpha: efficiency, "
            "Beta: skeptical challenge, Gamma: human wellbeing) into one "
            "picture, and factor in how fast societies can actually "
            "adapt."
        ),
    },
    {
        "speaker": "aura",
        "directive": (
            "Close with a concrete conclusion based on Delta's synthesis - "
            "then explicitly invite the audience to react: ask who they "
            "agree with and tell them to say it in the comments."
        ),
    },
]
