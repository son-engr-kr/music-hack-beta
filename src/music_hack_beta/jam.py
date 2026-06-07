"""AI Jam Partner — real-time improvisation companion.

Usage:
    mrt2-jam jam --style "jazz quartet" --midi

Listens to MIDI input (or simulated chords) and generates
complementary AI accompaniment in real-time via Magenta RT 2.
"""

import argparse
import time
import threading
import queue

import numpy as np

from magenta_rt import MagentaRT2Mlx, audio

_NOTES_OFF = [0] * 128
_NOTES_MASKED = [-1] * 128


class JamSession:
    """Call-and-response jam session with Magenta RT 2."""

    def __init__(
        self,
        style: str = "jazz quartet",
        model_size: str = "mrt2_small",
        temperature: float = 1.3,
    ):
        self.style_prompt = style
        self.temperature = temperature
        self._running = False
        self._midi_queue: queue.Queue = queue.Queue()
        self._state = None

        print(f"Loading Magenta RT 2 ({model_size})...")
        self._mrt = MagentaRT2Mlx(size=model_size, temperature=temperature)
        self._style_embedding = self._mrt.embed_style(style)
        print(f"Jam session ready — style: {style}")

    def send_midi(self, notes: list[int]):
        self._midi_queue.put(notes)

    def generate_response(
        self, frames: int = 50, user_notes: list[int] | None = None
    ) -> audio.Waveform:
        """Generate AI response, optionally conditioned on user notes."""
        notes = user_notes if user_notes is not None else _NOTES_MASKED
        wav, self._state = self._mrt.generate(
            style=self._style_embedding,
            notes=notes,
            frames=frames,
            state=self._state,
        )
        return wav

    def call_and_response(
        self, callback, duration_sec: float = 60.0
    ):
        """Run interactive call-and-response loop.

        callback(waveform) is called for each AI-generated chunk.
        Callback should play the audio and return user MIDI notes.
        """
        self._running = True
        chunk_frames = 50
        elapsed = 0.0

        while self._running and elapsed < duration_sec:
            try:
                user_notes = self._midi_queue.get_nowait()
            except queue.Empty:
                user_notes = None

            wav = self.generate_response(
                frames=chunk_frames, user_notes=user_notes
            )
            callback(wav)
            elapsed += chunk_frames / 25.0

    def stop(self):
        self._running = False

    @classmethod
    def cli(cls, argv: list[str] | None = None):
        parser = argparse.ArgumentParser(description="AI Jam Partner")
        parser.add_argument("--style", default="jazz quartet", help="Music style prompt")
        parser.add_argument("--model", default="mrt2_small", choices=["mrt2_small", "mrt2_base"])
        parser.add_argument("--temperature", type=float, default=1.3)
        parser.add_argument("--duration", type=float, default=30.0)
        args = parser.parse_args(argv)

        session = cls(
            style=args.style,
            model_size=args.model,
            temperature=args.temperature,
        )

        def play_cb(wav: audio.Waveform):
            print(f"  Generated {len(wav.samples) / wav.sample_rate:.1f}s")
            if hasattr(wav, "play"):
                wav.play()

        print(f"Jam session running for {args.duration}s...")
        session.call_and_response(play_cb, duration_sec=args.duration)
        print("Jam session ended.")
