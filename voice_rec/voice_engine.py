"""Speech emotion recognition for Japanese, CPU-only.

Model: Bagus/wav2vec2-xlsr-japanese-speech-emotion-recognition
       (HuBERT-large fine-tuned on JTES, a Japanese emotional speech corpus)

Four emotions: 怒り / 喜び / 中立 / 悲しみ.

Audio is analysed in short windows so one recording yields several readings
across time, and near-silent windows are skipped rather than guessed at --
silence must never be logged as an emotion.
"""

import io
import os

import numpy as np

SAMPLE_RATE = 16000
WINDOW_SEC = 4.0          # analysis window
HOP_SEC = 4.0             # no overlap: each window is an independent reading
MIN_CLIP_SEC = 0.6        # anything shorter cannot be judged
SILENCE_RMS = 0.006       # below this a window counts as silence, not speech

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "models", "ja-ser")

# The model's own label ids, kept in its config: 0=ang 1=joy 2=neu 3=sad
EMOTIONS = ["ang", "joy", "neu", "sad"]

JA = {"ang": "怒り", "joy": "喜び", "neu": "中立", "sad": "悲しみ"}
EN = {"ang": "anger", "joy": "joy", "neu": "neutral", "sad": "sadness"}

# Same valence convention as the face monitor, so the wellbeing score means
# the same thing in both apps.
VALENCE = {"joy": 1.0, "neu": 0.0, "sad": -0.8, "ang": -0.9}
NEGATIVE = {"sad", "ang"}

COLORS = {
    "joy": "#16a34a",
    "neu": "#9ca3af",
    "sad": "#e08a3c",
    "ang": "#dc2626",
}


def label_ja(code):
    return JA.get(code, code)


def label_en(code):
    return EN.get(code, code)


class NoSpeech(Exception):
    """Raised when a clip has no usable speech in it."""


def load_audio(data, sr_hint=None):
    """Read bytes / path / ndarray into mono float32 at 16 kHz."""
    import librosa
    import soundfile as sf

    if isinstance(data, np.ndarray):
        wav, sr = data.astype(np.float32), (sr_hint or SAMPLE_RATE)
    else:
        src = io.BytesIO(data) if isinstance(data, (bytes, bytearray)) else data
        wav, sr = sf.read(src, dtype="float32", always_2d=False)

    if wav.ndim > 1:                       # stereo -> mono
        wav = wav.mean(axis=1)
    if sr != SAMPLE_RATE:
        wav = librosa.resample(wav, orig_sr=sr, target_sr=SAMPLE_RATE)
    return np.ascontiguousarray(wav, dtype=np.float32)


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0


def _build_model(model_dir, torch, nn):
    """Rebuild the exact architecture this checkpoint was trained with.

    The published config says `HubertForSequenceClassification`, but the
    weights are a wav2vec2 backbone plus a two-layer head
    (`classifier.dense` 1024->1024, `classifier.out_proj` 1024->4).
    That is the custom `Wav2Vec2ForSpeechClassification` used by the common
    SER training scripts, not any stock transformers class.

    Loading it with AutoModelForAudioClassification silently discards the
    trained head and initialises a random one -- which yields ~25% on every
    class, i.e. pure chance. So we assemble it by hand instead.
    """
    from transformers import AutoConfig, Wav2Vec2Model

    cfg = AutoConfig.from_pretrained(model_dir)

    class ClassificationHead(nn.Module):
        def __init__(self, hidden, n_labels, dropout):
            super().__init__()
            self.dense = nn.Linear(hidden, hidden)
            self.dropout = nn.Dropout(dropout)
            self.out_proj = nn.Linear(hidden, n_labels)

        def forward(self, x):
            x = self.dropout(x)
            x = torch.tanh(self.dense(x))
            x = self.dropout(x)
            return self.out_proj(x)

    class SpeechClassifier(nn.Module):
        def __init__(self):
            super().__init__()
            self.wav2vec2 = Wav2Vec2Model(cfg)
            self.classifier = ClassificationHead(
                cfg.hidden_size, len(cfg.id2label),
                getattr(cfg, "final_dropout", 0.0))

        def forward(self, input_values, attention_mask=None):
            hidden = self.wav2vec2(input_values,
                                   attention_mask=attention_mask).last_hidden_state
            return self.classifier(hidden.mean(dim=1))    # pooling_mode: mean

    model = SpeechClassifier()

    from safetensors.torch import load_file
    state = load_file(os.path.join(model_dir, "model.safetensors"))
    missing, unexpected = model.load_state_dict(state, strict=False)

    # The trained head must land. If it does not, predictions are noise, and
    # a silent ~25%-everywhere failure is far worse than a loud error.
    critical = [k for k in missing
                if k.startswith("classifier.") or k.startswith("wav2vec2.encoder")]
    if critical:
        raise RuntimeError(
            "Model weights did not load correctly - missing: "
            + ", ".join(critical[:6]))
    return model, cfg


class VoiceEngine:
    def __init__(self, model_dir=MODEL_DIR):
        if not os.path.isdir(model_dir):
            raise FileNotFoundError(
                f"Missing model: {model_dir}\nRun:  python download_models.py")

        import torch
        from torch import nn
        from transformers import AutoFeatureExtractor

        torch.set_num_threads(2)           # keep the machine responsive
        self.torch = torch
        self.extractor = AutoFeatureExtractor.from_pretrained(model_dir)
        self.model, cfg = _build_model(model_dir, torch, nn)
        self.model.eval()

        self.id2label = {int(k): v for k, v in (cfg.id2label or {}).items()}

    def _forward(self, wav):
        """One window -> probability dict."""
        inputs = self.extractor(wav, sampling_rate=SAMPLE_RATE,
                                return_tensors="pt", padding=True)
        with self.torch.no_grad():
            logits = self.model(inputs.input_values,
                                getattr(inputs, "attention_mask", None))[0]
        probs = self.torch.softmax(logits, dim=-1).numpy()
        return {self.id2label.get(i, str(i)): float(p) for i, p in enumerate(probs)}

    def analyze(self, wav):
        """Analyse a clip.

        Returns {"overall": {...}, "windows": [...], "duration": sec}.
        Raises NoSpeech if the clip is too short or too quiet to judge.
        """
        duration = len(wav) / SAMPLE_RATE
        if duration < MIN_CLIP_SEC:
            raise NoSpeech("録音が短すぎます (too short to analyse)")
        if rms(wav) < SILENCE_RMS:
            raise NoSpeech("音声が検出されませんでした (no speech detected)")

        win = int(WINDOW_SEC * SAMPLE_RATE)
        hop = int(HOP_SEC * SAMPLE_RATE)
        starts = list(range(0, max(1, len(wav) - win + 1), hop)) or [0]
        # Keep a trailing remainder if it is long enough to stand on its own.
        if len(wav) - (starts[-1] + win) > MIN_CLIP_SEC * SAMPLE_RATE:
            starts.append(len(wav) - win)

        windows = []
        for s in starts:
            chunk = wav[s:s + win]
            if len(chunk) < MIN_CLIP_SEC * SAMPLE_RATE:
                continue
            if rms(chunk) < SILENCE_RMS:      # skip silent stretches
                continue
            probs = self._forward(chunk)
            code = max(probs, key=probs.get)
            windows.append({
                "start": round(s / SAMPLE_RATE, 2),
                "end": round(min(s + win, len(wav)) / SAMPLE_RATE, 2),
                "emotion": code,
                "confidence": round(probs[code] * 100, 1),
                "valence": round(sum(VALENCE.get(k, 0.0) * v
                                     for k, v in probs.items()), 3),
                "probs": {k: round(v * 100, 1) for k, v in probs.items()},
            })

        if not windows:
            raise NoSpeech("音声が検出されませんでした (no speech detected)")

        # Overall = mean probability across windows, so a long calm stretch
        # is not outvoted by one loud moment.
        keys = windows[0]["probs"].keys()
        mean = {k: float(np.mean([w["probs"][k] for w in windows])) for k in keys}
        code = max(mean, key=mean.get)
        overall = {
            "emotion": code,
            "ja": label_ja(code),
            "en": label_en(code),
            "confidence": round(mean[code], 1),
            "valence": round(sum(VALENCE.get(k, 0.0) * v / 100 for k, v in mean.items()), 3),
            "probs": {k: round(v, 1) for k, v in mean.items()},
        }
        return {"overall": overall, "windows": windows,
                "duration": round(duration, 2)}
