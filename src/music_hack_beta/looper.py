"""Multitrack Looper — build layered arrangements with AI.

Usage:
    mrt2-jam looper --style "lofi hip hop"

Record loop layers one by one. Each layer gets AI-generated
accompaniment. Re-style layers independently.
"""

import argparse
import time
import threading
import queue
from dataclasses import dataclass
from typing import Any

import numpy as np

from magenta_rt import MagentaRT2Mlx, audio


_NOTES_MASKED = [-1] * 128


@dataclass
class LoopLayer:
    """A single loop layer with optional AI accompaniment."""

    style: str
    notes: list[int] | None = None
    duration_frames: int = 100
    waveform: audio.Waveform | None = None
    state: Any = None


class MultitrackLooper:
    """Build layered loop arrangements with Magenta RT 2."""

    def __init__(
        self,
        style: str = "lofi hip hop",
        model_size: str = "mrt2_small",
        temperature: float = 1.2,
        bpm: int = 90,
    ):
        self.style = style
        self.temperature = temperature
        self.bpm = bpm
        self._layers: list[LoopLayer] = []

        print(f"Loading Magenta RT 2 ({model_size})...")
        self._mrt = MagentaRT2Mlx(size=model_size, temperature=temperature)
        self._style_embedding = self._mrt.embed_style(style)
        print(f"Looper ready — style: {style}, BPM: {bpm}")

    def add_layer(
        self,
        style: str | None = None,
        notes: list[int] | None = None,
        bars: int = 4,
    ) -> int:
        """Add a new loop layer with optional note conditioning.

        Returns the layer index.
        """
        prompt = style or self.style
        frames_per_bar = int(4 * 60 / self.bpm * 25)
        total_frames = frames_per_bar * bars

        embedding = self._mrt.embed_style(prompt)
        wav, state = self._mrt.generate(
            style=embedding,
            notes=notes or _NOTES_MASKED,
            frames=total_frames,
        )

        layer = LoopLayer(
            style=prompt,
            notes=notes,
            duration_frames=total_frames,
            waveform=wav,
            state=state,
        )
        self._layers.append(layer)
        idx = len(self._layers) - 1
        print(f"  Layer {idx}: {prompt} ({bars} bars)")
        return idx

    def restyle_layer(self, layer_idx: int, new_style: str):
        """Re-generate a layer with a new style."""
        if layer_idx < 0 or layer_idx >= len(self._layers):
            raise ValueError(f"Invalid layer index: {layer_idx}")

        layer = self._layers[layer_idx]
        embedding = self._mrt.embed_style(new_style)
        wav, state = self._mrt.generate(
            style=embedding,
            notes=layer.notes or _NOTES_MASKED,
            frames=layer.duration_frames,
        )

        layer.style = new_style
        layer.waveform = wav
        layer.state = state
        print(f"  Layer {layer_idx} restyled: {new_style}")

    def mix(self) -> audio.Waveform | None:
        """Mix all layers together."""
        if not self._layers:
            return None

        max_len = max(
            len(l.waveform.samples) for l in self._layers if l.waveform
        )
        mixed = np.zeros((max_len, 2), dtype=np.float32)
        gain = 1.0 / len(self._layers)

        for layer in self._layers:
            if layer.waveform is not None:
                n = len(layer.waveform.samples)
                mixed[:n] += layer.waveform.samples[:n] * gain

        first_waveform = next(layer.waveform for layer in self._layers if layer.waveform is not None)
        return audio.Waveform(mixed, sample_rate=first_waveform.sample_rate)

    def build_arrangement(self, callback, layers: list[dict]):
        """Build a multi-layer arrangement from a list of layer specs.

        Each layer spec: { "style": str, "bars": int }
        """
        for spec in layers:
            idx = self.add_layer(
                style=spec.get("style"),
                notes=spec.get("notes"),
                bars=spec.get("bars", 4),
            )
            if self._layers[idx].waveform is not None and hasattr(self._layers[idx].waveform, "play"):
                self._layers[idx].waveform.play()

        mixed = self.mix()
        if mixed is not None:
            print(f"Playing mixed arrangement ({len(mixed.samples) / mixed.sample_rate:.1f}s)")
            callback(mixed)

    @classmethod
    def cli(cls, argv: list[str] | None = None):
        parser = argparse.ArgumentParser(description="Multitrack Looper")
        parser.add_argument("--style", default="lofi hip hop", help="Base music style")
        parser.add_argument("--model", default="mrt2_small", choices=["mrt2_small", "mrt2_base"])
        parser.add_argument("--temperature", type=float, default=1.2)
        parser.add_argument("--bpm", type=int, default=90, help="Tempo")
        args = parser.parse_args(argv)

        looper = cls(
            style=args.style,
            model_size=args.model,
            temperature=args.temperature,
            bpm=args.bpm,
        )

        layers = [
            {"style": args.style, "bars": 4},
            {"style": "melodic piano", "bars": 4},
            {"style": "atmospheric pads", "bars": 4},
        ]

        def play_cb(wav: audio.Waveform):
            if hasattr(wav, "play"):
                wav.play()

        looper.build_arrangement(play_cb, layers)
