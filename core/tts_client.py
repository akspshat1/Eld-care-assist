"""Thin wrapper around the text-to-speech engine.

Feature code should only call speak() below, never pyttsx3 directly.
If we ever swap the TTS engine, this is the only file that changes.
"""
import pyttsx3


def speak(text):
    """Read the given text aloud using the offline TTS engine."""
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()
    engine.stop()
