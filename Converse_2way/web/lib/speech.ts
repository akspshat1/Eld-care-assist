/**
 * Text-to-speech helpers.
 *
 * speechSynthesis fails *silently* when no installed voice matches the
 * requested language: speak() resolves, nothing is heard, and there is no
 * error. So the voice is chosen explicitly here, and callers can find out
 * when one is missing and tell the user instead of leaving them puzzled.
 */

export type SpeakResult = { spoken: boolean; missingVoice: boolean };

function bcp47(lang: string) {
  return lang === "ja" ? "ja-JP" : "en-US";
}

/**
 * Voices load asynchronously in most browsers: getVoices() is empty on the
 * first call and only fills in once "voiceschanged" fires.
 */
export function loadVoices(): Promise<SpeechSynthesisVoice[]> {
  return new Promise((resolve) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      resolve([]);
      return;
    }
    const existing = window.speechSynthesis.getVoices();
    if (existing.length > 0) {
      resolve(existing);
      return;
    }
    const timer = window.setTimeout(() => resolve(window.speechSynthesis.getVoices()), 1500);
    window.speechSynthesis.addEventListener(
      "voiceschanged",
      () => {
        window.clearTimeout(timer);
        resolve(window.speechSynthesis.getVoices());
      },
      { once: true }
    );
  });
}

/** Best installed voice for a language, or null if there is none. */
export function pickVoice(
  voices: SpeechSynthesisVoice[],
  lang: string
): SpeechSynthesisVoice | null {
  const want = bcp47(lang).toLowerCase();
  const prefix = want.split("-")[0];
  return (
    voices.find((v) => v.lang.toLowerCase() === want) ??
    voices.find((v) => v.lang.toLowerCase().replace("_", "-").startsWith(prefix)) ??
    null
  );
}

export async function hasVoiceFor(lang: string): Promise<boolean> {
  return pickVoice(await loadVoices(), lang) !== null;
}

/**
 * Speak `text` in `lang`. Returns whether a matching voice existed, so the UI
 * can warn when Japanese audio is impossible on this machine.
 */
export async function speakText(text: string, lang: string): Promise<SpeakResult> {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    return { spoken: false, missingVoice: false };
  }
  // Drop anything queued so replies never talk over each other.
  window.speechSynthesis.cancel();

  const voices = await loadVoices();
  const voice = pickVoice(voices, lang);
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = bcp47(lang);
  if (voice) utterance.voice = voice;

  // With no matching voice this is very likely inaudible, but attempt it
  // anyway -- some platforms fall back to a usable default.
  window.speechSynthesis.speak(utterance);
  return { spoken: true, missingVoice: voice === null };
}

export function stopSpeaking() {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
}
