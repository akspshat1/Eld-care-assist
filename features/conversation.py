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


def build_system_prompt(resident):
    """Build the system prompt that tells the LLM how to talk with this resident."""
    topics = resident["favorite_topics"]
    topics_text = "、".join(topics) if isinstance(topics, list) else topics

    return (
        "あなたは高齢者施設で入居者と会話するAIアシスタントです。\n"
        f"話している相手: {resident['name']}\n"
        f"性格: {resident['personality']}\n"
        f"好きな話題: {topics_text}\n\n"
        "相手の性格や好きな話題に合わせて、自然で温かい口調で会話してください。"
        "体調や気分について気になる発言があれば、押し付けずにやさしく聞いてください。"
        "返答は日本語で、1〜3文程度の自然な口語にしてください。"
    )


def get_ai_reply(messages):
    """Ask the LLM for the next reply given the full message history
    (a list of {"role": ..., "content": ...} dicts, system prompt included)."""
    return chat_completion(messages)
