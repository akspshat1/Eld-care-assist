"""Thin wrapper around the LLM provider.

Feature code should only call the functions below, never the Groq SDK
directly. If we ever swap providers, this is the only file that changes.
"""
from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL, GROQ_WHISPER_MODEL

_client = Groq(api_key=GROQ_API_KEY)


def chat_completion(messages, temperature=0.7, response_format=None):
    """Send chat messages (OpenAI-style list of {role, content} dicts) and
    return the assistant's reply text. Pass response_format={"type": "json_object"}
    to ask the model to reply with JSON only."""
    kwargs = {"model": GROQ_MODEL, "messages": messages, "temperature": temperature}
    if response_format is not None:
        kwargs["response_format"] = response_format
    response = _client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def transcribe_audio(audio_bytes, filename="audio.wav", lang="ja"):
    """Transcribe recorded audio bytes using Groq's Whisper model.

    `lang` must match the language actually being spoken. Whisper will happily
    transcribe English audio as Japanese if told to, producing nonsense, so
    this follows the UI's language toggle rather than being fixed.
    """
    transcription = _client.audio.transcriptions.create(
        file=(filename, audio_bytes),
        model=GROQ_WHISPER_MODEL,
        language="en" if lang == "en" else "ja",
    )
    return transcription.text
