# Arona-owned launcher. Do not edit clone files from GPT-SoVITS_minimal_inference.
"""Run upstream api_server.py with local hooks (offline BERT, optional SV skip)."""
from __future__ import annotations

import argparse
import logging
import os
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
    sys.path.insert(0, os.path.join(_HERE, "GPT_SoVITS"))

logger = logging.getLogger("gpt-sovits-api")


def _wrap_from_pretrained(owner, name: str) -> None:
    orig = getattr(owner, name)

    def wrapped(*args, **kwargs):
        kwargs.setdefault("local_files_only", True)
        return orig(*args, **kwargs)

    setattr(owner, name, wrapped)


def _install_hooks() -> None:
    from transformers import AutoModelForMaskedLM, AutoTokenizer

    _wrap_from_pretrained(AutoTokenizer, "from_pretrained")
    _wrap_from_pretrained(AutoModelForMaskedLM, "from_pretrained")

    import GPT_SoVITS.sv as sv_mod

    sv_path = os.environ.get(
        "SV_MODEL_PATH",
        os.path.join(os.getcwd(), "pretrained_models", "sv", "pretrained_eres2netv2w24s4ep4.ckpt"),
    )
    if os.path.isfile(sv_path):
        return

    class SVOptional:
        def __init__(self, device, is_half):
            self.device = device
            self.is_half = is_half
            logger.info("SV checkpoint not found (%s); skipping (v2 / non-v2Pro).", sv_path)

        def compute_embedding3(self, wav):
            return None

    sv_mod.SV = SVOptional


def _preload_default_voice(api_server) -> None:
    names = list(api_server.voice_manager.voices.keys())
    if not names:
        logger.warning("No voices in config; skipping engine preload.")
        return
    name = names[0]
    voice_config = api_server.voice_manager.get_voice(name)
    logger.info("Preloading voice engine: %s", name)
    try:
        api_server.model_manager.get_engine(voice_config["gpt_path"], voice_config["sovits_path"])
    except Exception:
        logger.exception("Preload failed for voice %s", name)
        raise
    logger.info("Preloaded voice engine: %s", name)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    _install_hooks()

    import api_server
    import uvicorn

    @api_server.app.on_event("startup")
    def _on_startup():
        _preload_default_voice(api_server)

    parser = argparse.ArgumentParser(description="Arona launcher for GPT-SoVITS minimal api_server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--cnhubert_path")
    parser.add_argument("--bert_path")
    parser.add_argument("--voices_config")
    args = parser.parse_args()
    uvicorn.run(api_server.app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
