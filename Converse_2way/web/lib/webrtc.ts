import { apiPost } from "@/lib/api";

export type VoiceMessage = { role: "user" | "assistant"; text: string };

export type HandsFreeCall = {
  stop: () => void;
};

type StartOptions = {
  lang?: string;
  /** Fired when the mic picks up sustained speech, for barge-in. */
  onUserSpeaking?: () => void;
};

/** Mic level above which we treat the input as real speech. */
const SPEECH_RMS_THRESHOLD = 0.045;
/** Consecutive loud frames required, so a cough or click is ignored. */
const SPEECH_FRAMES_REQUIRED = 3;
const LEVEL_POLL_MS = 100;

/**
 * Only turn messages should reach the transcript. Pipecat also sends its own
 * protocol messages over this channel; forwarding those blindly is what
 * produced rows of empty bubbles.
 */
function isVoiceMessage(value: unknown): value is VoiceMessage {
  if (typeof value !== "object" || value === null) return false;
  const m = value as Record<string, unknown>;
  return (
    (m.role === "user" || m.role === "assistant") &&
    typeof m.text === "string" &&
    m.text.trim().length > 0
  );
}

/**
 * Watch the mic and call `onSpeech` once the resident actually starts talking.
 * Used to cut off the assistant's voice mid-sentence (barge-in).
 */
function watchMicLevel(stream: MediaStream, onSpeech: () => void) {
  const AudioCtx =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext })
      .webkitAudioContext;
  if (!AudioCtx) return () => {};

  const ctx = new AudioCtx();
  const source = ctx.createMediaStreamSource(stream);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  source.connect(analyser);

  const buf = new Float32Array(analyser.fftSize);
  let loudFrames = 0;

  const timer = window.setInterval(() => {
    analyser.getFloatTimeDomainData(buf);
    let sum = 0;
    for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
    const rms = Math.sqrt(sum / buf.length);

    if (rms > SPEECH_RMS_THRESHOLD) {
      loudFrames++;
      if (loudFrames === SPEECH_FRAMES_REQUIRED) onSpeech();
    } else {
      loudFrames = 0;
    }
  }, LEVEL_POLL_MS);

  return () => {
    window.clearInterval(timer);
    source.disconnect();
    ctx.close().catch(() => {});
  };
}

/**
 * Start a hands-free WebRTC call for a conversation: sends the mic straight
 * to the backend's Pipecat pipeline (Groq STT + Groq LLM, VAD-driven, no
 * button presses needed) and receives each finalized user/assistant turn
 * over the data channel as it happens, for live transcript + TTS playback.
 */
export async function startHandsFreeCall(
  conversationId: number,
  onMessage: (message: VoiceMessage) => void,
  options: StartOptions = {}
): Promise<HandsFreeCall> {
  const { lang = "ja", onUserSpeaking } = options;

  const stream = await navigator.mediaDevices.getUserMedia({
    // Echo cancellation matters here: without it the assistant's own voice
    // coming out of the speakers would trip the barge-in detector.
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  const pc = new RTCPeerConnection();
  stream.getTracks().forEach((track) => pc.addTrack(track, stream));

  const channel = pc.createDataChannel("chat");
  channel.onmessage = (event) => {
    try {
      const parsed = JSON.parse(event.data);
      if (isVoiceMessage(parsed)) onMessage(parsed);
    } catch {
      // Ignore malformed/non-JSON messages.
    }
  };

  const stopLevelWatch = onUserSpeaking
    ? watchMicLevel(stream, onUserSpeaking)
    : () => {};

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  const answer = await apiPost<{ sdp: string; type: RTCSdpType }>(
    `/conversations/${conversationId}/voice/offer`,
    { sdp: offer.sdp, type: offer.type, lang }
  );
  await pc.setRemoteDescription(answer);

  return {
    stop() {
      stopLevelWatch();
      channel.close();
      stream.getTracks().forEach((track) => track.stop());
      pc.close();
    },
  };
}
