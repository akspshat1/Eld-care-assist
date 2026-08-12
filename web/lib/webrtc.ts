import { apiPost } from "@/lib/api";

export type VoiceMessage = { role: "user" | "assistant"; text: string };

export type HandsFreeCall = {
  stop: () => void;
};

/**
 * Start a hands-free WebRTC call for a conversation: sends the mic straight
 * to the backend's Pipecat pipeline (Groq STT + Groq LLM, VAD-driven, no
 * button presses needed) and receives each finalized user/assistant turn
 * over the data channel as it happens, for live transcript + TTS playback.
 */
export async function startHandsFreeCall(
  conversationId: number,
  onMessage: (message: VoiceMessage) => void
): Promise<HandsFreeCall> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const pc = new RTCPeerConnection();
  stream.getTracks().forEach((track) => pc.addTrack(track, stream));

  const channel = pc.createDataChannel("chat");
  channel.onmessage = (event) => {
    try {
      onMessage(JSON.parse(event.data));
    } catch {
      // Ignore malformed/non-JSON messages.
    }
  };

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  const answer = await apiPost<{ sdp: string; type: RTCSdpType }>(
    `/conversations/${conversationId}/voice/offer`,
    { sdp: offer.sdp, type: offer.type }
  );
  await pc.setRemoteDescription(answer);

  return {
    stop() {
      channel.close();
      stream.getTracks().forEach((track) => track.stop());
      pc.close();
    },
  };
}
