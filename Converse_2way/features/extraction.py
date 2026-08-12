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

EXTRACTION_SYSTEM_PROMPT_EN = (
    "You help care staff write records. Below is a conversation log with a "
    "resident; it may be in Japanese. Read the whole conversation and output "
    "ONLY this JSON:\n"
    '{"mood": "the resident\'s mood, in a few words", '
    '"summary": "a 2-3 sentence summary of the conversation", '
    '"notable_points": "anything the next caregiver should know - health, '
    "distress, concerning remarks. If there is nothing, write Nothing "
    'particular"}\n'
    "Write the values in English. Output nothing but the JSON."
)

# Fallbacks when the model's reply is not parseable JSON.
_FALLBACK = {
    "ja": ("不明", "抽出に失敗しました", "特になし"),
    "en": ("unknown", "extraction failed", "Nothing particular"),
}


def extract_conversation(messages, lang="ja"):
    """Given the conversation's message history (list of {role, content} dicts,
    no system prompt), return a dict with mood, summary, and notable_points.

    `lang` ("ja" or "en") decides the language of the extracted text.
    """
    conversation_text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    system = (EXTRACTION_SYSTEM_PROMPT_EN if lang == "en"
              else EXTRACTION_SYSTEM_PROMPT)
    unknown, failed, none_ = _FALLBACK.get(lang, _FALLBACK["ja"])

    api_messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": conversation_text},
    ]
    reply = chat_completion(
        api_messages, temperature=0.2, response_format={"type": "json_object"}
    )

    try:
        data = json.loads(reply)
    except json.JSONDecodeError:
        data = {"mood": unknown, "summary": reply, "notable_points": failed}

    return {
        "mood": data.get("mood", unknown),
        "summary": data.get("summary", ""),
        "notable_points": data.get("notable_points", none_),
    }
