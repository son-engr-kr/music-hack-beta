"""Shared Magenta RT 2 engine for low-latency streaming."""

import io
import logging
import struct
import threading
import tempfile
from typing import Any

import numpy as np

from magenta_rt import MagentaRT2Mlxfn, audio

logger = logging.getLogger(__name__)

_NOTES_MASKED = [-1] * 128


def _wav_to_bytes(wav: audio.Waveform) -> bytes:
    samples = wav.samples
    if samples.ndim == 1:
        samples = samples[:, np.newaxis]
    n_channels = samples.shape[1]
    sample_rate = wav.sample_rate
    bits_per_sample = 16

    data = (samples * 32767).clip(-32768, 32767).astype(np.int16).tobytes()
    data_size = len(data)

    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))
    buf.write(struct.pack("<H", 1))
    buf.write(struct.pack("<H", n_channels))
    buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", sample_rate * n_channels * bits_per_sample // 8))
    buf.write(struct.pack("<H", n_channels * bits_per_sample // 8))
    buf.write(struct.pack("<H", bits_per_sample))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(data)
    return buf.getvalue()


class MRT2Engine:
    """Singleton engine. One model instance, serialized generation."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self, model_size: str = "mrt2_small"):
        self.model_size = model_size
        self._states: dict[str, Any] = {}
        self._style_cache: dict[str, Any] = {}
        self._audio_style_cache: dict[str, Any] = {}
        self._generate_lock = threading.Lock()

        logger.info("Loading Magenta RT 2 (%s)...", model_size)
        self._mrt = MagentaRT2Mlxfn(size=model_size)
        dummy_wav, _ = self._mrt.generate(frames=5)
        self._sample_rate = dummy_wav.sample_rate
        logger.info("Engine ready (sample rate: %d).", self._sample_rate)

    @classmethod
    def get_instance(cls, model_size: str = "mrt2_small") -> "MRT2Engine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(model_size=model_size)
        return cls._instance

    def get_style(self, prompt: str | None):
        if prompt is None:
            return None
        if prompt.startswith("audio:"):
            return self._audio_style_cache[prompt]
        with self._generate_lock:
            if prompt not in self._style_cache:
                self._style_cache[prompt] = self._mrt.embed_style(prompt)
            return self._style_cache[prompt]

    def get_mixed_style(self, sources: list[dict[str, Any]]):
        assert sources
        weighted = None
        total_weight = 0.0
        for source in sources:
            weight = float(source["weight"])
            if weight <= 0:
                continue
            kind = source["kind"]
            if kind == "audio":
                style = self.get_style(source["key"])
            elif kind == "text":
                style = self.get_style(source["text"])
            else:
                raise ValueError(f"Unsupported style source: {kind}")
            weighted = style * weight if weighted is None else weighted + style * weight
            total_weight += weight
        assert weighted is not None
        assert total_weight > 0
        return weighted / total_weight

    def set_audio_style(self, name: str, suffix: str, data: bytes) -> str:
        assert data
        key = f"audio:{time_safe_name(name)}:{len(data)}"
        with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
            tmp.write(data)
            tmp.flush()
            wav = audio.Waveform.from_file(tmp.name)
            with self._generate_lock:
                self._audio_style_cache[key] = self._mrt.embed_style(wav)
        return key

    def _generate_waveform(
        self,
        prompt: str | None,
        session_id: str,
        notes: list[int] | None,
        drums: list[int] | None,
        frames: int,
        temperature: float | None,
        top_k: int | None,
        cfg_musiccoca: float | None,
        cfg_notes: float | None,
        cfg_drums: float | None,
        continuous: bool,
        style_embedding: Any | None = None,
    ) -> audio.Waveform:
        assert frames > 0
        style = style_embedding if style_embedding is not None else self.get_style(prompt)
        with self._generate_lock:
            prev_state = self._states.get(session_id) if continuous else None
            kwargs = dict(
                style=style,
                notes=notes,
                drums=drums,
                frames=frames,
                state=prev_state,
            )
            if temperature is not None:
                kwargs["temperature"] = float(temperature)
            if top_k is not None:
                kwargs["top_k"] = int(top_k)
            if cfg_musiccoca is not None:
                kwargs["cfg_musiccoca"] = float(cfg_musiccoca)
            if cfg_notes is not None:
                kwargs["cfg_notes"] = float(cfg_notes)
            if cfg_drums is not None:
                kwargs["cfg_drums"] = float(cfg_drums)

            wav, new_state = self._mrt.generate(**kwargs)
            if continuous:
                self._states[session_id] = new_state
            return wav

    def generate_pcm32(
        self,
        prompt: str | None,
        session_id: str = "default",
        notes: list[int] | None = None,
        drums: list[int] | None = None,
        frames: int = 1,
        temperature: float | None = None,
        top_k: int | None = None,
        cfg_musiccoca: float | None = None,
        cfg_notes: float | None = None,
        cfg_drums: float | None = None,
        continuous: bool = True,
        style_embedding: Any | None = None,
    ) -> tuple[bytes, int, int, int]:
        wav = self._generate_waveform(
            prompt=prompt,
            session_id=session_id,
            notes=notes,
            drums=drums,
            frames=frames,
            temperature=temperature,
            top_k=top_k,
            cfg_musiccoca=cfg_musiccoca,
            cfg_notes=cfg_notes,
            cfg_drums=cfg_drums,
            continuous=continuous,
            style_embedding=style_embedding,
        )
        samples = wav.samples.astype(np.float32, copy=False)
        if samples.ndim == 1:
            samples = np.repeat(samples[:, np.newaxis], 2, axis=1)
        assert samples.shape[1] == 2
        return samples.tobytes(), wav.sample_rate, samples.shape[0], samples.shape[1]

    def generate(self, *args, **kwargs) -> bytes:
        wav = self._generate_waveform(*args, **kwargs)
        return _wav_to_bytes(wav)

    def reset_session(self, session_id: str):
        self._states.pop(session_id, None)

    @property
    def sample_rate(self) -> int:
        return self._sample_rate


def time_safe_name(name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in name)[:48] or "audio"
