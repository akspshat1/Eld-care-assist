/* Hands-free voice: continuous listening with automatic turn-taking.
 *
 * Deliberately browser-side VAD rather than a streaming server pipeline:
 *   - no extra service to run, and it works on the endpoints we already have;
 *   - each finished turn arrives as one complete WAV, which is exactly what
 *     the voice-emotion model needs later (a stream would have to be
 *     reassembled first).
 *
 * The loop is: listen -> detect speech -> detect the pause that ends it ->
 * hand the clip to a callback -> speak the reply -> listen again. The mic
 * stays open throughout, so nothing needs pressing between turns.
 */

const VAD = {
  START_RMS: 0.022,      // above this counts as speech
  STOP_RMS: 0.014,       // below this counts as silence (hysteresis)
  START_FRAMES: 3,       // ~150ms of sound before we call it speech
  SILENCE_MS: 1100,      // pause that ends a turn
  MIN_SPEECH_MS: 400,    // shorter than this is a cough, not a turn
  MAX_TURN_MS: 25000,    // hard stop so one turn cannot run forever
  FRAME_MS: 50,
};

function encodeWAVFloat(samples, rate) {
  const buf = new ArrayBuffer(44 + samples.length * 2), view = new DataView(buf);
  const str = (o, s) => { for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i)); };
  str(0, "RIFF"); view.setUint32(4, 36 + samples.length * 2, true); str(8, "WAVE");
  str(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 1, true); view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  str(36, "data"); view.setUint32(40, samples.length * 2, true);
  let off = 44;
  for (let i = 0; i < samples.length; i++, off += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([view], { type: "audio/wav" });
}

/**
 * @param {object} opts
 *   onTurn(blob)   - a finished spoken turn
 *   onState(s)     - "idle" | "listening" | "speaking" | "thinking"
 *   onLevel(v)     - 0..1 mic level, for the meter
 *   onSpeechStart  - fired when the user starts talking (used for barge-in)
 */
class VoiceLoop {
  constructor(opts = {}) {
    this.opts = opts;
    this.running = false;
    this.paused = false;          // true while the assistant talks or we wait
    this._reset();
  }

  _reset() {
    this.chunks = [];
    this.loudFrames = 0;
    this.speaking = false;
    this.silenceMs = 0;
    this.speechMs = 0;
  }

  async start() {
    if (this.running) return;
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true,
               noiseSuppression: true, autoGainControl: true },
    });
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    // An AudioContext created outside a click starts suspended, and then
    // onaudioprocess never fires -- the mic looks dead. The medicine reminder
    // starts listening from a timer, so this resume is what makes it work.
    if (this.ctx.state === "suspended") {
      try { await this.ctx.resume(); } catch (e) { /* older browsers */ }
    }
    this.src = this.ctx.createMediaStreamSource(this.stream);
    this.node = this.ctx.createScriptProcessor(2048, 1, 1);
    this.rate = this.ctx.sampleRate;
    this.running = true;
    this._reset();

    this.node.onaudioprocess = (e) => this._frame(e.inputBuffer.getChannelData(0));
    this.src.connect(this.node);
    this.node.connect(this.ctx.destination);
    this._setState("listening");
  }

  _setState(s) {
    this.state = s;
    this.opts.onState && this.opts.onState(s);
  }

  _frame(data) {
    if (!this.running) return;

    let sum = 0;
    for (let i = 0; i < data.length; i++) sum += data[i] * data[i];
    const rms = Math.sqrt(sum / data.length);
    this.opts.onLevel && this.opts.onLevel(Math.min(1, rms * 12));

    const frameMs = (data.length / this.rate) * 1000;

    // While the assistant is talking we only watch for barge-in.
    if (this.paused) {
      if (rms > VAD.START_RMS) {
        this.loudFrames++;
        if (this.loudFrames >= VAD.START_FRAMES) {
          this.loudFrames = 0;
          this.opts.onSpeechStart && this.opts.onSpeechStart();
        }
      } else {
        this.loudFrames = 0;
      }
      return;
    }

    if (!this.speaking) {
      if (rms > VAD.START_RMS) {
        this.loudFrames++;
        if (this.loudFrames >= VAD.START_FRAMES) {
          this.speaking = true;
          this.silenceMs = 0;
          this.speechMs = 0;
          this.opts.onSpeechStart && this.opts.onSpeechStart();
        }
      } else {
        this.loudFrames = 0;
        // Keep a small rolling pre-roll so the first syllable is not clipped.
        this.chunks.push(new Float32Array(data));
        if (this.chunks.length > 6) this.chunks.shift();
      }
      if (this.speaking) this.chunks.push(new Float32Array(data));
      return;
    }

    this.chunks.push(new Float32Array(data));
    this.speechMs += frameMs;

    if (rms < VAD.STOP_RMS) {
      this.silenceMs += frameMs;
    } else {
      this.silenceMs = 0;
    }

    const ended = this.silenceMs >= VAD.SILENCE_MS;
    const tooLong = this.speechMs >= VAD.MAX_TURN_MS;
    if (ended || tooLong) this._finishTurn();
  }

  _finishTurn() {
    const enough = this.speechMs - this.silenceMs >= VAD.MIN_SPEECH_MS;
    const chunks = this.chunks;
    this._reset();
    if (!enough) return;                       // too short: ignore, keep listening

    let total = 0; chunks.forEach(c => total += c.length);
    const flat = new Float32Array(total);
    let o = 0; chunks.forEach(c => { flat.set(c, o); o += c.length; });
    const blob = encodeWAVFloat(flat, this.rate);

    this.paused = true;                        // stop capturing until handled
    this._setState("thinking");
    Promise.resolve(this.opts.onTurn && this.opts.onTurn(blob))
      .finally(() => {
        if (!this.running) return;
        this.paused = false;
        this._reset();
        this._setState("listening");
      });
  }

  /** Hold the mic while the assistant speaks, then resume. */
  hold() { this.paused = true; this._setState("speaking"); }
  resume() { if (!this.running) return; this.paused = false; this._reset(); this._setState("listening"); }

  stop() {
    this.running = false;
    try { this.node && this.node.disconnect(); } catch (e) {}
    try { this.src && this.src.disconnect(); } catch (e) {}
    if (this.stream) this.stream.getTracks().forEach(t => t.stop());
    if (this.ctx && this.ctx.state !== "closed") this.ctx.close().catch(() => {});
    this._setState("idle");
    this.opts.onLevel && this.opts.onLevel(0);
  }
}

/* ---------- speech synthesis with a real voice picked for the language ---- */

function loadVoices() {
  return new Promise(resolve => {
    if (!("speechSynthesis" in window)) return resolve([]);
    const have = window.speechSynthesis.getVoices();
    if (have.length) return resolve(have);
    const timer = setTimeout(() => resolve(window.speechSynthesis.getVoices()), 1200);
    window.speechSynthesis.addEventListener("voiceschanged", () => {
      clearTimeout(timer);
      resolve(window.speechSynthesis.getVoices());
    }, { once: true });
  });
}

async function hasVoiceFor(lang) {
  const want = lang === "ja" ? "ja" : "en";
  return (await loadVoices()).some(v => v.lang.toLowerCase().startsWith(want));
}

/** Speak, resolving when finished so the caller can resume listening. */
async function say(text, lang) {
  if (!("speechSynthesis" in window) || !text) return;
  window.speechSynthesis.cancel();
  const voices = await loadVoices();
  const want = lang === "ja" ? "ja" : "en";
  const voice = voices.find(v => v.lang.toLowerCase().startsWith(want));
  return new Promise(resolve => {
    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang === "ja" ? "ja-JP" : "en-US";
    if (voice) u.voice = voice;
    u.onend = resolve;
    u.onerror = resolve;
    // Safety net: some browsers never fire onend for long text.
    setTimeout(resolve, Math.min(20000, 1800 + text.length * 90));
    window.speechSynthesis.speak(u);
  });
}

function shutUp() {
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
}

/**
 * Listen for a single spoken reply, then stop.
 *
 * Used by the medicine reminder: it asks a question aloud and needs one
 * answer, not a conversation. Resolves with a WAV Blob, or null if nothing
 * was said before the timeout.
 */
function listenOnce(timeoutMs = 12000, onLevel = null) {
  return new Promise(async (resolve) => {
    let loop, timer, done = false;

    const finish = (blob) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      try { loop && loop.stop(); } catch (e) {}
      resolve(blob);
    };

    try {
      loop = new VoiceLoop({
        onLevel: onLevel || (() => {}),
        onTurn: (blob) => finish(blob),
      });
      await loop.start();
    } catch (e) {
      finish(null);                            // no microphone permission
      return;
    }
    timer = setTimeout(() => finish(null), timeoutMs);
  });
}
