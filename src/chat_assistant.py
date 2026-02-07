from __future__ import annotations

import os
import threading
import tempfile
from typing import Optional

from openai import OpenAI


class ChatAssistant:
    """Send text to ChatGPT and play back the response with TTS."""

    def __init__(
        self,
        client: OpenAI,
        model_chat: str,
        model_tts: str,
        tts_voice: str,
        system_prompt: str = "Du bist ein hilfreicher, knapper Sprachassistent.",
    ) -> None:
        self.client = client
        self.model_chat = model_chat
        self.model_tts = model_tts
        self.tts_voice = tts_voice
        self.system_prompt = system_prompt
        self._inflight = False
        self._last_text: Optional[str] = None
        self._lock = threading.Lock()

    def handle_text(self, text: str) -> None:
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

        thread = threading.Thread(target=self._run, args=(text,), daemon=True)
        thread.start()

    def _run(self, text: str) -> None:
        try:
            chat = self.client.chat.completions.create(
                model=self.model_chat,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": text},
                ],
            )
            answer = (chat.choices[0].message.content or "").strip()
            if not answer:
                return
            print(f"ChatGPT: {answer}")
            self._tts_play(answer)
        except Exception as e:
            print(f"ChatGPT-Fehler: {e}")
        finally:
            with self._lock:
                self._inflight = False

    def _tts_play(self, text: str) -> None:
        speech = self.client.audio.speech.create(
            model=self.model_tts,
            voice=self.tts_voice,
            input=text,
        )
        mp3_path = self._bytes_to_tempfile(speech.read(), ".mp3")
        os.system(f'ffplay -autoexit -nodisp -loglevel quiet "{mp3_path}"')
        try:
            os.remove(mp3_path)
        except OSError:
            pass

    @staticmethod
    def _bytes_to_tempfile(data: bytes, suffix: str) -> str:
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        with open(path, "wb") as f:
            f.write(data)
        return path
