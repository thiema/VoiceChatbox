from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from typing import Optional, Sequence


def transcribe_wav_bytes(
    wav_bytes: bytes,
    bin_path: str,
    model_path: str,
    language: Optional[str] = None,
    threads: int = 4,
    temperature: float = 0.0,
    extra_args: Optional[str] = None,
) -> str:
    """Transcribe WAV bytes using whisper.cpp CLI."""
    if not wav_bytes:
        return ""
    bin_path = bin_path or "whisper.cpp/main"
    model_path = model_path or "models/ggml-base.bin"
    if not os.path.exists(bin_path):
        raise FileNotFoundError(f"whisper.cpp binary not found: {bin_path}")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"whisper.cpp model not found: {model_path}")

    wav_path = None
    out_prefix = None
    try:
        fd, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        with open(wav_path, "wb") as f:
            f.write(wav_bytes)
        out_prefix = tempfile.mktemp()

        cmd: list[str] = [
            bin_path,
            "-m",
            model_path,
            "-f",
            wav_path,
            "-otxt",
            "-of",
            out_prefix,
            "-nt",
            "-t",
            str(max(1, int(threads))),
        ]
        if temperature is not None:
            cmd.extend(["--temperature", str(float(temperature))])
        if language:
            cmd.extend(["-l", language])
        if extra_args:
            cmd.extend(_split_args(extra_args))

        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        txt_path = f"{out_prefix}.txt"
        if not os.path.exists(txt_path):
            return ""
        with open(txt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    finally:
        if wav_path:
            try:
                os.remove(wav_path)
            except OSError:
                pass
        if out_prefix:
            txt_path = f"{out_prefix}.txt"
            try:
                if os.path.exists(txt_path):
                    os.remove(txt_path)
            except OSError:
                pass


def _split_args(args: str) -> Sequence[str]:
    try:
        return shlex.split(args)
    except Exception:
        return []
