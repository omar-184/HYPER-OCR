"""Download the Unlimited-OCR weights once, for offline use.

    python -m hyperocr.download_model                 # from Hugging Face
    python -m hyperocr.download_model --source modelscope

The files go to ./models/Unlimited-OCR (or HYPEROCR_MODEL_DIR). After this the
app never needs the internet again.
"""

from __future__ import annotations

import argparse
import sys

from .engines.unlimited import MODEL_ID, model_dir, model_present


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=("huggingface", "modelscope"), default="huggingface")
    args = parser.parse_args(argv)
    target = model_dir()
    target.mkdir(parents=True, exist_ok=True)
    print("Downloading Unlimited-OCR (several GB) to %s ..." % target)
    if args.source == "huggingface":
        from huggingface_hub import snapshot_download

        snapshot_download(repo_id=MODEL_ID, local_dir=str(target))
    else:
        from modelscope import snapshot_download

        snapshot_download("PaddlePaddle/Unlimited-OCR", local_dir=str(target))
    if not model_present(target):
        print("The download finished but the model files are incomplete. Run this again to resume.")
        return 1
    print("Done. HYPER-OCR will now use Unlimited-OCR on this computer's NVIDIA GPU.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
