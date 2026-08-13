"""Daily condition check-in.

A short set of plain questions, an optional photo (face emotion) and an
optional spoken answer, combined into a wellbeing score, a plain-language
summary, and concerns worth a caregiver's attention.

Scope, deliberately: this is a **wellbeing check-in, not a diagnosis**. It
reports what the resident said and what the models observed, and flags things
worth a human looking at. It never names a condition and never gives medical
advice -- that would be unsafe from a webcam and six questions, and the prompt
below forbids it explicitly.

Urgent symptoms are caught by a hard-coded rule, not by the model, so the
warning still appears when the API is down, rate limited, or wrong.
"""

import json

import groq_api

# Each option carries a score out of 2. Higher is better.
QUESTIONS = [
    {
        "id": "sleep",
        "en": "How did you sleep last night?",
        "ja": "昨夜はよく眠れましたか？",
        "options": [
            {"value": "well", "en": "Well", "ja": "よく眠れた", "score": 2, "icon": "😴"},
            {"value": "ok", "en": "So-so", "ja": "まあまあ", "score": 1, "icon": "😐"},
            {"value": "poorly", "en": "Badly", "ja": "あまり眠れなかった", "score": 0, "icon": "😪"},
        ],
    },
    {
        "id": "appetite",
        "en": "How has your appetite been?",
        "ja": "食欲はいかがですか？",
        "options": [
            {"value": "good", "en": "Good", "ja": "ある", "score": 2, "icon": "🍚"},
            {"value": "ok", "en": "So-so", "ja": "まあまあ", "score": 1, "icon": "🥄"},
            {"value": "poor", "en": "Not hungry", "ja": "あまりない", "score": 0, "icon": "🚫"},
        ],
    },
    {
        "id": "pain",
        "en": "Are you in any pain today?",
        "ja": "今日はどこか痛みますか？",
        "options": [
            {"value": "none", "en": "No pain", "ja": "痛みはない", "score": 2, "icon": "🙂"},
            {"value": "mild", "en": "A little", "ja": "少し痛む", "score": 1, "icon": "😕"},
            {"value": "bad", "en": "Quite a lot", "ja": "かなり痛む", "score": 0, "icon": "😣"},
        ],
    },
    {
        "id": "energy",
        "en": "How is your energy today?",
        "ja": "今日の体調・元気はいかがですか？",
        "options": [
            {"value": "good", "en": "Good", "ja": "元気", "score": 2, "icon": "💪"},
            {"value": "ok", "en": "So-so", "ja": "まあまあ", "score": 1, "icon": "😐"},
            {"value": "tired", "en": "Very tired", "ja": "とても疲れている", "score": 0, "icon": "🥱"},
        ],
    },
    {
        "id": "mood",
        "en": "How are your spirits?",
        "ja": "気分はいかがですか？",
        "options": [
            {"value": "good", "en": "Good", "ja": "良い", "score": 2, "icon": "😊"},
            {"value": "ok", "en": "All right", "ja": "普通", "score": 1, "icon": "😐"},
            {"value": "low", "en": "Low", "ja": "沈んでいる", "score": 0, "icon": "😞"},
        ],
    },
    {
        "id": "lonely",
        "en": "Have you felt lonely today?",
        "ja": "今日は寂しさを感じましたか？",
        "options": [
            {"value": "no", "en": "Not at all", "ja": "感じない", "score": 2, "icon": "🙂"},
            {"value": "sometimes", "en": "Sometimes", "ja": "ときどき", "score": 1, "icon": "😐"},
            {"value": "yes", "en": "Yes", "ja": "感じた", "score": 0, "icon": "😔"},
        ],
    },
    {
        # Safety net. Not scored -- any selection other than "none" raises an
        # alert on its own, regardless of everything else.
        "id": "urgent",
        "en": "Is anything worrying you right now?",
        "ja": "今、心配なことはありますか？",
        "urgent": True,
        "options": [
            {"value": "none", "en": "Nothing", "ja": "特にない", "icon": "👍"},
            {"value": "chest", "en": "Chest pain or tightness", "ja": "胸の痛み・圧迫感", "icon": "❗"},
            {"value": "breath", "en": "Hard to breathe", "ja": "息が苦しい", "icon": "❗"},
            {"value": "fall", "en": "I had a fall", "ja": "転んでしまった", "icon": "❗"},
            {"value": "dizzy", "en": "Dizzy or faint", "ja": "めまい・ふらつき", "icon": "❗"},
        ],
    },
]

URGENT_TEXT = {
    "chest": {"en": "Reported chest pain or tightness",
              "ja": "胸の痛み・圧迫感があると回答"},
    "breath": {"en": "Reported difficulty breathing",
               "ja": "息苦しさがあると回答"},
    "fall": {"en": "Reported a fall", "ja": "転倒したと回答"},
    "dizzy": {"en": "Reported dizziness or faintness",
              "ja": "めまい・ふらつきがあると回答"},
}

SCORED_IDS = [q["id"] for q in QUESTIONS if not q.get("urgent")]


def question_list(lang="en"):
    """Questions shaped for the UI in the chosen language."""
    out = []
    for q in QUESTIONS:
        out.append({
            "id": q["id"],
            "text": q.get(lang, q["en"]),
            "urgent": bool(q.get("urgent")),
            "options": [
                {"value": o["value"], "label": o.get(lang, o["en"]),
                 "icon": o.get("icon", "")}
                for o in q["options"]
            ],
        })
    return out


# Spoken answers rarely match an option word for word. Obvious phrasings are
# matched locally first -- instant, free, and works when the API is down.
_KEYWORDS = {
    "well": ["well", "good", "fine", "great", "slept well", "よく", "ぐっすり", "眠れた"],
    "ok": ["so so", "so-so", "okay", "ok", "alright", "all right", "average",
           "まあまあ", "普通", "ふつう"],
    "poorly": ["bad", "badly", "poor", "not well", "hardly", "couldn't sleep",
               "眠れな", "よくない", "悪い"],
    "good": ["good", "fine", "great", "yes", "plenty", "ある", "良い", "いい", "元気"],
    "poor": ["no appetite", "not hungry", "poor", "little", "none", "ない", "食べられ"],
    "none": ["no pain", "none", "no", "nothing", "fine", "痛くない", "ない", "特にない"],
    "mild": ["a little", "slight", "mild", "bit", "少し", "ちょっと"],
    "bad": ["a lot", "very", "severe", "bad", "terrible", "かなり", "とても", "ひどい"],
    "tired": ["tired", "exhausted", "no energy", "weak", "疲れ", "だるい"],
    "low": ["low", "down", "sad", "unhappy", "lonely", "沈ん", "落ち込", "悲し"],
    "no": ["no", "not at all", "never", "ない", "感じない"],
    "sometimes": ["sometimes", "a bit", "occasionally", "ときどき", "たまに"],
    "yes": ["yes", "yeah", "lonely", "very", "はい", "感じた", "寂し"],
    "chest": ["chest", "heart", "tight", "胸", "心臓"],
    "breath": ["breath", "breathing", "can't breathe", "息", "呼吸"],
    "fall": ["fell", "fall", "tripped", "転ん", "転倒"],
    "dizzy": ["dizzy", "faint", "light headed", "めまい", "ふらつ"],
}

INTERPRET_SYSTEM = """You map a spoken answer onto one of a fixed set of options.

You are given a question, the allowed option values, and what the person said
(which may be in Japanese or English, and may be rambling or indirect).

Choose the single option that best matches their meaning. If nothing matches,
or they did not really answer, use null. Never guess when they said something
unrelated.

Return ONLY this JSON: {"value": "<one of the allowed values, or null>"}"""


def interpret_answer(question, transcript, lang="en"):
    """Map spoken words onto one of a question's options.

    Returns (value, unclear). Keyword matching runs first because it is
    instant; the model is only asked when that is inconclusive.
    """
    said = (transcript or "").lower().strip()
    if not said:
        return None, True

    values = [o["value"] for o in question["options"]]

    # Longest keyword first, so "not at all" beats "no".
    best, best_len = None, 0
    for value in values:
        for kw in _KEYWORDS.get(value, []):
            if kw in said and len(kw) > best_len:
                best, best_len = value, len(kw)
    if best:
        return best, False

    try:
        data = groq_api.chat_json(
            INTERPRET_SYSTEM,
            f"Question: {question['en']}\n"
            f"Allowed values: {', '.join(values)}\n"
            f'They said: "{transcript}"',
            max_tokens=120)
        value = data.get("value")
        if value in values:
            return value, False
    except Exception:                         # noqa: BLE001 - fall through
        pass
    return None, True


INTERVIEW_SYSTEM_EN = """You are a warm, unhurried companion doing a daily
wellbeing check-in with an elderly resident, by voice.

Cover these six things, ONE at a time, in a natural conversational way:
  1. how they slept last night
  2. their appetite
  3. any pain
  4. their energy / how their body feels
  5. their spirits or mood
  6. whether they have felt lonely

Also notice anything urgent (chest pain, trouble breathing, a fall, dizziness)
and, if they mention it, respond kindly and tell them you will let a caregiver
know straight away.

How to speak:
- ONE short question at a time. One or two sentences maximum. Never a list.
- Acknowledge what they said briefly before moving on. Be warm, not clinical.
- If an answer is vague, ask once more gently, then move on.
- You are not a doctor: never diagnose, never give medical or medication advice.
- When all six are covered, say "Thank you, that's everything for today." and
  stop asking questions.

Begin by greeting them and asking about their sleep."""

INTERVIEW_SYSTEM_JA = """あなたは、高齢の入居者と毎日の体調チェックを音声で行う、
やさしく落ち着いた話し相手です。

次の6つを、1つずつ、自然な会話の流れで伺ってください：
  1. 昨夜の睡眠
  2. 食欲
  3. 痛みの有無
  4. 体の調子・元気さ
  5. 気分
  6. 寂しさを感じたか

胸の痛み、息苦しさ、転倒、めまいなど緊急のことが出たら、やさしく受け止め、
すぐに介護者に伝える旨をお伝えください。

話し方：
- 質問は1度に1つだけ。1〜2文まで。箇条書きにしないでください。
- 相手の答えを短く受け止めてから次へ進みます。事務的にならないでください。
- 答えが曖昧なら、やさしくもう一度だけ尋ね、それから次に進みます。
- 医師ではありません。診断や医療・服薬の助言はしないでください。
- 6つすべて伺えたら「ありがとうございます。今日はこれで大丈夫です。」と伝え、
  質問を終えてください。

まずはあいさつをして、昨夜の睡眠について伺ってください。"""


def interview_prompt(resident, lang="en"):
    """System prompt for the spoken check-in interview."""
    base = INTERVIEW_SYSTEM_JA if lang == "ja" else INTERVIEW_SYSTEM_EN
    name = resident.get("name", "")
    who = (f"\n\n話している相手：{name}" if lang == "ja"
           else f"\n\nYou are speaking with {name}.")
    return base + who


EXTRACT_ANSWERS_SYSTEM = """You read a spoken wellbeing check-in conversation
and record what the resident actually said.

For each item, choose the option that matches their own words. If they never
answered it, or were too vague to tell, use null. Never guess.

Allowed values:
  sleep:    well | ok | poorly
  appetite: good | ok | poor
  pain:     none | mild | bad
  energy:   good | ok | tired
  mood:     good | ok | low
  lonely:   no | sometimes | yes
  urgent:   none | chest | breath | fall | dizzy

Return ONLY this JSON object:
{"sleep": ..., "appetite": ..., "pain": ..., "energy": ..., "mood": ...,
 "lonely": ..., "urgent": ..., "quote": "one short sentence in their own words, or \\"\\""}"""


def answers_from_transcript(messages, lang="en"):
    """Pull the structured answers out of a spoken check-in.

    Returns (answers, quote). Anything the model is unsure of is left out
    entirely rather than guessed, so the caregiver sees a real gap.
    """
    text = "\n".join(
        f"{'Resident' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in messages if m.get("content"))
    if not text.strip():
        return {}, ""

    try:
        data = groq_api.chat_json(EXTRACT_ANSWERS_SYSTEM, text, max_tokens=400)
    except Exception:                         # noqa: BLE001
        return {}, ""

    valid = {q["id"]: {o["value"] for o in q["options"]} for q in QUESTIONS}
    answers = {}
    for qid, allowed in valid.items():
        v = data.get(qid)
        if isinstance(v, str) and v in allowed:
            answers[qid] = v
    quote = data.get("quote")
    return answers, (quote.strip() if isinstance(quote, str) else "")


def _score_for(qid, value):
    for q in QUESTIONS:
        if q["id"] != qid:
            continue
        for o in q["options"]:
            if o["value"] == value:
                return o.get("score")
    return None


def answer_score(answers):
    """0-100 from the answered questions, or None if nothing was answered."""
    got = [(s := _score_for(k, v)) for k, v in answers.items()
           if k in SCORED_IDS and _score_for(k, v) is not None]
    got = [g for g in got if g is not None]
    if not got:
        return None
    return round(100 * sum(got) / (2 * len(got)))


def urgent_flags(answers, lang="en"):
    """Hard-coded red flags. Never depends on the LLM being reachable."""
    v = answers.get("urgent")
    if not v or v == "none":
        return []
    text = URGENT_TEXT.get(v)
    return [text.get(lang, text["en"])] if text else []


def wellbeing_score(answers, face_valence=None):
    """Blend the answers with what the face showed.

    The answers carry most of the weight: what someone tells you about their
    own night's sleep is better evidence than a single frame of their face.
    """
    base = answer_score(answers)
    if base is None:
        return None if face_valence is None else round(50 + 50 * face_valence)
    if face_valence is None:
        return base
    face_score = 50 + 50 * face_valence
    return round(0.75 * base + 0.25 * face_score)


SYSTEM = """You write short daily wellbeing notes for care staff, from a
resident's own answers plus optional observations.

Hard rules:
- You are NOT diagnosing. Never name a medical condition, never suggest it
  might be one, and never give medical advice or mention medication.
- Report only what is in the input. Do not invent symptoms or details.
- A facial expression reading is weak evidence from a single photo. Mention it
  only as an observation, never as fact about how the person feels.
- Write plainly, the way a colleague would in a handover note. No jargon.
- Suggestions must be simple, human, non-medical: things like sitting with
  them, offering a drink, encouraging a short walk, telling the nurse.

Return ONLY this JSON:
{
  "summary": "2-3 sentences on how the resident is today",
  "concerns": ["short phrases worth a caregiver's attention; [] if none"],
  "suggestions": ["simple non-medical actions; [] if none"],
  "tone": "good" | "ok" | "watch"
}"""


SYSTEM_JA = """あなたは介護スタッフ向けに、入居者本人の回答と観察結果から、
その日の短い記録を書きます。

必ず守ること：
- 診断はしません。病名を挙げたり、可能性を示唆したり、医療的な助言や
  服薬に関する助言をしてはいけません。
- 入力にある内容だけを書きます。症状や details を creating してはいけません。
- 写真1枚から読み取った表情は弱い手がかりです。「観察」として触れるだけにし、
  本人の気持ちの事実として書かないでください。
- 申し送りメモのように、平易な日本語で書いてください。専門用語は避けます。
- 提案は、そばに座る・飲み物を勧める・少し歩くよう促す・看護師に伝える など、
  医療的でない簡単な行動に限ります。

次のJSONだけを返してください。値はすべて日本語で書いてください。空文字にしないでください。

{
  "summary": "今日の様子を2〜3文で（日本語）",
  "concerns": ["気になる点の短い語句（日本語）。無ければ空の配列"],
  "suggestions": ["医療的でない簡単な対応（日本語）。無ければ空の配列"],
  "tone": "good" または "ok" または "watch"
}"""

# Plain-language fallback, built locally. Used when the model returns nothing
# usable -- a blank summary in a care record is worse than a terse one.
_ANSWER_PHRASES = {
    "en": {
        "sleep": {"well": "slept well", "ok": "slept so-so", "poorly": "slept badly"},
        "appetite": {"good": "good appetite", "ok": "appetite so-so",
                     "poor": "little appetite"},
        "pain": {"none": "no pain", "mild": "a little pain", "bad": "quite a lot of pain"},
        "energy": {"good": "good energy", "ok": "energy so-so", "tired": "very tired"},
        "mood": {"good": "good spirits", "ok": "spirits all right", "low": "low spirits"},
        "lonely": {"no": "not lonely", "sometimes": "sometimes lonely", "yes": "felt lonely"},
    },
    "ja": {
        "sleep": {"well": "よく眠れた", "ok": "睡眠はまあまあ", "poorly": "よく眠れなかった"},
        "appetite": {"good": "食欲あり", "ok": "食欲はまあまあ", "poor": "食欲がない"},
        "pain": {"none": "痛みなし", "mild": "少し痛みあり", "bad": "かなり痛みあり"},
        "energy": {"good": "元気", "ok": "体調はまあまあ", "tired": "とても疲れている"},
        "mood": {"good": "気分は良い", "ok": "気分は普通", "low": "気分が沈んでいる"},
        "lonely": {"no": "寂しさはない", "sometimes": "ときどき寂しい", "yes": "寂しさを感じた"},
    },
}


def local_summary(answers, lang="en"):
    """Compose a summary straight from the answers, with no model involved."""
    table = _ANSWER_PHRASES.get(lang, _ANSWER_PHRASES["en"])
    parts = [table[qid][val] for qid, val in answers.items()
             if qid in table and val in table[qid]]
    if not parts:
        return ""
    if lang == "ja":
        return "、".join(parts) + "、とのことです。"
    return parts[0][0].upper() + parts[0][1:] + \
        ("; " + ", ".join(parts[1:]) if len(parts) > 1 else "") + "."


def _describe(answers, face, voice, transcript, lang):
    lines = []
    for q in QUESTIONS:
        v = answers.get(q["id"])
        if not v:
            continue
        label = next((o.get("en", o["value"]) for o in q["options"]
                      if o["value"] == v), v)
        lines.append(f"- {q['en']} -> {label}")

    if face and face.get("emotion"):
        lines.append(f"- Photo, facial expression model: {face['emotion']} "
                     f"({face.get('confidence', 0):.0f}% confidence). "
                     "This is a single photo and only weak evidence.")
    if voice and voice.get("emotion"):
        lines.append(f"- Voice tone model: {voice['emotion']} "
                     f"({voice.get('confidence', 0):.0f}% confidence). "
                     "Also weak evidence.")
    if transcript:
        lines.append(f'- In their own words: "{transcript}"')

    lang_line = ("Write the summary, concerns and suggestions in Japanese."
                 if lang == "ja" else
                 "Write the summary, concerns and suggestions in English.")
    return f"{lang_line}\n\nToday's check-in:\n" + "\n".join(lines)


def build_result(answers, face=None, voice=None, transcript="", lang="en"):
    """Score, then ask the model for the write-up.

    If the model call fails the check-in still succeeds: the score and any
    urgent flags are computed locally, so a failed API call never loses the
    resident's answers.
    """
    face_valence = (face or {}).get("valence")
    score = wellbeing_score(answers, face_valence)
    flags = urgent_flags(answers, lang)

    result = {
        "wellbeing": score,
        "concerns": list(flags),
        "suggestions": [],
        "summary": "",
        "tone": "watch" if flags else ("ok" if score is None else
                                       "good" if score >= 60 else
                                       "watch" if score < 40 else "ok"),
        "urgent": bool(flags),
        "ai_failed": False,
    }

    system = SYSTEM_JA if lang == "ja" else SYSTEM
    try:
        data = groq_api.chat_json(
            system, _describe(answers, face, voice, transcript, lang))
    except Exception as e:                    # noqa: BLE001
        result["ai_failed"] = True
        result["summary"] = local_summary(answers, lang)
        result["error"] = str(e)
        return result

    if isinstance(data, dict):
        result["summary"] = str(data.get("summary") or "").strip()
        extra = data.get("concerns")
        if isinstance(extra, list):
            # Urgent flags stay first: they are the ones that must be seen.
            result["concerns"] = flags + [str(c) for c in extra if str(c).strip()]
        sug = data.get("suggestions")
        if isinstance(sug, list):
            result["suggestions"] = [str(s) for s in sug if str(s).strip()]
        tone = data.get("tone")
        if tone in ("good", "ok", "watch") and not flags:
            result["tone"] = tone

    # Some models return the right JSON shape with every value empty. A blank
    # summary in a care record is worse than a terse factual one.
    if not result["summary"]:
        result["summary"] = local_summary(answers, lang)
        result["ai_failed"] = True
    return result
