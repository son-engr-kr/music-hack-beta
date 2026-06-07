"""Gesture-Controlled Instrument — play music with your hands.

Usage:
    mrt2-jam gesture --style "synthwave lead"

Uses webcam hand tracking (MediaPipe) to map hand position to
pitch, velocity, and timbre.
"""

import argparse
import time
import math

import numpy as np

from magenta_rt import MagentaRT2Mlx, audio


_NOTES_MASKED = [-1] * 128


def _pitch_from_hand(x_norm: float, y_norm: float) -> tuple[int, float]:
    """Map hand position to MIDI pitch and velocity.

    x: 0.0-1.0 → pitch 36-96 (C2-C7)
    y: 0.0-1.0 → velocity 30-127
    """
    pitch = 36 + int(x_norm * 60)
    velocity = 30 + int((1.0 - y_norm) * 97)
    pitch = max(0, min(127, pitch))
    velocity = max(0, min(127, velocity))
    return pitch, velocity


class GestureInstrument:
    """Play music using webcam hand tracking + Magenta RT 2."""

    def __init__(
        self,
        style: str = "synthwave lead",
        model_size: str = "mrt2_small",
        temperature: float = 1.2,
        use_webcam: bool = True,
    ):
        self.style = style
        self.temperature = temperature
        self._use_webcam = use_webcam
        self._state = None
        self._active_notes: set[int] = set()

        print(f"Loading Magenta RT 2 ({model_size})...")
        self._mrt = MagentaRT2Mlx(size=model_size, temperature=temperature)
        self._style_embedding = self._mrt.embed_style(style)
        print(f"Gesture instrument ready — style: {style}")

        if self._use_webcam:
            self._init_webcam()

    def _init_webcam(self):
        import cv2
        import mediapipe as mp

        self._cv2 = cv2
        self._cap = self._cv2.VideoCapture(0)
        self._hands = mp.solutions.hands.Hands(
            max_num_hands=1,
            min_detection_confidence=0.7,
        )

    def _read_gesture(self) -> list[int]:
        """Read hand position from webcam → notes array."""
        if not self._use_webcam:
            return _NOTES_MASKED

        ret, frame = self._cap.read()
        if not ret:
            return list(self._active_notes) if self._active_notes else _NOTES_MASKED

        rgb = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)
        result = self._hands.process(rgb)

        notes = _NOTES_MASKED[:]
        if result.multi_hand_landmarks:
            landmarks = result.multi_hand_landmarks[0]
            wrist = landmarks.landmark[0]
            idx_tip = landmarks.landmark[8]
            x = (wrist.x + idx_tip.x) / 2
            y = (wrist.y + idx_tip.y) / 2

            pitch, velocity = _pitch_from_hand(x, y)
            notes[pitch] = 3
            self._active_notes = {pitch}

        return notes

    def generate_frame(self, frames: int = 25) -> audio.Waveform:
        notes = self._read_gesture()
        wav, self._state = self._mrt.generate(
            style=self._style_embedding,
            notes=notes,
            frames=frames,
            state=self._state,
        )
        return wav

    def play(self, callback, duration_sec: float = 30.0):
        chunk_frames = 25
        elapsed = 0.0

        while elapsed < duration_sec:
            wav = self.generate_frame(frames=chunk_frames)
            callback(wav)
            elapsed += chunk_frames / 25.0

        if self._use_webcam:
            self._cap.release()

    @classmethod
    def cli(cls, argv: list[str] | None = None):
        parser = argparse.ArgumentParser(description="Gesture-Controlled Instrument")
        parser.add_argument("--style", default="synthwave lead", help="Music style")
        parser.add_argument("--model", default="mrt2_small", choices=["mrt2_small", "mrt2_base"])
        parser.add_argument("--temperature", type=float, default=1.2)
        parser.add_argument("--duration", type=float, default=30.0)
        parser.add_argument("--no-webcam", action="store_true", help="Disable webcam")
        args = parser.parse_args(argv)

        inst = cls(
            style=args.style,
            model_size=args.model,
            temperature=args.temperature,
            use_webcam=not args.no_webcam,
        )

        def play_cb(wav: audio.Waveform):
            print(f"  Generated {len(wav.samples) / wav.sample_rate:.1f}s")
            if hasattr(wav, "play"):
                wav.play()

        print(f"Gesture instrument running for {args.duration}s...")
        inst.play(play_cb, duration_sec=args.duration)
        print("Gesture instrument ended.")
