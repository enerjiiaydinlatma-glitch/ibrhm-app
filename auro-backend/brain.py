from datetime import datetime

memory_store = {}

def get_user_memory(user_id):
    if user_id not in memory_store:
        memory_store[user_id] = {
            "personality": {},
            "history": [],
            "mood": "neutral"
        }
    return memory_store[user_id]


def detect_intent(message: str):
    message = message.lower()

    if any(x in message for x in ["üzgün", "moralim bozuk", "kötüyüm"]):
        return "emotional"

    if any(x in message for x in ["yap", "plan", "nasıl", "yardım et"]):
        return "assistant"

    if any(x in message for x in ["hikaye", "story", "anlat"]):
        return "story"

    return "general"


def update_memory(user_id, message, mood):
    mem = get_user_memory(user_id)
    
    mem["history"].append({
        "message": message,
        "time": str(datetime.now())
    })

    mem["mood"] = mood

    return mem


def aura_brain(user_id: str, message: str):
    mem = get_user_memory(user_id)

    intent = detect_intent(message)
    mood = "neutral"

    if intent == "emotional":
        mood = "sad"

    update_memory(user_id, message, mood)

    return {
        "intent": intent,
        "mood": mood,
        "memory": mem
    }