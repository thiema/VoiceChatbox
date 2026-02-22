from __future__ import annotations

import threading
import json
import os
import base64
import time
import shutil
import subprocess
from collections import deque
from typing import Optional, Callable, Deque, Tuple, List, Dict

from openai import OpenAI

from .audio_io import play_wav_bytes

class ChatAssistant:
    """Send text to ChatGPT and play back the response with TTS."""

    def __init__(
        self,
        client: OpenAI,
        model_chat: str,
        model_tts: str,
        tts_voice: str,
        audio_output_device: str | int | None = None,
        announce_output: bool = True,
        on_tts_done: Optional[Callable[[], None]] = None,
        system_prompt: str = "Du bist ein hilfreicher, knapper Sprachassistent.",
        echo_input_before_chat: bool = True,
        history_path: str | None = None,
        history_dir: str | None = None,
        history_max: int = 50,
    ) -> None:
        self.client = client
        self.model_chat = model_chat
        self.model_tts = model_tts
        self.tts_voice = tts_voice
        self.audio_output_device = audio_output_device
        self._announce_output = announce_output
        self._on_tts_done = on_tts_done
        self.system_prompt = system_prompt
        self.echo_input_before_chat = echo_input_before_chat
        self._inflight = False
        self._last_text: Optional[str] = None
        self._lock = threading.Lock()
        self._history_path = history_path or "data/tts_history/index.json"
        self._history_dir = history_dir or os.path.dirname(self._history_path) or "data/tts_history"
        self._history_max = max(1, history_max)
        self._history: Deque[Tuple[str, bytes, str]] = deque()
        self._history_seq = 0
        self._load_history()

    def set_on_tts_done(self, callback: Optional[Callable[[], None]]) -> None:
        self._on_tts_done = callback

    def handle_text(self, text: str, system_prompt_override: Optional[str] = None) -> None:
        """Send text to ChatGPT and speak the response (non-blocking)."""
        text = (text or "").strip()
        if not text:
            return
        if self._last_text == text:
            return

        with self._lock:
            if self._inflight:
                return
            self._inflight = True
            self._last_text = text

        thread = threading.Thread(target=self._run, args=(text, system_prompt_override), daemon=True)
        thread.start()

    def speak(self, text: str, notify: bool = True) -> None:
        """Speak text via TTS without sending it to ChatGPT (non-blocking)."""
        text = (text or "").strip()
        if not text:
            return

        def _speak() -> None:
            try:
                self._tts_play(text, notify=notify)
            except Exception as e:
                print(f"TTS-Fehler: {e}")

        thread = threading.Thread(target=_speak, daemon=True)
        thread.start()

    def speak_blocking(self, text: str, notify: bool = True) -> bool:
        """Speak text via TTS and wait for completion. Returns success."""
        text = (text or "").strip()
        if not text:
            return False
        try:
            self._tts_play(text, notify=notify)
            return True
        except Exception as e:
            print(f"TTS-Fehler: {e}")
            return False

    def _run(self, text: str, system_prompt_override: Optional[str]) -> None:
        try:
            if self.echo_input_before_chat:
                self._tts_play(text, notify=False)
            system_prompt = (system_prompt_override or self.system_prompt).strip() or self.system_prompt
            chat = self.client.chat.completions.create(
                model=self.model_chat,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
            )
            answer = (chat.choices[0].message.content or "").strip()
            if not answer:
                return
            print(f"ChatGPT: {answer}")
            wav_bytes = self._tts_synthesize(answer)
            self._append_history(answer, wav_bytes)
            self._save_history()
            self._play_wav_bytes(wav_bytes)
        except Exception as e:
            print(f"ChatGPT-Fehler: {e}")
        finally:
            with self._lock:
                self._inflight = False

    def _tts_play(self, text: str, notify: bool = True) -> None:
        wav_bytes = self._tts_synthesize(text)
        self._play_wav_bytes(wav_bytes, notify=notify)

    def _tts_synthesize(self, text: str) -> bytes:
        speech = self.client.audio.speech.create(
            model=self.model_tts,
            voice=self.tts_voice,
            input=text,
            response_format="wav",
        )
        return speech.read()

    def _play_wav_bytes(self, wav_bytes: bytes, notify: bool = True) -> None:
        announce = self._announce_output
        self._announce_output = False
        play_wav_bytes(wav_bytes, device=self.audio_output_device, announce=announce)
        if notify and self._on_tts_done:
            try:
                self._on_tts_done()
            except Exception:
                pass

    def play_history(self, index: int) -> bool:
        """Play a previous answer by 1-based index (1 = most recent)."""
        if index <= 0:
            return False
        if not self._history:
            return False
        if index > len(self._history):
            return False
        answer, wav_bytes, _ = list(self._history)[-index]
        print(f"Historie {index}: {answer}")
        self._play_wav_bytes(wav_bytes)
        return True

    def _load_history(self) -> None:
        try:
            if not os.path.exists(self._history_path):
                print("Historie: 0 Aufnahmen vorhanden.")
                return
            with open(self._history_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                print("Historie: 0 Aufnahmen vorhanden.")
                return
            for item in data[-self._history_max:]:
                if not isinstance(item, dict):
                    continue
                text = (item.get("text") or "").strip()
                ogg_rel = (item.get("ogg_path") or "").strip()
                if not text or not ogg_rel:
                    # Backward-compat: older JSON with base64 WAV
                    wav_b64 = (item.get("wav_b64") or "").strip()
                    if not text or not wav_b64:
                        continue
                    try:
                        wav_bytes = base64.b64decode(wav_b64.encode("ascii"))
                    except Exception:
                        continue
                    ogg_rel = self._write_ogg(wav_bytes)
                    if not ogg_rel:
                        continue
                    self._history.append((text, wav_bytes, ogg_rel))
                    continue
                ogg_path = os.path.join(self._history_dir, ogg_rel)
                wav_bytes = self._decode_ogg_to_wav(ogg_path)
                if not wav_bytes:
                    continue
                self._history.append((text, wav_bytes, ogg_rel))
            print(f"Historie: {len(self._history)} Aufnahme(n) vorhanden.")
        except Exception as e:
            print(f"Historie laden fehlgeschlagen: {e}")

    def _save_history(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._history_path) or ".", exist_ok=True)
            os.makedirs(self._history_dir, exist_ok=True)
            data: List[Dict[str, str]] = []
            for text, wav_bytes, ogg_rel in list(self._history):
                data.append({
                    "text": text,
                    "ogg_path": ogg_rel,
                })
            with open(self._history_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            self._prune_history_files()
        except Exception as e:
            print(f"Historie speichern fehlgeschlagen: {e}")

    def _append_history(self, text: str, wav_bytes: bytes) -> None:
        ogg_rel = self._write_ogg(wav_bytes)
        if not ogg_rel:
            return
        if len(self._history) >= self._history_max:
            old = self._history.popleft()
            self._remove_history_file(old[2])
        self._history.append((text, wav_bytes, ogg_rel))

    def _write_ogg(self, wav_bytes: bytes) -> str:
        if not self._ffmpeg_available():
            print("Historie: ffmpeg fehlt, OGG kann nicht gespeichert werden.")
            return ""
        os.makedirs(self._history_dir, exist_ok=True)
        self._history_seq += 1
        filename = f"tts_{int(time.time())}_{self._history_seq}.ogg"
        ogg_path = os.path.join(self._history_dir, filename)
        try:
            proc = subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-f",
                    "wav",
                    "-i",
                    "pipe:0",
                    "-c:a",
                    "libopus",
                    ogg_path,
                ],
                input=wav_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except Exception as e:
            print(f"Historie: OGG speichern fehlgeschlagen ({e})")
            return ""
        return filename

    def _decode_ogg_to_wav(self, ogg_path: str) -> bytes:
        if not self._ffmpeg_available():
            print("Historie: ffmpeg fehlt, OGG kann nicht geladen werden.")
            return b""
        try:
            proc = subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    ogg_path,
                    "-f",
                    "wav",
                    "pipe:1",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            return proc.stdout
        except Exception as e:
            print(f"Historie: OGG laden fehlgeschlagen ({e})")
            return b""

    def _prune_history_files(self) -> None:
        try:
            keep = {entry[2] for entry in self._history if entry[2]}
            for name in os.listdir(self._history_dir):
                if not name.endswith(".ogg"):
                    continue
                if name.startswith("tts_") and name not in keep:
                    try:
                        os.remove(os.path.join(self._history_dir, name))
                    except OSError:
                        pass
        except Exception:
            pass

    def _remove_history_file(self, ogg_rel: str) -> None:
        if not ogg_rel:
            return
        try:
            os.remove(os.path.join(self._history_dir, ogg_rel))
        except OSError:
            pass

    @staticmethod
    def _ffmpeg_available() -> bool:
        return shutil.which("ffmpeg") is not None