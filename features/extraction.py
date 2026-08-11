"""Extraction feature: turn a conversation log into mood / summary / notable points.

Uses the same LLM as the conversation feature, but asks it to reply in a
fixed JSON shape so the result can be saved into the extractions table.
"""
import json

from core.llm_client import chat_completion

EXTRACTION_SYSTEM_PROMPT = (
    "あなたは介護記録の作成を手伝うAIです。"
    "以下は入居者との会話ログです。会話全体を読んで、次のJSON形式だけで出力してください。\n"
    '{"mood": "会話から読み取れる入居者の気分を短い言葉で", '
    '"summary": "会話内容の要約を2〜3文で", '
    '"notable_points": "体調・不穏・気になる発言など、次の介護士に伝えるべき特記事項。無ければ「特になし」"}\n'
    "JSON以外の文字は出力しないでください。"
)


def extract_conversation(messages):
    """Given the conversation's message history (list of {role, content} dicts,
    no system prompt), return a dict with mood, summary, and notable_points."""
    conversation_text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)

    api_messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": conversation_text},
    ]
    reply = chat_completion(
        api_messages, temperature=0.2, response_format={"type": "json_object"}
    )

    try:
        data = json.loads(reply)
    except json.JSONDecodeError:
        data = {"mood": "不明", "summary": reply, "notable_points": "抽出に失敗しました"}

    return {
        "mood": data.get("mood", "不明"),
        "summary": data.get("summary", ""),
        "notable_points": data.get("notable_points", "特になし"),
    }
