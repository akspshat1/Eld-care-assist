"""Handoff report feature: turn a resident's daily records into a report
for the next caregiver."""
from core.llm_client import chat_completion

REPORT_SYSTEM_PROMPT = (
    "あなたは介護施設の申し送りレポート作成を手伝うAIです。"
    "以下は、ある入居者の1日分の会話記録（気分・要約・特記事項のリスト）です。"
    "これらを読んで、次の介護士に向けた申し送りレポートを日本語で作成してください。"
    "レポートは次の3つの見出しで構成してください。\n"
    "【今日の様子】\n【気になった点】\n【対応が必要な事項】\n"
    "各見出しの内容は、記録に無ければ「特になし」と書いてください。"
    "見出し以外の余計な前置きや後書きは書かないでください。"
)


def build_records_text(records):
    """Turn a list of {mood, summary, notable_points, started_at} dicts into
    plain text the LLM can read."""
    lines = [
        f"- {r['started_at']} 気分: {r['mood']} / 要約: {r['summary']} / "
        f"特記事項: {r['notable_points']}"
        for r in records
    ]
    return "\n".join(lines)


REPORT_SYSTEM_PROMPT_EN = (
    "You help care staff write handoff reports. Below is one day of "
    "conversation records for a resident (mood, summary, notable points); "
    "they may be written in Japanese. Write a handoff report in English for "
    "the next caregiver, using exactly these three headings:\n"
    "[Today's condition]\n[Points of concern]\n[Action needed]\n"
    'If a heading has nothing to report, write "Nothing particular". '
    "Do not add any preamble or closing remarks."
)


def generate_report(resident_name, records, lang="ja"):
    """Generate a handoff report text from a resident's daily conversation records.

    `lang` ("ja" or "en") decides the language of the report.
    """
    user_content = f"入居者: {resident_name}\n\n{build_records_text(records)}"
    messages = [
        {"role": "system",
         "content": REPORT_SYSTEM_PROMPT_EN if lang == "en" else REPORT_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    return chat_completion(messages, temperature=0.3)
