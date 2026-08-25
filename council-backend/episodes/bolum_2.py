"""
Episode 2 - real current news (verified via WebSearch, not invented):
DARPA/US Air Force flew an F-16 under real AI control (VENOM program,
disclosed by DARPA on 2026-07-16). Correction from the first draft: a
human safety pilot is still present and can switch control back at any
time - this is NOT a fully unmanned aircraft. The real tension is
authority handed over even with a human safety net, not "no human in
the loop."

Source: darpa.mil press release + FlightGlobal, Stars and Stripes,
Army Recognition (all cross-checked in chat history via WebSearch).
"""

TOPIC = (
    "DARPA just flew an F-16 under real AI control - a human safety "
    "pilot can still flip a switch and take back control at any moment. "
    "The real question isn't whether AI can fly a fighter jet - it's "
    "how much authority we're comfortable handing over, even when a "
    "human safety net still technically exists."
)

TURN_PLAN = [
    {
        "speaker": "aura",
        "directive": (
            "Open with a sharp, attention-grabbing hook about an AI "
            "flying a real F-16 with a human safety pilot able to take "
            "back control - one bold claim or provocative question, not "
            "a generic intro. Then hand the floor to Alpha."
        ),
    },
    {
        "speaker": "alpha",
        "directive": (
            "Give an independent analysis in terms of military "
            "capability, cost, and strategic advantage."
        ),
    },
    {
        "speaker": "beta",
        "directive": (
            "You don't know what Alpha said. From your own angle: is "
            "the 'human can always take back control' safeguard real, "
            "or a comforting illusion once split-second combat "
            "decisions are involved? Question it hard and directly."
        ),
    },
    {
        "speaker": "gamma",
        "directive": (
            "You don't know what Alpha or Beta said. Give an "
            "independent analysis on accountability and human "
            "responsibility when a machine flies a weapon of war."
        ),
    },
    {
        "speaker": "aura",
        "directive": (
            "Put Beta's 'is the safety switch even real in a real "
            "fight' challenge directly to Alpha, against Alpha's "
            "capability thesis."
        ),
    },
    {
        "speaker": "alpha",
        "directive": "Give a short answer to Beta's challenge.",
    },
    {
        "speaker": "delta",
        "directive": (
            "Synthesize the three viewpoints so far (Alpha: military "
            "capability, Beta: skeptical challenge to the safety net, "
            "Gamma: accountability) into one picture, and factor in how "
            "fast military doctrine and oversight can actually adapt."
        ),
    },
    {
        "speaker": "aura",
        "directive": (
            "Close with a concrete conclusion based on Delta's "
            "synthesis - then explicitly invite the audience to react: "
            "ask who they agree with and tell them to say it in the "
            "comments."
        ),
    },
]
