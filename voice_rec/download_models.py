"""Fetch the Japanese speech-emotion model (run once, ~1.2 GB).

Bagus/wav2vec2-xlsr-japanese-speech-emotion-recognition
  HuBERT-large fine-tuned on JTES (Japanese Twitter Emotional Speech).
  Labels: ang / joy / neu / sad.
"""

import os
import sys

MODEL_ID = "Bagus/wav2vec2-xlsr-japanese-speech-emotion-recognition"
HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "models", "ja-ser")


def main():
    from huggingface_hub import snapshot_download

    os.makedirs(DEST, exist_ok=True)
    print(f"Downloading {MODEL_ID}")
    print("~1.2 GB, one time. This can take a few minutes.\n")
    try:
        snapshot_download(
            MODEL_ID,
            local_dir=DEST,
            # safetensors only -- skip the duplicate pytorch_model.bin
            allow_patterns=["config.json", "preprocessor_config.json",
                            "model.safetensors"],
        )
    except Exception as e:                    # noqa: BLE001
        print(f"\nDownload failed: {e}")
        return 1

    weights = os.path.join(DEST, "model.safetensors")
    if not os.path.exists(weights):
        print("\nWeights missing after download.")
        return 1
    print(f"\nModel ready ({os.path.getsize(weights) / 1e9:.2f} GB)")
    print("Start the app with:  python run.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
