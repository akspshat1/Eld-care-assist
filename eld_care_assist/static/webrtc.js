/* Hands-free call client -- the browser half of Converse_2way's Pipecat
 * pipeline, ported from its web/lib/webrtc.ts.
 *
 * The mic goes straight to the backend over WebRTC; Silero VAD there decides
 * when a turn ends, so nothing is pressed between turns. Finished turns come
 * back on the data channel as {role, text} and are spoken here with
 * speechSynthesis (the pipeline has no TTS stage of its own).
 */

/** Only real turns belong in the transcript. The channel also carries
 *  Pipecat's own protocol messages; forwarding those blindly produced rows of
 *  empty bubbles in the original app. */
function isTurn(value) {
  if (typeof value !== "object" || value === null) return false;
  return (value.role === "user" || value.role === "assistant")
      && typeof value.text === "string" && value.text.trim().length > 0;
}

/**
 * @param {number} conversationId
 * @param {object} opts
 *   onTurn({role,text})   - a finished turn
 *   onUserSpeaking()      - mic picked up speech (used to cut off playback)
 *   onLevel(0..1)         - mic level for the meter
 *   lang                  - "en" | "ja"
 */
async function startHandsFreeCall(conversationId, opts = {}) {
  const { lang = "en", onTurn, onUserSpeaking, onLevel } = opts;

  const stream = await navigator.mediaDevices.getUserMedia({
    // Echo cancellation matters: without it the assistant's own voice from
    // the speakers trips the barge-in detector and it cancels itself.
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });

  const pc = new RTCPeerConnection();
  stream.getTracks().forEach(track => pc.addTrack(track, stream));

  const channel = pc.createDataChannel("chat");
  channel.onmessage = (event) => {
    try {
      const parsed = JSON.parse(event.data);
      // The backend also pushes non-turn events, e.g. an offer to place a
      // phone call the resident asked for out loud.
      if (parsed && parsed.type === "call") {
        if (opts.onCall) opts.onCall(parsed);
        return;
      }
      if (isTurn(parsed) && onTurn) onTurn(parsed);
    } catch { /* ignore non-JSON protocol frames */ }
  };

  // Local level metering + barge-in detection.
  let stopWatch = () => {};
  if (onLevel || onUserSpeaking) {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (AudioCtx) {
      const ctx = new AudioCtx();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      source.connect(analyser);
      const buf = new Float32Array(analyser.fftSize);
      let loud = 0;
      const timer = setInterval(() => {
        analyser.getFloatTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
        const rms = Math.sqrt(sum / buf.length);
        onLevel && onLevel(Math.min(1, rms * 12));
        if (rms > 0.045) {
          loud++;
          // Three frames, so a cough or a chair creak does not count.
          if (loud === 3 && onUserSpeaking) onUserSpeaking();
        } else loud = 0;
      }, 100);
      stopWatch = () => {
        clearInterval(timer);
        source.disconnect();
        ctx.close().catch(() => {});
      };
    }
  }

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  const res = await fetch(`/api/conversation/${conversationId}/voice/offer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sdp: offer.sdp, type: offer.type, lang }),
  });
  const answer = await res.json();
  if (!answer.ok) {
    stopWatch();
    stream.getTracks().forEach(t => t.stop());
    pc.close();
    throw new Error(answer.message || "Could not start the call.");
  }
  await pc.setRemoteDescription({ sdp: answer.sdp, type: answer.type });

  return {
    stop() {
      stopWatch();
      try { channel.close(); } catch {}
      stream.getTracks().forEach(t => t.stop());
      pc.close();
    },
  };
}
