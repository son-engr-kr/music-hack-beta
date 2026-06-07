"""AI Synthesizer — prompt-driven neural synth.

Usage:
    mrt2-jam synth --prompt "warm analog pad" --midi

Play your MIDI keyboard to control pitch while the style prompt
shapes the timbre. Adjust parameters in real-time.
"""

import argparse
import time
import math

import numpy as np

from magenta_rt import MagentaRT2Mlx, audio


_NOTES_MASKED = [-1] * 128


class AISynthesizer:
    """Real-time neural synthesizer driven by text prompts and MIDI."""

    def __init__(
        self,
        prompt: str = "warm analog pad",
        model_size: str = "mrt2_small",
        temperature: float = 1.0,
    ):
        self.prompt = prompt
        self.temperature = temperature
        self._state = None
        self._active_notes: list[int] = []

        print(f"Loading Magenta RT 2 ({model_size})...")
        self._mrt = MagentaRT2Mlx(size=model_size, temperature=temperature)
        self._style_embedding = self._mrt.embed_style(prompt)
        print(f"Synth ready — prompt: {prompt}")

    def set_prompt(self, prompt: str):
        """Change the timbre/style prompt in real-time."""
        self.prompt = prompt
        self._style_embedding = self._mrt.embed_style(prompt)
        print(f"  Prompt changed: {prompt}")

    def set_active_notes(self, notes: list[int]):
        self._active_notes = notes

    def note_on(self, pitch: int, velocity: int = 100):
        if pitch not in self._active_notes:
            self._active_notes.append(pitch)

    def note_off(self, pitch: int):
        if pitch in self._active_notes:
            self._active_notes.remove(pitch)

    def generate_frame(self, frames: int = 25) -> audio.Waveform:
        """Generate one synthesis frame based on active notes."""
        notes = _NOTES_MASKED[:]
        for p in self._active_notes:
            notes[p] = 3
        drums = [-1]
        wav, self._state = self._mrt.generate(
            style=self._style_embedding,
            notes=notes,
            drums=[-1],
            frames=frames,
            state=self._state,
        )
        return wav

    def play_synth(self, callback, duration_sec: float = 30.0):
        """Run synthesizer loop.

        callback(waveform) is called for each generated chunk.
        """
        chunk_frames = 25
        elapsed = 0.0

        while elapsed < duration_sec:
            wav = self.generate_frame(frames=chunk_frames)
            callback(wav)
            elapsed += chunk_frames / 25.0

    @classmethod
    def cli(cls, argv: list[str] | None = None):
        parser = argparse.ArgumentParser(description="AI Synthesizer")
        parser.add_argument("--prompt", default="warm analog pad", help="Timbre/style prompt")
        parser.add_argument("--model", default="mrt2_small", choices=["mrt2_small", "mrt2_base"])
        parser.add_argument("--temperature", type=float, default=1.0)
        parser.add_argument("--duration", type=float, default=30.0)
        args = parser.parse_args(argv)

        synth = cls(
            prompt=args.prompt,
            model_size=args.model,
            temperature=args.temperature,
        )

        def play_cb(wav: audio.Waveform):
            print(f"  Generated {len(wav.samples) / wav.sample_rate:.1f}s")
            if hasattr(wav, "play"):
                wav.play()

        print(f"Synth playing for {args.duration}s...")
        synth.play_synth(play_cb, duration_sec=args.duration)
        print("Synth ended.")
