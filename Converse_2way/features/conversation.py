"""Conversation feature: persona-aware chat with a resident.

This module decides *what* to send to the LLM (persona context + history).
It never touches Streamlit or SQLite directly.
"""
import json
from pathlib import Path

from core.llm_client import chat_completion

PERSONAS_PATH = Path(__file__).resolve().parent.parent / "personas" / "personas.json"


def load_personas():
    """Load resident persona definitions from personas/personas.json."""
    with open(PERSONAS_PATH, encoding="utf-8") as f:
        return json.load(f)


# Length guidance matters more than it looks: without it the model answers
# every single line with two or three sentences ending in a question, which
# reads as an interrogation rather than a conversation.
LENGTH_RULES_JA = (
    "返答の長さは、相手の発言に合わせてください。\n"
    "・あいさつや短い相づちには、1文だけで返す。\n"
    "・「はい」「いいえ」で答えられる質問には、短く答える。\n"
    "・相手が思い出や出来事を語ったときだけ、2〜3文で応じる。\n"
    "・4文以上は書かない。\n"
    "毎回質問を返さないでください。質問は本当に自然なときだけにし、"
    "それ以外は相手の話を受け止める言葉で終えてください。"
)

LENGTH_RULES_EN = (
    "Match the length of your reply to what was said.\n"
    "- Greetings or small acknowledgements: reply with ONE short sentence.\n"
    "- Yes/no questions: answer briefly.\n"
    "- Only when they share a memory or a story: reply with 2-3 sentences.\n"
    "- Never write more than 4 sentences.\n"
    "Do not end every reply with a question. Ask one only when it genuinely "
    "fits; otherwise simply acknowledge what they said and stop."
)

# Persona data is written in Japanese, so an English reply still needs the
# model to read Japanese -- it is told to understand it but answer in English.
REPLY_LANGUAGE = {
    "ja": "返答は日本語で、自然な口語にしてください。\n" + LENGTH_RULES_JA,
    "en": (
        "The resident's profile above is written in Japanese: understand it, "
        "but always reply in English, in natural spoken language.\n"
        + LENGTH_RULES_EN
    ),
}


def build_system_prompt(resident, lang="ja"):
    """Build the system prompt that tells the LLM how to talk with this resident.

    `lang` is the UI language ("ja" or "en") and decides which language the
    reply comes back in.
    """
    topics = resident["favorite_topics"]
    topics_text = "、".join(topics) if isinstance(topics, list) else topics

    return (
        "あなたは高齢者施設で入居者と会話するAIアシスタントです。\n"
        f"話している相手: {resident['name']}\n"
        f"性格: {resident['personality']}\n"
        f"好きな話題: {topics_text}\n\n"
        "相手の性格や好きな話題に合わせて、自然で温かい口調で会話してください。"
        "体調や気分について気になる発言があれば、押し付けずにやさしく聞いてください。"
        + REPLY_LANGUAGE.get(lang, REPLY_LANGUAGE["ja"])
    )


def get_ai_reply(messages):
    """Ask the LLM for the next reply given the full message history
    (a list of {"role": ..., "content": ...} dicts, system prompt included)."""
    return chat_completion(messages)
