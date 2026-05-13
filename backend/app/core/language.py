"""
Nigerian Language Intelligence
================================
Detects and routes conversations in:
- Nigerian Pidgin English (Naija)
- Yoruba
- Hausa
- Igbo
- Standard Nigerian English

This is a hard differentiator — no global fintech AI handles
code-switching between Pidgin and formal English,
or knows that "oga" means boss/manager, "abeg" means please,
"wahala" means trouble/problem, "chop" can mean spend/eat.

The LLM system prompt is dynamically adapted based on detected language.
"""

from typing import Literal

NigerianLanguage = Literal["pidgin", "yoruba", "hausa", "igbo", "english"]


# ── Detection Keyword Maps ────────────────────────────────────────────────────

PIDGIN_MARKERS = {
    "abeg", "oga", "wahala", "na", "wetin", "dey", "dem", "wey",
    "no be", "e be like", "make i", "comot", "chop", "gbege",
    "sabi", "kuku", "e don happen", "sharp sharp", "how far",
    "person", "ginger", "yarn", "ehn", "oya", "gbam",
}

YORUBA_MARKERS = {
    "bawo", "se", "jowo", "ekaaro", "ekasan", "ekale", "eku",
    "ori", "owo", "isegun", "iwe", "ile", "omo", "baba",
}

HAUSA_MARKERS = {
    "don allah", "yaya", "sannu", "nagode", "lafiya", "ina kwana",
    "ina wuni", "yauwa", "kudi", "banki",
}

IGBO_MARKERS = {
    "biko", "daalu", "nna", "nne", "kedu", "ọ dị mma", "ego",
    "ole", "nkọ", "i nọ", "gwa m",
}


def detect_language(text: str) -> NigerianLanguage:
    """Simple keyword-based language detector. Good enough for routing."""
    lower = text.lower()
    tokens = set(lower.split())

    scores = {
        "pidgin": len(tokens & PIDGIN_MARKERS),
        "yoruba": len(tokens & YORUBA_MARKERS),
        "hausa": len(tokens & HAUSA_MARKERS),
        "igbo": len(tokens & IGBO_MARKERS),
    }

    best = max(scores, key=lambda k: scores[k])
    if scores[best] >= 1:
        return best  # type: ignore
    return "english"


# ── Language-Specific System Prompt Additions ─────────────────────────────────

LANGUAGE_INSTRUCTIONS: dict[NigerianLanguage, str] = {
    "pidgin": """
The customer is writing in Nigerian Pidgin English. Reply in Pidgin English that is warm,
natural, and easy to understand. Use common Pidgin phrases but stay professional.
Examples of appropriate tone:
- "Abeg no worry, I go help you sort am"
- "Wetin dey happen to your account? Tell me more"
- "Your transfer don go through, e no get wahala"
- "Sharp sharp, make I check that transaction for you"
Keep financial terms in English (amount, account, BVN, transfer) for clarity.
""",
    "yoruba": """
The customer appears to be writing in Yoruba or a Yoruba-influenced style.
Respond warmly in simple English but include occasional Yoruba greetings and affirmations
where appropriate (e.g., "Ẹ káàbọ̀" for welcome, "A ó ṣe é" for we'll handle it).
Do not attempt to write full Yoruba — prioritize clarity.
""",
    "hausa": """
The customer appears to be writing in Hausa or a Hausa-influenced style.
Respond warmly in simple English. You may use common Hausa courtesies
(e.g., "Sannu" for hello, "Na gode" for thank you) where natural.
Prioritize clarity in English for financial information.
""",
    "igbo": """
The customer appears to be writing in Igbo or an Igbo-influenced style.
Respond warmly in simple English. You may use common Igbo greetings
(e.g., "Daalu" for thank you, "Kedu" for how are you) where natural.
Prioritize clarity in English for financial information.
""",
    "english": "",  # No addition needed
}

# ── Pidgin Financial Term Glossary ────────────────────────────────────────────
# Used for the LLM context so it understands user intent

PIDGIN_FINTECH_GLOSSARY = {
    "chop my money": "unauthorized deduction / money missing",
    "my account don block": "account frozen or suspended",
    "e no enter": "transfer failed / money not received",
    "double debit": "charged twice for same transaction",
    "dem carry my money": "fraudulent debit / money stolen",
    "e dey pending": "transaction still processing",
    "reverse am": "refund / reverse the transaction",
    "how much remain": "account balance enquiry",
    "e don expire": "card or token has expired",
    "them do me fraud": "I have been defrauded",
    "oga block my card": "my card has been blocked",
    "borrow me loan": "I want to apply for a loan",
    "my BVN wahala": "BVN verification issue",
    "send alert": "send transaction notification",
}


def enrich_context_with_glossary(text: str) -> str:
    """Appends glossary hints if Pidgin phrases are detected."""
    lower = text.lower()
    hints = []
    for phrase, meaning in PIDGIN_FINTECH_GLOSSARY.items():
        if phrase in lower:
            hints.append(f'"{phrase}" = {meaning}')
    if hints:
        return f"{text}\n\n[CONTEXT HINTS: {'; '.join(hints)}]"
    return text
