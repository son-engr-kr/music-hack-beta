"""Magenta RealTime 2 — Live AI Music Instruments.

Choose your instrument:

    mrt2-jam jam      --style "jazz quartet"
    mrt2-jam synth    --prompt "warm analog pad"
    mrt2-jam gesture  --style "synthwave lead"
    mrt2-jam looper   --style "lofi hip hop"
"""

import sys
import argparse


def cli():
    parser = argparse.ArgumentParser(
        description="Magenta RT 2 — Live AI Music Instruments"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("jam", help="AI Jam Partner — call-and-response improvisation")
    subparsers.add_parser("synth", help="AI Synthesizer — prompt-driven neural synth")
    subparsers.add_parser("gesture", help="Gesture-Controlled Instrument — play with hands")
    subparsers.add_parser("looper", help="Multitrack Looper — build layered arrangements")

    args, remaining = parser.parse_known_args()

    if args.command == "jam":
        from music_hack_beta.jam import JamSession
        JamSession.cli(remaining)
    elif args.command == "synth":
        from music_hack_beta.synth import AISynthesizer
        AISynthesizer.cli(remaining)
    elif args.command == "gesture":
        from music_hack_beta.gesture import GestureInstrument
        GestureInstrument.cli(remaining)
    elif args.command == "looper":
        from music_hack_beta.looper import MultitrackLooper
        MultitrackLooper.cli(remaining)
